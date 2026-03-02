import Foundation

/// Disk-backed JSON cache for wiki articles and roadmap data.
/// All operations are best-effort — failures are silent.
/// Cache lives in ~/Library/Caches/Hestia/ and can be purged by macOS at any time.
/// Thread safety: all file I/O is serialized through `ioQueue`.
final class WikiCacheService: @unchecked Sendable {
    static let shared = WikiCacheService()

    private let cacheDir: URL
    private let articlesFile: URL
    private let roadmapFile: URL
    private let metaFile: URL
    private let ioQueue = DispatchQueue(label: "com.hestia.wiki-cache", qos: .utility)

    private let encoder: JSONEncoder = {
        let enc = JSONEncoder()
        enc.keyEncodingStrategy = .convertToSnakeCase
        enc.dateEncodingStrategy = .iso8601
        return enc
    }()

    private let decoder: JSONDecoder = {
        let dec = JSONDecoder()
        dec.keyDecodingStrategy = .convertFromSnakeCase
        dec.dateDecodingStrategy = .iso8601
        return dec
    }()

    private init() {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
        cacheDir = base.appendingPathComponent("Hestia", isDirectory: true)
        articlesFile = cacheDir.appendingPathComponent("wiki-articles.json")
        roadmapFile = cacheDir.appendingPathComponent("wiki-roadmap.json")
        metaFile = cacheDir.appendingPathComponent("wiki-cache-meta.json")
        ensureDirectory()
    }

    // MARK: - Articles

    func loadCachedArticles() -> [WikiArticle]? {
        ioQueue.sync {
            guard let data = try? Data(contentsOf: articlesFile) else { return nil }
            return try? decoder.decode([WikiArticle].self, from: data)
        }
    }

    func saveArticles(_ articles: [WikiArticle]) {
        ioQueue.async { [encoder, decoder, articlesFile, metaFile] in
            guard let data = try? encoder.encode(articles) else { return }
            try? data.write(to: articlesFile, options: .atomic)

            // Update meta timestamp (serialized — no race with saveRoadmap)
            var meta = (try? decoder.decode(CacheMeta.self, from: Data(contentsOf: metaFile))) ?? CacheMeta()
            meta.articlesLastFetched = Date()
            if let metaData = try? encoder.encode(meta) {
                try? metaData.write(to: metaFile, options: .atomic)
            }
        }
    }

    // MARK: - Roadmap

    func loadCachedRoadmap() -> WikiRoadmapResponse? {
        ioQueue.sync {
            guard let data = try? Data(contentsOf: roadmapFile) else { return nil }
            return try? decoder.decode(WikiRoadmapResponse.self, from: data)
        }
    }

    func saveRoadmap(_ roadmap: WikiRoadmapResponse) {
        ioQueue.async { [encoder, decoder, roadmapFile, metaFile] in
            guard let data = try? encoder.encode(roadmap) else { return }
            try? data.write(to: roadmapFile, options: .atomic)

            var meta = (try? decoder.decode(CacheMeta.self, from: Data(contentsOf: metaFile))) ?? CacheMeta()
            meta.roadmapLastFetched = Date()
            if let metaData = try? encoder.encode(meta) {
                try? metaData.write(to: metaFile, options: .atomic)
            }
        }
    }

    // MARK: - Metadata

    func loadMeta() -> CacheMeta {
        ioQueue.sync {
            guard let data = try? Data(contentsOf: metaFile) else { return CacheMeta() }
            return (try? decoder.decode(CacheMeta.self, from: data)) ?? CacheMeta()
        }
    }

    // MARK: - Private

    private func ensureDirectory() {
        try? FileManager.default.createDirectory(at: cacheDir, withIntermediateDirectories: true)
    }
}

// MARK: - WikiCacheService.CacheMeta

extension WikiCacheService {
    struct CacheMeta: Codable {
        var articlesLastFetched: Date?
        var roadmapLastFetched: Date?
    }
}
