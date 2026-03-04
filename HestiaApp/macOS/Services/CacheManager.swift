import Foundation

/// UserDefaults-backed cache with TTL support for instant UI loading.
/// Pattern: show cached data immediately, fetch fresh in background, update cache.
final class CacheManager: @unchecked Sendable {
    static let shared = CacheManager()

    private let defaults: UserDefaults
    private let prefix = "hestia_cache_"
    private let lock = NSLock()

    private init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    // MARK: - Public API

    /// Cache a Codable value with an optional TTL (default 5 minutes).
    func cache<T: Codable>(_ value: T, forKey key: String, ttl: TimeInterval = 300) {
        guard let data = try? JSONEncoder().encode(value) else { return }
        let entry = CacheEntry(data: data, expiresAt: Date().addingTimeInterval(ttl))
        guard let entryData = try? JSONEncoder().encode(entry) else { return }
        lock.lock()
        defaults.set(entryData, forKey: prefixed(key))
        lock.unlock()
    }

    /// Retrieve a cached value if it exists and hasn't expired.
    func get<T: Codable>(_ type: T.Type, forKey key: String) -> T? {
        lock.lock()
        let entryData = defaults.data(forKey: prefixed(key))
        lock.unlock()
        guard let entryData,
              let entry = try? JSONDecoder().decode(CacheEntry.self, from: entryData) else {
            return nil
        }
        guard entry.expiresAt > Date() else {
            invalidate(forKey: key)
            return nil
        }
        return try? JSONDecoder().decode(type, from: entry.data)
    }

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

    private func prefixed(_ key: String) -> String {
        "\(prefix)\(key)"
    }
}

// MARK: - Cache Entry

private struct CacheEntry: Codable {
    let data: Data
    let expiresAt: Date
}

// MARK: - Standard Cache Keys

enum CacheKey {
    static let userProfile = "user_profile"
    static let userSettings = "user_settings"
    static let userPhoto = "user_photo"
    static let agentsList = "agents_list"
    static let cloudProviders = "cloud_providers"
    static let toolsList = "tools_list"
    static let devicesList = "devices_list"

    static func agentIdentity(_ name: String) -> String {
        "agent_\(name)_identity"
    }

    static func agentPersonality(_ name: String) -> String {
        "agent_\(name)_personality"
    }

    // Research
    static let researchGraph = "research_graph"
    static let researchPrinciples = "research_principles"
}
