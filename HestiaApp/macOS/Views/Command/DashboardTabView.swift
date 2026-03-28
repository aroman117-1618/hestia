import SwiftUI
import EventKit

// MARK: - DashboardTabView

struct DashboardTabView: View {
    @StateObject private var viewModel = DashboardTabViewModel()

    var body: some View {
        ScrollView {
            VStack(spacing: MacSpacing.xxl) {
                // Row 1: Health Summary
                healthSection

                // Row 2: Calendar + Tasks
                HStack(alignment: .top, spacing: MacSpacing.lg) {
                    calendarCard
                        .frame(minWidth: 0, maxWidth: .infinity)
                    tasksCard
                        .frame(minWidth: 0, maxWidth: .infinity)
                }

                // Row 3: Trading
                tradingCard
            }
            .padding(MacSpacing.xxl)
        }
        .background(MacColors.windowBackground)
        .task {
            await viewModel.loadData()
        }
    }

    // MARK: - Section Header

    private func sectionHeader(_ title: String, action: String? = nil) -> some View {
        HStack {
            Text(title)
                .font(MacTypography.sectionTitle)
                .foregroundStyle(MacColors.textPrimary)
            Spacer()
            if let action {
                Button(action) {}
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.amberAccent)
                    .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Row 1: Health Summary

    private var healthSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            sectionHeader("Health Summary", action: "View Details")

            HStack(spacing: MacSpacing.lg) {
                healthStatCard(
                    label: "Steps",
                    value: formatHealthValue(viewModel.healthSummary?.double(from: viewModel.healthSummary?.activity ?? [:], key: "steps"), unit: nil, isInt: true),
                    unit: nil,
                    delta: nil,
                    isPositive: nil,
                    sparklineColor: MacColors.healthGreen
                )
                healthStatCard(
                    label: "Sleep",
                    value: formatSleepValue(viewModel.healthSummary?.double(from: viewModel.healthSummary?.sleep ?? [:], key: "duration")),
                    unit: nil,
                    delta: nil,
                    isPositive: nil,
                    sparklineColor: MacColors.sleepPurple
                )
                healthStatCard(
                    label: "Heart Rate",
                    value: formatHealthValue(viewModel.healthSummary?.double(from: viewModel.healthSummary?.heart ?? [:], key: "resting_heart_rate"), unit: nil, isInt: true),
                    unit: "bpm",
                    delta: nil,
                    isPositive: nil,
                    sparklineColor: MacColors.heartRed
                )
                healthStatCard(
                    label: "Calories",
                    value: formatHealthValue(viewModel.healthSummary?.double(from: viewModel.healthSummary?.activity ?? [:], key: "calories"), unit: nil, isInt: true),
                    unit: "kcal",
                    delta: nil,
                    isPositive: nil,
                    sparklineColor: MacColors.amberAccent
                )
            }
        }
    }

