import SwiftUI
import HestiaShared

/// Device management view — list registered devices, revoke/restore access.
struct DeviceManagementView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = DeviceManagementViewModel()
    @State private var deviceToRevoke: DeviceItem?

    var body: some View {
        ZStack {
            GradientBackground(mode: appState.currentMode)

            ScrollView {
                VStack(spacing: Spacing.lg) {
                    if viewModel.isLoading && viewModel.devices.isEmpty {
                        loadingState
                    } else if let error = viewModel.errorMessage, viewModel.devices.isEmpty {
                        errorState(error)
                    } else {
                        deviceList
                    }
                }
                .padding(.top, Spacing.md)
                .padding(.horizontal, Spacing.lg)
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Devices")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await viewModel.loadDevices()
        }
        .alert("Revoke Device Access?", isPresented: .init(
            get: { deviceToRevoke != nil },
            set: { if !$0 { deviceToRevoke = nil } }
        )) {
            Button("Revoke", role: .destructive) {
                if let device = deviceToRevoke {
                    Task { await viewModel.revokeDevice(device) }
                }
                deviceToRevoke = nil
            }
            Button("Cancel", role: .cancel) {
                deviceToRevoke = nil
            }
        } message: {
            if let device = deviceToRevoke {
                Text("\(device.deviceName) will lose access to Hestia. You can restore it later.")
            }
        }
    }

    // MARK: - Device List

    private var deviceList: some View {
        VStack(spacing: Spacing.sm) {
            // Active devices
            let activeDevices = viewModel.devices.filter { $0.isActive }
            if !activeDevices.isEmpty {
                sectionHeader("Active Devices")
                ForEach(activeDevices) { device in
                    deviceRow(device)
                }
            }

            // Revoked devices
            let revokedDevices = viewModel.devices.filter { !$0.isActive }
            if !revokedDevices.isEmpty {
                sectionHeader("Revoked Devices")
                    .padding(.top, Spacing.md)
                ForEach(revokedDevices) { device in
                    deviceRow(device)
                }
            }
        }
    }

    private func sectionHeader(_ title: String) -> some View {
        Text(title)
            .font(.sectionHeader)
            .foregroundColor(.white.opacity(0.6))
            .textCase(.uppercase)
            .frame(maxWidth: .infinity, alignment: .leading)
    }

    private func deviceRow(_ device: DeviceItem) -> some View {
        HStack(spacing: Spacing.md) {
            // Device icon
            Image(systemName: device.iconName)
                .font(.system(size: 20))
                .foregroundColor(device.isActive ? .white : .white.opacity(0.4))
                .frame(width: 32)

            // Device info
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: Spacing.sm) {
                    Text(device.deviceName)
                        .foregroundColor(device.isActive ? .white : .white.opacity(0.5))

                    if viewModel.isCurrentDevice(device) {
                        Text("This Device")
                            .font(.caption2)
                            .foregroundColor(.healthyGreen)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.healthyGreen.opacity(0.15))
                            .cornerRadius(4)
                    }

                    if !device.isActive {
                        Text("Revoked")
                            .font(.caption2)
                            .foregroundColor(.errorRed)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Color.errorRed.opacity(0.15))
                            .cornerRadius(4)
                    }
                }

                HStack(spacing: Spacing.md) {
                    Text(device.deviceType.capitalized)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))

                    Text("Registered \(device.registeredDisplay)")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.4))

                    if device.isActive {
                        Text("Last seen \(device.lastSeenDisplay)")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.4))
                    }
                }
            }

            Spacer()

            // Action button
            if !viewModel.isCurrentDevice(device) {
                if device.isActive {
                    Button {
                        deviceToRevoke = device
                    } label: {
                        Text("Revoke")
                            .font(.caption)
                            .foregroundColor(.errorRed)
                            .padding(.horizontal, Spacing.md)
                            .padding(.vertical, Spacing.sm)
                            .background(Color.errorRed.opacity(0.1))
                            .cornerRadius(CornerRadius.small)
                    }
                } else {
                    Button {
                        Task { await viewModel.unrevokeDevice(device) }
                    } label: {
                        Text("Restore")
                            .font(.caption)
                            .foregroundColor(.healthyGreen)
                            .padding(.horizontal, Spacing.md)
                            .padding(.vertical, Spacing.sm)
                            .background(Color.healthyGreen.opacity(0.1))
                            .cornerRadius(CornerRadius.small)
                    }
                }
            }
        }
        .settingsRow()
    }

    // MARK: - States

    private var loadingState: some View {
        HStack {
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .white))
            Text("Loading devices...")
                .foregroundColor(.white.opacity(0.6))
            Spacer()
        }
        .settingsRow()
    }

    private func errorState(_ message: String) -> some View {
        HStack {
            Image(systemName: "exclamationmark.triangle")
                .foregroundColor(.warningYellow)
            Text(message)
                .foregroundColor(.white.opacity(0.7))
            Spacer()
            Button("Retry") {
                Task { await viewModel.loadDevices() }
            }
            .foregroundColor(.white)
        }
        .settingsRow()
    }
}
