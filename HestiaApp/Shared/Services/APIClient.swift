import Foundation
import UIKit

/// Real API client for connecting to the Hestia backend
/// Supports configurable environments (local/Tailscale) and automatic retry with exponential backoff
/// Uses certificate pinning for secure connections
@MainActor
class APIClient: HestiaClientProtocol {
    // MARK: - Singleton

    static let shared = APIClient()

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
    var onTokenRefresh: ((String) -> Void)?
    private var isReregistering = false

    // MARK: - Retry Configuration

    private let maxRetries: Int
    private let retryBaseDelay: TimeInterval
    private let retryMaxDelay: TimeInterval

    // MARK: - ETag Cache

    /// In-memory ETag cache: [URL path: (etag, cached response data)]
    /// Used for conditional GET on stable endpoints (wiki, tools, agents).
    private var etagCache: [String: (etag: String, data: Data)] = [:]

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

    init(configuration: Configuration = .shared, deviceToken: String? = nil) {
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
        // In DEBUG builds, allow development bypass for self-signed certs
        #if DEBUG
        self.certificatePinningDelegate = CertificatePinningDelegate(allowDevelopmentBypass: true)
        #else
        self.certificatePinningDelegate = CertificatePinningDelegate(allowDevelopmentBypass: false)
        #endif

        let sessionConfig = URLSessionConfiguration.default
        sessionConfig.timeoutIntervalForRequest = configuration.requestTimeout
        sessionConfig.timeoutIntervalForResource = configuration.resourceTimeout

        // Create session with certificate pinning delegate
        self.session = URLSession(
            configuration: sessionConfig,
            delegate: certificatePinningDelegate,
            delegateQueue: nil
        )

        // Listen for configuration changes
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(configurationDidChange),
            name: .hestiaConfigurationChanged,
            object: nil
        )
    }

    /// Legacy initializer for compatibility
    convenience init(baseURL: String, deviceToken: String? = nil) {
        // Create a temporary configuration - for testing/legacy use
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

        // Recreate session with new timeouts (and certificate pinning delegate)
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
    func setDeviceToken(_ token: String) {
        self.deviceToken = token
    }

    // MARK: - Device Registration

    /// Register this device with the Hestia backend
    /// This endpoint does not require authentication
    func registerDevice(deviceName: String, deviceType: String) async throws -> DeviceRegistrationResponse {
        let request = DeviceRegistrationRequest(
            deviceName: deviceName,
            deviceType: deviceType
        )
        return try await postUnauthenticated("/auth/register", body: request)
    }

    /// Register this device using an invite token from QR code onboarding
    /// This endpoint does not require authentication — the invite token IS the auth
    func registerWithInvite(inviteToken: String, deviceName: String?, deviceType: String?) async throws -> InviteRegisterResponse {
        let request = InviteRegisterRequest(
            inviteToken: inviteToken,
            deviceName: deviceName,
            deviceType: deviceType
        )
        return try await postUnauthenticated("/auth/register-with-invite", body: request)
    }

    // MARK: - HestiaClientProtocol Implementation

    func sendMessage(_ message: String, sessionId: String?, forceLocal: Bool = false) async throws -> HestiaResponse {
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
    func sendMessageStream(
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

                    var request = URLRequest(url: baseURL.appendingPathComponent("/chat/stream"))
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

    func getCurrentMode() async throws -> HestiaMode {
        struct ModeResponse: Codable {
            let current: ModeInfo
        }
        struct ModeInfo: Codable {
            let mode: String
        }

        let response: ModeResponse = try await get("/mode")
        return HestiaMode(rawValue: response.current.mode) ?? .tia
    }

    func switchMode(to mode: HestiaMode) async throws {
        struct SwitchRequest: Codable {
            let mode: String
        }
        struct SwitchResponse: Codable {
            let currentMode: String
        }

        let _: SwitchResponse = try await post("/mode/switch", body: SwitchRequest(mode: mode.rawValue))
    }

    func getSystemHealth() async throws -> SystemHealth {
        return try await get("/health")
    }

    func getPendingMemoryReviews() async throws -> [MemoryChunk] {
        struct PendingResponse: Codable {
            let pending: [MemoryChunk]
        }

        let response: PendingResponse = try await get("/memory/staged")
        return response.pending
    }

    func approveMemory(chunkId: String, notes: String?) async throws {
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

    func rejectMemory(chunkId: String) async throws {
        struct RejectResponse: Codable {
            let status: String
        }

        let _: RejectResponse = try await post("/memory/reject/\(chunkId)", body: EmptyBody())
    }

    func searchMemory(query: String, limit: Int) async throws -> [MemorySearchResult] {
        struct SearchResponse: Codable {
            let results: [MemorySearchResult]
            let count: Int
        }

        let response: SearchResponse = try await get("/memory/search?q=\(query.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? query)&limit=\(limit)")
        return response.results
    }

    func createSession(mode: HestiaMode) async throws -> String {
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

    func getSessionHistory(sessionId: String) async throws -> [ConversationMessage] {
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

    func createOrder(_ request: OrderCreateRequest) async throws -> OrderResponse {
        return try await post("/orders", body: request)
    }

    func listOrders(status: OrderStatus? = nil, limit: Int = 50, offset: Int = 0) async throws -> OrderListResponse {
        var path = "/orders?limit=\(limit)&offset=\(offset)"
        if let status = status {
            path += "&status=\(status.rawValue)"
        }
        return try await get(path)
    }

    func getOrder(_ orderId: String) async throws -> OrderResponse {
        return try await get("/orders/\(orderId)")
    }

    func updateOrder(_ orderId: String, request: OrderUpdateRequest) async throws -> OrderResponse {
        return try await patch("/orders/\(orderId)", body: request)
    }

    func deleteOrder(_ orderId: String) async throws -> OrderDeleteResponse {
        return try await delete("/orders/\(orderId)")
    }

    func listOrderExecutions(_ orderId: String, limit: Int = 50, offset: Int = 0) async throws -> OrderExecutionsResponse {
        return try await get("/orders/\(orderId)/executions?limit=\(limit)&offset=\(offset)")
    }

    func executeOrderNow(_ orderId: String) async throws -> OrderExecuteResponse {
        return try await post("/orders/\(orderId)/execute", body: EmptyBody())
    }

    // MARK: - Agent Profiles API

    func listAgents() async throws -> AgentListResponse {
        return try await get("/agents")
    }

    func getAgent(_ slotIndex: Int) async throws -> AgentProfileResponse {
        return try await get("/agents/\(slotIndex)")
    }

    func updateAgent(_ slotIndex: Int, request: AgentUpdateRequest) async throws -> AgentProfileResponse {
        return try await put("/agents/\(slotIndex)", body: request)
    }

    func deleteAgent(_ slotIndex: Int) async throws -> AgentDeleteResponse {
        return try await delete("/agents/\(slotIndex)")
    }

    func uploadAgentPhoto(_ slotIndex: Int, imageData: Data, contentType: String = "image/jpeg") async throws -> AgentPhotoResponse {
        return try await uploadMultipart("/agents/\(slotIndex)/photo", data: imageData, fieldName: "photo", contentType: contentType)
    }

    func getAgentPhoto(_ slotIndex: Int) async throws -> Data {
        return try await downloadData("/agents/\(slotIndex)/photo")
    }

    func deleteAgentPhoto(_ slotIndex: Int) async throws -> AgentPhotoResponse {
        return try await delete("/agents/\(slotIndex)/photo")
    }

    func listAgentSnapshots(_ slotIndex: Int) async throws -> AgentSnapshotsResponse {
        return try await get("/agents/\(slotIndex)/snapshots")
    }

    func restoreAgentSnapshot(_ slotIndex: Int, snapshotId: String) async throws -> AgentRestoreResponse {
        return try await post("/agents/\(slotIndex)/restore", body: AgentRestoreRequest(snapshotId: snapshotId))
    }

    // MARK: - User Profile API

    func getUserProfile() async throws -> UserProfileResponse {
        return try await get("/user/profile")
    }

    func updateUserProfile(_ request: UserProfileUpdateRequest) async throws -> UserProfileResponse {
        return try await patch("/user/profile", body: request)
    }

    func uploadUserPhoto(imageData: Data, contentType: String = "image/jpeg") async throws -> [String: String] {
        return try await uploadMultipart("/user/photo", data: imageData, fieldName: "photo", contentType: contentType)
    }

    func getUserPhoto() async throws -> Data {
        return try await downloadData("/user/photo")
    }

    func deleteUserPhoto() async throws -> [String: String] {
        return try await delete("/user/photo")
    }

    // MARK: - User Settings API

    func getUserSettings() async throws -> UserSettingsResponse {
        return try await get("/user/settings")
    }

    func updateUserSettings(_ request: UserSettingsUpdateRequest) async throws -> UserSettingsUpdateResponse {
        return try await patch("/user/settings", body: request)
    }

    func registerPushToken(_ token: String, deviceId: String, environment: PushEnvironment = .production) async throws -> PushTokenResponse {
        let request = PushTokenRequest(pushToken: token, deviceId: deviceId, environment: environment)
        return try await post("/user/push-token", body: request)
    }

    func unregisterPushToken() async throws -> PushTokenResponse {
        return try await delete("/user/push-token")
    }

    // MARK: - Cloud Providers API

    func listCloudProviders() async throws -> CloudProviderListResponse {
        return try await get("/cloud/providers")
    }

    func addCloudProvider(_ provider: APICloudProvider, apiKey: String, state: APICloudProviderState = .enabledSmart, modelId: String? = nil) async throws -> CloudProviderResponse {
        let request = CloudProviderAddRequest(provider: provider, apiKey: apiKey, state: state, modelId: modelId)
        return try await post("/cloud/providers", body: request)
    }

    func removeCloudProvider(_ provider: APICloudProvider) async throws -> CloudProviderDeleteResponse {
        return try await delete("/cloud/providers/\(provider.rawValue)")
    }

    func updateCloudProviderState(_ provider: APICloudProvider, state: APICloudProviderState) async throws -> CloudProviderResponse {
        let request = CloudProviderStateUpdateRequest(state: state)
        return try await patch("/cloud/providers/\(provider.rawValue)/state", body: request)
    }

    func updateCloudProviderModel(_ provider: APICloudProvider, modelId: String) async throws -> CloudProviderResponse {
        let request = CloudProviderModelUpdateRequest(modelId: modelId)
        return try await patch("/cloud/providers/\(provider.rawValue)/model", body: request)
    }

    func getCloudUsage(days: Int = 30) async throws -> CloudUsageSummaryResponse {
        return try await get("/cloud/usage?period_days=\(days)")
    }

    func checkCloudProviderHealth(_ provider: APICloudProvider) async throws -> CloudHealthCheckResponse {
        return try await post("/cloud/providers/\(provider.rawValue)/health", body: EmptyBody())
    }

    // MARK: - Voice Journaling API

    func voiceQualityCheck(transcript: String, knownEntities: [String]? = nil) async throws -> VoiceQualityCheckResponse {
        let request = VoiceQualityCheckRequest(transcript: transcript, knownEntities: knownEntities)
        return try await post("/voice/quality-check", body: request)
    }

    func voiceJournalAnalyze(transcript: String, mode: String? = nil) async throws -> VoiceJournalAnalyzeResponse {
        let request = VoiceJournalAnalyzeRequest(transcript: transcript, mode: mode)
        return try await post("/voice/journal-analyze", body: request)
    }

    // MARK: - Health Data API

    func syncHealthMetrics(_ request: HealthSyncRequest) async throws -> HealthSyncResponse {
        return try await post("/health_data/sync", body: request)
    }

    func getCoachingPreferences() async throws -> CoachingPreferencesResponse {
        return try await get("/health_data/coaching")
    }

    func updateCoachingPreferences(_ request: CoachingPreferencesUpdateRequest) async throws -> CoachingPreferencesResponse {
        return try await post("/health_data/coaching", body: request)
    }

    // MARK: - HTTP Methods

    func get<T: Decodable>(_ path: String) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "GET"
        addHeaders(to: &request)

        return try await execute(request)
    }

    /// GET with ETag-based conditional caching.
    /// On 304 Not Modified, returns the cached response without re-downloading.
    /// Use for stable endpoints: wiki articles, tools, agents.
    func getWithETag<T: Decodable>(_ path: String) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "GET"
        addHeaders(to: &request)

        // Send If-None-Match if we have a cached ETag
        if let cached = etagCache[path] {
            request.setValue("\"\(cached.etag)\"", forHTTPHeaderField: "If-None-Match")
        }

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw HestiaError.networkUnavailable
        }

        // 304: serve from cache
        if httpResponse.statusCode == 304, let cached = etagCache[path] {
            #if DEBUG
            print("[APIClient] ETag cache hit: \(path)")
            #endif
            return try decoder.decode(T.self, from: cached.data)
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw HestiaError.serverError(
                statusCode: httpResponse.statusCode,
                message: "Request failed"
            )
        }

        // Store new ETag + data
        if let etag = httpResponse.value(forHTTPHeaderField: "ETag") {
            let cleanEtag = etag.trimmingCharacters(in: CharacterSet(charactersIn: "\""))
            etagCache[path] = (etag: cleanEtag, data: data)
            #if DEBUG
            print("[APIClient] ETag cached: \(path) → \(cleanEtag)")
            #endif
        }

        return try decoder.decode(T.self, from: data)
    }

    private func post<T: Decodable, B: Encodable>(_ path: String, body: B, timeout: TimeInterval? = nil) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.httpBody = try encoder.encode(body)
        if let timeout { request.timeoutInterval = timeout }
        addHeaders(to: &request)

        return try await execute(request)
    }

    private func postUnauthenticated<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "POST"
        request.httpBody = try encoder.encode(body)
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        // Note: No device token header for unauthenticated requests

        return try await execute(request)
    }

    private func patch<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "PATCH"
        request.httpBody = try encoder.encode(body)
        addHeaders(to: &request)

        return try await execute(request)
    }

    func put<T: Decodable, B: Encodable>(_ path: String, body: B) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "PUT"
        request.httpBody = try encoder.encode(body)
        addHeaders(to: &request)

        return try await execute(request)
    }

    func delete<T: Decodable>(_ path: String) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
        request.httpMethod = "DELETE"
        addHeaders(to: &request)

        return try await execute(request)
    }

    private func uploadMultipart<T: Decodable>(_ path: String, data: Data, fieldName: String, contentType: String) async throws -> T {
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
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
        var request = URLRequest(url: baseURL.appendingPathComponent(path))
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
                        let deviceName = UIDevice.current.name
                        let regResponse = try await registerDevice(deviceName: deviceName, deviceType: "iOS")
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
                // Rate limited - extract retry-after if available
                let retryAfter = httpResponse.value(forHTTPHeaderField: "Retry-After")
                    .flatMap { Int($0) }
                throw HestiaError.rateLimited(retryAfterSeconds: retryAfter)
            case 500...599:
                // Server errors are retryable
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
            // Retryable error - attempt retry if we haven't exceeded max
            if attempt < maxRetries {
                let delay = calculateRetryDelay(attempt: attempt)
                #if DEBUG
                print("[APIClient] Retryable error, waiting \(String(format: "%.1f", delay))s before retry...")
                #endif
                try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                return try await executeWithRetry(request, attempt: attempt + 1)
            }
            // Max retries exceeded
            throw error.toHestiaError()
        } catch let error as URLError {
            // Network errors are retryable
            if isRetryableURLError(error) && attempt < maxRetries {
                let delay = calculateRetryDelay(attempt: attempt)
                #if DEBUG
                print("[APIClient] Network error (\(error.code.rawValue)), waiting \(String(format: "%.1f", delay))s before retry...")
                #endif
                try await Task.sleep(nanoseconds: UInt64(delay * 1_000_000_000))
                return try await executeWithRetry(request, attempt: attempt + 1)
            }
            // Not retryable or max retries exceeded
            throw mapURLError(error)
        }
    }

    /// Calculate delay for retry attempt using exponential backoff with jitter
    private func calculateRetryDelay(attempt: Int) -> TimeInterval {
        let baseDelay = retryBaseDelay * pow(2.0, Double(attempt))
        let cappedDelay = min(baseDelay, retryMaxDelay)
        // Add jitter (0-25% of delay)
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