    private func healthStatCard(
        label: String,
        value: String,
        unit: String?,
        delta: String?,
        isPositive: Bool?,
        sparklineColor: Color
    ) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text(label)
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)

            HStack(alignment: .firstTextBaseline, spacing: MacSpacing.sm) {
                Text(value)
                    .font(.system(size: 28, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)

                if let unit {
                    Text(unit)
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textSecondary)
                }

                if let delta {
                    deltaBadge(delta, isPositive: isPositive)
                }
            }

            SparklineView(color: sparklineColor)
                .frame(height: 24)
        }
        .padding(MacSpacing.lg)
        .frame(maxWidth: .infinity, minHeight: 100, alignment: .leading)
        .background(MacColors.panelBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .overlay(
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .stroke(MacColors.cardBorder, lineWidth: 1)
        )
    }

    private func deltaBadge(_ text: String, isPositive: Bool?) -> some View {
        Text(text)
            .font(MacTypography.label)
            .fontWeight(.medium)
            .foregroundStyle(deltaColor(isPositive))
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(deltaColor(isPositive).opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 6))
    }

    private func deltaColor(_ isPositive: Bool?) -> Color {
        guard let isPositive else { return MacColors.textSecondary }
        return isPositive ? MacColors.healthGreen : MacColors.healthRed
    }

    // MARK: - Row 2: Calendar Card

    private var calendarCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            Text("CALENDAR")
                .font(MacTypography.sectionLabel)
                .tracking(0.8)
                .textCase(.uppercase)
                .foregroundStyle(MacColors.textInactive)

            // Navigation header
            HStack {
                Button {
                    viewModel.navigateWeek(forward: false)
                } label: {
                    Image(systemName: "chevron.left")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                        .frame(width: 28, height: 28)
                        .background(Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                        .overlay(
                            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                                .stroke(MacColors.cardBorder, lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)

                Text(calendarRangeLabel)
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)

                Button {
                    viewModel.navigateWeek(forward: true)
                } label: {
                    Image(systemName: "chevron.right")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                        .frame(width: 28, height: 28)
                        .background(Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                        .overlay(
                            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                                .stroke(MacColors.cardBorder, lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)

                Spacer()
            }

            // Day headers
            let dayHeaders = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 2), count: 7), spacing: 2) {
                ForEach(dayHeaders, id: \.self) { day in
                    Text(day)
                        .font(MacTypography.metadata)
                        .fontWeight(.semibold)
                        .tracking(0.5)
                        .textCase(.uppercase)
                        .foregroundStyle(MacColors.textFaint)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, MacSpacing.xs)
                }

                // 14 day cells
                ForEach(calendarDays, id: \.self) { date in
                    calendarDayCell(date)
                }
            }

            // Today's events list (capped at 5 to prevent unbounded growth)
            if !viewModel.todayEvents.isEmpty {
                Divider()
                    .background(MacColors.divider)

                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    ForEach(viewModel.todayEvents.prefix(5), id: \.eventIdentifier) { event in
                        eventRow(event)
                    }
                    if viewModel.todayEvents.count > 5 {
                        Text("+\(viewModel.todayEvents.count - 5) more")
                            .font(MacTypography.label)
                            .foregroundStyle(MacColors.textFaint)
                            .padding(.leading, MacSpacing.sm)
                    }
                }
            }
        }
        .padding(MacSpacing.lg)
        .background(MacColors.panelBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .overlay(
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .stroke(MacColors.cardBorder, lineWidth: 1)
        )
    }

    private var calendarRangeLabel: String {
        let range = viewModel.twoWeekRange
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        let start = formatter.string(from: range.start)
        let end = formatter.string(from: range.end)
        let yearFormatter = DateFormatter()
        yearFormatter.dateFormat = ", yyyy"
        let year = yearFormatter.string(from: range.end)
        return "\(start) – \(end)\(year)"
    }

    private var calendarDays: [Date] {
        let calendar = Calendar.current
        let start = viewModel.currentWeekStart
        return (0..<14).compactMap { offset in
            calendar.date(byAdding: .day, value: offset, to: start)
        }
    }

    private func calendarDayCell(_ date: Date) -> some View {
        let calendar = Calendar.current
        let isToday = calendar.isDateInToday(date)
        let dayNumber = calendar.component(.day, from: date)
        let currentMonth = calendar.component(.month, from: Date())
        let cellMonth = calendar.component(.month, from: date)
        let isOtherMonth = cellMonth != currentMonth
        let hasEvent = viewModel.calendarEvents.contains { event in
            guard let eventStart = event.startDate else { return false }
            return calendar.isDate(eventStart, inSameDayAs: date)
        }

        return ZStack {
            if isToday {
                Circle()
                    .fill(MacColors.amberAccent)
                    .frame(width: MacSize.activeDayCircle, height: MacSize.activeDayCircle)
            }

            VStack(spacing: 2) {
                Text("\(dayNumber)")
                    .font(MacTypography.label)
                    .fontWeight(isToday ? .semibold : .regular)
                    .foregroundStyle(
                        isToday ? MacColors.buttonTextDark :
                        isOtherMonth ? MacColors.textFaint :
                        MacColors.textSecondary
                    )

                if hasEvent && !isToday {
                    Circle()
                        .fill(MacColors.statusInfo)
                        .frame(width: MacSize.eventDotSize, height: MacSize.eventDotSize)
                } else {
                    Spacer()
                        .frame(height: MacSize.eventDotSize)
                }
            }
        }
        .frame(maxWidth: .infinity)
        .frame(height: 36)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    private func eventRow(_ event: EKEvent) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Circle()
                .fill(Color(cgColor: event.calendar?.cgColor ?? CGColor(red: 0, green: 0.52, blue: 1, alpha: 1)))
                .frame(width: MacSize.eventDotSize, height: MacSize.eventDotSize)

            if let start = event.startDate {
                Text(eventTimeFormatter.string(from: start))
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
                    .frame(width: 40, alignment: .leading)
            }

            Text(event.title ?? "")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(1)

            Spacer()
        }
        .padding(.vertical, MacSpacing.xs)
    }

    private var eventTimeFormatter: DateFormatter {
        let formatter = DateFormatter()
        formatter.dateFormat = "H:mm"
        return formatter
    }

    // MARK: - Row 2: Tasks Card

    private var tasksCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            Text("TASKS")
                .font(MacTypography.sectionLabel)
                .tracking(0.8)
                .textCase(.uppercase)
                .foregroundStyle(MacColors.textInactive)

            // Count header
            Text("\(viewModel.overdueReminders.count) overdue, \(viewModel.currentReminders.count) current")
                .font(MacTypography.senderLabel)
                .foregroundStyle(MacColors.textPrimary)

            // Overdue section
            VStack(spacing: 2) {
                ForEach(viewModel.overdueReminders, id: \.calendarItemIdentifier) { reminder in
                    taskRow(reminder, isOverdue: true)
                }
            }

            if !viewModel.overdueReminders.isEmpty && !viewModel.currentReminders.isEmpty {
                Divider()
                    .background(MacColors.divider)
            }

            // Current section
            VStack(spacing: 2) {
                ForEach(viewModel.currentReminders, id: \.calendarItemIdentifier) { reminder in
                    taskRow(reminder, isOverdue: false)
                }
            }

            if viewModel.overdueReminders.isEmpty && viewModel.currentReminders.isEmpty {
                VStack(spacing: MacSpacing.sm) {
                    Image(systemName: "checkmark.circle")
                        .font(.system(size: 28))
                        .foregroundStyle(MacColors.textFaint)
                    Text(viewModel.reminders.isEmpty ? "No tasks" : "No dated tasks")
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textFaint)
                }
                .frame(maxWidth: .infinity, alignment: .center)
                .padding(.vertical, MacSpacing.xxl)
            }

            Spacer(minLength: 0)
        }
        .padding(MacSpacing.lg)
        .frame(minHeight: 200)
        .background(MacColors.panelBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .overlay(
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .stroke(MacColors.cardBorder, lineWidth: 1)
        )
    }

    private func taskRow(_ reminder: EKReminder, isOverdue: Bool) -> some View {
        HStack(spacing: MacSpacing.md) {
            // Priority dot
            Circle()
                .fill(taskPriorityColor(reminder.priority))
                .frame(width: 6, height: 6)

            // Checkbox
            RoundedRectangle(cornerRadius: 4)
                .stroke(
                    reminder.isCompleted ? MacColors.amberAccent : MacColors.cardBorderStrong,
                    lineWidth: 1.5
                )
                .fill(reminder.isCompleted ? MacColors.amberAccent : Color.clear)
                .frame(width: 16, height: 16)
                .overlay {
                    if reminder.isCompleted {
                        Image(systemName: "checkmark")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundStyle(MacColors.buttonTextDark)
                    }
                }

            // Title
            Text(reminder.title ?? "")
                .font(MacTypography.senderLabel)
                .foregroundStyle(reminder.isCompleted ? MacColors.textFaint : MacColors.textPrimary)
                .strikethrough(reminder.isCompleted)
                .lineLimit(1)

            Spacer()

            // Due date
            if let dueDate = reminder.dueDateComponents?.date {
                Text(dueDateFormatter.string(from: dueDate))
                    .font(MacTypography.sectionLabel)
                    .foregroundStyle(
                        reminder.isCompleted ? MacColors.textFaint :
                        isOverdue ? MacColors.healthRed :
                        MacColors.textSecondary
                    )
                    .fontWeight(isOverdue ? .medium : .regular)
            }
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    private func taskPriorityColor(_ priority: Int) -> Color {
        // EKReminder priority: 0 = none, 1-4 = high, 5 = medium, 6-9 = low
        switch priority {
        case 1...4: return MacColors.healthRed
        case 5: return MacColors.statusWarning
        case 6...9: return MacColors.healthGreen
        default: return MacColors.textFaint
        }
    }

    private var dueDateFormatter: DateFormatter {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMM d"
        return formatter
    }

    // MARK: - Row 3: Trading Card

    private var tradingCard: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Header row
            HStack {
                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    Text("TRADING")
                        .font(MacTypography.sectionLabel)
                        .tracking(0.8)
                        .textCase(.uppercase)
                        .foregroundStyle(MacColors.textInactive)

                    HStack(spacing: MacSpacing.sm) {
                        // Status dot
                        Circle()
                            .fill(tradingStatusColor)
                            .frame(width: MacSize.statusDotSize, height: MacSize.statusDotSize)
                            .shadow(color: viewModel.activeBotCount > 0 ? MacColors.healthGreen.opacity(0.5) : Color.clear, radius: 3)

                        Text(tradingStatusLabel)
                            .font(MacTypography.labelMedium)
                            .foregroundStyle(tradingStatusColor)

                        Text("Coinbase")
                            .font(MacTypography.label)
                            .foregroundStyle(MacColors.textFaint)
                    }
                }

                Spacer()

                HStack(spacing: MacSpacing.md) {
                    // Lookback toggle
                    lookbackToggle

                    // Kill switch
                    Button {
                        Task { await viewModel.killAllBots() }
                    } label: {
                        Text("KILL ALL")
                            .font(MacTypography.sectionLabel)
                            .tracking(0.5)
                            .foregroundStyle(MacColors.healthRed)
                            .padding(.horizontal, MacSpacing.md)
                            .padding(.vertical, MacSpacing.xs)
                            .background(MacColors.healthRed.opacity(0.08))
                            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                            .overlay(
                                RoundedRectangle(cornerRadius: MacCornerRadius.search)
                                    .stroke(MacColors.healthRed.opacity(0.3), lineWidth: 1)
                            )
                    }
                    .buttonStyle(.plain)
                }
            }

            // Content: P&L chart + Bot breakdown
            HStack(alignment: .top, spacing: MacSpacing.xxl) {
                // Left: P&L
                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    HStack(alignment: .firstTextBaseline, spacing: MacSpacing.sm) {
                        Text(formattedPnL)
                            .font(MacTypography.mediumValue)
                            .foregroundStyle(MacColors.textPrimary)

                        if let summary = viewModel.tradingSummary {
                            Text("\(summary.totalTrades) trades")
                                .font(MacTypography.caption)
                                .foregroundStyle(MacColors.textFaint)
                        }
                    }

                    Text("Portfolio P&L (\(viewModel.lookbackPeriod.displayName))")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textFaint)

                    // Chart placeholder
                    PnLChartPlaceholder(isPositive: (viewModel.tradingSummary?.totalPnl ?? 0) >= 0)
                        .frame(height: 120)
                        .padding(.top, MacSpacing.sm)
                }
                .frame(maxWidth: .infinity)

                // Right: Bot breakdown
                VStack(alignment: .leading, spacing: MacSpacing.md) {
                    Text("Bot Performance")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textFaint)

                    LazyVGrid(columns: [GridItem(.flexible(), spacing: MacSpacing.sm), GridItem(.flexible(), spacing: MacSpacing.sm)], spacing: MacSpacing.sm) {
                        ForEach(viewModel.bots) { bot in
                            botRow(bot)
                        }
                    }

                    if viewModel.bots.isEmpty {
                        Text("No active bots")
                            .font(MacTypography.body)
                            .foregroundStyle(MacColors.textFaint)
                            .frame(maxWidth: .infinity, alignment: .center)
                            .padding(.vertical, MacSpacing.lg)
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
        .padding(MacSpacing.lg)
        .background(MacColors.panelBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .overlay(
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .stroke(MacColors.cardBorder, lineWidth: 1)
        )
    }

    private var lookbackToggle: some View {
        HStack(spacing: 2) {
            ForEach(DashboardTabViewModel.LookbackPeriod.allCases) { period in
                Button {
                    viewModel.lookbackPeriod = period
                } label: {
                    Text(period.displayName)
                        .font(MacTypography.sectionLabel)
                        .foregroundStyle(
                            viewModel.lookbackPeriod == period ? MacColors.amberAccent : MacColors.textInactive
                        )
                        .padding(.horizontal, MacSpacing.md)
                        .padding(.vertical, MacSpacing.xs)
                        .background(
                            viewModel.lookbackPeriod == period ? MacColors.activeTabBackground : Color.clear
                        )
                        .clipShape(RoundedRectangle(cornerRadius: 6))
                }
                .buttonStyle(.plain)
            }
        }
        .padding(2)
        .background(MacColors.chatInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    private var tradingStatusColor: Color {
        guard let summary = viewModel.tradingSummary else { return MacColors.textFaint }
        if summary.killSwitchActive { return MacColors.healthRed }
        if summary.activeBots > 0 { return MacColors.healthGreen }
        return MacColors.statusWarning
    }

    private var tradingStatusLabel: String {
        guard let summary = viewModel.tradingSummary else { return "Loading..." }
        if summary.killSwitchActive { return "Kill Switch Active" }
        let count = summary.activeBots
        return count == 0 ? "No Active Bots" : "\(count) Bot\(count == 1 ? "" : "s") Live"
    }

    private var formattedPnL: String {
        guard let summary = viewModel.tradingSummary else { return "--" }
        let pnl = summary.totalPnl
        let sign = pnl >= 0 ? "+" : "-"
        return "\(sign)$\(String(format: "%.2f", abs(pnl)))"
    }

    private func botRow(_ bot: TradingBotResponse) -> some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text(bot.name)
                    .font(MacTypography.senderLabel)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)

                Text(bot.strategy)
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.textFaint)
                    .lineLimit(1)
            }

            Spacer()

            // P&L placeholder — TradingBotResponse doesn't have per-bot P&L yet
            Text("—")
                .font(MacTypography.senderLabel)
                .foregroundStyle(MacColors.textFaint)

            Circle()
                .fill(bot.status == "running" ? MacColors.healthGreen : MacColors.textSecondary)
                .frame(width: 6, height: 6)
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.chatInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Health Formatting Helpers

    private func formatHealthValue(_ value: Double?, unit: String?, isInt: Bool) -> String {
        guard let value else { return "--" }
        if isInt {
            let intVal = Int(value)
            let formatter = NumberFormatter()
            formatter.numberStyle = .decimal
            return formatter.string(from: NSNumber(value: intVal)) ?? "\(intVal)"
        }
        return String(format: "%.1f", value)
    }

    private func formatSleepValue(_ totalMinutes: Double?) -> String {
        guard let totalMinutes else { return "--" }
        let hours = Int(totalMinutes) / 60
        let minutes = Int(totalMinutes) % 60
        return "\(hours)h \(minutes)m"
    }
}

