import SwiftUI
import HestiaShared

struct HealthMetricsRow: View {
    @ObservedObject var viewModel: MacHealthViewModel

    var body: some View {
        HStack(spacing: MacSpacing.lg) {
            methylationCard
            immunityCard
            inflammationCard
        }
    }

    // MARK: - Methylation Risk Score

    private var methylationCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            HStack {
                Text("Methylation risk score")
                    .font(MacTypography.cardTitle)
                    .foregroundStyle(.white)
                Spacer()
                Button {} label: {
                    HStack(spacing: MacSpacing.xs) {
                        Text("View report")
                            .font(MacTypography.smallMedium)
                            .foregroundStyle(Color(red: 255/255, green: 185/255, blue: 0).opacity(0.5))
                        Image(systemName: "chevron.right")
                            .font(.system(size: 12))
                            .foregroundStyle(Color(red: 255/255, green: 185/255, blue: 0).opacity(0.5))
                    }
                }
                .buttonStyle(.plain)
            }

            Text("A methylation score of 0.76 equals a biological age of 47, indicating accelerated aging.")
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.healthDimText)

            // Score display
            HStack(spacing: MacSpacing.md) {
                Text("0.76")
                    .font(.system(size: 28))
                    .foregroundStyle(.white)

                VStack(alignment: .leading) {
                    Text("(Equal")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.healthGoldText)
                    Text("to 47)")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.healthGoldText)
                }

                Text("/")
                    .font(MacTypography.label)
                    .foregroundStyle(Color(red: 255/255, green: 185/255, blue: 0).opacity(0.2))

                Text("42")
                    .font(.system(size: 20))
                    .foregroundStyle(.white)

                VStack(alignment: .leading) {
                    Text("Chronological")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.healthGoldText)
                }

                HStack(spacing: MacSpacing.xs) {
                    Circle().fill(MacColors.healthAmber).frame(width: 6, height: 6)
                    Text("Moderate")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.healthAmber)
                }
            }

            // Progress bar
            GradientProgressBar(value: 0.4, height: 6, indicatorHeight: 12)

            // Labels
            HStack {
                Text("Low").font(MacTypography.micro).foregroundStyle(Color(red: 255/255, green: 185/255, blue: 0).opacity(0.3))
                Spacer()
                Text("Medium").font(MacTypography.micro).foregroundStyle(Color(red: 255/255, green: 185/255, blue: 0).opacity(0.3))
                Spacer()
                Text("High").font(MacTypography.micro).foregroundStyle(Color(red: 255/255, green: 185/255, blue: 0).opacity(0.3))
            }
        }
        .healthCard()
    }

    // MARK: - Immunity

    private var immunityCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            Text("Immunity")
                .font(MacTypography.cardTitle)
                .foregroundStyle(.white)

            HStack(alignment: .top, spacing: MacSpacing.xxl) {
                // Left: total T cells
                VStack(alignment: .leading) {
                    Text("Your %,\nT Cells (Total)")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.healthAmberText)
                    HStack(alignment: .firstTextBaseline, spacing: 0) {
                        Text("60-80")
                            .font(.system(size: 28))
                            .foregroundStyle(.white)
                        Text("%")
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.healthGoldText)
                    }
                }

                // Right: cell counts
                VStack(spacing: MacSpacing.sm) {
                    ForEach(viewModel.immunityValues, id: \.label) { item in
                        HStack {
                            Text(item.label)
                                .font(MacTypography.caption)
                                .foregroundStyle(MacColors.healthLabelText)
                                .lineLimit(1)
                            Spacer()
                            HStack(alignment: .firstTextBaseline, spacing: 0) {
                                Text(item.range)
                                    .font(MacTypography.smallBody)
                                    .foregroundStyle(.white)
                                Text(" %")
                                    .font(MacTypography.micro)
                                    .foregroundStyle(MacColors.healthAmberText)
                            }
                        }
                    }
                }
            }

            MacColors.subtleBorder.frame(height: 1)

            // Ratios
            VStack(spacing: MacSpacing.sm) {
                ratioRow(label: "CD4T/CD8T Cell Ratio", status: "Suboptimal", value: "1.4", isNormal: false)
                ratioRow(label: "Lymphocyte/Monocyte", status: "Normal", value: "3.7", isNormal: true)
            }
        }
        .healthCard()
    }

    private func ratioRow(label: String, status: String, value: String, isNormal: Bool) -> some View {
        HStack {
            Image(systemName: "info.circle")
                .font(.system(size: 10))
                .foregroundStyle(MacColors.healthAmberText)
            Text(label)
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.healthLabelText)
            Spacer()
            Text(status)
                .font(MacTypography.metadata)
                .foregroundStyle(isNormal ? MacColors.healthGreen : MacColors.healthAmber)
            Text(value)
                .font(MacTypography.label)
                .foregroundStyle(.white)
            Circle()
                .fill(isNormal ? MacColors.healthGreen : MacColors.healthAmber)
                .frame(width: 5, height: 5)
        }
    }

    // MARK: - Inflammation

    private var inflammationCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            Text("Inflammation")
                .font(MacTypography.cardTitle)
                .foregroundStyle(.white)

            HStack(spacing: MacSpacing.xs) {
                Text("DNAm CRP")
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.healthLabelText)
                Text("(DNA Methylation C-Reactive Protein)")
                    .font(MacTypography.metadata)
                    .foregroundStyle(Color(red: 255/255, green: 185/255, blue: 0).opacity(0.3))
            }

            // Score + percentile + progress bar
            HStack(spacing: MacSpacing.xxl) {
                VStack(alignment: .leading) {
                    Text("3.2")
                        .font(.system(size: 22))
                        .foregroundStyle(.white)
                    Text("mg/L")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.healthAmberText)
                }

                VStack(alignment: .leading) {
                    Text("75")
                        .font(.system(size: 22))
                        .foregroundStyle(.white)
                    Text("th")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.healthAmberText)
                }

                GradientProgressBar(value: 0.75, height: 5, indicatorHeight: 9)
                    .frame(width: 170)
            }

            Text("This means the score is higher than 75% of the reference population, indicating ")
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.healthDimText)
            +
            Text("above-average chronic inflammation")
                .font(.system(size: 10, weight: .bold))
                .foregroundStyle(.white)

            // Change over time
            HStack(spacing: MacSpacing.sm) {
                Text("Change Over Time")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.healthAmberText)
                Text("2.5")
                    .font(.system(size: 15))
                    .foregroundStyle(.white)
                Text("mg/L")
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.healthAmberText)
                Image(systemName: "arrow.up.right")
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.healthRed)
                Text("14.2%")
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.healthRed)
            }
            .padding(MacSpacing.md)
            .background(MacColors.innerPillBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
            .overlay {
                RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                    .strokeBorder(MacColors.subtleBorder, lineWidth: 1)
            }

            // Bullet points
            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                bulletPoint("Suggests an increased risk of cardiovascular disease and metabolic syndrome.")
                bulletPoint("Suggests an increased risk of cardiovascular disease and metabolic syndrome.")
                bulletPoint("Decreased vaccine efficacy.")
            }
        }
        .healthCard()
    }

    private func bulletPoint(_ text: String) -> some View {
        HStack(alignment: .top, spacing: MacSpacing.sm) {
            Image(systemName: "chevron.right")
                .font(.system(size: 10))
                .foregroundStyle(MacColors.healthAmberText)
                .padding(.top, 2)
            Text(text)
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.healthLabelText)
        }
    }
}

// MARK: - Gradient Progress Bar

struct GradientProgressBar: View {
    let value: Double
    let height: CGFloat
    let indicatorHeight: CGFloat

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                // Track
                RoundedRectangle(cornerRadius: height / 2)
                    .fill(
                        LinearGradient(
                            colors: [MacColors.healthGreen, MacColors.healthAmber, MacColors.healthRed],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(height: height)

                // Indicator
                Circle()
                    .fill(.white)
                    .frame(width: indicatorHeight, height: indicatorHeight)
                    .shadow(color: .white.opacity(0.5), radius: height == 6 ? 6 : 4)
                    .offset(x: geo.size.width * value - indicatorHeight / 2)
            }
        }
        .frame(height: indicatorHeight)
    }
}

// MARK: - Health Card Modifier

extension View {
    func healthCard() -> some View {
        self
            .padding(MacSpacing.xl)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                LinearGradient(
                    colors: [
                        Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.3),
                        Color(red: 12/255, green: 10/255, blue: 9/255).opacity(0.2)
                    ],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            )
            .overlay {
                RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                    .strokeBorder(MacColors.cardBorder, lineWidth: 1)
            }
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }
}
