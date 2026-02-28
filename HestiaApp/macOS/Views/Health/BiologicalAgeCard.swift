import SwiftUI
import HestiaShared

struct BiologicalAgeCard: View {
    @ObservedObject var viewModel: MacHealthViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Breadcrumb
            HStack(spacing: MacSpacing.md) {
                Button {} label: {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 12))
                        Text("Age Report")
                            .font(MacTypography.labelMedium)
                    }
                    .foregroundStyle(Color(red: 254/255, green: 230/255, blue: 133/255).opacity(0.6))
                }
                .buttonStyle(.plain)

                Text("Suboptimal")
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.healthAmber)
                    .padding(.horizontal, MacSpacing.sm)
                    .background(MacColors.healthAmberBg)
                    .clipShape(Capsule())
                    .overlay { Capsule().strokeBorder(MacColors.healthAmberBorder, lineWidth: 1) }
            }

            // Three columns
            HStack(alignment: .top, spacing: MacSpacing.xxl) {
                // Column 1: Radar chart
                radarChartColumn
                    .frame(width: 220)

                // Column 2: Gauge dial
                gaugeColumn
                    .frame(maxWidth: .infinity)

                // Column 3: Telomere card
                telomereCard
                    .frame(width: 220)
            }
        }
        .padding(MacSpacing.xxl)
        .background(
            LinearGradient(
                colors: [
                    Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.45),
                    Color(red: 12/255, green: 10/255, blue: 9/255).opacity(0.35)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(Color(red: 254/255, green: 154/255, blue: 0).opacity(0.12), lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    // MARK: - Radar Chart Column

    private var radarChartColumn: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("Biological Age")
                .font(MacTypography.sectionTitle)
                .foregroundStyle(.white)

            Text("Measures how your body's aging, reveals your biological age")
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.healthAmberText)
                .lineLimit(3)

            RadarChart(
                values: viewModel.radarValues,
                labels: viewModel.radarLabels
            )
            .frame(width: 220, height: 200)
        }
    }

    // MARK: - Gauge Column

    private var gaugeColumn: some View {
        VStack(spacing: MacSpacing.sm) {
            ZStack {
                // Semicircular gauge
                GaugeArc(value: Double(viewModel.percentile) / 100.0)
                    .frame(width: 280, height: 160)

                // Center text
                VStack(spacing: 2) {
                    HStack(alignment: .firstTextBaseline, spacing: 0) {
                        Text("\(viewModel.percentile)")
                            .font(MacTypography.heroNumber)
                            .foregroundStyle(.white)
                        Text("th")
                            .font(.system(size: 8))
                            .foregroundStyle(Color(red: 254/255, green: 230/255, blue: 133/255).opacity(0.6))
                            .baselineOffset(20)
                    }
                    Text("Percentile")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.healthGoldText)
                    Text("Your risk of disease")
                        .font(MacTypography.body)
                        .foregroundStyle(Color(red: 255/255, green: 185/255, blue: 0).opacity(0.7))
                }
                .offset(y: 20)
            }

            // Risk values
            HStack(spacing: MacSpacing.xxl) {
                ForEach(viewModel.riskValues, id: \.label) { risk in
                    VStack(spacing: 2) {
                        HStack(alignment: .firstTextBaseline, spacing: 0) {
                            Text(risk.value)
                                .font(.system(size: 15))
                                .foregroundStyle(.white)
                            Text("%")
                                .font(MacTypography.micro)
                                .foregroundStyle(MacColors.healthGoldText)
                        }
                        Text(risk.label)
                            .font(MacTypography.micro)
                            .foregroundStyle(MacColors.healthAmberText)
                            .multilineTextAlignment(.center)
                    }
                }
            }
        }
    }

    // MARK: - Telomere Card

    private var telomereCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            // Header
            HStack {
                HStack(alignment: .firstTextBaseline, spacing: 2) {
                    Text("5.2")
                        .font(MacTypography.largeValue)
                        .foregroundStyle(.white)
                    Text("Kb")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.healthGoldText)
                }
                Spacer()
                // Medium badge
                HStack(spacing: MacSpacing.xs) {
                    Circle()
                        .fill(MacColors.healthAmber)
                        .frame(width: 5, height: 5)
                    Text("Medium")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.healthAmber)
                }
                .padding(.horizontal, MacSpacing.sm)
                .background(MacColors.healthAmberBg)
                .clipShape(Capsule())
                .overlay { Capsule().strokeBorder(MacColors.healthAmberBorder, lineWidth: 1) }
            }

            Text("Telomere length")
                .font(MacTypography.cardSubtitle)
                .foregroundStyle(.white)

            Text("Your telomere length matches that of a typical 50-year-old")
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.healthAmberText)

            // Sparkline
            SparklineChart()
                .frame(height: 55)

            // X-axis labels
            HStack {
                ForEach(["0", "10", "20", "30", "40", "50"], id: \.self) { label in
                    Text(label)
                        .font(MacTypography.axis)
                        .foregroundStyle(Color(red: 255/255, green: 185/255, blue: 0).opacity(0.25))
                    if label != "50" { Spacer() }
                }
            }

            Text("Age (years)")
                .font(MacTypography.axis)
                .foregroundStyle(Color(red: 255/255, green: 185/255, blue: 0).opacity(0.25))
                .frame(maxWidth: .infinity, alignment: .center)

            // View full report
            Button {} label: {
                HStack(spacing: MacSpacing.xs) {
                    Text("View full report")
                        .font(MacTypography.captionMedium)
                    Image(systemName: "arrow.up.right")
                        .font(.system(size: 10))
                }
                .foregroundStyle(Color(red: 254/255, green: 230/255, blue: 133/255).opacity(0.7))
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, MacSpacing.sm)
                .overlay {
                    RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                        .strokeBorder(MacColors.cardBorderStrong, lineWidth: 1)
                }
            }
            .buttonStyle(.plain)
        }
        .padding(MacSpacing.lg)
        .background(
            LinearGradient(
                colors: [
                    Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.5),
                    Color(red: 12/255, green: 10/255, blue: 9/255).opacity(0.3)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorderStrong, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }
}

