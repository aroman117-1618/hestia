import SwiftUI
import HestiaShared

/// System detail — Security, Devices, Server status, Danger Zone.
struct SystemDetailView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var apiClientProvider: APIClientProvider
    @ObservedObject var viewModel: SettingsViewModel
    @State private var showUnregisterConfirmation = false

    var body: some View {
        ZStack {
            GradientBackground(mode: appState.currentMode)
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: Spacing.md) {
                    // Security
                    HestiaCard(label: "SECURITY") {
                        VStack(spacing: Spacing.md) {
                            Toggle(isOn: .constant(viewModel.biometricEnabled)) {
                                Label("Face ID", systemImage: "faceid")
                                    .foregroundColor(.textPrimary)
                            }
                            .tint(.healthyGreen)

                            HStack {
                                Label("Auto-Lock", systemImage: "clock.fill")
                                    .foregroundColor(.textPrimary)
                                Spacer()
                                Text("\(viewModel.autoLockMinutes) min")
                                    .foregroundColor(.white.opacity(0.5))
                            }
                        }
                    }

                    // Devices
                    HestiaSettingsBlock(
                        icon: "iphone.gen3",
                        iconColor: .systemBlue,
                        title: "Devices",
                        subtitle: "\(viewModel.deviceCount) registered"
                    ) {
                        DeviceManagementView()
                    }

                    // Server
                    HestiaCard(label: "SERVER") {
                        HStack {
                            Text("Status")
                                .foregroundColor(.textPrimary)
                            Spacer()
                            HestiaStatusBadge(
                                text: viewModel.serverOnline ? "Online" : "Offline",
                                status: viewModel.serverOnline ? .healthy : .error
                            )
                        }
                    }

                    // Version
                    HestiaCard(label: "VERSION") {
                        HStack {
                            Text("Build")
                                .foregroundColor(.textPrimary)
                            Spacer()
                            Text("\(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?") (\(Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "?"))")
                                .foregroundColor(.white.opacity(0.5))
                        }
                    }

                    // Danger Zone
                    HestiaCard(label: "DANGER ZONE") {
                        Button {
                            showUnregisterConfirmation = true
                        } label: {
                            HStack {
                                Image(systemName: "trash.fill")
                                Text("Unregister Device")
                                    .font(.body.weight(.medium))
                            }
                            .foregroundColor(.errorRed)
                            .frame(maxWidth: .infinity)
                        }
                        .alert("Unregister Device?", isPresented: $showUnregisterConfirmation) {
                            Button("Cancel", role: .cancel) {}
                            Button("Unregister", role: .destructive) {
                                authService.unregisterDevice()
                            }
                        } message: {
                            Text("This will remove this device from Hestia. You'll need to re-register with a new invite code.")
                        }
                    }
                }
                .padding(.horizontal, Spacing.md)
                .padding(.vertical, Spacing.md)
            }
        }
        .navigationTitle("System")
        .navigationBarTitleDisplayMode(.large)
        .toolbarColorScheme(.dark, for: .navigationBar)
    }
}
