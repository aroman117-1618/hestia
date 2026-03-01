import SwiftUI
import HestiaShared
#if os(iOS)
import UIKit
#endif

/// Manages device list, revocation, and restoration.
@MainActor
class DeviceManagementViewModel: ObservableObject {
    @Published var devices: [DeviceItem] = []
    @Published var isLoading = false
    @Published var errorMessage: String?

    /// The current device's name for UI hinting (server enforces actual protection)
    private var currentDeviceName: String {
        #if os(iOS)
        UIDevice.current.name
        #else
        Host.current().localizedName ?? "Mac"
        #endif
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
            print("[DeviceManagementViewModel] Load failed: \(error)")
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
            print("[DeviceManagementViewModel] Revoke failed: \(error)")
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
            print("[DeviceManagementViewModel] Unrevoke failed: \(error)")
            #endif
        }
    }

    /// Best-effort check using device name. Server returns 400 if you try to revoke your own.
    func isCurrentDevice(_ device: DeviceItem) -> Bool {
        device.deviceName == currentDeviceName && device.isActive
    }
}
