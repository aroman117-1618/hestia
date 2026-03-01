import SwiftUI
import HestiaShared

// MARK: - Research View (3D Graph + Data Explorer modes)

struct ResearchView: View {
    @State private var selectedMode: ResearchMode = .graph
    @State private var selectedTimeRange: TimeRange = .thirtyDays
    @State private var searchText: String = ""
    @State private var activeFilters: Set<DataSource> = Set(DataSource.allCases)
    @StateObject private var graphViewModel = MacNeuralNetViewModel()

    var body: some View {
        GeometryReader { geo in
            let isCompact = geo.size.width < 700

            VStack(spacing: 0) {
                headerBar(compact: isCompact)

                // Filter bar only in explorer mode
                if selectedMode == .explorer {
                    filterBar(compact: isCompact)
                        .padding(.top, MacSpacing.sm)
                }

                // Main content
                ZStack {
                    ambientBackground

                    switch selectedMode {
                    case .graph:
                        graphContent
                    case .explorer:
                        ResearchExplorerPlaceholder()
                    }
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .background(MacColors.windowBackground)
        .onAppear {
            if graphViewModel.nodes.isEmpty && !graphViewModel.isLoading {
                Task { await graphViewModel.loadGraph() }
            }
        }
    }

    // MARK: - Graph Content (SceneKit 3D)

    @ViewBuilder
    private var graphContent: some View {
        if graphViewModel.isLoading {
            graphLoadingState
        } else if graphViewModel.nodes.isEmpty {
            graphEmptyState
        } else {
            ZStack {
                MacSceneKitGraphView(
                    nodes: graphViewModel.nodes,
                    edges: graphViewModel.edges,
                    selectedNode: $graphViewModel.selectedNode,
                    onNodeMoved: { id, position in
                        graphViewModel.updateNodePosition(id: id, position: position)
                    }
                )

                // Legend overlay (bottom-left)
                graphLegend
                    .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
                    .padding(MacSpacing.lg)

                // Node count badge (top-right)
                if graphViewModel.memoryCount > 0 {
                    nodeCountBadge
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                        .padding(MacSpacing.lg)
                }

                // Selected node detail (bottom-center)
                if let node = graphViewModel.selectedNode {
                    VStack {
                        Spacer()
                        nodeDetailCard(node)
                    }
                    .padding(.horizontal, MacSpacing.xxxl)
                    .padding(.bottom, MacSpacing.lg)
                }
            }
        }
    }

    private var graphLoadingState: some View {
        VStack(spacing: MacSpacing.md) {
            ProgressView()
                .controlSize(.regular)
            Text("Mapping neural connections...")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textSecondary)
        }
    }

    private var graphEmptyState: some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "brain")
                .font(.system(size: 48))
                .foregroundStyle(MacColors.textSecondary.opacity(0.3))
            Text("No memories yet")
                .font(.system(size: 18, weight: .medium))
                .foregroundStyle(MacColors.textSecondary)
            Text("Start chatting to build your neural net")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textFaint)
        }
    }

    private var graphLegend: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            legendDot(color: Color(red: 0.6, green: 0.3, blue: 0.9), label: "Preference")
            legendDot(color: Color(red: 0.2, green: 0.5, blue: 1.0), label: "Fact")
            legendDot(color: Color(red: 1.0, green: 0.6, blue: 0.2), label: "Decision")
            legendDot(color: Color(red: 1.0, green: 0.3, blue: 0.3), label: "Action")
            legendDot(color: Color(red: 0.2, green: 0.8, blue: 0.6), label: "Research")
            Text("Node size = confidence")
                .font(.system(size: 10).italic())
                .foregroundStyle(MacColors.textFaint)
                .padding(.top, MacSpacing.xs)
        }
        .padding(MacSpacing.md)
        .background(
            RoundedRectangle(cornerRadius: MacCornerRadius.tab + 2)
                .fill(Color(red: 17/255, green: 11/255, blue: 3/255).opacity(0.85))
                .overlay(
                    RoundedRectangle(cornerRadius: MacCornerRadius.tab + 2)
                        .strokeBorder(Color(red: 254/255, green: 154/255, blue: 0).opacity(0.08), lineWidth: 1)
                )
        )
    }

    private func legendDot(color: Color, label: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(label)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textSecondary)
        }
    }

    private var nodeCountBadge: some View {
        Text("\(graphViewModel.nodes.count) nodes · \(graphViewModel.edges.count) edges")
            .font(.system(size: 10, weight: .medium))
            .foregroundStyle(MacColors.textSecondary)
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs)
            .background(
                RoundedRectangle(cornerRadius: MacCornerRadius.search)
                    .fill(Color(red: 17/255, green: 11/255, blue: 3/255).opacity(0.85))
            )
    }

    private func nodeDetailCard(_ node: MacNeuralNetViewModel.GraphNode) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Circle()
                .fill(node.swiftUIColor)
                .frame(width: 12, height: 12)

            VStack(alignment: .leading, spacing: 2) {
                Text(node.chunkType.rawValue.capitalized)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)

                Text(node.content)
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textSecondary)
                    .lineLimit(2)
            }

            Spacer()

            Text("\(Int(node.confidence * 100))%")
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(MacColors.textSecondary)
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, MacSpacing.xs)
                .background(MacColors.textPrimary.opacity(0.06))
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))

            Button {
                withAnimation(.easeInOut(duration: 0.15)) {
                    graphViewModel.selectedNode = nil
                }
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .foregroundStyle(MacColors.textSecondary)
                    .font(.system(size: 16))
            }
            .buttonStyle(.plain)
        }
        .padding(MacSpacing.md)
        .background(
            RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                .fill(Color(red: 17/255, green: 11/255, blue: 3/255).opacity(0.9))
                .overlay(
                    RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                        .strokeBorder(MacColors.amberAccent.opacity(0.15), lineWidth: 1)
                )
        )
        .transition(.move(edge: .bottom).combined(with: .opacity))
    }

    // MARK: - Header Bar

    private func headerBar(compact: Bool) -> some View {
        HStack {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "atom")
                    .font(.system(size: MacSize.navIcon))
                    .foregroundStyle(MacColors.textPrimary)
                if !compact {
                    Text("Research")
                        .font(.system(size: 18))
                        .foregroundStyle(MacColors.textPrimary)
                }
            }

            Spacer()

            modeToggle(compact: compact)

            Spacer()

            // Refresh button (graph mode) or time range picker (explorer mode)
            if selectedMode == .graph {
                Button {
                    Task { await graphViewModel.loadGraph() }
                } label: {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 13))
                        .foregroundStyle(MacColors.textSecondary)
                        .padding(MacSpacing.sm)
                        .background(MacColors.textPrimary.opacity(0.04))
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.plain)
            } else {
                timeRangePicker(compact: compact)
            }
        }
        .padding(.horizontal, MacSpacing.xl)
        .padding(.vertical, MacSpacing.md)
    }

    private func modeToggle(compact: Bool) -> some View {
        HStack(spacing: 2) {
            modeButton(.graph, icon: "point.3.connected.trianglepath.dotted", label: "Graph", compact: compact)
            modeButton(.explorer, icon: "tablecells", label: "Explorer", compact: compact)
        }
        .padding(MacSpacing.xs)
        .background(MacColors.textPrimary.opacity(0.04))
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
    }

    private func modeButton(_ mode: ResearchMode, icon: String, label: String, compact: Bool) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                selectedMode = mode
                if mode == .graph && graphViewModel.nodes.isEmpty && !graphViewModel.isLoading {
                    Task { await graphViewModel.loadGraph() }
                }
            }
        } label: {
            HStack(spacing: MacSpacing.xs) {
                Image(systemName: icon)
                    .font(.system(size: 14))
                if !compact {
                    Text(label)
                        .font(.system(size: 13, weight: .medium))
                }
            }
            .foregroundStyle(selectedMode == mode ? MacColors.amberAccent : MacColors.textSecondary)
            .padding(.horizontal, compact ? MacSpacing.sm : MacSpacing.md)
            .padding(.vertical, MacSpacing.sm)
            .background(selectedMode == mode ? MacColors.amberAccent.opacity(0.15) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
        }
        .buttonStyle(.plain)
    }

    private func timeRangePicker(compact: Bool) -> some View {
        Menu {
            ForEach(TimeRange.allCases, id: \.self) { range in
                Button(range.label) {
                    selectedTimeRange = range
                }
            }
        } label: {
            HStack(spacing: MacSpacing.xs) {
                Image(systemName: "calendar")
                    .font(.system(size: 13))
                if !compact {
                    Text(selectedTimeRange.label)
                        .font(.system(size: 12, weight: .medium))
                    Image(systemName: "chevron.down")
                        .font(.system(size: 12))
                }
            }
            .foregroundStyle(MacColors.textSecondary)
            .padding(.horizontal, compact ? MacSpacing.sm : MacSpacing.md)
            .padding(.vertical, MacSpacing.sm)
            .background(MacColors.textPrimary.opacity(0.04))
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        }
    }

    // MARK: - Filter Bar (Explorer mode only)

    private func filterBar(compact: Bool) -> some View {
        HStack(spacing: MacSpacing.sm) {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: compact ? MacSpacing.xs : MacSpacing.sm) {
                    ForEach(DataSource.allCases, id: \.self) { source in
                        filterPill(source, compact: compact)
                    }
                }
            }

            Spacer(minLength: MacSpacing.sm)

            if compact {
                Button {} label: {
                    Image(systemName: "magnifyingglass")
                        .font(.system(size: 14))
                        .foregroundStyle(MacColors.textPlaceholder)
                        .frame(width: 32, height: 31.5)
                        .background(MacColors.textPrimary.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.plain)
            } else {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: "magnifyingglass")
                        .font(.system(size: 13))
                        .foregroundStyle(MacColors.textPlaceholder)
                    TextField("Search tags, topics, people...", text: $searchText)
                        .textFieldStyle(.plain)
                        .font(.system(size: 13))
                        .foregroundStyle(MacColors.textPrimary)
                }
                .padding(.horizontal, MacSpacing.md)
                .frame(minWidth: 140, maxWidth: 240, minHeight: 31.5, maxHeight: 31.5)
                .background(MacColors.textPrimary.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            }
        }
        .padding(.horizontal, MacSpacing.xl)
    }

    private func filterPill(_ source: DataSource, compact: Bool) -> some View {
        let isActive = activeFilters.contains(source)

        return Button {
            withAnimation(.easeInOut(duration: 0.15)) {
                if isActive {
                    activeFilters.remove(source)
                } else {
                    activeFilters.insert(source)
                }
            }
        } label: {
            HStack(spacing: compact ? 0 : MacSpacing.xs) {
                Image(systemName: source.icon)
                    .font(.system(size: 13))
                if !compact {
                    Text(source.label)
                        .font(.system(size: 12))
                        .fixedSize()
                }
            }
            .foregroundStyle(isActive ? source.color : MacColors.textSecondary.opacity(0.5))
            .padding(.horizontal, compact ? MacSpacing.sm : MacSpacing.md)
            .padding(.vertical, MacSpacing.xs + 1)
            .background(isActive ? source.color.opacity(0.13) : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        }
        .buttonStyle(.plain)
    }

    // MARK: - Ambient Background

    private var ambientBackground: some View {
        ZStack {
            Circle()
                .fill(Color(red: 225/255, green: 113/255, blue: 0).opacity(0.04))
                .frame(width: 500, height: 500)
                .blur(radius: 120)
                .offset(x: 0, y: -100)

            Circle()
                .fill(Color(red: 245/255, green: 73/255, blue: 0).opacity(0.03))
                .frame(width: 400, height: 400)
                .blur(radius: 100)
                .offset(x: 100, y: 200)
        }
    }
}

