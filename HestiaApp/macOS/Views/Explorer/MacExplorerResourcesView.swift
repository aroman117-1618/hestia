import SwiftUI
import HestiaShared

struct MacExplorerResourcesView: View {
    @StateObject private var viewModel = MacExplorerResourcesViewModel()
    @State private var selectedTabIndex = 0
    @State private var showingNewDraft = false
    @State private var newDraftTitle = ""

    var body: some View {
        VStack(spacing: 0) {
            // Filter bar
            filterBar
                .padding(.horizontal, MacSpacing.lg)
                .padding(.top, MacSpacing.md)
                .padding(.bottom, MacSpacing.sm)

            // Search
            searchBar
                .padding(.horizontal, MacSpacing.lg)
                .padding(.bottom, MacSpacing.sm)

            MacColors.divider.frame(height: 1)
                .padding(.horizontal, MacSpacing.md)

            // Resource list
            if viewModel.isLoading && viewModel.resources.isEmpty {
                loadingState
            } else if viewModel.resources.isEmpty {
                emptyState
            } else {
                resourceList
            }
        }
        .task {
            await viewModel.loadResources()
        }
        .alert("New Draft", isPresented: $showingNewDraft) {
            TextField("Title", text: $newDraftTitle)
            Button("Create") {
                guard !newDraftTitle.isEmpty else { return }
                let title = newDraftTitle
                newDraftTitle = ""
                Task { await viewModel.createDraft(title: title) }
            }
            Button("Cancel", role: .cancel) { newDraftTitle = "" }
        }
    }

    // MARK: - Filter Bar

    private var filterBar: some View {
        HStack(spacing: MacSpacing.sm) {
            ForEach(Array(MacExplorerResourcesViewModel.filterTabs.enumerated()), id: \.offset) { index, tab in
                Button {
                    selectedTabIndex = index
                    Task { await viewModel.applyFilter(type: tab.type) }
                } label: {
                    Text(tab.label)
                        .font(.system(size: 12, weight: selectedTabIndex == index ? .semibold : .regular))
                        .foregroundStyle(selectedTabIndex == index ? MacColors.amberAccent : MacColors.textSecondary)
                        .padding(.horizontal, MacSpacing.sm)
                        .padding(.vertical, 4)
                        .background(
                            selectedTabIndex == index
                                ? MacColors.activeTabBackground
                                : Color.clear
                        )
                        .cornerRadius(MacCornerRadius.treeItem)
                }
                .buttonStyle(.hestia)
            }

            Spacer()

            Button {
                showingNewDraft = true
            } label: {
                Image(systemName: "square.and.pencil")
                    .font(.system(size: 13))
                    .foregroundStyle(MacColors.amberAccent)
            }
            .buttonStyle(.hestia)
        }
    }

    // MARK: - Search

    private var searchBar: some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 12))
                .foregroundStyle(MacColors.textPlaceholder)

            TextField("Search resources...", text: $viewModel.searchText)
                .textFieldStyle(.plain)
                .font(.system(size: 12))
                .foregroundStyle(MacColors.textPrimary)
                .onSubmit {
                    Task { await viewModel.search() }
                }

            if !viewModel.searchText.isEmpty {
                Button {
                    viewModel.searchText = ""
                    Task { await viewModel.search() }
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 12))
                        .foregroundStyle(MacColors.textPlaceholder)
                }
                .buttonStyle(.hestia)
            }
        }
        .padding(MacSpacing.sm)
        .background(MacColors.searchInputBackground)
        .cornerRadius(MacCornerRadius.search)
    }

    // MARK: - Resource List

    private var resourceList: some View {
        ScrollView {
            LazyVStack(spacing: 2) {
                ForEach(viewModel.resources) { resource in
                    MacExplorerResourceRow(resource: resource) {
                        if resource.type == .draft {
                            Task { await viewModel.deleteDraft(resource) }
                        }
                    }
                }
            }
            .padding(.horizontal, MacSpacing.md)
            .padding(.top, MacSpacing.sm)
        }
    }

    // MARK: - States

    private var loadingState: some View {
        VStack {
            Spacer()
            ProgressView()
                .controlSize(.regular)
                .tint(MacColors.amberAccent)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var emptyState: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: selectedTabIcon)
                .font(.system(size: 36))
                .foregroundStyle(MacColors.textFaint)
            Text("No resources found")
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(MacColors.textSecondary)
            if !viewModel.searchText.isEmpty {
                Text("Try a different search term")
                    .font(.system(size: 12))
                    .foregroundStyle(MacColors.textFaint)
            }
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var selectedTabIcon: String {
        switch MacExplorerResourcesViewModel.filterTabs[selectedTabIndex].type {
        case .draft: return "doc.text"
        case .mail: return "envelope"
        case .task: return "checklist"
        case .note: return "note.text"
        case .file: return "folder"
        case .none: return "square.grid.2x2"
        }
    }
}

