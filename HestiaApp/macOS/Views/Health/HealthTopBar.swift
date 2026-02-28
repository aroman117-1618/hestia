import SwiftUI
import HestiaShared

struct HealthTopBar: View {
    @ObservedObject var viewModel: MacHealthViewModel

    var body: some View {
        HStack {
            // Title
            Text("Health")
                .font(MacTypography.pageTitle)
                .foregroundStyle(.white)
                .tracking(0.45)

            Spacer()

            // Age pills
            HStack(spacing: MacSpacing.md) {
                agePill(
                    icon: "dna",
                    label: "Biological age",
                    age: viewModel.biologicalAge,
                    unit: "yrs"
                )

                Rectangle()
                    .fill(Color(red: 254/255, green: 154/255, blue: 0).opacity(0.2))
                    .frame(width: 1, height: 20)

                agePill(
                    icon: nil,
                    label: "Chronological age",
                    age: viewModel.chronologicalAge,
                    unit: "yrs"
                )
            }
            .padding(.horizontal, MacSpacing.lg)
            .padding(.vertical, MacSpacing.sm)
            .background(
                LinearGradient(
                    colors: [
                        Color(red: 254/255, green: 154/255, blue: 0).opacity(0.15),
                        Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.4)
                    ],
                    startPoint: .leading,
                    endPoint: .trailing
                )
            )
            .clipShape(Capsule())
            .overlay {
                Capsule().strokeBorder(Color(red: 254/255, green: 154/255, blue: 0).opacity(0.2), lineWidth: 1)
            }

            Spacer()

            // Warning message
            warningBadge
        }
        .padding(.horizontal, MacSpacing.xxl)
        .frame(height: 52)
        .background(
            LinearGradient(
                colors: [
                    Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.6),
                    Color(red: 254/255, green: 154/255, blue: 0).opacity(0.08),
                    Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.6)
                ],
                startPoint: .leading,
                endPoint: .trailing
            )
        )
        .overlay(alignment: .bottom) {
            MacColors.cardBorderStrong.frame(height: 1)
        }
    }

    private func agePill(icon: String?, label: String, age: Int, unit: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            if let icon = icon {
                Image(systemName: icon)
                    .font(.system(size: 14))
                    .foregroundStyle(MacColors.amberAccent)
            }
            Text(label + " ")
                .font(MacTypography.label)
                .foregroundStyle(.white)
            +
            Text("\(age)")
                .font(.system(size: 20))
                .foregroundStyle(MacColors.healthGold)
            +
            Text(" " + unit)
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.healthAmber.opacity(0.5))
        }
    }

    private var warningBadge: some View {
        HStack(spacing: MacSpacing.xs) {
            Text("Your body is aging ")
                .font(MacTypography.smallBody)
                .foregroundStyle(MacColors.healthRed)
            +
            Text("5 years faster ")
                .font(.system(size: 12, weight: .bold))
                .foregroundStyle(.white)
            +
            Text("than your chronological age")
                .font(MacTypography.smallBody)
                .foregroundStyle(MacColors.healthRed.opacity(0.7))
        }
        .padding(.horizontal, MacSpacing.md)
        .frame(height: 32)
        .background(MacColors.healthRedBg)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                .strokeBorder(MacColors.healthRedBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
    }
}