// MARK: - Explorer Placeholder

struct ResearchExplorerPlaceholder: View {
    var body: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: "tablecells")
                .font(.system(size: 48))
                .foregroundStyle(MacColors.textSecondary.opacity(0.3))
            Text("Data Explorer")
                .font(.system(size: 18, weight: .medium))
                .foregroundStyle(MacColors.textSecondary)
            Text("Unified timeline of all your data sources.\nComing in the next sprint.")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textFaint)
                .multilineTextAlignment(.center)
            Spacer()
        }
    }
}

// MARK: - Research Models

enum ResearchMode {
    case graph
    case explorer
}

enum TimeRange: CaseIterable {
    case sevenDays, thirtyDays, ninetyDays, allTime

    var label: String {
        switch self {
        case .sevenDays: return "7 days"
        case .thirtyDays: return "30 days"
        case .ninetyDays: return "90 days"
        case .allTime: return "All time"
        }
    }
}

enum DataSource: CaseIterable {
    case chat, email, notes, calendar, reminders, health

    var label: String {
        switch self {
        case .chat: return "Chat"
        case .email: return "Email"
        case .notes: return "Notes"
        case .calendar: return "Calendar"
        case .reminders: return "Reminders"
        case .health: return "Health"
        }
    }

    var icon: String {
        switch self {
        case .chat: return "bubble.left"
        case .email: return "envelope"
        case .notes: return "note.text"
        case .calendar: return "calendar"
        case .reminders: return "checklist"
        case .health: return "heart"
        }
    }

    var color: Color {
        switch self {
        case .chat: return Color(red: 224/255, green: 160/255, blue: 80/255)
        case .email: return Color(red: 74/255, green: 158/255, blue: 255/255)
        case .notes: return Color(red: 0, green: 212/255, blue: 146/255)
        case .calendar: return Color(red: 176/255, green: 106/255, blue: 255/255)
        case .reminders: return Color(red: 255/255, green: 100/255, blue: 103/255)
        case .health: return Color(red: 44/255, green: 194/255, blue: 149/255)
        }
    }
}
