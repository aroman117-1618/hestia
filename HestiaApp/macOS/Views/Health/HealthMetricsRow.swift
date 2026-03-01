import SwiftUI
import HestiaShared

/// Three metric cards: Heart, Sleep, Body.
struct HealthMetricsRow: View {
    @ObservedObject var viewModel: MacHealthViewModel

    var body: some View {
        GeometryReader { geo in
            let isNarrow = geo.size.width < 600

            if isNarrow {
                // Stack vertically when narrow
                VStack(spacing: MacSpacing.lg) {
                    heartCard
                    sleepCard
                    bodyCard
                }
            } else {
                HStack(spacing: MacSpacing.lg) {
                    heartCard
                    sleepCard
                    bodyCard
                }
            }
        }
    }

    // MARK: - Heart Card

    private var heartCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "heart.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(Color(hex: "FF6467"))
                Text("Heart")
                    .font(MacTypography.cardTitle)
                    .foregroundStyle(.white)
            }

            if viewModel.restingHR > 0 {
                // Resting HR
                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    Text("Resting Heart Rate")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)

                    HStack(alignment: .firstTextBaseline, spacing: 4) {
                        Text("\(viewModel.restingHR)")
                            .font(.system(size: 36, weight: .medium))
                            .foregroundStyle(.white)
                        Text("bpm")
                            .font(MacTypography.label)
                            .foregroundStyle(MacColors.textSecondary)
                    }
                }

                MacColors.subtleBorder.frame(height: 1)

                // HRV
                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    Text("Heart Rate Variability")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)

                    HStack(alignment: .firstTextBaseline, spacing: 4) {
                        Text(String(format: "%.0f", viewModel.hrv))
                            .font(.system(size: 24, weight: .medium))
                            .foregroundStyle(.white)
                        Text("ms")
                            .font(MacTypography.label)
                            .foregroundStyle(MacColors.textSecondary)
                    }
                }

                // Status badge
                statusBadge(viewModel.restingHR < 80 ? "Normal" : "Elevated", isGood: viewModel.restingHR < 80)
            } else {
                noDataPlaceholder
            }
        }
        .healthCard()
    }

    // MARK: - Sleep Card

    private var sleepCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "moon.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(Color(hex: "8B5CF6"))
                Text("Sleep")
                    .font(MacTypography.cardTitle)
                    .foregroundStyle(.white)
            }

            if viewModel.sleepMinutes > 0 {
                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    Text("Duration")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)

                    Text(viewModel.sleepDisplay)
                        .font(.system(size: 36, weight: .medium))
                        .foregroundStyle(.white)
                }

                // Sleep trend sparkline
                if !viewModel.sleepTrend.isEmpty {
                    MacColors.subtleBorder.frame(height: 1)

                    VStack(alignment: .leading, spacing: MacSpacing.xs) {
                        Text("7-Day Trend")
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textSecondary)

                        SparklineChart(
                            dataPoints: viewModel.sleepTrend,
                            lineColor: Color(hex: "8B5CF6")
                        )
                        .frame(height: 40)
                    }
                }

                let hours = Double(viewModel.sleepMinutes) / 60.0
                statusBadge(hours >= 7 ? "Good" : "Below target", isGood: hours >= 7)
            } else {
                noDataPlaceholder
            }
        }
        .healthCard()
    }

    // MARK: - Body Card

    private var bodyCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "figure.arms.open")
                    .font(.system(size: 14))
                    .foregroundStyle(MacColors.amberAccent)
                Text("Body")
                    .font(MacTypography.cardTitle)
                    .foregroundStyle(.white)
            }

            if viewModel.weight > 0 {
                // Weight
                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    Text("Weight")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)

                    HStack(alignment: .firstTextBaseline, spacing: 4) {
                        Text(String(format: "%.1f", viewModel.weight))
                            .font(.system(size: 36, weight: .medium))
                            .foregroundStyle(.white)
                        Text("kg")
                            .font(MacTypography.label)
                            .foregroundStyle(MacColors.textSecondary)
                    }
                }

                // BMI
                if viewModel.bmi > 0 {
                    MacColors.subtleBorder.frame(height: 1)

                    VStack(alignment: .leading, spacing: MacSpacing.xs) {
                        Text("BMI")
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textSecondary)

                        HStack(alignment: .firstTextBaseline, spacing: 4) {
                            Text(String(format: "%.1f", viewModel.bmi))
                                .font(.system(size: 24, weight: .medium))
                                .foregroundStyle(.white)
                        }
                    }

                    GradientProgressBar(
                        value: min(max((viewModel.bmi - 15) / 25.0, 0), 1.0),
                        height: 5,
                        indicatorHeight: 9
                    )

                    HStack {
                        Text("Underweight").font(MacTypography.micro).foregroundStyle(MacColors.textFaint)
                        Spacer()
                        Text("Normal").font(MacTypography.micro).foregroundStyle(MacColors.textFaint)
                        Spacer()
                        Text("Overweight").font(MacTypography.micro).foregroundStyle(MacColors.textFaint)
                    }
                }
            } else {
                noDataPlaceholder
            }
        }
        .healthCard()
    }

    // MARK: - Helpers

    private func statusBadge(_ text: String, isGood: Bool) -> some View {
        HStack(spacing: MacSpacing.xs) {
            Circle()
                .fill(isGood ? MacColors.healthGreen : MacColors.healthAmber)
                .frame(width: 6, height: 6)
            Text(text)
                .font(MacTypography.metadata)
                .foregroundStyle(isGood ? MacColors.healthGreen : MacColors.healthAmber)
        }
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, 2)
        .background((isGood ? MacColors.healthGreenBg : MacColors.healthAmberBg))
        .clipShape(Capsule())
    }

    private var noDataPlaceholder: some View {
        VStack(spacing: MacSpacing.sm) {
            Text("--")
                .font(.system(size: 36, weight: .medium))
                .foregroundStyle(MacColors.textFaint)
            Text("No data synced")
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textFaint)
        }
        .frame(maxWidth: .infinity, minHeight: 80)
    }
}

// MARK: - Sparkline Chart (updated with configurable color)

struct SparklineChart: View {
    let dataPoints: [CGFloat]
    var lineColor: Color = MacColors.amberAccent

    var body: some View {
        GeometryReader { geo in
            if dataPoints.count >= 2, let maxVal = dataPoints.max(), maxVal > 0 {
                let normalized = dataPoints.map { $0 / maxVal }

                Path { path in
                    let stepX = geo.size.width / CGFloat(normalized.count - 1)
                    for (i, value) in normalized.enumerated() {
                        let x = CGFloat(i) * stepX
                        let y = geo.size.height * (1 - value)
                        if i == 0 { path.move(to: CGPoint(x: x, y: y)) }
                        else { path.addLine(to: CGPoint(x: x, y: y)) }
                    }
                }
                .stroke(lineColor, lineWidth: 1.5)
            }
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
                RoundedRectangle(cornerRadius: height / 2)
                    .fill(
                        LinearGradient(
                            colors: [MacColors.healthGreen, MacColors.healthAmber, MacColors.healthRed],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .frame(height: height)

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