// MARK: - Radar Chart (SwiftUI Path)

struct RadarChart: View {
    let values: [Double]
    let labels: [String]
    private let gridLevels = 4

    var body: some View {
        GeometryReader { geo in
            let center = CGPoint(x: geo.size.width / 2, y: geo.size.height / 2)
            let radius = min(geo.size.width, geo.size.height) / 2 - 20

            ZStack {
                // Grid rings
                ForEach(1...gridLevels, id: \.self) { level in
                    polygonPath(sides: values.count, radius: radius * Double(level) / Double(gridLevels), center: center)
                        .stroke(MacColors.healthAmberText.opacity(0.2), lineWidth: 0.5)
                }

                // Data polygon
                dataPolygon(radius: radius, center: center)
                    .fill(MacColors.amberAccent.opacity(0.2))
                dataPolygon(radius: radius, center: center)
                    .stroke(MacColors.amberAccent.opacity(0.6), lineWidth: 1.5)

                // Labels
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

// MARK: - Gauge Arc (SwiftUI Shape)

struct GaugeArc: View {
    let value: Double

    var body: some View {
        GeometryReader { geo in
            let center = CGPoint(x: geo.size.width / 2, y: geo.size.height)
            let radius = min(geo.size.width / 2, geo.size.height) - 10

            ZStack {
                // Track
                arcPath(center: center, radius: radius, startAngle: .degrees(180), endAngle: .degrees(360))
                    .stroke(
                        LinearGradient(
                            colors: [MacColors.healthGreen, MacColors.healthAmber, MacColors.healthRed],
                            startPoint: .leading,
                            endPoint: .trailing
                        ),
                        style: StrokeStyle(lineWidth: 8, lineCap: .round)
                    )
                    .opacity(0.3)

                // Fill
                arcPath(center: center, radius: radius, startAngle: .degrees(180), endAngle: .degrees(180 + 180 * value))
                    .stroke(
                        LinearGradient(
                            colors: [MacColors.healthGreen, MacColors.healthAmber, MacColors.healthRed],
                            startPoint: .leading,
                            endPoint: .trailing
                        ),
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

// MARK: - Sparkline Chart

struct SparklineChart: View {
    // Simulated telomere decline curve
    private let dataPoints: [CGFloat] = [0.95, 0.9, 0.82, 0.73, 0.62, 0.53, 0.47, 0.42, 0.38, 0.35]

    var body: some View {
        GeometryReader { geo in
            Path { path in
                let stepX = geo.size.width / CGFloat(dataPoints.count - 1)
                for (i, value) in dataPoints.enumerated() {
                    let x = CGFloat(i) * stepX
                    let y = geo.size.height * (1 - value)
                    if i == 0 { path.move(to: CGPoint(x: x, y: y)) }
                    else { path.addLine(to: CGPoint(x: x, y: y)) }
                }
            }
            .stroke(MacColors.amberAccent, lineWidth: 1.5)
        }
    }
}
