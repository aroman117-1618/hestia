import Foundation

/// Protocol for providing device-specific information across platforms.
/// iOS implements this with UIDevice, macOS with Host/ProcessInfo.
@MainActor
public protocol DeviceInfoProvider: Sendable {
    var deviceName: String { get }
    var deviceType: String { get }
}
