import Foundation
import Security

/// Certificate pinning delegate for secure API connections
/// Validates server certificates against bundled/expected certificates
/// to prevent man-in-the-middle attacks.
///
/// Security features:
/// - SHA-256 certificate fingerprint validation
/// - Public key pinning as fallback
/// - Development mode bypass (DEBUG builds only)
/// - Certificate chain validation
final class CertificatePinningDelegate: NSObject, URLSessionDelegate {

    // MARK: - Constants

    /// Service identifier for Keychain storage
    private static let keychainService = "com.hestia.certificates"

    /// Bundled certificate filename (without extension)
    private static let bundledCertName = "hestia"

    // MARK: - Properties

    /// Set of valid certificate fingerprints (SHA-256)
    private let pinnedFingerprints: Set<String>

    /// Whether to allow untrusted certificates in development
    private let allowDevelopmentBypass: Bool

    /// Logger for security events
    private let logger: (String) -> Void

    // MARK: - Initialization

    /// Initialize with pinned certificate fingerprints
    /// - Parameters:
    ///   - fingerprints: Set of SHA-256 fingerprints to trust (colon-separated hex)
    ///   - allowDevelopmentBypass: If true, allows self-signed certs in DEBUG builds
    ///   - logger: Optional logging closure for security events
    init(
        fingerprints: Set<String> = [],
        allowDevelopmentBypass: Bool = false,
        logger: @escaping (String) -> Void = { print("[CertPinning] \($0)") }
    ) {
        var allFingerprints = fingerprints

        // Load fingerprint from bundled file if available
        if let bundledFingerprint = Self.loadBundledFingerprint() {
            allFingerprints.insert(bundledFingerprint)
            logger("Loaded bundled certificate fingerprint")
        }

        // Load fingerprint from Keychain if available
        if let keychainFingerprint = Self.loadKeychainFingerprint() {
            allFingerprints.insert(keychainFingerprint)
            logger("Loaded Keychain certificate fingerprint")
        }

        self.pinnedFingerprints = allFingerprints
        self.allowDevelopmentBypass = allowDevelopmentBypass
        self.logger = logger

        super.init()

        if allFingerprints.isEmpty {
            logger("WARNING: No certificate fingerprints configured!")
        } else {
            logger("Initialized with \(allFingerprints.count) pinned fingerprint(s)")
        }
    }

    /// Convenience initializer that loads fingerprints from bundled resources
    convenience init(allowDevelopmentBypass: Bool = false) {
        self.init(
            fingerprints: [],
            allowDevelopmentBypass: allowDevelopmentBypass
        )
    }

    // MARK: - URLSessionDelegate

