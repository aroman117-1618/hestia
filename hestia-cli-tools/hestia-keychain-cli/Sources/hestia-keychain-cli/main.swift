import Foundation
import Security
import LocalAuthentication

/// Hestia Keychain CLI - Hardware-backed credential management
/// Provides Secure Enclave integration for master key storage and biometric ACLs

// MARK: - JSON Response Helpers

struct JSONResponse: Encodable {
    let success: Bool
    let data: [String: String]?
    let error: String?

    init(success: Bool, data: [String: String]? = nil, error: String? = nil) {
        self.success = success
        self.data = data
        self.error = error
    }

    func print() {
        let encoder = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        if let jsonData = try? encoder.encode(self),
           let jsonString = String(data: jsonData, encoding: .utf8) {
            Swift.print(jsonString)
        }
    }
}

// MARK: - Keychain Operations

/// Generate a master encryption key and store it in Keychain
/// Uses Secure Enclave if available for hardware-backed security
func generateMasterKey() {
    let keyTag = "com.hestia.master-key"
    let keySize = 256

    // Check if key already exists
    let checkQuery: [String: Any] = [
        kSecClass as String: kSecClassKey,
        kSecAttrApplicationTag as String: keyTag.data(using: .utf8)!,
        kSecReturnData as String: false
    ]

    let existsStatus = SecItemCopyMatching(checkQuery as CFDictionary, nil)
    if existsStatus == errSecSuccess {
        JSONResponse(success: false, error: "Master key already exists. Use get-master-key to retrieve.").print()
        return
    }

    // Generate random key bytes
    var keyBytes = [UInt8](repeating: 0, count: keySize / 8)
    let result = SecRandomCopyBytes(kSecRandomDefault, keyBytes.count, &keyBytes)

    guard result == errSecSuccess else {
        JSONResponse(success: false, error: "Failed to generate random bytes: \(result)").print()
        return
    }

    let keyData = Data(keyBytes)

    // Create access control requiring biometric authentication
    var error: Unmanaged<CFError>?
    guard let access = SecAccessControlCreateWithFlags(
        kCFAllocatorDefault,
        kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        [.biometryCurrentSet, .privateKeyUsage],
        &error
    ) else {
        JSONResponse(success: false, error: "Failed to create access control: \(error?.takeRetainedValue().localizedDescription ?? "unknown")").print()
        return
    }

    // Store in Keychain with biometric protection
    let addQuery: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: "hestia.system",
        kSecAttrAccount as String: "master_encryption_key",
        kSecAttrAccessControl as String: access,
        kSecValueData as String: keyData,
        kSecUseAuthenticationContext as String: LAContext()
    ]

    let addStatus = SecItemAdd(addQuery as CFDictionary, nil)

    if addStatus == errSecSuccess {
        // Return base64 encoded key
        let keyBase64 = keyData.base64EncodedString()
        JSONResponse(success: true, data: ["key": keyBase64]).print()
    } else if addStatus == errSecDuplicateItem {
        JSONResponse(success: false, error: "Master key already exists").print()
    } else {
        JSONResponse(success: false, error: "Failed to store key: \(addStatus)").print()
    }
}

/// Retrieve the master encryption key (requires biometric authentication)
func getMasterKey() {
    let context = LAContext()
    context.localizedReason = "Hestia needs access to the master encryption key"

    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: "hestia.system",
        kSecAttrAccount as String: "master_encryption_key",
        kSecReturnData as String: true,
        kSecUseAuthenticationContext as String: context
    ]

    var result: AnyObject?
    let status = SecItemCopyMatching(query as CFDictionary, &result)

    if status == errSecSuccess, let keyData = result as? Data {
        let keyBase64 = keyData.base64EncodedString()
        JSONResponse(success: true, data: ["key": keyBase64]).print()
    } else if status == errSecItemNotFound {
        JSONResponse(success: false, error: "Master key not found. Use generate-master-key first.").print()
    } else if status == errSecUserCanceled {
        JSONResponse(success: false, error: "Biometric authentication cancelled").print()
    } else if status == errSecAuthFailed {
        JSONResponse(success: false, error: "Biometric authentication failed").print()
    } else {
        JSONResponse(success: false, error: "Failed to retrieve key: \(status)").print()
    }
}

/// Store a credential in the Keychain
func storeCredential(service: String, account: String, value: String) {
    guard let valueData = value.data(using: .utf8) else {
        JSONResponse(success: false, error: "Invalid credential value").print()
        return
    }

    // First try to delete existing item
    let deleteQuery: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: account
    ]
    SecItemDelete(deleteQuery as CFDictionary)

    // Add new item
    let addQuery: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: account,
        kSecValueData as String: valueData,
        kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
    ]

    let status = SecItemAdd(addQuery as CFDictionary, nil)

    if status == errSecSuccess {
        JSONResponse(success: true, data: ["stored": "true"]).print()
    } else {
        JSONResponse(success: false, error: "Failed to store credential: \(status)").print()
    }
}

