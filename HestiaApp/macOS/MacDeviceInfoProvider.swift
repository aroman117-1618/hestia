import Foundation
import HestiaShared

@MainActor
struct MacDeviceInfoProvider: DeviceInfoProvider {
    var deviceName: String { Host.current().localizedName ?? ProcessInfo.processInfo.hostName }
    var deviceType: String { "macOS" }
}