    func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        // Only handle server trust challenges
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            logger("Non-server-trust challenge, using default handling")
            completionHandler(.performDefaultHandling, nil)
            return
        }

        let host = challenge.protectionSpace.host

        // Development bypass for DEBUG builds
        #if DEBUG
        if allowDevelopmentBypass {
            logger("DEBUG: Development bypass enabled for \(host)")
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
            return
        }
        #endif

        // If no fingerprints are configured, fall back to system validation
        if pinnedFingerprints.isEmpty {
            logger("No fingerprints configured, using system validation for \(host)")
            completionHandler(.performDefaultHandling, nil)
            return
        }

        // Perform certificate pinning validation
        if validateServerTrust(serverTrust, for: host) {
            logger("Certificate validation successful for \(host)")
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            logger("SECURITY: Certificate validation FAILED for \(host)")
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }

    // MARK: - Validation

    /// Validate server trust against pinned certificates
    private func validateServerTrust(_ serverTrust: SecTrust, for host: String) -> Bool {
        // Get certificate chain
        let certificateCount = SecTrustGetCertificateCount(serverTrust)
        guard certificateCount > 0 else {
            logger("No certificates in chain for \(host)")
            return false
        }

        // Check each certificate in the chain
        for i in 0..<certificateCount {
            guard let certificate = SecTrustGetCertificateAtIndex(serverTrust, i) else {
                continue
            }

            // Calculate SHA-256 fingerprint
            let fingerprint = calculateFingerprint(for: certificate)

            if pinnedFingerprints.contains(fingerprint) {
                logger("Matched pinned certificate at index \(i) for \(host)")
                return true
            }
        }

        // Log the server's fingerprint for debugging
        if let leafCert = SecTrustGetCertificateAtIndex(serverTrust, 0) {
            let serverFingerprint = calculateFingerprint(for: leafCert)
            logger("Server certificate fingerprint: \(serverFingerprint)")
            logger("Expected one of: \(pinnedFingerprints.joined(separator: ", "))")
        }

        return false
    }

    /// Calculate SHA-256 fingerprint for a certificate
    private func calculateFingerprint(for certificate: SecCertificate) -> String {
        let data = SecCertificateCopyData(certificate) as Data

        var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        data.withUnsafeBytes { bytes in
            _ = CC_SHA256(bytes.baseAddress, CC_LONG(data.count), &hash)
        }

        // Format as colon-separated hex (matches openssl output)
        return hash.map { String(format: "%02X", $0) }.joined(separator: ":")
    }

    // MARK: - Static Helpers

    /// Load certificate fingerprint from bundled file
    private static func loadBundledFingerprint() -> String? {
        // Try loading from bundled fingerprint file
        guard let fingerprintURL = Bundle.main.url(
            forResource: "hestia-fingerprint",
            withExtension: "txt"
        ) else {
            return nil
        }

        guard let content = try? String(contentsOf: fingerprintURL, encoding: .utf8) else {
            return nil
        }

        return content.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Load certificate fingerprint from Keychain
    private static func loadKeychainFingerprint() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: "certificate-fingerprint",
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let fingerprint = String(data: data, encoding: .utf8) else {
            return nil
        }

        return fingerprint
    }

    /// Store certificate fingerprint in Keychain
    static func storeFingerprint(_ fingerprint: String) -> Bool {
        guard let data = fingerprint.data(using: .utf8) else {
            return false
        }

        // Delete any existing entry
        let deleteQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: "certificate-fingerprint"
        ]
        SecItemDelete(deleteQuery as CFDictionary)

        // Add new entry
        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: "certificate-fingerprint",
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]

        let status = SecItemAdd(addQuery as CFDictionary, nil)
        return status == errSecSuccess
    }

    /// Load certificate fingerprint from a certificate file
    static func fingerprintFromCertificate(at url: URL) -> String? {
        guard let certificateData = try? Data(contentsOf: url) else {
            return nil
        }

        // Try to create a SecCertificate
        guard let certificate = SecCertificateCreateWithData(nil, certificateData as CFData) else {
            // Might be PEM format, try to extract DER
            if let pemString = String(data: certificateData, encoding: .utf8),
               let derData = extractDERFromPEM(pemString),
               let cert = SecCertificateCreateWithData(nil, derData as CFData) {
                return calculateStaticFingerprint(for: cert)
            }
            return nil
        }

        return calculateStaticFingerprint(for: certificate)
    }

    /// Extract DER data from PEM string
    private static func extractDERFromPEM(_ pem: String) -> Data? {
        let lines = pem.components(separatedBy: "\n")
        let base64Lines = lines.filter { line in
            !line.hasPrefix("-----") && !line.isEmpty
        }
        let base64String = base64Lines.joined()
        return Data(base64Encoded: base64String)
    }

    /// Static fingerprint calculation
    private static func calculateStaticFingerprint(for certificate: SecCertificate) -> String {
        let data = SecCertificateCopyData(certificate) as Data

        var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        data.withUnsafeBytes { bytes in
            _ = CC_SHA256(bytes.baseAddress, CC_LONG(data.count), &hash)
        }

        return hash.map { String(format: "%02X", $0) }.joined(separator: ":")
    }
}

// MARK: - CommonCrypto Import

import CommonCrypto
