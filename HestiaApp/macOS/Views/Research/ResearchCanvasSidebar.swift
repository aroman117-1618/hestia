import SwiftUI
import HestiaShared

/// Left sidebar for the Research Canvas — collapsible sections for memories, entities, principles, boards.
struct ResearchCanvasSidebar: View {
    @ObservedObject var viewModel: ResearchCanvasViewModel

    var body: some View {
        VStack(spacing: 0) {
            // Search bar
            searchBar

            Divider()
                .overlay(MacColors.divider)

            // Scrollable sections
            ScrollView {
                VStack(spacing: MacSpacing.xs) {
                    entitiesSection
                    principlesSection
                    memoriesSection
                    collectionsSection
                    investigationsSection
                }
                .padding(.vertical, MacSpacing.sm)
                .padding(.horizontal, MacSpacing.sm)
            }
        }
        .frame(width: 240)
        .background(MacColors.sidebarBackground)
        .overlay(
            Rectangle()
                .frame(width: 1)
                .foregroundStyle(MacColors.sidebarBorder),
            alignment: .trailing
        )
    }

    // MARK: - Search Bar

    private var searchBar: some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 12))
                .foregroundStyle(MacColors.textPlaceholder)
            TextField("Search...", text: $viewModel.sidebarSearchText)
                .textFieldStyle(.plain)
                .font(.system(size: 12))
                .foregroundStyle(MacColors.textPrimary)
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        .padding(MacSpacing.sm)
    }

    // MARK: - Entities Section

    private var entitiesSection: some View {
        DisclosureGroup(
            isExpanded: $viewModel.entitiesExpanded
        ) {
            if viewModel.filteredEntities.isEmpty {
                sidebarEmptyLabel("No entities")
            } else {
                ForEach(viewModel.filteredEntities) { entity in
                    entityRow(entity)
                }
            }
        } label: {
            sidebarSectionHeader(icon: "person.text.rectangle", title: "Entities", count: viewModel.filteredEntities.count)
        }
        .tint(MacColors.textSecondary)
    }

    private func entityRow(_ entity: ResearchCanvasEntity) -> some View {
        Button {
            viewModel.selectEntity(entity)
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Circle()
                    .fill(entityTypeColor(entity.entityType))
                    .frame(width: 6, height: 6)
                Text(entity.name)
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)
                Spacer()
                if entity.connectionCount > 0 {
                    Text("\(entity.connectionCount)")
                        .font(.system(size: 9))
                        .foregroundStyle(MacColors.textFaint)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(MacColors.textPrimary.opacity(0.06))
                        .clipShape(Capsule())
                }
            }
            .padding(.vertical, 3)
            .padding(.horizontal, MacSpacing.sm)
            .background(
                viewModel.selectedEntity?.id == entity.id
                    ? MacColors.amberAccent.opacity(0.12)
                    : Color.clear
            )
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Principles Section

    private var principlesSection: some View {
        DisclosureGroup(
            isExpanded: $viewModel.principlesExpanded
        ) {
            // Status filter
            HStack(spacing: MacSpacing.xs) {
                statusFilterPill(nil, label: "All")
                statusFilterPill("pending", label: "Pending")
                statusFilterPill("approved", label: "Approved")
                statusFilterPill("rejected", label: "Rejected")
            }
            .padding(.vertical, 2)

            if viewModel.filteredPrinciples.isEmpty {
                sidebarEmptyLabel("No principles")
            } else {
                ForEach(viewModel.filteredPrinciples) { principle in
                    principleRow(principle)
                }
            }
        } label: {
            sidebarSectionHeader(icon: "lightbulb", title: "Principles", count: viewModel.filteredPrinciples.count)
        }
        .tint(MacColors.textSecondary)
    }

    private func statusFilterPill(_ status: String?, label: String) -> some View {
        Button {
            viewModel.principleStatusFilter = status
        } label: {
            Text(label)
                .font(.system(size: 9, weight: .medium))
                .foregroundStyle(
                    viewModel.principleStatusFilter == status
                        ? MacColors.amberAccent
                        : MacColors.textFaint
                )
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(
                    viewModel.principleStatusFilter == status
                        ? MacColors.amberAccent.opacity(0.12)
                        : MacColors.textPrimary.opacity(0.04)
                )
                .clipShape(Capsule())
        }
        .buttonStyle(.plain)
    }

    private func principleRow(_ principle: ResearchPrinciple) -> some View {
        HStack(spacing: MacSpacing.sm) {
            principleStatusDot(principle.status)
            Text(principle.content)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(2)
        }
        .padding(.vertical, 3)
        .padding(.horizontal, MacSpacing.sm)
    }

    private func principleStatusDot(_ status: String) -> some View {
        Circle()
            .fill(principleStatusColor(status))
            .frame(width: 6, height: 6)
    }

    // MARK: - Memories Section

    private var memoriesSection: some View {
        DisclosureGroup(
            isExpanded: $viewModel.memoriesExpanded
        ) {
            if viewModel.filteredMemories.isEmpty {
                sidebarEmptyLabel("No memories")
            } else {
                ForEach(viewModel.filteredMemories) { chunk in
                    memoryRow(chunk)
                }
            }
        } label: {
            sidebarSectionHeader(icon: "brain", title: "Memories", count: viewModel.filteredMemories.count)
        }
        .tint(MacColors.textSecondary)
    }

    private func memoryRow(_ chunk: MemoryChunkItem) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Text(chunk.chunkType)
                .font(.system(size: 8, weight: .semibold))
                .foregroundStyle(MacColors.amberAccent)
                .textCase(.uppercase)
                .frame(width: 32, alignment: .leading)
            Text(chunk.content)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(1)
            Spacer()
            // Importance indicator
            Circle()
                .fill(importanceColor(chunk.importance))
                .frame(width: 5, height: 5)
        }
        .padding(.vertical, 3)
        .padding(.horizontal, MacSpacing.sm)
    }

    // MARK: - Collections Section (Boards)

    private var collectionsSection: some View {
        DisclosureGroup(
            isExpanded: $viewModel.collectionsExpanded
        ) {
            if viewModel.boards.isEmpty {
                sidebarEmptyLabel("No saved boards")
            } else {
                ForEach(viewModel.boards) { board in
                    Button {
                        viewModel.currentBoard = board
                    } label: {
                        HStack(spacing: MacSpacing.sm) {
                            Image(systemName: "rectangle.3.group")
                                .font(.system(size: 10))
                                .foregroundStyle(MacColors.textSecondary)
                            Text(board.name)
                                .font(.system(size: 11))
                                .foregroundStyle(MacColors.textPrimary)
                                .lineLimit(1)
                        }
                        .padding(.vertical, 3)
                        .padding(.horizontal, MacSpacing.sm)
                        .background(
                            viewModel.currentBoard?.id == board.id
                                ? MacColors.amberAccent.opacity(0.12)
                                : Color.clear
                        )
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
                    }
                    .buttonStyle(.plain)
                }
            }

            Button {
                Task { await viewModel.createBoard(name: "Untitled Board") }
            } label: {
                HStack(spacing: MacSpacing.xs) {
                    Image(systemName: "plus")
                        .font(.system(size: 10))
                    Text("New Board")
                        .font(.system(size: 11))
                }
                .foregroundStyle(MacColors.amberAccent)
                .padding(.vertical, 3)
                .padding(.horizontal, MacSpacing.sm)
            }
            .buttonStyle(.plain)
        } label: {
            sidebarSectionHeader(icon: "tray.2", title: "Collections", count: viewModel.boards.count)
        }
        .tint(MacColors.textSecondary)
    }

    // MARK: - Investigations Section

    private var investigationsSection: some View {
        DisclosureGroup(
            isExpanded: $viewModel.investigationsExpanded
        ) {
            sidebarEmptyLabel("No investigations")
        } label: {
            sidebarSectionHeader(icon: "doc.text.magnifyingglass", title: "Investigations", count: 0)
        }
        .tint(MacColors.textSecondary)
    }

    // MARK: - Helpers

    private func sidebarSectionHeader(icon: String, title: String, count: Int) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textSecondary)
            Text(title)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(MacColors.textPrimary)
            Spacer()
            if count > 0 {
                Text("\(count)")
                    .font(.system(size: 9))
                    .foregroundStyle(MacColors.textFaint)
            }
        }
    }

    private func sidebarEmptyLabel(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(MacColors.textFaint)
            .padding(.vertical, MacSpacing.xs)
            .padding(.horizontal, MacSpacing.sm)
    }

    private func entityTypeColor(_ type: String) -> Color {
        switch type.lowercased() {
        case "person": return Color(red: 0.19, green: 0.82, blue: 0.35)
        case "organization": return Color(red: 0.35, green: 0.78, blue: 0.98)
        case "location": return Color(red: 1.0, green: 0.84, blue: 0.04)
        case "concept": return Color(red: 0.75, green: 0.35, blue: 0.95)
        default: return MacColors.textSecondary
        }
    }

    private func principleStatusColor(_ status: String) -> Color {
        switch status {
        case "approved": return MacColors.statusGreen
        case "rejected": return MacColors.statusCritical
        case "pending": return MacColors.statusWarning
        default: return MacColors.textFaint
        }
    }

    private func importanceColor(_ importance: Double) -> Color {
        if importance >= 0.7 { return MacColors.amberBright }
        if importance >= 0.4 { return MacColors.textSecondary }
        return MacColors.textFaint
    }
}