// MARK: - Resource Row (macOS-adapted)

struct MacExplorerResourceRow: View {
    let resource: ExplorerResource
    var onDelete: (() -> Void)?
    @State private var isHovered = false

    var body: some View {
        HStack(spacing: MacSpacing.md) {
            Image(systemName: iconName)
                .font(.system(size: 16))
                .foregroundStyle(iconColor)
                .frame(width: 24, height: 24)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: MacSpacing.xs) {
                    Text(resource.title)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(MacColors.textPrimary)
                        .lineLimit(1)

                    Spacer()

                    flagIcons
                }

                if let preview = resource.preview, !preview.isEmpty {
                    Text(preview)
                        .font(.system(size: 11))
                        .foregroundStyle(MacColors.textSecondary)
                        .lineLimit(1)
                }

                HStack(spacing: MacSpacing.sm) {
                    Text(sourceLabel)
                        .font(.system(size: 10))
                        .foregroundStyle(MacColors.textFaint)

                    if let date = formattedDate {
                        Text(date)
                            .font(.system(size: 10))
                            .foregroundStyle(MacColors.textFaint)
                    }
                }
            }

            if isHovered && resource.type == .draft, let onDelete = onDelete {
                Button {
                    onDelete()
                } label: {
                    Image(systemName: "trash")
                        .font(.system(size: 11))
                        .foregroundStyle(MacColors.healthRed.opacity(0.7))
                }
                .buttonStyle(.hestia)
            }
        }
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, 6)
        .background(isHovered ? MacColors.activeNavBackground.opacity(0.4) : Color.clear)
        .cornerRadius(MacCornerRadius.treeItem)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.1)) {
                isHovered = hovering
            }
        }
    }

    private var iconName: String {
        switch resource.type {
        case .draft: return "doc.text.fill"
        case .mail: return "envelope.fill"
        case .task: return "checklist"
        case .note: return "note.text"
        case .file: return "doc.fill"
        }
    }

    private var iconColor: Color {
        switch resource.type {
        case .draft: return .blue
        case .mail: return .cyan
        case .task: return .orange
        case .note: return .yellow
        case .file: return .gray
        }
    }

    @ViewBuilder
    private var flagIcons: some View {
        HStack(spacing: 3) {
            if resource.flags.contains(.unread) {
                Circle()
                    .fill(Color.blue)
                    .frame(width: 6, height: 6)
            }
            if resource.flags.contains(.flagged) {
                Image(systemName: "flag.fill")
                    .font(.system(size: 9))
                    .foregroundStyle(.orange)
            }
        }
    }

    private var sourceLabel: String {
        switch resource.source {
        case .hestia: return "Hestia"
        case .mail: return "Mail"
        case .notes: return "Notes"
        case .reminders: return "Reminders"
        case .files: return "Files"
        }
    }

    private var formattedDate: String? {
        guard let dateStr = resource.modifiedAt ?? resource.createdAt else { return nil }
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: dateStr) else { return nil }
        let relative = RelativeDateTimeFormatter()
        relative.unitsStyle = .abbreviated
        return relative.localizedString(for: date, relativeTo: Date())
    }
}
