import Foundation

/// UserDefaults-backed cache with TTL support for instant UI loading.
/// Pattern: show cached data immediately, fetch fresh in background, update cache.
///
/// Supports two retrieval modes:
/// - `get()` — returns data only if not expired (normal operation)
/// - `getStale()` — returns data even if expired (offline fallback)
final class CacheManager: @unchecked Sendable {
    static let shared = CacheManager()

    private let defaults: UserDefaults
    private let prefix = "hestia_cache_"
    private let lock = NSLock()

    private init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    // MARK: - Write

    /// Cache a Codable value with an optional TTL (default 5 minutes).
    func cache<T: Codable>(_ value: T, forKey key: String, ttl: TimeInterval = CacheTTL.standard) {
        guard let data = try? JSONEncoder().encode(value) else { return }
        let entry = CacheEntry(data: data, expiresAt: Date().addingTimeInterval(ttl), cachedAt: Date())
        guard let entryData = try? JSONEncoder().encode(entry) else { return }
        lock.lock()
        defaults.set(entryData, forKey: prefixed(key))
        lock.unlock()
    }

    // MARK: - Read (fresh only)

    /// Retrieve a cached value if it exists and hasn't expired.
    func get<T: Codable>(_ type: T.Type, forKey key: String) -> T? {
        guard let entry = loadEntry(forKey: key) else { return nil }
        guard entry.expiresAt > Date() else { return nil }
        return try? JSONDecoder().decode(type, from: entry.data)
    }

    // MARK: - Read (stale fallback — for offline mode)

    /// Retrieve a cached value even if expired. Returns nil only if no cache exists
    /// or the data can't be decoded (e.g., model changed between app versions).
    func getStale<T: Codable>(_ type: T.Type, forKey key: String) -> T? {
        guard let entry = loadEntry(forKey: key) else { return nil }
        return try? JSONDecoder().decode(type, from: entry.data)
    }

    /// Check if a cached value exists (expired or not).
    func has(forKey key: String) -> Bool {
        loadEntry(forKey: key) != nil
    }

    /// When was this key last successfully cached? Returns nil if never cached.
    func cachedAt(forKey key: String) -> Date? {
        loadEntry(forKey: key)?.cachedAt
    }

    /// Is the cached value still within its TTL?
    func isFresh(forKey key: String) -> Bool {
        guard let entry = loadEntry(forKey: key) else { return false }
        return entry.expiresAt > Date()
    }

    // MARK: - Invalidation

    /// Invalidate a specific cache key.
    func invalidate(forKey key: String) {
        lock.lock()
        defaults.removeObject(forKey: prefixed(key))
        lock.unlock()
    }

    /// Invalidate all cached entries.
    func invalidateAll() {
        lock.lock()
        let allKeys = defaults.dictionaryRepresentation().keys
        for key in allKeys where key.hasPrefix(prefix) {
            defaults.removeObject(forKey: key)
        }
        lock.unlock()
    }

    // MARK: - Private

    private func loadEntry(forKey key: String) -> CacheEntry? {
        lock.lock()
        let entryData = defaults.data(forKey: prefixed(key))
        lock.unlock()
        guard let entryData else { return nil }
        // try? ensures old/incompatible cache entries don't crash — they just return nil
        return try? JSONDecoder().decode(CacheEntry.self, from: entryData)
    }

    private func prefixed(_ key: String) -> String {
        "\(prefix)\(key)"
    }
}

// MARK: - Cache Entry

private struct CacheEntry: Codable {
    let data: Data
    let expiresAt: Date
    let cachedAt: Date

    // Backward compatibility: old entries without cachedAt decode gracefully
    init(data: Data, expiresAt: Date, cachedAt: Date) {
        self.data = data
        self.expiresAt = expiresAt
        self.cachedAt = cachedAt
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        data = try container.decode(Data.self, forKey: .data)
        expiresAt = try container.decode(Date.self, forKey: .expiresAt)
        cachedAt = (try? container.decode(Date.self, forKey: .cachedAt)) ?? Date.distantPast
    }

    enum CodingKeys: String, CodingKey {
        case data, expiresAt, cachedAt
    }
}

// MARK: - TTL Constants

enum CacheTTL {
    /// 30 seconds — trading data, positions, real-time metrics
    static let realtime: TimeInterval = 30
    /// 2 minutes — orders, frequently changing data
    static let frequent: TimeInterval = 120
    /// 5 minutes — default for most data (newsfeed, calendar, memory)
    static let standard: TimeInterval = 300
    /// 10 minutes — profile, agents, config (user-initiated changes only)
    static let stable: TimeInterval = 600
    /// 1 hour — wiki articles, rarely changing content
    static let longLived: TimeInterval = 3600
}

// MARK: - Standard Cache Keys

enum CacheKey {
    // User
    static let userProfile = "user_profile"
    static let userSettings = "user_settings"
    static let userPhoto = "user_photo"

    // Agents
    static let agentsList = "agents_list"
    static func agentIdentity(_ name: String) -> String { "agent_\(name)_identity" }
    static func agentPersonality(_ name: String) -> String { "agent_\(name)_personality" }

    // Resources
    static let cloudProviders = "cloud_providers"
    static let toolsList = "tools_list"
    static let devicesList = "devices_list"
    static let integrationsStatus = "integrations_status"

    // Research
    static let researchGraph = "research_graph"
    static let researchPrinciples = "research_principles"

    // Command Center
    static let systemHealth = "system_health"
    static let pendingMemories = "pending_memories"
    static let orders = "orders"
    static let newsfeed = "newsfeed"
    static let metaMonitorReport = "meta_monitor"
    static let memoryHealth = "memory_health"
    static let triggerAlerts = "trigger_alerts"
    static let investigations = "investigations"
    static let healthSummary = "health_summary"
    static let tradingSummary = "trading_summary"

    // Trading
    static let tradingPortfolio = "trading_portfolio"
    static let tradingPositions = "trading_positions"
    static let tradingBots = "trading_bots"
    static let tradingTrades = "trading_trades"
    static let tradingRiskStatus = "trading_risk_status"
    static let tradingWatchlist = "trading_watchlist"

    // Other
    static let inboxItems = "inbox_items"
    static let healthMetrics = "health_metrics"
    static let memoryChunks = "memory_chunks"
    static let explorerResources = "explorer_resources"
}
