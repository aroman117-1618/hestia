import SwiftUI
import HestiaShared

/// View for configuring health coaching preferences.
///
/// Fetches preferences from the backend on appear,
/// allows editing, and saves changes back.
struct HealthCoachingPreferencesView: View {
    @StateObject private var viewModel = HealthCoachingPreferencesViewModel()

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            if viewModel.isLoading && !viewModel.hasLoaded {
                ProgressView()
                    .tint(.white)
            } else {
                ScrollView {
                    VStack(spacing: Spacing.lg) {
                        // Master toggle
                        masterToggleSection

                        if viewModel.enabled {
                            // Coaching domains
                            domainsSection

                            // Goals
                            goalsSection

                            // Notifications
                            notificationsSection

                            // Coaching tone
                            toneSection
                        }

                        // Sync info
                        syncInfoSection

                        Spacer()
                            .frame(height: Spacing.xxl)
                    }
                    .padding(.top, Spacing.md)
                }
                .scrollContentBackground(.hidden)
            }
        }
        .navigationTitle("Health Coaching")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            Task {
                await viewModel.loadPreferences()
            }
        }
        .alert("Error", isPresented: $viewModel.showError) {
            Button("OK") {}
        } message: {
            Text(viewModel.errorMessage)
        }
    }

    // MARK: - Master Toggle

    private var masterToggleSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Coaching")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            HStack {
                Image(systemName: "heart.fill")
                    .foregroundColor(.pink)

                Text("Health Coaching")
                    .foregroundColor(.textPrimary)

                Spacer()

                Toggle("", isOn: $viewModel.enabled)
                    .labelsHidden()
                    .tint(.healthyGreen)
                    .onChange(of: viewModel.enabled) { _ in
                        viewModel.scheduleSave()
                    }
            }
            .settingsRow()
            .padding(.horizontal, Spacing.lg)

            Text("When enabled, Hestia provides health insights in daily briefings and responds to health-related questions.")
                .font(.caption)
                .foregroundColor(.textTertiary)
                .padding(.horizontal, Spacing.lg)
        }
    }

    // MARK: - Coaching Domains

    private var domainsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Domains")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                domainToggle(title: "Activity", icon: "figure.walk", isOn: $viewModel.activityCoaching)
                domainToggle(title: "Sleep", icon: "bed.double.fill", isOn: $viewModel.sleepCoaching)
                domainToggle(title: "Nutrition", icon: "fork.knife", isOn: $viewModel.nutritionCoaching)
                domainToggle(title: "Heart", icon: "heart.circle", isOn: $viewModel.heartCoaching)
                domainToggle(title: "Mindfulness", icon: "brain.head.profile", isOn: $viewModel.mindfulnessCoaching)
            }
            .padding(.horizontal, Spacing.lg)
        }
    }

    private func domainToggle(title: String, icon: String, isOn: Binding<Bool>) -> some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(.textSecondary)
                .frame(width: 24)

            Text(title)
                .foregroundColor(.textPrimary)

            Spacer()

            Toggle("", isOn: isOn)
                .labelsHidden()
                .tint(.healthyGreen)
                .onChange(of: isOn.wrappedValue) { _ in
                    viewModel.scheduleSave()
                }
        }
        .settingsRow()
    }

    // MARK: - Goals

    private var goalsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Daily Goals")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                goalRow(
                    title: "Steps",
                    icon: "figure.walk",
                    value: "\(viewModel.dailyStepGoal.formatted())",
                    stepper: AnyView(
                        Stepper("", value: $viewModel.dailyStepGoal, in: 1000...50000, step: 1000)
                            .labelsHidden()
                            .onChange(of: viewModel.dailyStepGoal) { _ in viewModel.scheduleSave() }
                    )
                )

                goalRow(
                    title: "Active Calories",
                    icon: "flame.fill",
                    value: "\(viewModel.dailyActiveCalGoal) kcal",
                    stepper: AnyView(
                        Stepper("", value: $viewModel.dailyActiveCalGoal, in: 100...2000, step: 50)
                            .labelsHidden()
                            .onChange(of: viewModel.dailyActiveCalGoal) { _ in viewModel.scheduleSave() }
                    )
                )

                goalRow(
                    title: "Sleep",
                    icon: "bed.double.fill",
                    value: String(format: "%.1f hrs", viewModel.sleepHoursGoal),
                    stepper: AnyView(
                        Stepper("", value: $viewModel.sleepHoursGoal, in: 4.0...12.0, step: 0.5)
                            .labelsHidden()
                            .onChange(of: viewModel.sleepHoursGoal) { _ in viewModel.scheduleSave() }
                    )
                )

                goalRow(
                    title: "Water",
                    icon: "drop.fill",
                    value: "\(viewModel.dailyWaterMlGoal) mL",
                    stepper: AnyView(
                        Stepper("", value: $viewModel.dailyWaterMlGoal, in: 500...5000, step: 250)
                            .labelsHidden()
                            .onChange(of: viewModel.dailyWaterMlGoal) { _ in viewModel.scheduleSave() }
                    )
                )
            }
            .padding(.horizontal, Spacing.lg)
        }
    }

    private func goalRow(title: String, icon: String, value: String, stepper: AnyView) -> some View {
        HStack {
            Image(systemName: icon)
                .foregroundColor(.textSecondary)
                .frame(width: 24)

            Text(title)
                .foregroundColor(.textPrimary)

            Spacer()

            Text(value)
                .foregroundColor(.textSecondary)
                .font(.caption)

            stepper
        }
        .settingsRow()
    }

    // MARK: - Notifications

    private var notificationsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Notifications")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                HStack {
                    Image(systemName: "bell.fill")
                        .foregroundColor(.textSecondary)
                        .frame(width: 24)

                    Text("Daily Summary")
                        .foregroundColor(.textPrimary)

                    Spacer()

                    Toggle("", isOn: $viewModel.dailySummary)
                        .labelsHidden()
                        .tint(.healthyGreen)
                        .onChange(of: viewModel.dailySummary) { _ in viewModel.scheduleSave() }
                }
                .settingsRow()

                HStack {
                    Image(systemName: "target")
                        .foregroundColor(.textSecondary)
                        .frame(width: 24)

                    Text("Goal Alerts")
                        .foregroundColor(.textPrimary)

                    Spacer()

                    Toggle("", isOn: $viewModel.goalAlerts)
                        .labelsHidden()
                        .tint(.healthyGreen)
                        .onChange(of: viewModel.goalAlerts) { _ in viewModel.scheduleSave() }
                }
                .settingsRow()

                HStack {
                    Image(systemName: "exclamationmark.triangle")
                        .foregroundColor(.textSecondary)
                        .frame(width: 24)

                    Text("Anomaly Alerts")
                        .foregroundColor(.textPrimary)

                    Spacer()

                    Toggle("", isOn: $viewModel.anomalyAlerts)
                        .labelsHidden()
                        .tint(.healthyGreen)
                        .onChange(of: viewModel.anomalyAlerts) { _ in viewModel.scheduleSave() }
                }
                .settingsRow()
            }
            .padding(.horizontal, Spacing.lg)
        }
    }

    // MARK: - Coaching Tone

    private var toneSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Coaching Tone")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                toneOption(
                    title: "Encouraging",
                    description: "Positive reinforcement and gentle nudges",
                    value: "encouraging"
                )
                toneOption(
                    title: "Balanced",
                    description: "Mix of encouragement and honest feedback",
                    value: "balanced"
                )
                toneOption(
                    title: "Direct",
                    description: "Straightforward data-driven feedback",
                    value: "direct"
                )
            }
            .padding(.horizontal, Spacing.lg)
        }
    }

    private func toneOption(title: String, description: String, value: String) -> some View {
        Button {
            viewModel.coachingTone = value
            viewModel.scheduleSave()
        } label: {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .foregroundColor(.textPrimary)
                        .font(.subheadline)

                    Text(description)
                        .foregroundColor(.white.opacity(0.4))
                        .font(.caption)
                }

                Spacer()

                if viewModel.coachingTone == value {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundColor(.healthyGreen)
                } else {
                    Image(systemName: "circle")
                        .foregroundColor(.textTertiary)
                }
            }
            .settingsRow()
        }
    }

    // MARK: - Sync Info

    private var syncInfoSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Data Sync")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                HStack {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .foregroundColor(.textSecondary)
                        .frame(width: 24)

                    Text("Sync Now")
                        .foregroundColor(.textPrimary)

                    Spacer()

                    if viewModel.isSyncing {
                        ProgressView()
                            .tint(.white)
                            .scaleEffect(0.8)
                    }
                }
                .settingsRow()
                .onTapGesture {
                    Task {
                        await viewModel.syncNow()
                    }
                }

                if let lastSync = viewModel.lastSyncFormatted {
                    HStack {
                        Text("Last sync: \(lastSync)")
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.4))

                        Spacer()
                    }
                }
            }
            .padding(.horizontal, Spacing.lg)

            Text("Health data is synced from Apple Health to Hestia's backend for analysis. Data stays on your devices and server.")
                .font(.caption)
                .foregroundColor(.textTertiary)
                .padding(.horizontal, Spacing.lg)
        }
    }
}

