import SwiftUI
import HestiaShared

/// Device management ViewModel for macOS.
@MainActor
class MacDeviceManagementViewModel: ObservableObject {
    @Published var devices: [DeviceItem] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    private var currentDeviceName: String {
        Host.current().localizedName ?? "Mac"
    }

    func loadDevices() async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await APIClient.shared.getDevices()
            devices = response.devices
        } catch {
            errorMessage = "Failed to load devices"
            #if DEBUG
            print("[MacDeviceManagementViewModel] Load failed: \(error)")
            #endif
        }
        isLoading = false
    }

    func revokeDevice(_ device: DeviceItem) async {
        do {
            _ = try await APIClient.shared.revokeDevice(device.deviceId)
            await loadDevices()
        } catch {
            errorMessage = "Failed to revoke device"
            #if DEBUG
            print("[MacDeviceManagementViewModel] Revoke failed: \(error)")
            #endif
        }
    }

    func unrevokeDevice(_ device: DeviceItem) async {
        do {
            _ = try await APIClient.shared.unrevokeDevice(device.deviceId)
            await loadDevices()
        } catch {
            errorMessage = "Failed to restore device"
            #if DEBUG
            print("[MacDeviceManagementViewModel] Unrevoke failed: \(error)")
            #endif
        }
    }

    func isCurrentDevice(_ device: DeviceItem) -> Bool {
        device.deviceName == currentDeviceName && device.isActive
    }
}