// MARK: - SparklineView

private struct SparklineView: View {
    let color: Color

    // Static sample points for visual placeholder sparklines
    private let points: [CGFloat] = [0.7, 0.55, 0.6, 0.45, 0.4, 0.5, 0.35, 0.25, 0.38, 0.2, 0.3, 0.15, 0.22]

    var body: some View {
        GeometryReader { geometry in
            let width = geometry.size.width
            let height = geometry.size.height

            ZStack {
                // Area fill
                Path { path in
                    drawSparkline(path: &path, width: width, height: height)
                    path.addLine(to: CGPoint(x: width, y: height))
                    path.addLine(to: CGPoint(x: 0, y: height))
                    path.closeSubpath()
                }
                .fill(color.opacity(0.08))

                // Line stroke
                Path { path in
                    drawSparkline(path: &path, width: width, height: height)
                }
                .stroke(color, style: StrokeStyle(lineWidth: 1.5, lineCap: .round, lineJoin: .round))
            }
        }
    }

    private func drawSparkline(path: inout Path, width: CGFloat, height: CGFloat) {
        guard points.count > 1 else { return }
        let step = width / CGFloat(points.count - 1)
        let firstPoint = CGPoint(x: 0, y: points[0] * height)
        path.move(to: firstPoint)
        for i in 1..<points.count {
            path.addLine(to: CGPoint(x: CGFloat(i) * step, y: points[i] * height))
        }
    }
}

