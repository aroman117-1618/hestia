import SwiftUI
import HestiaShared

// MARK: - Explorer Inbox View (split: item list + detail)

struct ExplorerInboxView: View {
    @ObservedObject var viewModel: MacInboxViewModel

    private let sources: [(label: String, value: String?)] = [
        ("All", nil),
        ("Email", "mail"),
        ("Reminders", "reminders"),
        ("Calendar", "calendar")
    ]

    var body: some View {
        VStack(spacing: 0) {
            // Source filter bar
            filterBar

            MacColors.divider.frame(height: 1)

            // Main content area
            HStack(spacing: 0) {
                // Item list panel
                itemListPanel
                    .frame(minWidth: 300, idealWidth: 420, maxWidth: .infinity)

                // Detail panel (shown when item selected)
                if viewModel.selectedItem != nil {
                    MacColors.divider.frame(width: 1)

                    InboxDetailSheet(viewModel: viewModel)
                        .frame(minWidth: 300, idealWidth: 500, maxWidth: .infinity)
                }
            }

            MacColors.divider.frame(height: 1)

            // Bottom bar
            bottomBar
        }
        .background(MacColors.panelBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .padding(.horizontal, MacSpacing.xl)
        .padding(.bottom, MacSpacing.xl)
        .task {
            await viewModel.loadInbox()
        }
    }

    // MARK: - Filter Bar

    private var filterBar: some View {
        HStack(spacing: MacSpacing.sm) {
            // Source filter chips
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 0) {
                    ForEach(sources, id: \.label) { source in
                        Button {
                            Task { [weak viewModel] in
                                await viewModel?.filterBySource(source.value)
                            }
                        } label: {
                            HStack(spacing: MacSpacing.xs) {
                                Text(source.label)
                                    .font(MacTypography.body)
                                    .foregroundStyle(
                                        viewModel.selectedSource == source.value
                                            ? MacColors.textPrimary
                                            : MacColors.textSecondary
                                    )

                                // Unread badge per source
                                if let sourceKey = source.value,
                                   let count = viewModel.unreadBySource[sourceKey],
                                   count > 0 {
                                    Text("\(count)")
                                        .font(MacTypography.micro)
                                        .foregroundStyle(MacColors.buttonTextDark)
                                        .padding(.horizontal, MacSpacing.xs)
                                        .padding(.vertical, 1)
                                        .background(MacColors.amberAccent)
                                        .clipShape(Capsule())
                                } else if source.value == nil && viewModel.unreadCount > 0 {
                                    Text("\(viewModel.unreadCount)")
                                        .font(MacTypography.micro)
                                        .foregroundStyle(MacColors.buttonTextDark)
                                        .padding(.horizontal, MacSpacing.xs)
                                        .padding(.vertical, 1)
                                        .background(MacColors.amberAccent)
                                        .clipShape(Capsule())
                                }
                            }
                            .padding(.horizontal, MacSpacing.md)
                            .padding(.vertical, MacSpacing.sm)
                            .background(
                                viewModel.selectedSource == source.value
                                    ? MacColors.activeTabBackground
                                    : Color.clear
                            )
                            .clipShape(Capsule())
                            .fixedSize()
                        }
                        .buttonStyle(.hestia)
                    }
                }
            }

            Spacer()

            // Mark all read
            if viewModel.unreadCount > 0 {
                Button {
                    Task { [weak viewModel] in
                        await viewModel?.markAllRead()
                    }
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "envelope.open")
                            .font(.system(size: 12))
                        Text("Mark All Read")
                            .font(MacTypography.label)
                    }
                    .foregroundStyle(MacColors.amberAccent)
                    .padding(.horizontal, MacSpacing.md)
                    .padding(.vertical, MacSpacing.xs)
                }
                .buttonStyle(.hestia)
                .accessibilityLabel("Mark all items as read")
            }

            // Refresh button
            Button {
                Task { [weak viewModel] in
                    await viewModel?.refresh()
                }
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 13))
                    .foregroundStyle(MacColors.textSecondary)
            }
            .buttonStyle(.hestia)
            .accessibilityLabel("Refresh inbox")
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.sm)
    }

    // MARK: - Item List Panel

    private var itemListPanel: some View {
        Group {
            if viewModel.isLoading && viewModel.items.isEmpty {
                loadingState
            } else if viewModel.hasError {
                errorState
            } else if viewModel.filteredItems.isEmpty {
                emptyState
            } else {
                itemList
            }
        }
    }

    private var itemList: some View {
        ScrollView {
            LazyVStack(spacing: 1) {
                ForEach(viewModel.filteredItems) { item in
                    InboxItemRow(
                        item: item,
                        isSelected: viewModel.selectedItem?.id == item.id,
                        onSelect: {
                            Task { [weak viewModel] in
                                await viewModel?.selectItem(item)
                            }
                        },
                        onMarkRead: {
                            Task { [weak viewModel] in
                                await viewModel?.selectItem(item)
                            }
                        },
                        onArchive: {
                            Task { [weak viewModel] in
                                await viewModel?.archiveItem(item)
                            }
                        }
                    )
                }
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs)
        }
    }

    // MARK: - States

    private var loadingState: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            ProgressView()
                .controlSize(.regular)
                .tint(MacColors.amberAccent)
            Text("Loading inbox...")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var errorState: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 36))
                .foregroundStyle(MacColors.statusWarning)

            Text(viewModel.error ?? "Something went wrong")
                .font(MacTypography.bodyMedium)
                .foregroundStyle(MacColors.textPrimary)

            Text("Check that the server is running and try again.")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
                .multilineTextAlignment(.center)

            Button {
                viewModel.error = nil
                Task { [weak viewModel] in
                    await viewModel?.loadInbox()
                }
            } label: {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 13))
                    Text("Retry")
                        .font(MacTypography.bodyMedium)
                }
                .foregroundStyle(MacColors.buttonTextDark)
                .padding(.horizontal, MacSpacing.xxl)
                .padding(.vertical, MacSpacing.md)
                .background(MacColors.amberAccent)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            }
            .buttonStyle(.hestia)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyState: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: "tray")
                .font(.system(size: 36, weight: .light))
                .foregroundStyle(MacColors.amberAccent.opacity(0.5))

            Text("Your inbox is empty")
                .font(MacTypography.bodyMedium)
                .foregroundStyle(MacColors.textPrimary)

            Text("New messages, reminders, and events will appear here")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
                .multilineTextAlignment(.center)

            Button {
                Task { [weak viewModel] in
                    await viewModel?.refresh()
                }
            } label: {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 13))
                    Text("Refresh")
                        .font(MacTypography.bodyMedium)
                }
                .foregroundStyle(MacColors.amberAccent)
                .padding(.horizontal, MacSpacing.xxl)
                .padding(.vertical, MacSpacing.md)
                .background(MacColors.searchInputBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            }
            .buttonStyle(.hestia)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Bottom Bar

    private var bottomBar: some View {
        HStack(spacing: MacSpacing.md) {
            // Item count
            Text("\(viewModel.filteredItems.count) items")
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textFaint)

            if viewModel.unreadCount > 0 {
                Text("\(viewModel.unreadCount) unread")
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.amberAccent)
            }

            Spacer()

            if viewModel.isLoading {
                ProgressView()
                    .controlSize(.small)
                    .tint(MacColors.amberAccent)
            }
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.sm)
    }
}
