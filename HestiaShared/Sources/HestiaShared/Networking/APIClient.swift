import Foundation

/// Real API client for connecting to the Hestia backend
/// Supports configurable environments (local/Tailscale) and automatic retry with exponential backoff
/// Uses certificate pinning for secure connections
@MainActor
public class APIClient: HestiaClientProtocol {
    // MARK: - Singleton

    public static let shared = APIClient()

    // MARK: - Device Info

    /// Platform-specific device info provider. Set via `configure(deviceInfo:)` at app launch.
    public static var deviceInfo: DeviceInfoProvider?

    /// Configure the shared client with a platform-specific device info provider
    public static func configure(deviceInfo: DeviceInfoProvider) {
        Self.deviceInfo = deviceInfo
    }

    // MARK: - Configuration

    private var baseURL: URL
    private var deviceToken: String?
    private var session: URLSession
    private let config: Configuration

    // MARK: - Security

    /// Certificate pinning delegate for HTTPS connections
    private let certificatePinningDelegate: CertificatePinningDelegate

    // MARK: - Token Refresh

    /// Called when APIClient auto-reregisters on 401, so AuthService can persist the new token
    public var onTokenRefresh: ((String) -> Void)?
    private var isReregistering = false

    // MARK: - Retry Configuration

    private let maxRetries: Int
    private let retryBaseDelay: TimeInterval
    private let retryMaxDelay: TimeInterval

    // MARK: - JSON Coding

    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()

    // MARK: - Initialization

