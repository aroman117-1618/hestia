import SwiftUI
import HestiaShared

/// Health dashboard ViewModel with static mock data for initial UI.
@MainActor
class MacHealthViewModel: ObservableObject {
    // MARK: - Biological Age
    @Published var biologicalAge: Int = 47
    @Published var chronologicalAge: Int = 42
    @Published var percentile: Int = 74

    // Radar chart axes (0-1 normalized)
    @Published var radarValues: [Double] = [0.85, 0.72, 0.45, 0.35, 0.68, 0.62, 0.78]
    let radarLabels = ["Biological", "Metabolic", "Lipid", "Cancer", "Heme-Immune", "Kidney", "Liver"]

    // Risk values around gauge
    let riskValues: [(label: String, value: String)] = [
        ("Heart Disease", "34.21"),
        ("Type 2 Diabetes", "17.32"),
        ("Stroke", "17.54"),
        ("COPD", "14.45"),
        ("Cancer", "4.94")
    ]

    // MARK: - Telomere
    @Published var telomereLength: Double = 5.2
    @Published var telomereStatus: String = "Medium"

    // MARK: - Methylation
    @Published var methylationScore: Double = 0.76
    @Published var methylationAge: Int = 47

    // MARK: - Immunity
    let immunityValues: [(label: String, range: String)] = [
        ("CD4+ T Cells (Helper T Cells)", "30-60"),
        ("CD8+ T Cells (Cytotoxic T Cells)", "20-40"),
        ("B Cells", "5-15"),
        ("Monocytes", "2-10")
    ]
    @Published var cd4Cd8Ratio: Double = 1.4
    @Published var lymphMonoRatio: Double = 3.7

    // MARK: - Inflammation
    @Published var crpScore: Double = 3.2
    @Published var crpPercentile: Int = 75
    @Published var crpChange: Double = 2.5
    @Published var crpChangePercent: Double = 14.2

    // MARK: - Data Loading
    @Published var isLoading = false

    func loadData() async {
        // Future: fetch from /v1/health_data/summary
        // For now, static mock data is already populated
    }
}
