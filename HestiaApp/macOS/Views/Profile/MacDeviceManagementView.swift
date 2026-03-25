import SwiftUI
import HestiaShared

/// macOS device management — list, revoke, restore devices.
struct MacDeviceManagementView: View {
    @StateObject private var viewModel = MacDeviceManagementViewModel()
    @State private var deviceToRevoke: DeviceItem?

    var body: some View {
        VStack(spacing: 0) {
            // Top bar
            HStack {
                Text("Manage Devices")
                    .font(MacTypography.cardTitle)
                    .foregroundStyle(MacColors.textPrimary)

                Spacer()

                Button {
                    Task { await viewModel.loadDevices() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textSecondary)
                }
                .buttonStyle(.hestia)
            }
            .padding(.horizontal, MacSpacing.lg)
            .padding(.vertical, MacSpacing.md)

            Divider()
                .background(MacColors.divider)

            ScrollView {
                VStack(spacing: MacSpacing.md) {
                    if viewModel.isLoading && viewModel.devices.isEmpty {
                        loadingState
                    } else if let error = viewModel.errorMessage, viewModel.devices.isEmpty {
                        errorState(error)
                    } else if viewModel.devices.isEmpty {
                        emptyState
                    } else {
                        deviceList
                    }
                }
                .padding(MacSpacing.lg)
            }
        }
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
                Text("\(device.deviceName) will lose access to Hestia.")
            }
        }
    }

    // MARK: - Device List

    private var deviceList: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            let activeDevices = viewModel.devices.filter { $0.isActive }
            let revokedDevices = viewModel.devices.filter { !$0.isActive }

            if !activeDevices.isEmpty {
                Text("ACTIVE")
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.textFaint)
                    .tracking(1.2)

                ForEach(activeDevices) { device in
                    deviceRow(device)
                }
            }

            if !revokedDevices.isEmpty {
                Text("REVOKED")
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.textFaint)
                    .tracking(1.2)
                    .padding(.top, MacSpacing.sm)

                ForEach(revokedDevices) { device in
                    deviceRow(device)
                }
            }
        }
    }

    private func deviceRow(_ device: DeviceItem) -> some View {
        HStack(spacing: MacSpacing.md) {
            Image(systemName: device.iconName)
                .font(MacTypography.pageTitle)
                .foregroundStyle(device.isActive ? MacColors.textPrimary : MacColors.textFaint)
                .frame(width: 28)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: MacSpacing.sm) {
                    Text(device.deviceName)
                        .font(MacTypography.label)
                        .foregroundStyle(device.isActive ? MacColors.textPrimary : MacColors.textSecondary)

                    if viewModel.isCurrentDevice(device) {
                        Text("This Mac")
                            .font(MacTypography.metadata)
                            .foregroundStyle(MacColors.healthGreen)
                            .padding(.horizontal, MacSpacing.xs)
                            .padding(.vertical, 1)
                            .background(MacColors.healthGreenBg)
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                    }

                    if !device.isActive {
                        Text("Revoked")
                            .font(MacTypography.metadata)
                            .foregroundStyle(MacColors.healthRed)
                            .padding(.horizontal, MacSpacing.xs)
                            .padding(.vertical, 1)
                            .background(MacColors.healthRedBg)
                            .clipShape(RoundedRectangle(cornerRadius: 4))
                    }
                }

                HStack(spacing: MacSpacing.md) {
                    Text(device.deviceType.capitalized)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                    Text("Registered \(device.registeredDisplay)")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    if device.isActive {
                        Text("Last seen \(device.lastSeenDisplay)")
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textFaint)
                    }
                }
            }

            Spacer()

            if !viewModel.isCurrentDevice(device) {
                if device.isActive {
                    Button("Revoke") {
                        deviceToRevoke = device
                    }
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.healthRed)
                    .buttonStyle(.hestia)
                } else {
                    Button("Restore") {
                        Task { await viewModel.unrevokeDevice(device) }
                    }
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.healthGreen)
                    .buttonStyle(.hestia)
                }
            }
        }
        .padding(MacSpacing.md)
        .background(MacColors.innerPillBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                .strokeBorder(MacColors.subtleBorder, lineWidth: 1)
        }
    }

    // MARK: - States

    private var loadingState: some View {
        HStack {
            ProgressView()
                .controlSize(.small)
            Text("Loading devices...")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func errorState(_ message: String) -> some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "exclamationmark.triangle")
                .font(MacTypography.mediumValue)
                .foregroundStyle(MacColors.healthAmber)
            Text(message)
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
            Button("Retry") {
                Task { await viewModel.loadDevices() }
            }
            .font(MacTypography.label)
            .foregroundStyle(MacColors.amberAccent)
            .buttonStyle(.hestia)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyState: some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "desktopcomputer")
                .font(MacTypography.largeValue)
                .foregroundStyle(MacColors.textFaint)
            Text("No devices registered")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
