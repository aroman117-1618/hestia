import SwiftUI
import HestiaShared

// MARK: - Activity Tab View

struct ActivityTabView: View {
    @StateObject private var viewModel = ActivityTabViewModel()

    var body: some View {
        HStack(spacing: 0) {
            // Feed pane (always visible, fills remaining space)
            feedPane

            // Detail panel (slides in from right, 420px wide)
            if viewModel.isPanelOpen, let item = viewModel.selectedItem {
                ActivityDetailPanelView(
                    item: item,
                    runDetail: viewModel.selectedRunDetail,
                    isLoadingDetail: viewModel.isLoadingDetail,
                    onClose: { viewModel.closePanel() },
                    onSendToChat: { context in viewModel.sendToChat(context) }
                )
                .frame(width: 420)
                .transition(.move(edge: .trailing))
            }
        }
        .animation(.easeInOut(duration: 0.25), value: viewModel.isPanelOpen)
        .task { await viewModel.loadData() }
    }

    // MARK: - Feed Pane

    private var feedPane: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header section (pinned at top, not scrollable)
            HStack {
                Text("ACTIVITY FEED")
                    .font(MacTypography.sectionLabel)
                    .tracking(0.8)
                    .foregroundStyle(MacColors.textFaint)

                Spacer()

                Button {
                    // Mark all read
                } label: {
                    Text("Mark All Read")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.amberAccent)
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, MacSpacing.xxl)
            .padding(.top, MacSpacing.xxl)
            .padding(.bottom, MacSpacing.lg)

            // Filter pills
            HStack(spacing: MacSpacing.xs) {
                ForEach(ActivityTabViewModel.FeedFilter.allCases) { filter in
                    filterPill(filter)
                }
            }
            .padding(.horizontal, MacSpacing.xxl)
            .padding(.bottom, MacSpacing.lg)

            // Divider
            MacColors.divider.frame(height: 0.5)

            // Feed list (scrollable)
            if viewModel.isLoading {
                Spacer()
                HStack {
                    Spacer()
                    ProgressView()
                        .controlSize(.small)
                    Spacer()
                }
                Spacer()
            } else if viewModel.filteredItems.isEmpty {
                Spacer()
                HStack {
                    Spacer()
                    Text("No activity yet")
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textFaint)
                    Spacer()
                }
                Spacer()
            } else {
                ScrollView {
                    LazyVStack(spacing: 2) {
                        ForEach(viewModel.filteredItems) { item in
                            feedItemRow(item)
                                .onTapGesture { viewModel.selectItem(item) }
                        }
                    }
                    .padding(MacSpacing.lg)
                }
            }
        }
    }

    // MARK: - Filter Pill

    private func filterPill(_ filter: ActivityTabViewModel.FeedFilter) -> some View {
        let isActive = viewModel.activeFilter == filter
        return Button {
            withAnimation(.easeInOut(duration: 0.15)) {
                viewModel.activeFilter = filter
            }
        } label: {
            Text(filter.rawValue)
                .font(MacTypography.labelMedium)
                .foregroundStyle(isActive ? MacColors.amberAccent : MacColors.textInactive)
                .padding(.horizontal, 14)
                .padding(.vertical, 4)
                .background(
                    RoundedRectangle(cornerRadius: 9999)
                        .stroke(isActive ? MacColors.amberAccent : MacColors.cardBorder, lineWidth: 1)
                )
                .background(
                    isActive
                        ? MacColors.amberAccent.opacity(0.08)
                        : Color.clear
                )
                .clipShape(Capsule())
        }
        .buttonStyle(.plain)
    }

    // MARK: - Feed Item Row

    private func feedItemRow(_ item: NewsfeedItem) -> some View {
        let isSelected = item.id == viewModel.selectedItemId

        return HStack(alignment: .top, spacing: MacSpacing.md) {
            // Icon circle
            iconCircle(for: item)

            // Body
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                Text(item.title)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)

                if let description = item.body, !description.isEmpty {
                    Text(description)
                        .font(.system(size: 12))
                        .foregroundStyle(MacColors.textSecondary)
                        .lineLimit(2)
                }

                // Meta row: time + category badge
                HStack(spacing: MacSpacing.sm) {
                    if let date = item.parsedTimestamp {
                        Text(formatTime(date))
                            .font(.system(size: 11))
                            .foregroundStyle(MacColors.textFaint)
                    }

                    categoryTag(for: item)
                }
            }

            Spacer(minLength: 0)
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(
            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                .fill(isSelected ? MacColors.activeTabBackground : Color.clear)
        )
        .contentShape(Rectangle())
    }

    // MARK: - Icon Circle

    private func iconCircle(for item: NewsfeedItem) -> some View {
        let config = iconConfig(for: item)
        return ZStack {
            Circle()
                .fill(config.color.opacity(0.12))
            Image(systemName: config.icon)
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(config.color)
        }
        .frame(width: 32, height: 32)
    }

    private struct IconConfig {
        let color: Color
        let icon: String
    }

    private func iconConfig(for item: NewsfeedItem) -> IconConfig {
        switch item.source {
        case "orders":
            return IconConfig(color: MacColors.amberAccent, icon: "checkmark.rectangle")
        case "trading":
            return IconConfig(color: MacColors.healthRed, icon: "exclamationmark.triangle")
        case "sentinel":
            return IconConfig(color: MacColors.statusWarning, icon: "shield")
        case "learning":
            return IconConfig(color: MacColors.sleepPurple, icon: "lightbulb")
        default:
            if item.itemType.contains("suggestion") {
                return IconConfig(color: MacColors.sleepPurple, icon: "lightbulb")
            }
            return IconConfig(color: MacColors.statusInfo, icon: "info.circle")
        }
    }

    // MARK: - Category Tag Badge

    @ViewBuilder
    private func categoryTag(for item: NewsfeedItem) -> some View {
        let config = tagConfig(for: item)
        Text(config.label)
            .font(.system(size: 10, weight: .semibold))
            .textCase(.uppercase)
            .tracking(0.5)
            .padding(.horizontal, 6)
            .padding(.vertical, 1)
            .background(config.color.opacity(0.12))
            .foregroundStyle(config.color)
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    private struct TagConfig {
        let label: String
        let color: Color
    }

    private func tagConfig(for item: NewsfeedItem) -> TagConfig {
        switch item.source {
        case "orders":
            return TagConfig(label: "ORDER", color: MacColors.amberAccent)
        case "trading":
            return TagConfig(label: "TRADING", color: MacColors.healthRed)
        case "sentinel":
            return TagConfig(label: "SECURITY", color: MacColors.statusWarning)
        case "learning":
            return TagConfig(label: "SELF-DEV", color: MacColors.sleepPurple)
        default:
            if item.itemType.contains("suggestion") {
                return TagConfig(label: "SELF-DEV", color: MacColors.sleepPurple)
            }
            if item.priority == "high" {
                return TagConfig(label: "ALERT", color: MacColors.healthRed)
            }
            return TagConfig(label: "SYSTEM", color: MacColors.statusInfo)
        }
    }

    // MARK: - Time Formatting

    private func formatTime(_ date: Date) -> String {
        let calendar = Calendar.current
        if calendar.isDateInToday(date) {
            return date.formatted(date: .omitted, time: .shortened)
        } else if calendar.isDateInYesterday(date) {
            return "Yesterday, \(date.formatted(date: .omitted, time: .shortened))"
        } else {
            return date.formatted(date: .abbreviated, time: .shortened)
        }
    }
}
