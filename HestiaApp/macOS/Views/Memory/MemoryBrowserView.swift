import SwiftUI
import HestiaShared

struct MemoryBrowserView: View {
    @StateObject private var viewModel = MacMemoryBrowserViewModel()
    var onChunkEdited: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: 0) {
            headerBar
            filterBar
            Divider().overlay(MacColors.divider)

            if viewModel.isLoading && viewModel.chunks.isEmpty {
                Spacer()
                ProgressView("Loading memories...")
                    .foregroundStyle(MacColors.textSecondary)
                Spacer()
            } else if viewModel.chunks.isEmpty {
                Spacer()
                VStack(spacing: MacSpacing.md) {
                    Image(systemName: "brain")
                        .font(.system(size: 36))
                        .foregroundStyle(MacColors.textFaint)
                    Text("No memories found")
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textSecondary)
                }
                Spacer()
            } else {
                chunkList
                paginationBar
            }
        }
        .background(MacColors.windowBackground)
        .task {
            await viewModel.loadChunks()
        }
    }

    // MARK: - Header

    private var headerBar: some View {
        HStack {
            Text("Memory Browser")
                .font(MacTypography.pageTitle)
                .foregroundStyle(MacColors.textPrimary)

            Spacer()

            // Sort picker
            Picker("Sort", selection: $viewModel.sortBy) {
                ForEach(MacMemoryBrowserViewModel.SortOption.allCases, id: \.self) { option in
                    Text(option.label).tag(option)
                }
            }
            .pickerStyle(.segmented)
            .frame(width: 240)
            .onChange(of: viewModel.sortBy) { _, _ in
                Task { await viewModel.resetAndLoad() }
            }

            // Sort order toggle
            Button {
                viewModel.sortOrder = viewModel.sortOrder == "desc" ? "asc" : "desc"
                Task { await viewModel.resetAndLoad() }
            } label: {
                Image(systemName: viewModel.sortOrder == "desc" ? "arrow.down" : "arrow.up")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(MacColors.textSecondary)
            }
            .buttonStyle(.plain)
        }
        .padding(.horizontal, MacSpacing.xxl)
        .padding(.vertical, MacSpacing.lg)
    }

    // MARK: - Filter Bar

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: MacSpacing.sm) {
                Text("Type:")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)

                filterPill("All", value: nil, current: viewModel.chunkTypeFilter)
                filterPill("Fact", value: "fact", current: viewModel.chunkTypeFilter)
                filterPill("Preference", value: "preference", current: viewModel.chunkTypeFilter)
                filterPill("Decision", value: "decision", current: viewModel.chunkTypeFilter)
                filterPill("Action", value: "action_item", current: viewModel.chunkTypeFilter)
                filterPill("Research", value: "research", current: viewModel.chunkTypeFilter)
                filterPill("System", value: "system", current: viewModel.chunkTypeFilter)
                filterPill("Insight", value: "insight", current: viewModel.chunkTypeFilter)

                Divider()
                    .frame(height: 16)
                    .overlay(MacColors.divider)

                Text("Status:")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)

                statusPill("Active", value: "active")
                statusPill("Committed", value: "committed")
                statusPill("Archived", value: "archived")
                statusPill("All", value: nil)
            }
            .padding(.horizontal, MacSpacing.xxl)
            .padding(.vertical, MacSpacing.sm)
        }
    }

    private func filterPill(_ label: String, value: String?, current: String?) -> some View {
        let isActive = value == current
        return Button {
            viewModel.chunkTypeFilter = value
            Task { await viewModel.resetAndLoad() }
        } label: {
            Text(label)
                .font(MacTypography.captionMedium)
                .foregroundStyle(isActive ? MacColors.buttonTextDark : MacColors.textSecondary)
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, MacSpacing.xs)
                .background(isActive ? MacColors.amberAccent : MacColors.searchInputBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        }
        .buttonStyle(.plain)
    }

    private func statusPill(_ label: String, value: String?) -> some View {
        let isActive = value == viewModel.statusFilter
        return Button {
            viewModel.statusFilter = value
            Task { await viewModel.resetAndLoad() }
        } label: {
            Text(label)
                .font(MacTypography.captionMedium)
                .foregroundStyle(isActive ? MacColors.buttonTextDark : MacColors.textSecondary)
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, MacSpacing.xs)
                .background(isActive ? MacColors.amberAccent : MacColors.searchInputBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Chunk List

    private var chunkList: some View {
        ScrollView {
            LazyVStack(spacing: MacSpacing.sm) {
                ForEach(viewModel.chunks) { chunk in
                    MemoryChunkRow(chunk: chunk, viewModel: viewModel, onChunkEdited: onChunkEdited)
                }
            }
            .padding(.horizontal, MacSpacing.xxl)
            .padding(.vertical, MacSpacing.md)
        }
    }

    // MARK: - Pagination

    private var paginationBar: some View {
        HStack {
            Button {
                Task { await viewModel.previousPage() }
            } label: {
                HStack(spacing: MacSpacing.xs) {
                    Image(systemName: "chevron.left")
                    Text("Previous")
                }
                .font(MacTypography.smallMedium)
            }
            .buttonStyle(.plain)
            .foregroundStyle(viewModel.hasPreviousPage ? MacColors.amberAccent : MacColors.textFaint)
            .disabled(!viewModel.hasPreviousPage)

            Spacer()

            Text("Page \(viewModel.currentPage + 1) of \(viewModel.totalPages)")
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textSecondary)

            Text("\(viewModel.totalCount) chunks")
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textFaint)

            Spacer()

            Button {
                Task { await viewModel.nextPage() }
            } label: {
                HStack(spacing: MacSpacing.xs) {
                    Text("Next")
                    Image(systemName: "chevron.right")
                }
                .font(MacTypography.smallMedium)
            }
            .buttonStyle(.plain)
            .foregroundStyle(viewModel.hasNextPage ? MacColors.amberAccent : MacColors.textFaint)
            .disabled(!viewModel.hasNextPage)
        }
        .padding(.horizontal, MacSpacing.xxl)
        .padding(.vertical, MacSpacing.md)
        .background(MacColors.panelBackground)
        .overlay(alignment: .top) {
            MacColors.divider.frame(height: 1)
        }
    }
}
