import SwiftUI
import HestiaShared

/// Activity overview card — steps, distance, exercise, calories with gauges.
struct ActivityCard: View {
    @ObservedObject var viewModel: MacHealthViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Header
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "figure.walk")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.healthGreen)
                Text("Activity")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)
            }

            // Three columns
            HStack(alignment: .top, spacing: MacSpacing.xxl) {
                // Column 1: Steps gauge
                stepsColumn
                    .frame(maxWidth: .infinity)

                // Column 2: Exercise ring
                exerciseColumn
                    .frame(maxWidth: .infinity)

                // Column 3: Step sparkline
                sparklineColumn
                    .frame(maxWidth: .infinity)
            }
        }
        .padding(MacSpacing.xxl)
        .background(
            LinearGradient(
                colors: [
                    Color(red: 0/255, green: 50/255, blue: 35/255).opacity(0.35),
                    Color(red: 12/255, green: 10/255, blue: 9/255).opacity(0.35)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.healthGreen.opacity(0.1), lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    // MARK: - Steps Gauge

    private var stepsColumn: some View {
        VStack(spacing: MacSpacing.sm) {
            ZStack {
                GaugeArc(
                    value: viewModel.stepProgress,
                    colors: [MacColors.healthGreen, MacColors.healthGreen]
                )
                .frame(width: 200, height: 120)

                VStack(spacing: 2) {
                    Text(formatSteps(viewModel.steps))
                        .font(MacTypography.heroNumber)
                        .foregroundStyle(MacColors.textPrimary)
                    Text("steps")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.healthGreen.opacity(0.6))
                }
                .offset(y: 15)
            }

            if viewModel.distance > 0 {
                Text(String(format: "%.1f km", viewModel.distance))
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
            }
        }
    }

    // MARK: - Exercise Column

    private var exerciseColumn: some View {
        VStack(spacing: MacSpacing.md) {
            // Exercise ring
            ZStack {
                Circle()
                    .stroke(MacColors.healthGreen.opacity(0.15), lineWidth: 10)
                Circle()
                    .trim(from: 0, to: viewModel.exerciseProgress)
                    .stroke(
                        LinearGradient(colors: [MacColors.healthGreen, MacColors.healthLime], startPoint: .leading, endPoint: .trailing),
                        style: StrokeStyle(lineWidth: 10, lineCap: .round)
                    )
                    .rotationEffect(.degrees(-90))

                VStack(spacing: 2) {
                    Text("\(viewModel.exerciseMinutes)")
                        .font(MacTypography.mediumValue)
                        .foregroundStyle(MacColors.textPrimary)
                    Text("min")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.healthGreen.opacity(0.6))
                }
            }
            .frame(width: 110, height: 110)

            Text("Exercise")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)
        }
    }

    // MARK: - Sparkline Column

    private var sparklineColumn: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            Text("7-Day Steps")
                .font(MacTypography.cardSubtitle)
                .foregroundStyle(MacColors.textPrimary)

            if viewModel.stepTrend.isEmpty {
                Text("No trend data")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)
                    .frame(height: 60)
            } else {
                SparklineChart(
                    dataPoints: viewModel.stepTrend,
                    lineColor: MacColors.healthGreen
                )
                .frame(height: 60)
            }

            // Calories pill
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "flame.fill")
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.calorieRed)
                Text("\(viewModel.calories)")
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.textPrimary)
                Text("kcal")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
            }
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, MacSpacing.sm)
            .background(MacColors.innerPillBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
            .overlay {
                RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                    .strokeBorder(MacColors.subtleBorder, lineWidth: 1)
            }
        }
    }

    private func formatSteps(_ n: Int) -> String {
        if n >= 1000 {
            return String(format: "%.1fk", Double(n) / 1000.0)
        }
        return "\(n)"
    }
}

// MARK: - Radar Chart (preserved for future use)

struct RadarChart: View {
    let values: [Double]
    let labels: [String]
    private let gridLevels = 4

    var body: some View {
        GeometryReader { geo in
            let center = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
            let radius = min(geo.size.width, geo.size.height) / 2 - 20

            ZStack {
                ForEach(1...gridLevels, id: \.self) { level in
                    polygonPath(sides: values.count, radius: radius * Double(level) / Double(gridLevels), center: center)
                        .stroke(MacColors.healthAmberText.opacity(0.2), lineWidth: 0.5)
                }

                dataPolygon(radius: radius, center: center)
                    .fill(MacColors.amberAccent.opacity(0.2))
                dataPolygon(radius: radius, center: center)
                    .stroke(MacColors.amberAccent.opacity(0.6), lineWidth: 1.5)

                ForEach(labels.indices, id: \.self) { i in
                    let angle = angleFor(index: i) - .pi / 2
                    let labelRadius = radius + 14
                    let x = center.x + cos(angle) * labelRadius
                    let y = center.y + sin(angle) * labelRadius

                    Text(labels[i])
                        .font(MacTypography.micro)
                        .foregroundStyle(Color(red: 254/255, green: 230/255, blue: 133/255).opacity(0.5))
                        .position(x: x, y: y)
                }
            }
        }
    }

    private func polygonPath(sides: Int, radius: Double, center: CGPoint) -> Path {
        Path { path in
            for i in 0...sides {
                let angle = angleFor(index: i % sides) - .pi / 2
                let point = CGPoint(
                    x: center.x + cos(angle) * radius,
                    y: center.y + sin(angle) * radius
                )
                if i == 0 { path.move(to: point) }
                else { path.addLine(to: point) }
            }
        }
    }

    private func dataPolygon(radius: Double, center: CGPoint) -> Path {
        Path { path in
            for i in 0...values.count {
                let idx = i % values.count
                let angle = angleFor(index: idx) - .pi / 2
                let r = radius * values[idx]
                let point = CGPoint(
                    x: center.x + cos(angle) * r,
                    y: center.y + sin(angle) * r
                )
                if i == 0 { path.move(to: point) }
                else { path.addLine(to: point) }
            }
        }
    }

    private func angleFor(index: Int) -> Double {
        2 * .pi * Double(index) / Double(values.count)
    }
}

// MARK: - Gauge Arc (updated with configurable colors)

struct GaugeArc: View {
    let value: Double
    var colors: [Color] = [MacColors.healthGreen, MacColors.healthAmber, MacColors.healthRed]

    var body: some View {
        GeometryReader { geo in
            let center = CGPoint(x: geo.size.width / 2, y: geo.size.height)
            let radius = min(geo.size.width / 2, geo.size.height) - 10

            ZStack {
                arcPath(center: center, radius: radius, startAngle: .degrees(180), endAngle: .degrees(360))
                    .stroke(
                        LinearGradient(colors: colors, startPoint: .leading, endPoint: .trailing),
                        style: StrokeStyle(lineWidth: 8, lineCap: .round)
                    )
                    .opacity(0.3)

                arcPath(center: center, radius: radius, startAngle: .degrees(180), endAngle: .degrees(180 + 180 * value))
                    .stroke(
                        LinearGradient(colors: colors, startPoint: .leading, endPoint: .trailing),
                        style: StrokeStyle(lineWidth: 8, lineCap: .round)
                    )
            }
        }
    }

    private func arcPath(center: CGPoint, radius: CGFloat, startAngle: Angle, endAngle: Angle) -> Path {
        Path { path in
            path.addArc(center: center, radius: radius, startAngle: startAngle, endAngle: endAngle, clockwise: false)
        }
    }
}
