import SwiftUI
import CoreData

/// Settings view with System Status, User Profile, and Agent Profiles
struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.managedObjectContext) private var viewContext
    @StateObject private var viewModel = SettingsViewModel()
    @State private var showingLockConfirmation = false
    @State private var showingUnregisterConfirmation = false

    // Fetch agent profiles from Core Data
    @FetchRequest(
        sortDescriptors: [NSSortDescriptor(keyPath: \AgentProfileEntity.slotIndex, ascending: true)],
        animation: .default
    )
    private var agentProfiles: FetchedResults<AgentProfileEntity>

    var body: some View {
        NavigationView {
            ZStack {
                GradientBackground(mode: appState.currentMode)

                ScrollView {
                    VStack(spacing: Spacing.lg) {
                        // System Status (TOP - moved from CommandCenter)
                        settingsSection("System Status") {
                            systemStatusSection
                        }

                        // User Profile
                        settingsSection("User Profile") {
                            userProfileSection
                        }

                        // Agent Profiles
                        settingsSection("Agent Profiles") {
                            agentProfilesSection
                        }

                        // Security
                        settingsSection("Security") {
                            securitySettings
                        }

                        // About
                        settingsSection("About") {
                            aboutSection
                        }

                        // Advanced / Danger Zone
                        settingsSection("Advanced") {
                            dangerZone
                        }

                        Spacer()
                            .frame(height: Spacing.xxl)
                    }
                    .padding(.top, Spacing.md)
                }
                .scrollContentBackground(.hidden)
            }
            .navigationTitle("Settings")
            .navigationBarTitleDisplayMode(.large)
            .onAppear {
                Task {
                    await viewModel.refresh()
                }
                initializeDefaultAgentProfilesIfNeeded()
            }
        }
        .alert("Lock Hestia?", isPresented: $showingLockConfirmation) {
            Button("Lock", role: .destructive) {
                viewModel.lockApp()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("You'll need to authenticate to unlock.")
        }
        .alert("Unregister Device?", isPresented: $showingUnregisterConfirmation) {
            Button("Unregister", role: .destructive) {
                viewModel.unregisterDevice()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will remove this device's access to Hestia. You'll need to set up again.")
        }
    }

    // MARK: - Section Builder

    private func settingsSection<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text(title)
                .font(.sectionHeader)
                .foregroundColor(.white.opacity(0.6))
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            content()
        }
    }

    // MARK: - System Status Section (Moved from CommandCenter)

    private var systemStatusSection: some View {
        VStack(spacing: Spacing.sm) {
            if let health = viewModel.systemHealth {
                // Overall status
                HStack {
                    Image(systemName: health.status.iconName)
                        .foregroundColor(health.status.color)

                    Text(health.status.displayText)
                        .foregroundColor(.white)

                    Spacer()

                    // Refresh button
                    Button {
                        Task {
                            await viewModel.refresh()
                        }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
                .settingsRow()

                // Component details
                Group {
                    statusRow("Inference", health.components.inference.status)
                    statusRow("Memory", health.components.memory.status)
                    statusRow("Tools", health.components.tools.status)
                }
            } else if viewModel.isLoading {
                HStack {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))

                    Text("Checking system status...")
                        .foregroundColor(.white.opacity(0.6))

                    Spacer()
                }
                .settingsRow()
            } else {
                HStack {
                    Image(systemName: "exclamationmark.triangle")
                        .foregroundColor(.warningYellow)

                    Text("Unable to connect to server")
                        .foregroundColor(.white.opacity(0.7))

                    Spacer()

                    Button("Retry") {
                        Task {
                            await viewModel.refresh()
                        }
                    }
                    .foregroundColor(.white)
                }
                .settingsRow()
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    private func statusRow(_ name: String, _ status: HealthStatus) -> some View {
        HStack {
            Text(name)
                .foregroundColor(.white.opacity(0.7))

            Spacer()

            Circle()
                .fill(status.color)
                .frame(width: 8, height: 8)
        }
        .settingsRow()
    }

    // MARK: - User Profile Section

    private var userProfileSection: some View {
        NavigationLink(destination: UserProfileView()) {
            HStack {
                // User avatar placeholder
                Circle()
                    .fill(Color.white.opacity(0.2))
                    .frame(width: 40, height: 40)
                    .overlay(
                        Text("A")
                            .font(.system(size: 18, weight: .bold))
                            .foregroundColor(.white)
                    )

                VStack(alignment: .leading, spacing: 2) {
                    Text("Andrew")
                        .foregroundColor(.white)

                    Text("Edit profile, photo, notifications")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                }

                Spacer()

                Image(systemName: "chevron.right")
                    .foregroundColor(.white.opacity(0.5))
            }
        }
        .settingsRow()
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Agent Profiles Section

    private var agentProfilesSection: some View {
        VStack(spacing: Spacing.sm) {
            // Show existing agent profiles
            ForEach(0..<3) { index in
                let profile = getAgentProfile(for: index)
                NavigationLink(destination: AgentProfileView(slotIndex: index, profile: profile)) {
                    HStack {
                        // Agent avatar
                        Circle()
                            .fill(
                                LinearGradient(
                                    colors: profile?.gradientColors ?? [Color.white.opacity(0.2)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                            .frame(width: 40, height: 40)
                            .overlay(
                                Text(profile?.initial ?? "\(index + 1)")
                                    .font(.system(size: 18, weight: .bold))
                                    .foregroundColor(.white)
                            )

                        VStack(alignment: .leading, spacing: 2) {
                            HStack {
                                Text(profile?.name ?? "Agent \(index + 1)")
                                    .foregroundColor(.white)

                                if index == 0 {
                                    Text("Primary")
                                        .font(.caption2)
                                        .foregroundColor(.white.opacity(0.5))
                                        .padding(.horizontal, 6)
                                        .padding(.vertical, 2)
                                        .background(Color.white.opacity(0.1))
                                        .cornerRadius(4)
                                }
                            }

                            Text(agentDescription(for: profile))
                                .font(.caption)
                                .foregroundColor(.white.opacity(0.6))
                                .lineLimit(1)
                        }

                        Spacer()

                        Image(systemName: "chevron.right")
                            .foregroundColor(.white.opacity(0.5))
                    }
                }
                .settingsRow()
            }

            // Info text
            Text("3 agent slots available. Primary agent cannot be deleted.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.4))
                .padding(.horizontal, Spacing.md)
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Security Settings

    private var securitySettings: some View {
        VStack(spacing: Spacing.sm) {
            // Biometric info
            HStack {
                Image(systemName: viewModel.biometricType.iconName)
                    .foregroundColor(.white)

                Text(viewModel.biometricType.displayName)
                    .foregroundColor(.white)

                Spacer()

                Text("Enabled")
                    .foregroundColor(.healthyGreen)
                    .font(.caption)
            }
            .settingsRow()

            // Auto-lock timeout
            HStack {
                Text("Auto-Lock")
                    .foregroundColor(.white)

                Spacer()

                Picker("", selection: $viewModel.autoLockTimeout) {
                    ForEach(SettingsViewModel.AutoLockTimeout.allCases) { timeout in
                        Text(timeout.displayName).tag(timeout)
                    }
                }
                .pickerStyle(.menu)
                .accentColor(.white)
                .onChange(of: viewModel.autoLockTimeout) { _ in
                    viewModel.saveSettings()
                }
            }
            .settingsRow()

            // Lock now button
            Button {
                showingLockConfirmation = true
            } label: {
                HStack {
                    Image(systemName: "lock.fill")
                    Text("Lock Now")
                    Spacer()
                }
                .foregroundColor(.white)
            }
            .settingsRow()
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - About Section

    private var aboutSection: some View {
        VStack(spacing: Spacing.sm) {
            HStack {
                Text("Version")
                    .foregroundColor(.white)
                Spacer()
                Text("\(viewModel.appVersion) (\(viewModel.buildNumber))")
                    .foregroundColor(.white.opacity(0.6))
            }
            .settingsRow()
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Danger Zone

    private var dangerZone: some View {
        VStack(spacing: Spacing.sm) {
            Button {
                showingUnregisterConfirmation = true
            } label: {
                HStack {
                    Image(systemName: "xmark.circle")
                    Text("Unregister Device")
                    Spacer()
                }
                .foregroundColor(.errorRed)
            }
            .settingsRow()
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Helper Methods

    private func getAgentProfile(for index: Int) -> AgentProfile? {
        if let entity = agentProfiles.first(where: { $0.slotIndex == Int16(index) }) {
            return entity.toAgentProfile()
        }
        // Return default profile for that slot
        return AgentProfile.defaults[safe: index]
    }

    private func agentDescription(for profile: AgentProfile?) -> String {
        guard let profile = profile else {
            return "Not configured"
        }
        // Return first 50 chars of instructions
        let instructions = profile.instructions
        if instructions.count > 50 {
            return String(instructions.prefix(50)) + "..."
        }
        return instructions
    }

    private func initializeDefaultAgentProfilesIfNeeded() {
        // Only initialize if no profiles exist
        guard agentProfiles.isEmpty else { return }

        // Create default profiles
        for (index, defaultProfile) in AgentProfile.defaults.enumerated() {
            _ = AgentProfileEntity.create(from: defaultProfile, slotIndex: Int16(index), in: viewContext)
        }

        try? viewContext.save()
    }
}

// MARK: - Settings Row Modifier

extension View {
    func settingsRow() -> some View {
        self
            .padding(Spacing.md)
            .background(Color.white.opacity(0.05))
            .cornerRadius(CornerRadius.small)
    }
}

// MARK: - Preview

struct SettingsView_Previews: PreviewProvider {
    static var previews: some View {
        SettingsView()
            .environmentObject(AppState())
            .environment(\.managedObjectContext, PersistenceController.preview.viewContext)
    }
}
