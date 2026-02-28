import UIKit
import HestiaShared

@MainActor
struct IOSDeviceInfoProvider: DeviceInfoProvider {
    var deviceName: String { UIDevice.current.name }
    var deviceType: String { "iOS" }
}