/// Retrieve a credential from the Keychain
func retrieveCredential(service: String, account: String) {
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: account,
        kSecReturnData as String: true
    ]

    var result: AnyObject?
    let status = SecItemCopyMatching(query as CFDictionary, &result)

    if status == errSecSuccess, let data = result as? Data, let value = String(data: data, encoding: .utf8) {
        JSONResponse(success: true, data: ["value": value]).print()
    } else if status == errSecItemNotFound {
        JSONResponse(success: false, error: "Credential not found").print()
    } else {
        JSONResponse(success: false, error: "Failed to retrieve credential: \(status)").print()
    }
}

/// Set biometric access control on an existing keychain item
func setBiometricACL(service: String, account: String) {
    // First retrieve the existing value
    let getQuery: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: account,
        kSecReturnData as String: true
    ]

    var result: AnyObject?
    let getStatus = SecItemCopyMatching(getQuery as CFDictionary, &result)

    guard getStatus == errSecSuccess, let valueData = result as? Data else {
        JSONResponse(success: false, error: "Credential not found: \(getStatus)").print()
        return
    }

    // Delete the old item
    let deleteQuery: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: account
    ]
    SecItemDelete(deleteQuery as CFDictionary)

    // Create biometric access control
    var error: Unmanaged<CFError>?
    guard let access = SecAccessControlCreateWithFlags(
        kCFAllocatorDefault,
        kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
        .biometryCurrentSet,
        &error
    ) else {
        JSONResponse(success: false, error: "Failed to create access control: \(error?.takeRetainedValue().localizedDescription ?? "unknown")").print()
        return
    }

    // Re-add with biometric ACL
    let addQuery: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: account,
        kSecValueData as String: valueData,
        kSecAttrAccessControl as String: access
    ]

    let addStatus = SecItemAdd(addQuery as CFDictionary, nil)

    if addStatus == errSecSuccess {
        JSONResponse(success: true, data: ["biometric_set": "true"]).print()
    } else {
        JSONResponse(success: false, error: "Failed to set biometric ACL: \(addStatus)").print()
    }
}

/// Delete a credential from the Keychain
func deleteCredential(service: String, account: String) {
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrService as String: service,
        kSecAttrAccount as String: account
    ]

    let status = SecItemDelete(query as CFDictionary)

    if status == errSecSuccess || status == errSecItemNotFound {
        JSONResponse(success: true, data: ["deleted": "true"]).print()
    } else {
        JSONResponse(success: false, error: "Failed to delete credential: \(status)").print()
    }
}

/// Print usage information
func printUsage() {
    let usage = """
    hestia-keychain-cli - Secure credential management for Hestia

    Usage:
        hestia-keychain-cli <command> [arguments]

    Commands:
        generate-master-key                    Generate and store master encryption key
        get-master-key                         Retrieve master key (requires biometric)
        store-credential <service> <account>   Store credential from stdin
        retrieve-credential <service> <account> Retrieve credential
        set-biometric-acl <service> <account>  Add biometric requirement to credential
        delete-credential <service> <account>  Delete credential
        help                                   Show this help message

    Output:
        All commands output JSON with format:
        {"success": true/false, "data": {...}, "error": "..."}

    Examples:
        hestia-keychain-cli generate-master-key
        echo "sk-my-api-key" | hestia-keychain-cli store-credential hestia.operational anthropic_api_key
        hestia-keychain-cli retrieve-credential hestia.operational anthropic_api_key
        hestia-keychain-cli set-biometric-acl hestia.sensitive ssn
    """
    print(usage)
}

// MARK: - Main Entry Point

let args = CommandLine.arguments

guard args.count >= 2 else {
    printUsage()
    exit(1)
}

let command = args[1]

switch command {
case "generate-master-key":
    generateMasterKey()

case "get-master-key":
    getMasterKey()

case "store-credential":
    guard args.count >= 4 else {
        JSONResponse(success: false, error: "Usage: store-credential <service> <account>").print()
        exit(1)
    }
    // Read value from stdin
    let value = readLine() ?? ""
    storeCredential(service: args[2], account: args[3], value: value)

case "retrieve-credential":
    guard args.count >= 4 else {
        JSONResponse(success: false, error: "Usage: retrieve-credential <service> <account>").print()
        exit(1)
    }
    retrieveCredential(service: args[2], account: args[3])

case "set-biometric-acl":
    guard args.count >= 4 else {
        JSONResponse(success: false, error: "Usage: set-biometric-acl <service> <account>").print()
        exit(1)
    }
    setBiometricACL(service: args[2], account: args[3])

case "delete-credential":
    guard args.count >= 4 else {
        JSONResponse(success: false, error: "Usage: delete-credential <service> <account>").print()
        exit(1)
    }
    deleteCredential(service: args[2], account: args[3])

case "help", "--help", "-h":
    printUsage()

default:
    JSONResponse(success: false, error: "Unknown command: \(command)").print()
    printUsage()
    exit(1)
}
