import SwiftUI
import HestiaShared

/// Resources detail — Cloud LLMs, Integrations, Health coaching.
/// Links to existing detail views for each subsection.
struct ResourcesDetailView: View {
    @EnvironmentObject var appState: AppState

    var body: some View {
        ZStack {
            GradientBackground(mode: appState.currentMode)
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: Spacing.md) {
                    // Cloud LLMs
                    HestiaSettingsBlock(
                        icon: "cloud.fill",
                        iconColor: .accent,
                        title: "Cloud LLMs",
                        subtitle: "Manage cloud AI providers"
                    ) {
                        CloudSettingsView()
                    }

                    // Integrations
                    HestiaSettingsBlock(
                        icon: "puzzlepiece.fill",
                        iconColor: .healthyGreen,
                        title: "Integrations",
                        subtitle: "Calendar, Reminders, HealthKit"
                    ) {
                        IntegrationsView()
                    }

                    // Health Coaching
                    HestiaSettingsBlock(
                        icon: "heart.fill",
                        iconColor: .errorRed,
                        title: "Health Coaching",
                        subtitle: "Coaching preferences"
                    ) {
                        HealthCoachingPreferencesView()
                    }
                }
                .padding(.horizontal, Spacing.md)
                .padding(.vertical, Spacing.md)
            }
        }
        .navigationTitle("Resources")
        .navigationBarTitleDisplayMode(.large)
        .toolbarColorScheme(.dark, for: .navigationBar)
    }
}
