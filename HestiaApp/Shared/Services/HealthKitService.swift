import Foundation
import HestiaShared
import HealthKit
import Combine

/// Service for syncing HealthKit data to the Hestia backend.
///
/// HealthKit is iOS-only — no macOS API. This service collects samples
/// from HealthKit and POSTs them to the backend's `/v1/health_data/sync`
/// endpoint for storage, analysis, and coaching.
///
/// Read-only access — Hestia never writes health data.
@MainActor
final class HealthKitService: ObservableObject {
    // MARK: - Published State

    @Published private(set) var isAuthorized: Bool = false
    @Published private(set) var isSyncing: Bool = false
    @Published private(set) var lastSyncDate: Date?
    @Published private(set) var lastSyncResult: HealthSyncResponse?
    @Published private(set) var error: String?

    // MARK: - Private Properties

    private let healthStore = HKHealthStore()
    private var apiClient: APIClient!

    // MARK: - UserDefaults Keys

    private static let lastSyncKey = "hestia.health.lastSyncDate"

    // MARK: - HealthKit Types

    /// All quantity types Hestia reads (26 types)
    private let quantityTypes: [HKQuantityType] = [
        // Activity (7)
        HKQuantityType(.stepCount),
        HKQuantityType(.distanceWalkingRunning),
        HKQuantityType(.activeEnergyBurned),
        HKQuantityType(.appleExerciseTime),
        HKQuantityType(.appleStandTime),
        HKQuantityType(.flightsClimbed),
        HKQuantityType(.vo2Max),
        // Heart (4)
        HKQuantityType(.heartRate),
        HKQuantityType(.restingHeartRate),
        HKQuantityType(.heartRateVariabilitySDNN),
        HKQuantityType(.walkingHeartRateAverage),
        // Body (4)
        HKQuantityType(.bodyMass),
        HKQuantityType(.bodyMassIndex),
        HKQuantityType(.bodyFatPercentage),
        HKQuantityType(.leanBodyMass),
        // Nutrition (6)
        HKQuantityType(.dietaryEnergyConsumed),
        HKQuantityType(.dietaryProtein),
        HKQuantityType(.dietaryCarbohydrates),
        HKQuantityType(.dietaryFatTotal),
        HKQuantityType(.dietaryFiber),
        HKQuantityType(.dietaryWater),
        // Vitals (4)
        HKQuantityType(.respiratoryRate),
        HKQuantityType(.oxygenSaturation),
        HKQuantityType(.bloodPressureSystolic),
        HKQuantityType(.bloodPressureDiastolic),
    ]

    /// Category types Hestia reads (2 types)
    private let categoryTypes: [HKCategoryType] = [
        HKCategoryType(.sleepAnalysis),
        HKCategoryType(.mindfulSession),
    ]

    /// All types combined for authorization
    private var allReadTypes: Set<HKObjectType> {
        var types = Set<HKObjectType>(quantityTypes)
        types.formUnion(categoryTypes)
        return types
    }