// MARK: - ViewModel

@MainActor
class HealthCoachingPreferencesViewModel: ObservableObject {
    // MARK: - Published State

    @Published var isLoading = false
    @Published var hasLoaded = false
    @Published var showError = false
    @Published var errorMessage = ""
    @Published var isSyncing = false

    // MARK: - Preferences

    @Published var enabled = true
    @Published var activityCoaching = true
    @Published var sleepCoaching = true
    @Published var nutritionCoaching = true
    @Published var heartCoaching = true
    @Published var mindfulnessCoaching = true
    @Published var dailySummary = true
    @Published var goalAlerts = true
    @Published var anomalyAlerts = true
    @Published var dailyStepGoal = 10000
    @Published var dailyActiveCalGoal = 500
    @Published var sleepHoursGoal = 8.0
    @Published var dailyWaterMlGoal = 2500
    @Published var coachingTone = "balanced"

    // MARK: - Private

    private var saveTask: Task<Void, Never>?
    private let healthService = HealthKitService()

    var lastSyncFormatted: String? {
        guard let date = healthService.lastSyncDate else { return nil }
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }

    // MARK: - Initialization

    nonisolated init() {}

    // MARK: - API Methods

    func loadPreferences() async {
        guard !hasLoaded else { return }
        isLoading = true
        defer { isLoading = false }

        do {
            let response = try await APIClient.shared.getCoachingPreferences()
            let prefs = response.preferences

            enabled = prefs.enabled
            activityCoaching = prefs.activityCoaching
            sleepCoaching = prefs.sleepCoaching
            nutritionCoaching = prefs.nutritionCoaching
            heartCoaching = prefs.heartCoaching
            mindfulnessCoaching = prefs.mindfulnessCoaching
            dailySummary = prefs.dailySummary
            goalAlerts = prefs.goalAlerts
            anomalyAlerts = prefs.anomalyAlerts
            dailyStepGoal = prefs.dailyStepGoal
            dailyActiveCalGoal = prefs.dailyActiveCalGoal
            sleepHoursGoal = prefs.sleepHoursGoal
            dailyWaterMlGoal = prefs.dailyWaterMlGoal
            coachingTone = prefs.coachingTone

            hasLoaded = true
        } catch {
            #if DEBUG
            print("[HealthCoachingPrefs] Failed to load: \(error)")
            #endif
            // Use defaults on failure — still show the UI
            hasLoaded = true
        }
    }

