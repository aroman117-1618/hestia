import Foundation

/// Shared stale-while-revalidate fetch helper.
///
/// Encapsulates the pattern: show cached data immediately → fetch fresh in background
/// → update cache on success → fall back to stale data on error.
///
/// Usage:
/// ```swift
/// let (orders, source) = await CacheFetcher.load(
///     key: CacheKey.orders,
///     ttl: CacheTTL.frequent
/// ) {
///     try await APIClient.shared.listOrders(limit: 20)
/// }
/// self.orders = orders?.orders ?? []
/// ```
enum CacheFetcher {

    /// Result source — tells the caller where the data came from.
    enum Source {
        /// Fresh data from the server (cache updated).
        case fresh
        /// Stale data from cache (server call failed or skipped).
        case cached
        /// No data available (no cache, server failed).
        case empty
    }

    /// Load data with stale-while-revalidate semantics.
    ///
    /// - Parameters:
    ///   - key: Cache key for storage/retrieval
    ///   - ttl: Time-to-live for fresh cache entries
    ///   - isOnline: Whether the network is available (skip fetch if false)
    ///   - fetch: Async closure that fetches fresh data from the server
    /// - Returns: Tuple of (data, source). Data is nil only if no cache AND fetch failed.
    static func load<T: Codable>(
        key: String,
        ttl: TimeInterval = CacheTTL.standard,
        isOnline: Bool = true,
        fetch: @Sendable () async throws -> T
    ) async -> (T?, Source) {
        let cache = CacheManager.shared

        // 1. Try stale cache first (instant, even if expired)
        let cached: T? = cache.getStale(T.self, forKey: key)

        // 2. If offline, return whatever cache we have
        guard isOnline else {
            return cached != nil ? (cached, .cached) : (nil, .empty)
        }

        // 3. Try fresh fetch
        do {
            let fresh = try await fetch()
            cache.cache(fresh, forKey: key, ttl: ttl)
            return (fresh, .fresh)
        } catch {
            // Fetch failed — return stale cache if available
            #if DEBUG
            print("[CacheFetcher] Fetch failed for \(key): \(error)")
            #endif
            return cached != nil ? (cached, .cached) : (nil, .empty)
        }
    }

    /// Convenience: load and apply to a binding in one step.
    /// Calls `apply` with cached data immediately (if available), then again with fresh data.
    ///
    /// Usage:
    /// ```swift
    /// let source = await CacheFetcher.loadAndApply(
    ///     key: CacheKey.orders, ttl: CacheTTL.frequent
    /// ) { (response: OrderListResponse) in
    ///     self.orders = response.orders
    /// }
    /// ```
    @discardableResult
    static func loadAndApply<T: Codable>(
        key: String,
        ttl: TimeInterval = CacheTTL.standard,
        isOnline: Bool = true,
        apply: (T) -> Void,
        fetch: @Sendable () async throws -> T
    ) async -> Source {
        let cache = CacheManager.shared

        // 1. Apply cached data immediately
        if let cached: T = cache.getStale(T.self, forKey: key) {
            apply(cached)
        }
        let hadCache = cache.has(forKey: key)

        // 2. If offline, done
        guard isOnline else {
            return hadCache ? .cached : .empty
        }

        // 3. Fetch fresh and apply
        do {
            let fresh = try await fetch()
            cache.cache(fresh, forKey: key, ttl: ttl)
            apply(fresh)
            return .fresh
        } catch {
            #if DEBUG
            print("[CacheFetcher] Fetch failed for \(key): \(error)")
            #endif
            return hadCache ? .cached : .empty
        }
    }
}
