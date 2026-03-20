import SwiftUI
import HestiaShared

/// Health dashboard ViewModel backed by real HealthKit data from the API.
@MainActor
class MacHealthViewModel: ObservableObject {
    // MARK: - Activity
    @Published var steps: Int = 0
    @Published var distance: Double = 0  // km
    @Published var calories: Int = 0     // active calories
    @Published var exerciseMinutes: Int = 0

    // MARK: - Heart
    @Published var restingHR: Int = 0
    @Published var hrv: Double = 0

    // MARK: - Sleep
    @Published var sleepMinutes: Int = 0
    @Published var sleepTrend: [CGFloat] = []

    // MARK: - Body
    @Published var weight: Double = 0    // kg
    @Published var bmi: Double = 0

    // MARK: - State
    @Published var isLoading = false
    @Published var hasData = false
    @Published var lastSyncDate: String?
    @Published var errorMessage: String?

    // MARK: - Step Trend (sparkline)
    @Published var stepTrend: [CGFloat] = []

    /// Formatted sleep duration
    var sleepDisplay: String {
        let hours = sleepMinutes / 60
        let mins = sleepMinutes % 60
        if hours == 0 && mins == 0 { return "--" }
        return "\(hours)h \(mins)m"
    }

    /// Step goal progress (0-1)
    var stepProgress: Double {
        let goal = 10_000.0
        return min(Double(steps) / goal, 1.0)
    }

    /// Exercise ring progress (0-1, goal = 30 min)
    var exerciseProgress: Double {
        let goal = 30.0
        return min(Double(exerciseMinutes) / goal, 1.0)
    }

    /// Calorie ring progress (0-1, goal = 500 kcal)
    var calorieProgress: Double {
        let goal = 500.0
        return min(Double(calories) / goal, 1.0)
    }

    // MARK: - Loading

    func loadData() async {
        if !CacheManager.shared.has(forKey: CacheKey.healthMetrics) {
            isLoading = true
        }
        errorMessage = nil

        let (summary, source) = await CacheFetcher.load(
            key: CacheKey.healthMetrics,
            ttl: CacheTTL.standard
        ) {
            try await APIClient.shared.getHealthSummary()
        }

        if let summary {
            parseSummary(summary)
            hasData = true
            lastSyncDate = summary.date
        } else if source == .empty {
            errorMessage = "Unable to load health data"
        }

        // Load step trend in parallel (non-blocking)
        do {
            let trend = try await APIClient.shared.getHealthTrend(metricType: "stepCount", days: 7)
            stepTrend = trend.dataPoints.compactMap { point in
                guard let v = point.value else { return nil }
                return CGFloat(v)
            }
        } catch {
            #if DEBUG
            print("[MacHealthViewModel] Step trend load failed: \(error)")
            #endif
        }

        // Load sleep trend
        do {
            let trend = try await APIClient.shared.getHealthTrend(metricType: "sleepAnalysis", days: 7)
            sleepTrend = trend.dataPoints.compactMap { point in
                guard let v = point.value else { return nil }
                return CGFloat(v)
            }
        } catch {
            #if DEBUG
            print("[MacHealthViewModel] Sleep trend load failed: \(error)")
            #endif
        }

        isLoading = false
    }

    // MARK: - Parse

    private func parseSummary(_ s: MacHealthSummaryResponse) {
        // Activity
        steps = Int(s.double(from: s.activity, key: "steps") ?? 0)
        distance = (s.double(from: s.activity, key: "distance_km") ?? s.double(from: s.activity, key: "distance") ?? 0)
        calories = Int(s.double(from: s.activity, key: "active_calories") ?? s.double(from: s.activity, key: "calories") ?? 0)
        exerciseMinutes = Int(s.double(from: s.activity, key: "exercise_minutes") ?? s.double(from: s.activity, key: "exercise_time") ?? 0)

        // Heart
        restingHR = Int(s.double(from: s.heart, key: "resting_hr") ?? s.double(from: s.heart, key: "resting_heart_rate") ?? 0)
        hrv = s.double(from: s.heart, key: "hrv") ?? s.double(from: s.heart, key: "heart_rate_variability") ?? 0

        // Sleep
        let sleepHours = s.double(from: s.sleep, key: "duration_hours") ?? s.double(from: s.sleep, key: "total_hours") ?? 0
        sleepMinutes = Int(sleepHours * 60)

        // Body
        weight = s.double(from: s.body, key: "weight_kg") ?? s.double(from: s.body, key: "weight") ?? 0
        bmi = s.double(from: s.body, key: "bmi") ?? 0
    }
}