// MARK: - PnLChartPlaceholder

private struct PnLChartPlaceholder: View {
    let isPositive: Bool

    private var lineColor: Color {
        isPositive ? MacColors.healthGreen : MacColors.healthRed
    }

    var body: some View {
        GeometryReader { geometry in
            let width = geometry.size.width
            let height = geometry.size.height

            ZStack {
                // Subtle horizontal grid lines
                ForEach(1..<4, id: \.self) { i in
                    let y = height * CGFloat(i) / 4.0
                    Path { path in
                        path.move(to: CGPoint(x: 0, y: y))
                        path.addLine(to: CGPoint(x: width, y: y))
                    }
                    .stroke(MacColors.textPrimary.opacity(0.04), lineWidth: 1)
                }

                // Area gradient
                Path { path in
                    drawCurve(path: &path, width: width, height: height)
                    path.addLine(to: CGPoint(x: width, y: height))
                    path.addLine(to: CGPoint(x: 0, y: height))
                    path.closeSubpath()
                }
                .fill(
                    LinearGradient(
                        colors: [lineColor.opacity(0.15), lineColor.opacity(0)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )

                // Line
                Path { path in
                    drawCurve(path: &path, width: width, height: height)
                }
                .stroke(lineColor, style: StrokeStyle(lineWidth: 2, lineCap: .round))
            }
        }
    }

    private func drawCurve(path: inout Path, width: CGFloat, height: CGFloat) {
        // Upward-trending placeholder curve
        let points: [(CGFloat, CGFloat)] = isPositive
            ? [(0, 0.67), (0.25, 0.54), (0.5, 0.42), (0.65, 0.4), (0.75, 0.33), (0.9, 0.29), (1.0, 0.25)]
            : [(0, 0.3), (0.25, 0.38), (0.5, 0.5), (0.65, 0.55), (0.75, 0.6), (0.9, 0.58), (1.0, 0.65)]

        guard let first = points.first else { return }
        path.move(to: CGPoint(x: first.0 * width, y: first.1 * height))

        for i in 1..<points.count {
            let current = points[i]
            let prev = points[i - 1]
            let midX = (prev.0 + current.0) / 2 * width
            path.addQuadCurve(
                to: CGPoint(x: current.0 * width, y: current.1 * height),
                control: CGPoint(x: midX, y: prev.1 * height)
            )
        }
    }
}

// MARK: - Preview

#if DEBUG
#Preview("Dashboard Tab") {
    DashboardTabView()
        .frame(width: 900, height: 800)
}
#endif
