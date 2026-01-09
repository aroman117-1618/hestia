import Foundation

/// Errors that can occur in the Hestia app
enum HestiaError: Error, Equatable {
    // MARK: - Network Errors
    case networkUnavailable
    case serverUnreachable
    case timeout
    case requestTimeout  // Kept for backward compatibility
    case serverError(statusCode: Int, message: String)

    // MARK: - Validation Errors
    case validationError(String)
    case emptyInput
    case inputTooLong(maxLength: Int)
    case forbiddenPattern

    // MARK: - Authentication Errors
    case unauthorized
    case deviceNotRegistered
    case biometricFailed
    case biometricNotAvailable

    // MARK: - Model Errors
    case modelUnavailable
    case rateLimited(retryAfterSeconds: Int?)

    // MARK: - General Errors
    case unknown(String)

    /// Error code for API matching
    var code: String {
        switch self {
        case .networkUnavailable: return "network_unavailable"
        case .serverUnreachable: return "server_unreachable"
        case .timeout, .requestTimeout: return "timeout"
        case .serverError: return "server_error"
        case .validationError: return "validation_error"
        case .emptyInput: return "empty_input"
        case .inputTooLong: return "input_too_long"
        case .forbiddenPattern: return "forbidden_pattern"
        case .unauthorized: return "unauthorized"
        case .deviceNotRegistered: return "device_not_registered"
        case .biometricFailed: return "biometric_failed"
        case .biometricNotAvailable: return "biometric_not_available"
        case .modelUnavailable: return "model_unavailable"
        case .rateLimited: return "rate_limited"
        case .unknown: return "unknown"
        }
    }

    /// User-friendly error message
    var userMessage: String {
        switch self {
        case .networkUnavailable:
            return "No connection available. Please check your network."
        case .serverUnreachable:
            return "Can't reach Hestia server. Is it running?"
        case .timeout, .requestTimeout:
            return "That took too long. Please try again."
        case .serverError(_, let message):
            return message.isEmpty ? "Server error occurred. Please try again." : message
        case .validationError(let message):
            return message
        case .emptyInput:
            return "Please enter a message."
        case .inputTooLong(let maxLength):
            return "Message is too long. Maximum \(maxLength) characters allowed."
        case .forbiddenPattern:
            return "I can't process that request."
        case .unauthorized:
            return "Please re-authenticate to continue."
        case .deviceNotRegistered:
            return "This device is not registered. Please set up Hestia."
        case .biometricFailed:
            return "Authentication failed. Please try again."
        case .biometricNotAvailable:
            return "Face ID / Touch ID is not available on this device."
        case .modelUnavailable:
            return "I'm having trouble connecting. Is the server running?"
        case .rateLimited(let seconds):
            if let seconds = seconds {
                return "Slow down! Try again in \(seconds) seconds."
            }
            return "Slow down! Try again in a moment."
        case .unknown(let message):
            return message.isEmpty ? "Something went wrong. Please try again." : message
        }
    }

    /// Whether the error is recoverable by retrying
    var isRetryable: Bool {
        switch self {
        case .timeout, .requestTimeout, .serverError, .rateLimited, .modelUnavailable, .serverUnreachable:
            return true
        default:
            return false
        }
    }

    /// Parse error from API response
    static func from(responseError: ResponseError) -> HestiaError {
        switch responseError.code {
        case "validation_error":
            return .validationError(responseError.message)
        case "empty_input":
            return .emptyInput
        case "input_too_long":
            return .inputTooLong(maxLength: 32000)
        case "forbidden_pattern":
            return .forbiddenPattern
        case "timeout":
            return .requestTimeout
        case "model_unavailable":
            return .modelUnavailable
        case "unauthorized":
            return .unauthorized
        case "rate_limited":
            return .rateLimited(retryAfterSeconds: nil)
        default:
            return .unknown(responseError.message)
        }
    }
}

// MARK: - LocalizedError Conformance

extension HestiaError: LocalizedError {
    var errorDescription: String? {
        return userMessage
    }
}
