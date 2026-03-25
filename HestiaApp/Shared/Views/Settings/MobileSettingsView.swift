import SwiftUI
import HestiaShared
import CoreData

/// Rebuilt settings view — 4 Notion-style blocks: Profile, Agents, Resources, System.
struct MobileSettingsView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var apiClientProvider: APIClientProvider
    @StateObject private var viewModel = SettingsViewModel()

    @FetchRequest(sortDescriptors: [
        NSSortDescriptor(keyPath: \AgentProfileEntity.slotIndex, ascending: true)
    ])
    private var agentProfiles: FetchedResults<AgentProfileEntity>

    var body: some View {
        NavigationView {
            ZStack {
                GradientBackground(mode: appState.currentMode)
                    .ignoresSafeArea()

                ScrollView {
                    VStack(spacing: Spacing.md) {
                        // Profile header
                        profileHeader

                        // Agents block
                        HestiaSettingsBlock(
                            icon: "person.3.fill",
                            iconColor: .agentAmber,
                            title: "Agents",
                            subtitle: agentSubtitle
                        ) {
                            AgentCustomizationView()
                        }

                        // Resources block
                        HestiaSettingsBlock(
                            icon: "externaldrive.connected.to.line.below.fill",
                            iconColor: .agentTeal,
                            title: "Resources",
                            subtitle: resourcesSubtitle
                        ) {
                            ResourcesDetailView()
                        }

                        // System block
                        HestiaSettingsBlock(
                            icon: "gearshape.2.fill",
                            iconColor: .white.opacity(0.7),
                            title: "System",
                            subtitle: systemSubtitle
                        ) {
                            SystemDetailView(viewModel: viewModel)
                        }
                    }
                    .padding(.horizontal, Spacing.md)
                    .padding(.bottom, Spacing.xl)
                }
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .toolbarColorScheme(.dark, for: .navigationBar)
        }
        .onAppear {
            if apiClientProvider.isReady {
                viewModel.configure(apiClient: apiClientProvider.client)
                Task { await viewModel.loadSettings() }
            }
        }
        .onChange(of: apiClientProvider.isReady) { _, isReady in
            if isReady {
                viewModel.configure(apiClient: apiClientProvider.client)
                Task { await viewModel.loadSettings() }
            }
        }
    }

    // MARK: - Profile Header

    private var profileHeader: some View {
        VStack(spacing: Spacing.sm) {
            // Avatar
            Circle()
                .fill(Color.agentAmber.opacity(0.2))
                .frame(width: 80, height: 80)
                .overlay(
                    Text("A")
                        .font(.system(size: 32, weight: .bold))
                        .foregroundColor(.agentAmber)
                )

            // Name + version
            Text("Andrew")
                .font(.title3.weight(.semibold))
                .foregroundColor(.white)
            Text("v\(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "?") · \(viewModel.serverOnline ? "Server Online" : "Offline")")
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.lg)
    }

    // MARK: - Subtitles

    private var agentSubtitle: String {
        let names = agentProfiles.prefix(3).map { $0.name }.joined(separator: ", ")
        return names.isEmpty ? "\(agentProfiles.count) agents" : names
    }

    private var resourcesSubtitle: String {
        let cloudState = viewModel.cloudState ?? "disabled"
        let display = cloudState == "enabled_full" ? "Full" : cloudState == "enabled_smart" ? "Smart" : "Off"
        return "Cloud: \(display)"
    }

    private var systemSubtitle: String {
        let faceID = viewModel.biometricEnabled ? "Face ID" : "No biometric"
        let devices = viewModel.deviceCount
        return "\(faceID) · \(devices) device\(devices == 1 ? "" : "s")"
    }
}