    /// Maps HKQuantityType to (metricType string, HKUnit)
    private let quantityTypeMap: [(HKQuantityType, String, HKUnit)] = [
        // Activity
        (HKQuantityType(.stepCount), "stepCount", .count()),
        (HKQuantityType(.distanceWalkingRunning), "distanceWalkingRunning", .mile()),
        (HKQuantityType(.activeEnergyBurned), "activeEnergyBurned", .kilocalorie()),
        (HKQuantityType(.appleExerciseTime), "appleExerciseTime", .minute()),
        (HKQuantityType(.appleStandTime), "appleStandTime", .minute()),
        (HKQuantityType(.flightsClimbed), "flightsClimbed", .count()),
        (HKQuantityType(.vo2Max), "vo2Max", HKUnit.literUnit(with: .milli).unitDivided(by: HKUnit.gramUnit(with: .kilo)).unitDivided(by: HKUnit.minute())),
        // Heart
        (HKQuantityType(.heartRate), "heartRate", HKUnit.count().unitDivided(by: .minute())),
        (HKQuantityType(.restingHeartRate), "restingHeartRate", HKUnit.count().unitDivided(by: .minute())),
        (HKQuantityType(.heartRateVariabilitySDNN), "heartRateVariabilitySDNN", .secondUnit(with: .milli)),
        (HKQuantityType(.walkingHeartRateAverage), "walkingHeartRateAverage", HKUnit.count().unitDivided(by: .minute())),
        // Body
        (HKQuantityType(.bodyMass), "bodyMass", .pound()),
        (HKQuantityType(.bodyMassIndex), "bodyMassIndex", .count()),
        (HKQuantityType(.bodyFatPercentage), "bodyFatPercentage", .percent()),
        (HKQuantityType(.leanBodyMass), "leanBodyMass", .pound()),
        // Nutrition
        (HKQuantityType(.dietaryEnergyConsumed), "dietaryEnergyConsumed", .kilocalorie()),
        (HKQuantityType(.dietaryProtein), "dietaryProtein", .gram()),
        (HKQuantityType(.dietaryCarbohydrates), "dietaryCarbohydrates", .gram()),
        (HKQuantityType(.dietaryFatTotal), "dietaryFatTotal", .gram()),
        (HKQuantityType(.dietaryFiber), "dietaryFiber", .gram()),
        (HKQuantityType(.dietaryWater), "dietaryWater", .literUnit(with: .milli)),
        // Vitals
        (HKQuantityType(.respiratoryRate), "respiratoryRate", HKUnit.count().unitDivided(by: .minute())),
        (HKQuantityType(.oxygenSaturation), "oxygenSaturation", .percent()),
        (HKQuantityType(.bloodPressureSystolic), "bloodPressureSystolic", .millimeterOfMercury()),
        (HKQuantityType(.bloodPressureDiastolic), "bloodPressureDiastolic", .millimeterOfMercury()),
    ]

    // MARK: - Initialization

    nonisolated init() {}

    /// Setup method — call from .onAppear
    func setup() {
        apiClient = APIClient.shared
        updateAuthorizationStatus()
        loadLastSyncDate()
    }

    // MARK: - Authorization

    /// Whether HealthKit is available on this device
    nonisolated var isHealthKitAvailable: Bool {
        HKHealthStore.isHealthDataAvailable()
    }

    /// Request HealthKit authorization (read-only, no write types)
    func requestAuthorization() async -> Bool {
        guard isHealthKitAvailable else {
            error = "HealthKit is not available on this device"
            return false
        }

        do {
            try await healthStore.requestAuthorization(
                toShare: [],  // Read-only — Hestia doesn't write health data
                read: allReadTypes
            )

            // HealthKit doesn't reveal per-type authorization for reads,
            // so we assume success if no error was thrown
            isAuthorized = true
            error = nil
            return true
        } catch {
            #if DEBUG
            print("[HealthKitService] Authorization failed: \(error)")
            #endif
            self.error = "HealthKit authorization failed"
            isAuthorized = false
            return false
        }
    }

    // MARK: - Sync

