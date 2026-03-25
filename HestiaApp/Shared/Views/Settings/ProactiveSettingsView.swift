import SwiftUI
import HestiaShared

/// Proactive intelligence settings — interruption policy, briefings, quiet hours, patterns.
struct ProactiveSettingsView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = ProactiveSettingsViewModel()

    var body: some View {
        ZStack {
            GradientBackground(mode: appState.currentMode)

            ScrollView {
                VStack(spacing: Spacing.lg) {
                    if viewModel.isLoading {
                        loadingState
                    } else if let error = viewModel.errorMessage, !viewModel.isLoading {
                        errorState(error)
                    }

                    // Interruption Policy
                    settingsSection("Interruption Policy") {
                        policyPicker
                    }

                    // Daily Briefing
                    settingsSection("Daily Briefing") {
                        briefingSettings
                    }

                    // Quiet Hours
                    settingsSection("Quiet Hours") {
                        quietHoursSettings
                    }

                    // Pattern Detection
                    settingsSection("Pattern Detection") {
                        patternSettings
                    }

                    // Weather
                    settingsSection("Weather") {
                        weatherSettings
                    }

                    // Save button
                    Button {
                        Task { await viewModel.savePolicy() }
                    } label: {
                        HStack {
                            if viewModel.isSaving {
                                ProgressView()
                                    .progressViewStyle(CircularProgressViewStyle(tint: .black))
                                    .scaleEffect(0.8)
                            }
                            Text(viewModel.isSaving ? "Saving..." : "Save Settings")
                                .font(.system(size: 16, weight: .semibold))
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Spacing.md)
                        .background(Color.white)
                        .foregroundColor(.black)
                        .cornerRadius(CornerRadius.small)
                    }
                    .disabled(viewModel.isSaving)
                    .padding(.horizontal, Spacing.lg)

                    Spacer().frame(height: Spacing.xxl)
                }
                .padding(.top, Spacing.md)
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Proactive Intelligence")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await viewModel.loadPolicy()
        }
    }

    // MARK: - Section Builder

    private func settingsSection<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text(title)
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            content()
        }
    }

    // MARK: - Policy Picker

    private var policyPicker: some View {
        VStack(spacing: Spacing.sm) {
            ForEach(InterruptionPolicyOption.allCases) { option in
                Button {
                    viewModel.interruptionPolicy = option
                } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(option.displayName)
                                .foregroundColor(.textPrimary)
                            Text(option.description)
                                .font(.caption)
                                .foregroundColor(.textSecondary)
                        }

                        Spacer()

                        if viewModel.interruptionPolicy == option {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundColor(.healthyGreen)
                        } else {
                            Image(systemName: "circle")
                                .foregroundColor(.textTertiary)
                        }
                    }
                }
                .settingsRow()
            }

            // Current status
            if viewModel.canInterruptNow {
                HStack(spacing: Spacing.sm) {
                    Circle()
                        .fill(Color.healthyGreen)
                        .frame(width: 8, height: 8)
                    Text("Can interrupt now")
                        .font(.caption)
                        .foregroundColor(.healthyGreen)
                }
                .padding(.horizontal, Spacing.md)
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Briefing Settings

    private var briefingSettings: some View {
        VStack(spacing: Spacing.sm) {
            Toggle(isOn: $viewModel.briefingEnabled) {
                Text("Enable Daily Briefing")
                    .foregroundColor(.textPrimary)
            }
            .tint(.healthyGreen)
            .settingsRow()

            if viewModel.briefingEnabled {
                HStack {
                    Text("Briefing Time")
                        .foregroundColor(.textPrimary)
                    Spacer()
                    DatePicker("", selection: $viewModel.briefingTime, displayedComponents: .hourAndMinute)
                        .labelsHidden()
                        .colorScheme(.dark)
                }
                .settingsRow()
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Quiet Hours

    private var quietHoursSettings: some View {
        VStack(spacing: Spacing.sm) {
            Toggle(isOn: $viewModel.quietHoursEnabled) {
                Text("Enable Quiet Hours")
                    .foregroundColor(.textPrimary)
            }
            .tint(.healthyGreen)
            .settingsRow()

            if viewModel.quietHoursEnabled {
                HStack {
                    Text("Start")
                        .foregroundColor(.textPrimary)
                    Spacer()
                    DatePicker("", selection: $viewModel.quietHoursStart, displayedComponents: .hourAndMinute)
                        .labelsHidden()
                        .colorScheme(.dark)
                }
                .settingsRow()

                HStack {
                    Text("End")
                        .foregroundColor(.textPrimary)
                    Spacer()
                    DatePicker("", selection: $viewModel.quietHoursEnd, displayedComponents: .hourAndMinute)
                        .labelsHidden()
                        .colorScheme(.dark)
                }
                .settingsRow()
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Pattern Detection

    private var patternSettings: some View {
        VStack(spacing: Spacing.sm) {
            Toggle(isOn: $viewModel.patternDetectionEnabled) {
                HStack {
                    Text("Enable Pattern Detection")
                        .foregroundColor(.textPrimary)
                    Spacer()
                    if viewModel.patternCount > 0 {
                        Text("\(viewModel.patternCount) patterns")
                            .font(.caption)
                            .foregroundColor(.textSecondary)
                    }
                }
            }
            .tint(.healthyGreen)
            .settingsRow()
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Weather

    private var weatherSettings: some View {
        VStack(spacing: Spacing.sm) {
            Toggle(isOn: $viewModel.weatherEnabled) {
                Text("Include Weather in Briefing")
                    .foregroundColor(.textPrimary)
            }
            .tint(.healthyGreen)
            .settingsRow()

            if viewModel.weatherEnabled {
                HStack {
                    Text("Location")
                        .foregroundColor(.textPrimary)
                    Spacer()
                    TextField("City name", text: $viewModel.weatherLocation)
                        .multilineTextAlignment(.trailing)
                        .foregroundColor(.textPrimary)
                        .frame(maxWidth: 200)
                }
                .settingsRow()
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - States

    private var loadingState: some View {
        HStack {
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .white))
            Text("Loading settings...")
                .foregroundColor(.textSecondary)
            Spacer()
        }
        .settingsRow()
        .padding(.horizontal, Spacing.lg)
    }

    private func errorState(_ message: String) -> some View {
        HStack {
            Image(systemName: "exclamationmark.triangle")
                .foregroundColor(.warningYellow)
            Text(message)
                .foregroundColor(.white.opacity(0.7))
            Spacer()
            Button("Retry") {
                Task { await viewModel.loadPolicy() }
            }
            .foregroundColor(.textPrimary)
        }
        .settingsRow()
        .padding(.horizontal, Spacing.lg)
    }
}
