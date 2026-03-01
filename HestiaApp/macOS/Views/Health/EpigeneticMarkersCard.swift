import SwiftUI
import HestiaShared

/// Coaching status card — shows coaching preferences state and sync info.
struct CoachingCard: View {
    @ObservedObject var viewModel: MacHealthViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Header
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "brain.head.profile")
                    .font(.system(size: 16))
                    .foregroundStyle(MacColors.amberAccent)
                Text("Health Coaching")
                    .font(MacTypography.cardTitle)
                    .foregroundStyle(.white)
            }

            if viewModel.hasData {
                // Status summary
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 14))
                        .foregroundStyle(MacColors.healthGreen)
                    Text("HealthKit data synced")
                        .font(MacTypography.smallBody)
                        .foregroundStyle(.white)
                }
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, MacSpacing.sm)
                .background(MacColors.healthGreenBg)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
                .overlay {
                    RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                        .strokeBorder(MacColors.healthGreen.opacity(0.15), lineWidth: 1)
                }

                // Quick metrics grid
                LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: MacSpacing.md) {
                    coachingMetric(label: "Steps Today", value: "\(viewModel.steps)", icon: "figure.walk")
                    coachingMetric(label: "Exercise", value: "\(viewModel.exerciseMinutes) min", icon: "flame.fill")
                    coachingMetric(label: "Sleep", value: viewModel.sleepDisplay, icon: "moon.fill")
                    coachingMetric(label: "Resting HR", value: viewModel.restingHR > 0 ? "\(viewModel.restingHR) bpm" : "--", icon: "heart.fill")
                }

                // Last sync info
                if let syncDate = viewModel.lastSyncDate {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "clock")
                            .font(.system(size: 11))
                            .foregroundStyle(MacColors.textFaint)
                        Text("Data from \(syncDate)")
                            .font(MacTypography.metadata)
                            .foregroundStyle(MacColors.textFaint)
                    }
                }
            } else {
                // No data state
                VStack(spacing: MacSpacing.md) {
                    Image(systemName: "iphone.and.arrow.forward")
                        .font(.system(size: 24))
                        .foregroundStyle(MacColors.textFaint)

                    Text("Sync health data from your iPhone to enable coaching insights.")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                        .multilineTextAlignment(.center)

                    Text("Open the Hestia iOS app and enable HealthKit sync in Settings > Integrations.")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)
                        .multilineTextAlignment(.center)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, MacSpacing.lg)
            }
        }
        .healthCard()
    }

    private func coachingMetric(label: String, value: String, icon: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .foregroundStyle(MacColors.textSecondary)
                .frame(width: 16)

            VStack(alignment: .leading, spacing: 1) {
                Text(label)
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.textFaint)
                Text(value)
                    .font(MacTypography.label)
                    .foregroundStyle(.white)
            }

            Spacer()
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.innerPillBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                .strokeBorder(MacColors.subtleBorder, lineWidth: 1)
        }
    }
}
