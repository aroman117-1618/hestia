import SwiftUI
import HestiaShared

struct HealthView: View {
    @StateObject private var viewModel = MacHealthViewModel()

    var body: some View {
        VStack(spacing: 0) {
            HealthTopBar(viewModel: viewModel)

            ScrollView {
                VStack(spacing: MacSpacing.lg) {
                    BiologicalAgeCard(viewModel: viewModel)
                    HealthMetricsRow(viewModel: viewModel)
                    EpigeneticMarkersCard()
                }
                .padding(MacSpacing.xl)
            }
        }
        .background(MacColors.windowBackground)
        .task {
            await viewModel.loadData()
        }
    }
}
