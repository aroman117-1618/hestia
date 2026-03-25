import Foundation
import Security
import CommonCrypto

/// Certificate pinning delegate for secure API connections
/// Validates server certificates against bundled/expected certificates
/// to prevent man-in-the-middle attacks.
public final class CertificatePinningDelegate: NSObject, URLSessionDelegate {

    // MARK: - Constants

    private static let keychainService = "com.hestia.certificates"
    private static let bundledCertName = "hestia"

    // MARK: - Properties

    private let pinnedFingerprints: Set<String>
    private let allowDevelopmentBypass: Bool
    private let logger: @Sendable (String) -> Void

    // MARK: - Initialization

    public init(
        fingerprints: Set<String> = [],
        allowDevelopmentBypass: Bool = false,
        logger: @escaping @Sendable (String) -> Void = {
            #if DEBUG
            print("[CertPinning] \($0)")
            #endif
        }
    ) {
        var allFingerprints = fingerprints

        if let bundledFingerprint = Self.loadBundledFingerprint() {
            allFingerprints.insert(bundledFingerprint)
            logger("Loaded bundled certificate fingerprint")
        }

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

    public convenience init(allowDevelopmentBypass: Bool = false) {
        self.init(
            fingerprints: [],
            allowDevelopmentBypass: allowDevelopmentBypass
        )
    }

    // MARK: - URLSessionDelegate

    public func urlSession(
        _ session: URLSession,
        didReceive challenge: URLAuthenticationChallenge,
        completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
    ) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              let serverTrust = challenge.protectionSpace.serverTrust else {
            logger("Non-server-trust challenge, using default handling")
            completionHandler(.performDefaultHandling, nil)
            return
        }

        let host = challenge.protectionSpace.host

        #if DEBUG
        if allowDevelopmentBypass {
            logger("DEBUG: Development bypass enabled for \(host)")
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
            return
        }
        #endif

        if pinnedFingerprints.isEmpty {
            // TOFU (Trust On First Use): no fingerprints configured, so accept the server cert
            // and store its fingerprint for future connections. This enables the Apple Sign In
            // flow where no QR-provided fingerprint is available.
            if let leafCert = SecTrustGetCertificateAtIndex(serverTrust, 0) {
                let fingerprint = calculateFingerprint(for: leafCert)
                let stored = Self.storeFingerprint(fingerprint)
                logger("TOFU: Accepted and stored server certificate for \(host) (stored: \(stored))")
            }
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
            return
        }

        if validateServerTrust(serverTrust, for: host) {
            logger("Certificate validation successful for \(host)")
            completionHandler(.useCredential, URLCredential(trust: serverTrust))
        } else {
            logger("SECURITY: Certificate validation FAILED for \(host)")
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }

    // MARK: - Validation

    private func validateServerTrust(_ serverTrust: SecTrust, for host: String) -> Bool {
        let certificateCount = SecTrustGetCertificateCount(serverTrust)
        guard certificateCount > 0 else {
            logger("No certificates in chain for \(host)")
            return false
        }

        for i in 0..<certificateCount {
            guard let certificate = SecTrustGetCertificateAtIndex(serverTrust, i) else {
                continue
            }

            let fingerprint = calculateFingerprint(for: certificate)

            if pinnedFingerprints.contains(fingerprint) {
                logger("Matched pinned certificate at index \(i) for \(host)")
                return true
            }
        }

        if let leafCert = SecTrustGetCertificateAtIndex(serverTrust, 0) {
            let serverFingerprint = calculateFingerprint(for: leafCert)
            logger("Server certificate fingerprint: \(serverFingerprint)")
            logger("Expected one of: \(pinnedFingerprints.joined(separator: ", "))")
        }

        return false
    }

    private func calculateFingerprint(for certificate: SecCertificate) -> String {
        let data = SecCertificateCopyData(certificate) as Data

        var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        data.withUnsafeBytes { bytes in
            _ = CC_SHA256(bytes.baseAddress, CC_LONG(data.count), &hash)
        }

        return hash.map { String(format: "%02X", $0) }.joined(separator: ":")
    }

    // MARK: - Static Helpers

    private static func loadBundledFingerprint() -> String? {
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

        // Discard empty/invalid fingerprints left by previous buggy onboarding
        let trimmed = fingerprint.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty || !trimmed.contains(":") {
            // Clean up the invalid entry
            let deleteQuery: [String: Any] = [
                kSecClass as String: kSecClassGenericPassword,
                kSecAttrService as String: keychainService,
                kSecAttrAccount as String: "certificate-fingerprint"
            ]
            SecItemDelete(deleteQuery as CFDictionary)
            return nil
        }

        return trimmed
    }

    public static func storeFingerprint(_ fingerprint: String) -> Bool {
        guard let data = fingerprint.data(using: .utf8) else {
            return false
        }

        let deleteQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: "certificate-fingerprint"
        ]
        SecItemDelete(deleteQuery as CFDictionary)

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

    public static func fingerprintFromCertificate(at url: URL) -> String? {
        guard let certificateData = try? Data(contentsOf: url) else {
            return nil
        }

        guard let certificate = SecCertificateCreateWithData(nil, certificateData as CFData) else {
            if let pemString = String(data: certificateData, encoding: .utf8),
               let derData = extractDERFromPEM(pemString),
               let cert = SecCertificateCreateWithData(nil, derData as CFData) {
                return calculateStaticFingerprint(for: cert)
            }
            return nil
        }

        return calculateStaticFingerprint(for: certificate)
    }

    private static func extractDERFromPEM(_ pem: String) -> Data? {
        let lines = pem.components(separatedBy: "\n")
        let base64Lines = lines.filter { line in
            !line.hasPrefix("-----") && !line.isEmpty
        }
        let base64String = base64Lines.joined()
        return Data(base64Encoded: base64String)
    }

    private static func calculateStaticFingerprint(for certificate: SecCertificate) -> String {
        let data = SecCertificateCopyData(certificate) as Data

        var hash = [UInt8](repeating: 0, count: Int(CC_SHA256_DIGEST_LENGTH))
        data.withUnsafeBytes { bytes in
            _ = CC_SHA256(bytes.baseAddress, CC_LONG(data.count), &hash)
        }

        return hash.map { String(format: "%02X", $0) }.joined(separator: ":")
    }
}