    public init(configuration: Configuration = .shared, deviceToken: String? = nil) {
        self.config = configuration
        self.deviceToken = deviceToken
        self.maxRetries = configuration.maxRetries
        self.retryBaseDelay = configuration.retryBaseDelay
        self.retryMaxDelay = configuration.retryMaxDelay

        guard let url = URL(string: configuration.apiBaseURL) else {
            fatalError("Invalid Hestia API base URL: \(configuration.apiBaseURL)")
        }
        self.baseURL = url

        // Initialize certificate pinning delegate
        #if DEBUG
        self.certificatePinningDelegate = CertificatePinningDelegate(allowDevelopmentBypass: true)
        #else
        self.certificatePinningDelegate = CertificatePinningDelegate(allowDevelopmentBypass: false)
        #endif

        let sessionConfig = URLSessionConfiguration.default
        sessionConfig.timeoutIntervalForRequest = configuration.requestTimeout
        sessionConfig.timeoutIntervalForResource = configuration.resourceTimeout

        self.session = URLSession(
            configuration: sessionConfig,
            delegate: certificatePinningDelegate,
            delegateQueue: nil
        )

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(configurationDidChange),
            name: .hestiaConfigurationChanged,
            object: nil
        )
    }

    /// Legacy initializer for compatibility
    public convenience init(baseURL: String, deviceToken: String? = nil) {
        self.init(configuration: .shared, deviceToken: deviceToken)
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    @objc private func configurationDidChange() {
        guard let url = URL(string: config.apiBaseURL) else {
            #if DEBUG
            print("[APIClient] Warning: Invalid URL after config change: \(config.apiBaseURL)")
            #endif
            return
        }
        self.baseURL = url

        let sessionConfig = URLSessionConfiguration.default
        sessionConfig.timeoutIntervalForRequest = config.requestTimeout
        sessionConfig.timeoutIntervalForResource = config.resourceTimeout
        self.session = URLSession(
            configuration: sessionConfig,
            delegate: certificatePinningDelegate,
            delegateQueue: nil
        )

        #if DEBUG
        print("[APIClient] Configuration updated: \(config.apiBaseURL)")
        #endif
    }

    /// Set the device token for authenticated requests
    public func setDeviceToken(_ token: String) {
        self.deviceToken = token
    }

    // MARK: - Device Registration

    /// Register this device with the Hestia backend
    public func registerDevice(deviceName: String, deviceType: String) async throws -> DeviceRegistrationResponse {
        let request = DeviceRegistrationRequest(
            deviceName: deviceName,
            deviceType: deviceType
        )
        return try await postUnauthenticated("/auth/register", body: request)
    }

    /// Register this device using an invite token from QR code onboarding
    public func registerWithInvite(inviteToken: String, deviceName: String, deviceType: String) async throws -> InviteRegisterResponse {
        let request = InviteRegisterRequest(
            inviteToken: inviteToken,
            deviceName: deviceName,
            deviceType: deviceType
        )
        return try await postUnauthenticated("/auth/register-with-invite", body: request)
    }

    // MARK: - HestiaClientProtocol Implementation

    public func sendMessage(_ message: String, sessionId: String?, forceLocal: Bool = false) async throws -> HestiaResponse {
        let request = HestiaRequest(
            message: message,
            sessionId: sessionId,
            deviceId: nil,
            forceLocal: forceLocal,
            contextHints: nil
        )

        return try await post("/chat", body: request)
    }

    /// Send a message and receive an SSE token stream.
    /// Returns an AsyncThrowingStream of ChatStreamEvent for real-time display.
    public func sendMessageStream(
        _ message: String,
        sessionId: String?,
        forceLocal: Bool = false
    ) -> AsyncThrowingStream<ChatStreamEvent, Error> {
        AsyncThrowingStream { [weak self] continuation in
            Task { [weak self] in
                guard let self else {
                    continuation.finish()
                    return
                }
                do {
                    let body = HestiaRequest(
                        message: message,
                        sessionId: sessionId,
                        deviceId: nil,
                        forceLocal: forceLocal,
                        contextHints: nil
                    )

                    var request = URLRequest(url: makeURL("/chat/stream"))
                    request.httpMethod = "POST"
                    request.httpBody = try encoder.encode(body)
                    request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                    request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
                    if let token = deviceToken {
                        request.setValue(token, forHTTPHeaderField: "X-Hestia-Device-Token")
                    }

                    let (bytes, response) = try await session.bytes(for: request)

                    guard let httpResponse = response as? HTTPURLResponse,
                          (200...299).contains(httpResponse.statusCode) else {
                        let statusCode = (response as? HTTPURLResponse)?.statusCode ?? 0
                        continuation.finish(throwing: HestiaError.serverError(
                            statusCode: statusCode,
                            message: "Stream request failed"
                        ))
                        return
                    }

                    // Parse SSE stream line by line
                    var currentEvent = ""
                    var currentData = ""

                    for try await line in bytes.lines {
                        if line.hasPrefix("event: ") {
                            currentEvent = String(line.dropFirst(7))
                        } else if line.hasPrefix("data: ") {
                            currentData = String(line.dropFirst(6))
                        } else if line.isEmpty {
                            // Empty line = end of SSE frame
                            if !currentData.isEmpty {
                                if let event = parseChatStreamEvent(
                                    type: currentEvent, data: currentData
                                ) {
                                    continuation.yield(event)
                                    if case .done = event {
                                        continuation.finish()
                                        return
                                    }
                                    if case .error = event {
                                        continuation.finish()
                                        return
                                    }
                                }
                            }
                            currentEvent = ""
                            currentData = ""
                        }
                    }

                    continuation.finish()
                } catch {
                    continuation.finish(throwing: error)
                }
            }
        }
    }

    public func getCurrentMode() async throws -> HestiaMode {
        struct ModeResponse: Codable {
            let current: ModeInfo
        }
        struct ModeInfo: Codable {
            let mode: String
        }

        let response: ModeResponse = try await get("/mode")
        return HestiaMode(rawValue: response.current.mode) ?? .tia
    }

    public func switchMode(to mode: HestiaMode) async throws {
        struct SwitchRequest: Codable {
            let mode: String
        }
        struct SwitchResponse: Codable {
            let currentMode: String
        }

        let _: SwitchResponse = try await post("/mode/switch", body: SwitchRequest(mode: mode.rawValue))
    }

    public func getSystemHealth() async throws -> SystemHealth {
        return try await get("/health")
    }

    public func getPendingMemoryReviews() async throws -> [MemoryChunk] {
        struct PendingResponse: Codable {
            let pending: [MemoryChunk]
        }

        let response: PendingResponse = try await get("/memory/staged")
        return response.pending
    }

    public func approveMemory(chunkId: String, notes: String?) async throws {
        struct ApproveRequest: Codable {
            let reviewerNotes: String?
        }
        struct ApproveResponse: Codable {
            let status: String
        }

        let _: ApproveResponse = try await post(
            "/memory/approve/\(chunkId)",
            body: ApproveRequest(reviewerNotes: notes)
        )
    }

    public func rejectMemory(chunkId: String) async throws {
        struct RejectResponse: Codable {
            let status: String
        }

        let _: RejectResponse = try await post("/memory/reject/\(chunkId)", body: EmptyBody())
    }

    public func searchMemory(query: String, limit: Int) async throws -> [MemorySearchResult] {
        struct SearchResponse: Codable {
            let results: [MemorySearchResult]
            let count: Int
        }

        let response: SearchResponse = try await get("/memory/search?q=\(query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query)&limit=\(limit)")
        return response.results
    }

    public func createSession(mode: HestiaMode) async throws -> String {
        struct SessionRequest: Codable {
            let mode: String
            let deviceId: String?
        }
        struct SessionResponse: Codable {
            let sessionId: String
        }

        let response: SessionResponse = try await post(
            "/sessions",
            body: SessionRequest(mode: mode.rawValue, deviceId: nil)
        )
        return response.sessionId
    }

    public func getSessionHistory(sessionId: String) async throws -> [ConversationMessage] {
        struct HistoryResponse: Codable {
            let messages: [MessageDTO]
        }
        struct MessageDTO: Codable {
            let role: String
            let content: String
        }

        let response: HistoryResponse = try await get("/sessions/\(sessionId)/history")

        return response.messages.enumerated().map { index, dto in
            ConversationMessage(
                id: "\(sessionId)-\(index)",
                role: dto.role == "user" ? .user : .assistant,
                content: dto.content,
                timestamp: Date(),
                mode: nil
            )
        }
    }

    // MARK: - Orders API

    public func createOrder(_ request: OrderCreateRequest) async throws -> OrderResponse {
        return try await post("/orders", body: request)
    }

    public func listOrders(status: OrderStatus? = nil, limit: Int = 50, offset: Int = 0) async throws -> OrderListResponse {
        var path = "/orders?limit=\(limit)&offset=\(offset)"
        if let status = status {
            path += "&status=\(status.rawValue)"
        }
        return try await get(path)
    }

    public func getOrder(_ orderId: String) async throws -> OrderResponse {
        return try await get("/orders/\(orderId)")
    }

    public func updateOrder(_ orderId: String, request: OrderUpdateRequest) async throws -> OrderResponse {
        return try await patch("/orders/\(orderId)", body: request)
    }

    public func deleteOrder(_ orderId: String) async throws -> OrderDeleteResponse {
        return try await delete("/orders/\(orderId)")
    }

    public func listOrderExecutions(_ orderId: String, limit: Int = 50, offset: Int = 0) async throws -> OrderExecutionsResponse {
        return try await get("/orders/\(orderId)/executions?limit=\(limit)&offset=\(offset)")
    }

    public func executeOrderNow(_ orderId: String) async throws -> OrderExecuteResponse {
        return try await post("/orders/\(orderId)/execute", body: EmptyBody())
    }

    // MARK: - Agent Profiles API

    public func listAgents() async throws -> AgentListResponse {
        return try await get("/agents")
    }

    public func getAgent(_ slotIndex: Int) async throws -> AgentProfileResponse {
        return try await get("/agents/\(slotIndex)")
    }

    public func updateAgent(_ slotIndex: Int, request: AgentUpdateRequest) async throws -> AgentProfileResponse {
        return try await put("/agents/\(slotIndex)", body: request)
    }

    public func deleteAgent(_ slotIndex: Int) async throws -> AgentDeleteResponse {
        return try await delete("/agents/\(slotIndex)")
    }

    public func uploadAgentPhoto(_ slotIndex: Int, imageData: Data, contentType: String = "image/jpeg") async throws -> AgentPhotoResponse {
        return try await uploadMultipart("/agents/\(slotIndex)/photo", data: imageData, fieldName: "photo", contentType: contentType)
    }

    public func getAgentPhoto(_ slotIndex: Int) async throws -> Data {
        return try await downloadData("/agents/\(slotIndex)/photo")
    }

    public func deleteAgentPhoto(_ slotIndex: Int) async throws -> AgentPhotoResponse {
        return try await delete("/agents/\(slotIndex)/photo")
    }

    public func listAgentSnapshots(_ slotIndex: Int) async throws -> AgentSnapshotsResponse {
        return try await get("/agents/\(slotIndex)/snapshots")
    }

    public func restoreAgentSnapshot(_ slotIndex: Int, snapshotId: String) async throws -> AgentRestoreResponse {
        return try await post("/agents/\(slotIndex)/restore", body: AgentRestoreRequest(snapshotId: snapshotId))
    }

    // MARK: - User Profile API

    public func getUserProfile() async throws -> UserProfileResponse {
        return try await get("/user/profile")
    }

    public func updateUserProfile(_ request: UserProfileUpdateRequest) async throws -> UserProfileResponse {
        return try await patch("/user/profile", body: request)
    }

    public func uploadUserPhoto(imageData: Data, contentType: String = "image/jpeg") async throws -> [String: String] {
        return try await uploadMultipart("/user/photo", data: imageData, fieldName: "photo", contentType: contentType)
    }

    public func getUserPhoto() async throws -> Data {
        return try await downloadData("/user/photo")
    }

    public func deleteUserPhoto() async throws -> [String: String] {
        return try await delete("/user/photo")
    }

    // MARK: - User Settings API

    public func getUserSettings() async throws -> UserSettingsResponse {
        return try await get("/user/settings")
    }

    public func updateUserSettings(_ request: UserSettingsUpdateRequest) async throws -> UserSettingsUpdateResponse {
        return try await patch("/user/settings", body: request)
    }

    public func registerPushToken(_ token: String, deviceId: String, environment: PushEnvironment = .production) async throws -> PushTokenResponse {
        let request = PushTokenRequest(pushToken: token, deviceId: deviceId, environment: environment)
        return try await post("/user/push-token", body: request)
    }

    public func unregisterPushToken() async throws -> PushTokenResponse {
        return try await delete("/user/push-token")
    }

    // MARK: - Cloud Providers API

    public func listCloudProviders() async throws -> CloudProviderListResponse {
        return try await get("/cloud/providers")
    }

    public func addCloudProvider(_ provider: APICloudProvider, apiKey: String, state: APICloudProviderState = .enabledSmart, modelId: String? = nil) async throws -> CloudProviderResponse {
        let request = CloudProviderAddRequest(provider: provider, apiKey: apiKey, state: state, modelId: modelId)
        return try await post("/cloud/providers", body: request)
    }

    public func removeCloudProvider(_ provider: APICloudProvider) async throws -> CloudProviderDeleteResponse {
        return try await delete("/cloud/providers/\(provider.rawValue)")
    }

    public func updateCloudProviderState(_ provider: APICloudProvider, state: APICloudProviderState) async throws -> CloudProviderResponse {
        let request = CloudProviderStateUpdateRequest(state: state)
        return try await patch("/cloud/providers/\(provider.rawValue)/state", body: request)
    }

    public func updateCloudProviderModel(_ provider: APICloudProvider, modelId: String) async throws -> CloudProviderResponse {
        let request = CloudProviderModelUpdateRequest(modelId: modelId)
        return try await patch("/cloud/providers/\(provider.rawValue)/model", body: request)
    }

    public func getCloudUsage(days: Int = 30) async throws -> CloudUsageSummaryResponse {
        return try await get("/cloud/usage?period_days=\(days)")
    }

    public func checkCloudProviderHealth(_ provider: APICloudProvider) async throws -> CloudHealthCheckResponse {
        return try await post("/cloud/providers/\(provider.rawValue)/health", body: EmptyBody())
    }

    // MARK: - Voice Journaling API

    public func voiceQualityCheck(transcript: String, knownEntities: [String]? = nil) async throws -> VoiceQualityCheckResponse {
        let request = VoiceQualityCheckRequest(transcript: transcript, knownEntities: knownEntities)
        return try await post("/voice/quality-check", body: request)
    }

    public func voiceJournalAnalyze(transcript: String, mode: String? = nil) async throws -> VoiceJournalAnalyzeResponse {
        let request = VoiceJournalAnalyzeRequest(transcript: transcript, mode: mode)
        return try await post("/voice/journal-analyze", body: request)
    }

    // MARK: - Health Data API

    public func syncHealthMetrics(_ request: HealthSyncRequest) async throws -> HealthSyncResponse {
        return try await post("/health_data/sync", body: request)
    }

    public func getCoachingPreferences() async throws -> CoachingPreferencesResponse {
        return try await get("/health_data/coaching")
    }

    public func updateCoachingPreferences(_ request: CoachingPreferencesUpdateRequest) async throws -> CoachingPreferencesResponse {
        return try await post("/health_data/coaching", body: request)
    }

    // MARK: - URL Construction

    /// Build a URL from a path that may contain query parameters.
    /// `appendingPathComponent` percent-encodes `?` and `&`, breaking query strings.
    /// This splits the query string out and attaches it via URLComponents instead.
    private func makeURL(_ path: String) -> URL {
        guard let queryStart = path.firstIndex(of: "?") else {
            return baseURL.appendingPathComponent(path).standardized
        }

        let pathPart = String(path[..<queryStart])
        let queryPart = String(path[path.index(after: queryStart)...])

        guard var components = URLComponents(
            url: baseURL.appendingPathComponent(pathPart).standardized,
            resolvingAgainstBaseURL: false
        ) else {
            return baseURL.appendingPathComponent(path).standardized
        }

        components.percentEncodedQuery = queryPart
        return components.url ?? baseURL.appendingPathComponent(path).standardized
    }

    // MARK: - Private HTTP Methods

    public func get<T: Decodable>(_ path: String) async throws -> T {
        var request = URLRequest(url: makeURL(path))
        request.httpMethod = "GET"
        addHeaders(to: &request)

        return try await execute(request)
    }

    public func post<T: Decodable, B: Encodable>(_ path: String, body: B, timeout: TimeInterval? = nil) async throws -> T {
        var request = URLRequest(url: makeURL(path))
        request.httpMethod = "POST"
        request.httpBody = try encoder.encode(body)
        if let timeout { request.timeoutInterval = timeout }
        addHeaders(to: &request)

        return try await execute(request)
    }

    private func postUnauthenticated<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        var request = URLRequest(url: makeURL(path))
        request.httpMethod = "POST"
        request.httpBody = try encoder.encode(body)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        return try await execute(request)
    }

    private func patch<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        var request = URLRequest(url: makeURL(path))
        request.httpMethod = "PATCH"
        request.httpBody = try encoder.encode(body)
        addHeaders(to: &request)

        return try await execute(request)
    }

    public func put<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        var request = URLRequest(url: makeURL(path))
        request.httpMethod = "PUT"
        request.httpBody = try encoder.encode(body)
        addHeaders(to: &request)

        return try await execute(request)
    }

    private func delete<T: Decodable>(_ path: String) async throws -> T {
        var request = URLRequest(url: makeURL(path))
        request.httpMethod = "DELETE"
        addHeaders(to: &request)

        return try await execute(request)
    }

    private func uploadMultipart<T: Decodable>(_ path: String, data: Data, fieldName: String, contentType: String) async throws -> T {
        var request = URLRequest(url: makeURL(path))
        request.httpMethod = "POST"

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        if let token = deviceToken {
            request.setValue(token, forHTTPHeaderField: "X-Hestia-Device-Token")
        }

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"\(fieldName)\"; filename=\"image.jpg\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: \(contentType)\r\n\r\n".data(using: .utf8)!)
        body.append(data)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body

        return try await execute(request)
    }

    private func downloadData(_ path: String) async throws -> Data {
        var request = URLRequest(url: makeURL(path))
        request.httpMethod = "GET"

        if let token = deviceToken {
            request.setValue(token, forHTTPHeaderField: "X-Hestia-Device-Token")
        }

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw HestiaError.networkUnavailable
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw HestiaError.serverError(statusCode: httpResponse.statusCode, message: "Failed to download data")
        }

        return data
    }

    private func addHeaders(to request: inout URLRequest) {
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")

        if let token = deviceToken {
            request.setValue(token, forHTTPHeaderField: "X-Hestia-Device-Token")
        }
    }

    private func execute<T: Decodable>(_ request: URLRequest) async throws -> T {
        return try await executeWithRetry(request)
    }

    /// Execute request with automatic retry and exponential backoff
    private func executeWithRetry<T: Decodable>(_ request: URLRequest, attempt: Int = 0) async throws -> T {
        #if DEBUG
        let attemptStr = attempt > 0 ? " (attempt \(attempt + 1)/\(maxRetries + 1))" : ""
        print("[APIClient] \(request.httpMethod ?? "?") \(request.url?.absoluteString ?? "?")\(attemptStr)")
        #endif

        do {
            let (data, response) = try await session.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw HestiaError.networkUnavailable
            }

            #if DEBUG
            print("[APIClient] Response status: \(httpResponse.statusCode)")
            #endif

            switch httpResponse.statusCode {
            case 200...299:
                do {
                    return try decoder.decode(T.self, from: data)
                } catch {
                    #if DEBUG
                    if let rawJSON = String(data: data, encoding: .utf8) {
                        print("[APIClient] Raw response: \(rawJSON)")
                    }
                    print("[APIClient] Decoding error: \(error)")
                    #endif
                    throw error
                }
            case 401:
                // Auto-reregister: get a fresh device token and retry once
                if !isReregistering {
                    isReregistering = true
                    defer { isReregistering = false }

                    #if DEBUG
                    print("[APIClient] 401 received, attempting auto-reregistration...")
                    #endif

                    do {
                        let deviceName = Self.deviceInfo?.deviceName ?? "Unknown"
                        let deviceType = Self.deviceInfo?.deviceType ?? "Unknown"
                        let regResponse = try await registerDevice(deviceName: deviceName, deviceType: deviceType)
                        self.deviceToken = regResponse.token
                        onTokenRefresh?(regResponse.token)

                        #if DEBUG
                        print("[APIClient] Re-registration successful, retrying request...")
                        #endif

                        // Rebuild original request with new token
                        var retryRequest = request
                        retryRequest.setValue(regResponse.token, forHTTPHeaderField: "X-Hestia-Device-Token")
                        return try await executeWithRetry(retryRequest, attempt: attempt + 1)
                    } catch {
                        #if DEBUG
                        print("[APIClient] Auto-reregistration failed: \(error)")
                        #endif
                    }
                }
                throw HestiaError.unauthorized
            case 429:
                let retryAfter = httpResponse.value(forHTTPHeaderField: "Retry-After")
                    .flatMap { Int($0) }
                throw HestiaError.rateLimited(retryAfterSeconds: retryAfter)
            case 500...599:
                throw RetryableError.serverError(httpResponse.statusCode)
            default:
                #if DEBUG
                if let rawJSON = String(data: data, encoding: .utf8) {
                    print("[APIClient] Error response: \(rawJSON)")
                }
                #endif
                if let errorResponse = try? decoder.decode(ErrorResponse.self, from: data) {
                    throw HestiaError.from(responseError: ResponseError(
                        code: errorResponse.error?.code ?? "unknown",
                        message: errorResponse.error?.message ?? "Unknown error"
                    ))
                }
                throw HestiaError.unknown("HTTP \(httpResponse.statusCode)")
            }
        } catch let error as RetryableError {
            if attempt < maxRetries {
                let delay = calculateRetryDelay(attempt: attempt)
                #if DEBUG
                print("[APIClient] Retryable error, waiting \(String(format: "%.1f", delay))s before retry...")
                #endif
                try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                return try await executeWithRetry(request, attempt: attempt + 1)
            }
            throw error.toHestiaError()
        } catch let error as URLError {
            if isRetryableURLError(error) && attempt < maxRetries {
                let delay = calculateRetryDelay(attempt: attempt)
                #if DEBUG
                print("[APIClient] Network error (\(error.code.rawValue)), waiting \(String(format: "%.1f", delay))s before retry...")
                #endif
                try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                return try await executeWithRetry(request, attempt: attempt + 1)
            }
            throw mapURLError(error)
        }
    }

    /// Calculate delay for retry attempt using exponential backoff with jitter
    private func calculateRetryDelay(attempt: Int) -> TimeInterval {
        let baseDelay = retryBaseDelay * pow(2.0, Double(attempt))
        let cappedDelay = min(baseDelay, retryMaxDelay)
        let jitter = cappedDelay * Double.random(in: 0...0.25)
        return cappedDelay + jitter
    }

    /// Check if a URLError is retryable
    private func isRetryableURLError(_ error: URLError) -> Bool {
        switch error.code {
        case .timedOut,
             .networkConnectionLost,
             .notConnectedToInternet,
             .cannotConnectToHost,
             .dnsLookupFailed:
            return true
        default:
            return false
        }
    }

    /// Map URLError to HestiaError
    private func mapURLError(_ error: URLError) -> HestiaError {
        switch error.code {
        case .timedOut:
            return .timeout
        case .notConnectedToInternet, .networkConnectionLost:
            return .networkUnavailable
        case .cannotConnectToHost, .dnsLookupFailed:
            return .serverUnreachable
        default:
            return .unknown(error.localizedDescription)
        }
    }

    // MARK: - Explorer

    public func getExplorerResources(
        type: ExplorerResourceType? = nil,
        source: ExplorerResourceSource? = nil,
        search: String? = nil,
        limit: Int = 100,
        offset: Int = 0
    ) async throws -> ExplorerResourceListResponse {
        var queryParts: [String] = ["limit=\(limit)", "offset=\(offset)"]
        if let type = type { queryParts.append("type=\(type.rawValue)") }
        if let source = source { queryParts.append("source=\(source.rawValue)") }
        if let search = search, let encoded = search.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) {
            queryParts.append("search=\(encoded)")
        }
        let query = queryParts.joined(separator: "&")
        return try await get("/explorer/resources?\(query)")
    }

    public func getExplorerResource(id: String) async throws -> ExplorerResource {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        return try await get("/explorer/resources/\(encoded)")
    }

    public func getExplorerContent(id: String) async throws -> ExplorerContentResponse {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        return try await get("/explorer/resources/\(encoded)/content")
    }

    public func createDraft(title: String, body: String? = nil, color: String? = nil) async throws -> ExplorerResource {
        let request = DraftCreateRequest(title: title, body: body, color: color)
        return try await post("/explorer/drafts", body: request)
    }

    public func updateDraft(id: String, title: String? = nil, body: String? = nil) async throws -> ExplorerResource {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        let request = DraftUpdateRequest(title: title, body: body)
        return try await patch("/explorer/drafts/\(encoded)", body: request)
    }

    public func deleteDraft(id: String) async throws -> DraftDeleteResponse {
        let encoded = id.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? id
        return try await delete("/explorer/drafts/\(encoded)")
    }
}

// MARK: - Retryable Error Type

private enum RetryableError: Error {
    case serverError(Int)
    case networkError(URLError)

    func toHestiaError() -> HestiaError {
        switch self {
        case .serverError(let code):
            return .serverError(statusCode: code, message: "Server error after retries")
        case .networkError(let error):
            return .unknown(error.localizedDescription)
        }
    }
}

// MARK: - Helper Types

private struct EmptyBody: Codable {}

private struct ErrorResponse: Codable {
    let error: ResponseError?
}