    /// Sync today's health metrics to the Hestia backend
    func syncDailyMetrics(for date: Date = Date()) async -> HealthSyncResponse? {
        guard isAuthorized else {
            error = "HealthKit not authorized"
            return nil
        }

        isSyncing = true
        error = nil
        defer { isSyncing = false }

        do {
            // Collect metrics from all types
            var allMetrics: [HealthMetricPayload] = []

            // Collect quantity samples
            for (quantityType, metricType, unit) in quantityTypeMap {
                let metrics = await collectQuantitySamples(
                    type: quantityType,
                    metricType: metricType,
                    unit: unit,
                    date: date
                )
                allMetrics.append(contentsOf: metrics)
            }

            // Collect category samples (sleep, mindfulness)
            let sleepMetrics = await collectCategorySamples(
                type: HKCategoryType(.sleepAnalysis),
                metricType: "sleepAnalysis",
                date: date
            )
            allMetrics.append(contentsOf: sleepMetrics)

            let mindfulMetrics = await collectCategorySamples(
                type: HKCategoryType(.mindfulSession),
                metricType: "mindfulSession",
                date: date
            )
            allMetrics.append(contentsOf: mindfulMetrics)

            #if DEBUG
            print("[HealthKitService] Collected \(allMetrics.count) metrics for sync")
            #endif

            guard !allMetrics.isEmpty else {
                error = "No health data available for this date"
                return nil
            }

            // POST to backend
            let request = HealthSyncRequest(metrics: allMetrics, syncDate: date)
            let response = try await apiClient.syncHealthMetrics(request)

            lastSyncResult = response
            lastSyncDate = Date()
            saveLastSyncDate()

            #if DEBUG
            print("[HealthKitService] Sync complete: \(response.metricsStored) stored, \(response.metricsDeduplicated) deduped")
            #endif

            return response
        } catch {
            #if DEBUG
            print("[HealthKitService] Sync failed: \(error)")
            #endif
            self.error = "Sync failed: \(error.localizedDescription)"
            return nil
        }
    }

    // MARK: - Sample Collection

    /// Collect quantity samples for a given type and date
    private func collectQuantitySamples(
        type: HKQuantityType,
        metricType: String,
        unit: HKUnit,
        date: Date
    ) async -> [HealthMetricPayload] {
        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: date)
        guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else {
            return []
        }

        let predicate = HKQuery.predicateForSamples(
            withStart: startOfDay,
            end: endOfDay,
            options: .strictStartDate
        )

        let sortDescriptor = NSSortDescriptor(
            key: HKSampleSortIdentifierStartDate,
            ascending: true
        )

