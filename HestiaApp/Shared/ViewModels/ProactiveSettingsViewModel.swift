import SwiftUI
import HestiaShared

/// Interruption policy picker values.
enum InterruptionPolicyOption: String, CaseIterable, Identifiable {
    case never
    case daily
    case proactive

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .never: return "Never"
        case .daily: return "Daily Briefing Only"
        case .proactive: return "Proactive"
        }
    }

    var description: String {
        switch self {
        case .never: return "No interruptions"
        case .daily: return "Daily briefing at a set time"
        case .proactive: return "Hestia initiates when it has something useful"
        }
    }
}

/// Manages proactive intelligence settings, syncs with backend.
@MainActor
class ProactiveSettingsViewModel: ObservableObject {
    // MARK: - Published State

    @Published var interruptionPolicy: InterruptionPolicyOption = .never
    @Published var briefingEnabled = false
    @Published var briefingTime = Date()
    @Published var quietHoursEnabled = false
    @Published var quietHoursStart = Date()
    @Published var quietHoursEnd = Date()
    @Published var patternDetectionEnabled = false
    @Published var patternCount = 0
    @Published var weatherEnabled = false
    @Published var weatherLocation = ""
    @Published var canInterruptNow = false

    @Published var isLoading = false
    @Published var isSaving = false
    @Published var errorMessage: String?

    // MARK: - Load

    func loadPolicy() async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await APIClient.shared.getProactivePolicy()
            applyResponse(response)
        } catch {
            errorMessage = "Failed to load proactive settings"
            #if DEBUG
            print("[ProactiveSettingsViewModel] Load failed: \(error)")
            #endif
        }
        isLoading = false
    }

    // MARK: - Save

    func savePolicy() async {
        isSaving = true
        let request = ProactivePolicyUpdateRequest(
            interruptionPolicy: interruptionPolicy.rawValue,
            briefingEnabled: briefingEnabled,
            briefingTime: formatTime(briefingTime),
            quietHoursEnabled: quietHoursEnabled,
            quietHoursStart: formatTime(quietHoursStart),
            quietHoursEnd: formatTime(quietHoursEnd),
            patternDetectionEnabled: patternDetectionEnabled,
            weatherEnabled: weatherEnabled,
            weatherLocation: weatherLocation.isEmpty ? nil : weatherLocation
        )

        do {
            let response = try await APIClient.shared.updateProactivePolicy(request)
            applyResponse(response)
        } catch {
            errorMessage = "Failed to save settings"
            #if DEBUG
            print("[ProactiveSettingsViewModel] Save failed: \(error)")
            #endif
        }
        isSaving = false
    }

    // MARK: - Private

    private func applyResponse(_ response: ProactivePolicyResponse) {
        interruptionPolicy = InterruptionPolicyOption(rawValue: response.interruptionPolicy) ?? .never
        briefingEnabled = response.briefingEnabled
        briefingTime = parseTime(response.briefingTime) ?? Calendar.current.date(bySettingHour: 8, minute: 0, second: 0, of: Date()) ?? Date()
        quietHoursEnabled = response.quietHoursEnabled
        quietHoursStart = parseTime(response.quietHoursStart) ?? Calendar.current.date(bySettingHour: 22, minute: 0, second: 0, of: Date()) ?? Date()
        quietHoursEnd = parseTime(response.quietHoursEnd) ?? Calendar.current.date(bySettingHour: 8, minute: 0, second: 0, of: Date()) ?? Date()
        patternDetectionEnabled = response.patternDetectionEnabled
        patternCount = response.patternCount
        weatherEnabled = response.weatherEnabled
        weatherLocation = response.weatherLocation
        canInterruptNow = response.canInterruptNow
    }

    private func formatTime(_ date: Date) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        return formatter.string(from: date)
    }

    private func parseTime(_ str: String) -> Date? {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        guard let time = formatter.date(from: str) else { return nil }
        // Transfer hour/minute to today
        let cal = Calendar.current
        let comps = cal.dateComponents([.hour, .minute], from: time)
        return cal.date(bySettingHour: comps.hour ?? 0, minute: comps.minute ?? 0, second: 0, of: Date())
    }
}
