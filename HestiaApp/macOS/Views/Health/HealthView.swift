import SwiftUI
import HestiaShared

struct HealthView: View {
    @StateObject private var viewModel = MacHealthViewModel()

    var body: some View {
        VStack(spacing: 0) {
            HealthTopBar(viewModel: viewModel)

            if viewModel.isLoading && !viewModel.hasData {
                loadingState
            } else if !viewModel.hasData && viewModel.errorMessage != nil {
                emptyState
            } else {
                ScrollView {
                    VStack(spacing: MacSpacing.lg) {
                        ActivityCard(viewModel: viewModel)
                        HealthMetricsRow(viewModel: viewModel)
                        CoachingCard(viewModel: viewModel)
                    }
                    .padding(MacSpacing.xl)
                }
            }
        }
        .background(MacColors.windowBackground)
        .task {
            await viewModel.loadData()
        }
    }

    private var loadingState: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            ProgressView()
                .controlSize(.large)
            Text("Loading health data...")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyState: some View {
        VStack(spacing: MacSpacing.xl) {
            Spacer()

            Image(systemName: "heart.text.clipboard")
                .font(.system(size: 48))
                .foregroundStyle(MacColors.textFaint)

            VStack(spacing: MacSpacing.sm) {
                Text("No health data synced yet")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)

                Text("Sync from your iPhone to see metrics here.")
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textSecondary)

                Text("Open Hestia on iOS > Settings > Integrations > Health")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)
            }
            .multilineTextAlignment(.center)

            Button {
                Task { await viewModel.loadData() }
            } label: {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 14))
                    Text("Check Again")
                        .font(MacTypography.labelMedium)
                }
                .foregroundStyle(MacColors.buttonTextDark)
                .padding(.horizontal, MacSpacing.xl)
                .padding(.vertical, MacSpacing.md)
                .background(MacColors.amberAccent)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
            }
            .buttonStyle(.hestia)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