    /// Debounced save — waits 0.5s after last change before saving
    func scheduleSave() {
        saveTask?.cancel()
        saveTask = Task {
            try? await Task.sleep(nanoseconds: 500_000_000)
            guard !Task.isCancelled else { return }
            await savePreferences()
        }
    }

    private func savePreferences() async {
        let request = CoachingPreferencesUpdateRequest(
            enabled: enabled,
            activityCoaching: activityCoaching,
            sleepCoaching: sleepCoaching,
            nutritionCoaching: nutritionCoaching,
            heartCoaching: heartCoaching,
            mindfulnessCoaching: mindfulnessCoaching,
            dailySummary: dailySummary,
            goalAlerts: goalAlerts,
            anomalyAlerts: anomalyAlerts,
            dailyStepGoal: dailyStepGoal,
            dailyActiveCalGoal: dailyActiveCalGoal,
            sleepHoursGoal: sleepHoursGoal,
            dailyWaterMlGoal: dailyWaterMlGoal,
            coachingTone: coachingTone
        )

        do {
            _ = try await APIClient.shared.updateCoachingPreferences(request)
            #if DEBUG
            print("[HealthCoachingPrefs] Preferences saved")
            #endif
        } catch {
            #if DEBUG
            print("[HealthCoachingPrefs] Failed to save: \(error)")
            #endif
            errorMessage = "Failed to save preferences"
            showError = true
        }
    }

    func syncNow() async {
        isSyncing = true
        defer { isSyncing = false }

        healthService.setup()

        // Ensure authorization
        var authorized = healthService.isAuthorized
        if !authorized {
            authorized = await healthService.requestAuthorization()
        }
        guard authorized else {
            errorMessage = "HealthKit authorization required"
            showError = true
            return
        }

        let result = await healthService.syncDailyMetrics()
        if result == nil, let error = healthService.error {
            errorMessage = error
            showError = true
        }
    }
}

// MARK: - Preview

struct HealthCoachingPreferencesView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            HealthCoachingPreferencesView()
        }
    }
}
