#if os(iOS)
import SwiftUI
import HestiaShared
import EventKit
import HealthKit
import UserNotifications

/// Permission step definition
private struct PermissionStep: Identifiable {
    let id: String
    let title: String
    let description: String
    let iconName: String
    let iconColor: Color
    let request: () async -> Bool
    let isAvailable: () -> Bool
}

/// Apple HIG-compliant guided permission onboarding (one at a time)
struct PermissionsOnboardingView: View {
    @EnvironmentObject var authService: AuthService
    @State private var currentIndex = 0
    @State private var isRequesting = false
    @State private var grantResults: [String: Bool] = [:]
    @State private var isComplete = false

    private let calendarService = CalendarService()
    private let remindersService = RemindersService()
    private let healthKitService = HealthKitService()

    private var steps: [PermissionStep] {
        [
            PermissionStep(
                id: "calendar",
                title: "Calendar",
                description: "Hestia reads your calendar to include upcoming events in daily briefings and schedule-aware responses.",
                iconName: "calendar",
                iconColor: .red,
                request: { [calendarService] in await calendarService.requestAccess() },
                isAvailable: { true }
            ),
            PermissionStep(
                id: "reminders",
                title: "Reminders",
                description: "Hestia reads your reminders to help you stay on top of tasks and incorporate them into planning.",
                iconName: "checklist",
                iconColor: .orange,
                request: { [remindersService] in await remindersService.requestAccess() },
                isAvailable: { true }
            ),
            PermissionStep(
                id: "health",
                title: "Health",
                description: "Hestia reads your health data to provide personalized coaching and activity insights. No data is shared externally.",
                iconName: "heart.fill",
                iconColor: .pink,
                request: { [healthKitService] in await healthKitService.requestAuthorization() },
                isAvailable: { HKHealthStore.isHealthDataAvailable() }
            ),
            PermissionStep(
                id: "notifications",
                title: "Notifications",
                description: "Hestia sends notifications for briefings, task reminders, and proactive alerts.",
                iconName: "bell.fill",
                iconColor: .blue,
                request: {
                    let center = UNUserNotificationCenter.current()
                    do {
                        return try await center.requestAuthorization(options: [.alert, .badge, .sound])
                    } catch {
                        return false
                    }
                },
                isAvailable: { true }
            ),
            PermissionStep(
                id: "biometric",
                title: authService.biometricType.displayName,
                description: "Hestia uses \(authService.biometricType.displayName) to secure your conversations and personal data.",
                iconName: authService.biometricType.iconName,
                iconColor: .green,
                request: { [authService] in
                    do {
                        try await authService.authenticate()
                        return true
                    } catch {
                        return false
                    }
                },
                isAvailable: { authService.biometricType != .none }
            ),
        ]
    }

    private var availableSteps: [PermissionStep] {
        steps.filter { $0.isAvailable() }
    }

    var body: some View {
        ZStack {
            StaticGradientBackground(mode: .tia)

            if isComplete {
                completionView
            } else if currentIndex < availableSteps.count {
                permissionStepView(step: availableSteps[currentIndex])
            }
        }
    }

    // MARK: - Permission Step

    private func permissionStepView(step: PermissionStep) -> some View {
        VStack(spacing: Spacing.xl) {
            Spacer()

            // Progress indicator
            HStack(spacing: Spacing.xs) {
                ForEach(0..<availableSteps.count, id: \.self) { index in
                    Circle()
                        .fill(index <= currentIndex ? Color.white : Color.white.opacity(0.3))
                        .frame(width: 8, height: 8)
                }
            }

            // Icon
            Image(systemName: step.iconName)
                .font(.system(size: 56))
                .foregroundColor(step.iconColor)
                .shadow(color: step.iconColor.opacity(0.4), radius: 15)

            // Title + description
            VStack(spacing: Spacing.sm) {
                Text(step.title)
                    .font(.title2.bold())
                    .foregroundColor(.white)

                Text(step.description)
                    .font(.body)
                    .foregroundColor(.white.opacity(0.7))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Spacing.xl)
            }

            Spacer()

            // Actions
            VStack(spacing: Spacing.md) {
                Button {
                    Task { await requestPermission(step: step) }
                } label: {
                    HStack(spacing: Spacing.sm) {
                        if isRequesting {
                            ProgressView()
                                .tint(.white)
                        } else {
                            Text("Allow \(step.title)")
                                .font(.buttonText)
                        }
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(Spacing.md)
                    .background(Color.white.opacity(0.2))
                    .cornerRadius(CornerRadius.button)
                }
                .disabled(isRequesting)

                Button {
                    skipStep(step: step)
                } label: {
                    Text("Skip")
                        .font(.body)
                        .foregroundColor(.white.opacity(0.5))
                }
                .disabled(isRequesting)
            }
            .padding(.horizontal, Spacing.xl)

            Spacer()
                .frame(height: Spacing.xxl)
        }
    }

    // MARK: - Completion

    private var completionView: some View {
        VStack(spacing: Spacing.xl) {
            Spacer()

            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 64))
                .foregroundColor(.healthyGreen)

            VStack(spacing: Spacing.sm) {
                Text("All Set")
                    .font(.greeting)
                    .foregroundColor(.white)

                Text("Hestia is ready to assist you.")
                    .font(.subheading)
                    .foregroundColor(.white.opacity(0.8))
            }

            // Summary of grants
            VStack(alignment: .leading, spacing: Spacing.sm) {
                ForEach(availableSteps) { step in
                    HStack(spacing: Spacing.sm) {
                        Image(systemName: grantResults[step.id] == true ? "checkmark.circle.fill" : "xmark.circle")
                            .foregroundColor(grantResults[step.id] == true ? .healthyGreen : .white.opacity(0.3))
                        Text(step.title)
                            .font(.body)
                            .foregroundColor(.white.opacity(0.8))
                        Spacer()
                    }
                }
            }
            .padding(.horizontal, Spacing.xxl)

            Spacer()

            Spacer()
                .frame(height: Spacing.xxl)
        }
    }

    // MARK: - Actions

    private func requestPermission(step: PermissionStep) async {
        isRequesting = true
        let granted = await step.request()
        grantResults[step.id] = granted
        saveGrant(step: step, granted: granted)
        isRequesting = false
        advanceOrComplete()
    }

    private func skipStep(step: PermissionStep) {
        grantResults[step.id] = false
        saveGrant(step: step, granted: false)
        advanceOrComplete()
    }

    private func advanceOrComplete() {
        if currentIndex + 1 < availableSteps.count {
            withAnimation(.easeInOut(duration: 0.3)) {
                currentIndex += 1
            }
        } else {
            withAnimation(.easeInOut(duration: 0.3)) {
                isComplete = true
            }
            // Mark onboarding as complete
            UserDefaults.standard.set(true, forKey: "hestia_permissions_onboarding_complete")
        }
    }

    private func saveGrant(step: PermissionStep, granted: Bool) {
        UserDefaults.standard.set(granted, forKey: "hestia_permission_\(step.id)")
    }
}

// MARK: - Preview

struct PermissionsOnboardingView_Previews: PreviewProvider {
    static var previews: some View {
        PermissionsOnboardingView()
            .environmentObject(AuthService())
    }
}
#endif