        return await withCheckedContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: type,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: [sortDescriptor]
            ) { _, samples, queryError in
                if let queryError = queryError {
                    #if DEBUG
                    print("[HealthKitService] Query error for \(metricType): \(queryError)")
                    #endif
                    continuation.resume(returning: [])
                    return
                }

                guard let quantitySamples = samples as? [HKQuantitySample] else {
                    continuation.resume(returning: [])
                    return
                }

                // For high-frequency metrics (heart rate), aggregate to reduce payload
                let metrics: [HealthMetricPayload]
                if metricType == "heartRate" && quantitySamples.count > 24 {
                    metrics = Self.aggregateHourly(
                        samples: quantitySamples,
                        metricType: metricType,
                        unit: unit
                    )
                } else {
                    metrics = quantitySamples.map { sample in
                        HealthMetricPayload(
                            metricType: metricType,
                            value: sample.quantity.doubleValue(for: unit),
                            unit: unit.unitString,
                            startDate: sample.startDate,
                            endDate: sample.endDate,
                            source: sample.sourceRevision.source.name
                        )
                    }
                }

                continuation.resume(returning: metrics)
            }

            healthStore.execute(query)
        }
    }

    /// Collect category samples (sleep, mindfulness) for a given date
    private func collectCategorySamples(
        type: HKCategoryType,
        metricType: String,
        date: Date
    ) async -> [HealthMetricPayload] {
        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: date)
        guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else {
            return []
        }

        // For sleep, look back to previous evening (sleep spans midnight)
        let queryStart: Date
        if metricType == "sleepAnalysis" {
            queryStart = calendar.date(byAdding: .hour, value: -12, to: startOfDay) ?? startOfDay
        } else {
            queryStart = startOfDay
        }

        let predicate = HKQuery.predicateForSamples(
            withStart: queryStart,
            end: endOfDay,
            options: .strictStartDate
        )

        let sortDescriptor = NSSortDescriptor(
            key: HKSampleSortIdentifierStartDate,
            ascending: true
        )

        return await withCheckedContinuation { continuation in
            let query = HKSampleQuery(
                sampleType: type,
                predicate: predicate,
                limit: HKObjectQueryNoLimit,
                sortDescriptors: [sortDescriptor]
            ) { _, samples, queryError in
                if let queryError = queryError {
                    #if DEBUG
                    print("[HealthKitService] Category query error for \(metricType): \(queryError)")
                    #endif
                    continuation.resume(returning: [])
                    return
                }

                guard let categorySamples = samples as? [HKCategorySample] else {
                    continuation.resume(returning: [])
                    return
                }

                let metrics = categorySamples.map { sample in
                    // Value is duration in minutes for both sleep and mindfulness
                    let durationMinutes = sample.endDate.timeIntervalSince(sample.startDate) / 60.0

                    var metadata: [String: AnyCodableValue]? = nil
                    if metricType == "sleepAnalysis" {
                        let stageName: String
                        if #available(iOS 16.0, *) {
                            switch HKCategoryValueSleepAnalysis(rawValue: sample.value) {
                            case .inBed: stageName = "inBed"
                            case .asleepCore: stageName = "asleepCore"
                            case .asleepDeep: stageName = "asleepDeep"
                            case .asleepREM: stageName = "asleepREM"
                            case .awake: stageName = "awake"
                            case .asleepUnspecified: stageName = "asleepUnspecified"
                            default: stageName = "unknown"
                            }
                        } else {
                            switch HKCategoryValueSleepAnalysis(rawValue: sample.value) {
                            case .inBed: stageName = "inBed"
                            case .asleep: stageName = "asleep"
                            case .awake: stageName = "awake"
                            default: stageName = "unknown"
                            }
                        }
                        metadata = ["stage": .string(stageName)]
                    }

                    return HealthMetricPayload(
                        metricType: metricType,
                        value: durationMinutes,
                        unit: "min",
                        startDate: sample.startDate,
                        endDate: sample.endDate,
                        source: sample.sourceRevision.source.name,
                        metadata: metadata
                    )
                }

                continuation.resume(returning: metrics)
            }

            healthStore.execute(query)
        }
    }

    /// Aggregate high-frequency samples (heart rate) to hourly min/avg/max
    private static func aggregateHourly(
        samples: [HKQuantitySample],
        metricType: String,
        unit: HKUnit
    ) -> [HealthMetricPayload] {
        let calendar = Calendar.current
        var hourlyBuckets: [Int: [Double]] = [:]

        for sample in samples {
            let hour = calendar.component(.hour, from: sample.startDate)
            let value = sample.quantity.doubleValue(for: unit)
            hourlyBuckets[hour, default: []].append(value)
        }

        return hourlyBuckets.sorted(by: { $0.key < $1.key }).map { hour, values in
            let avg = values.reduce(0, +) / Double(values.count)
            let date = calendar.date(
                bySettingHour: hour,
                minute: 0,
                second: 0,
                of: samples.first!.startDate
            ) ?? samples.first!.startDate
            let endDate = calendar.date(
                bySettingHour: hour,
                minute: 59,
                second: 59,
                of: samples.first!.startDate
            ) ?? date

            return HealthMetricPayload(
                metricType: metricType,
                value: avg,
                unit: unit.unitString,
                startDate: date,
                endDate: endDate,
                source: "Apple Health (aggregated)",
                metadata: [
                    "min": .double(values.min() ?? 0),
                    "max": .double(values.max() ?? 0),
                    "count": .int(values.count),
                ]
            )
        }
    }

    // MARK: - Persistence

    private func loadLastSyncDate() {
        lastSyncDate = UserDefaults.standard.object(forKey: Self.lastSyncKey) as? Date
    }

    private func saveLastSyncDate() {
        UserDefaults.standard.set(lastSyncDate, forKey: Self.lastSyncKey)
    }

    private func updateAuthorizationStatus() {
        // HealthKit doesn't expose per-type read authorization status.
        // We check if HealthKit is available and if we've previously authorized.
        guard isHealthKitAvailable else {
            isAuthorized = false
            return
        }

        // Use a representative type to check general authorization
        let stepType = HKQuantityType(.stepCount)
        let status = healthStore.authorizationStatus(for: stepType)
        isAuthorized = (status == .sharingAuthorized || status != .notDetermined)
    }
}
