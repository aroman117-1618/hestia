import SwiftUI
import HestiaShared

// MARK: - Research View (3D Graph + Data Explorer modes)

struct ResearchView: View {
    @State private var selectedMode: ResearchMode = .graph
    @State private var selectedTimeRange: TimeRange = .thirtyDays
    @State private var searchText: String = ""
    @State private var graphNeedsRefresh = false
    // activeFilters derived from graphViewModel.activeDataSources
    @State private var hoveredNode: MacNeuralNetViewModel.GraphNode?
    @StateObject private var graphViewModel = MacNeuralNetViewModel()

    var body: some View {
        GeometryReader { geo in
            let isCompact = geo.size.width < 700

            VStack(spacing: 0) {
                headerBar(compact: isCompact)

                // Filter bar visible in graph and principles modes (not memory)
                if selectedMode != .memory {
                    filterBar(compact: isCompact)
                        .padding(.top, MacSpacing.sm)
                }

                // Main content: graph (+ optional detail panel), principles, or memory
                switch selectedMode {
                case .graph:
                    graphContentWithPanel
                case .principles:
                    ZStack {
                        ambientBackground
                        ResearchPrinciplesView(viewModel: graphViewModel)
                    }
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                case .memory:
                    MemoryBrowserView(onChunkEdited: { graphNeedsRefresh = true })
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
        }
        .background(MacColors.windowBackground)
        .onChange(of: selectedMode) { _, newMode in
            if newMode == .graph && graphNeedsRefresh {
                graphNeedsRefresh = false
                Task { await graphViewModel.loadGraph() }
            }
        }
        .onAppear {
            if graphViewModel.nodes.isEmpty && !graphViewModel.isLoading {
                Task { await graphViewModel.loadGraph() }
            }
        }
    }

    // MARK: - Graph Content with Detail Panel

    @ViewBuilder
    private var graphContentWithPanel: some View {
        if graphViewModel.isLoading {
            ZStack {
                ambientBackground
                graphLoadingState
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else if graphViewModel.nodes.isEmpty {
            ZStack {
                ambientBackground
                graphEmptyState
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            HStack(spacing: 0) {
                // Left: Graph view with overlays
                ZStack {
                    ambientBackground
                        .allowsHitTesting(false)

                    MacSceneKitGraphView(
                        nodes: graphViewModel.nodes,
                        edges: graphViewModel.edges,
                        selectedNode: $graphViewModel.selectedNode,
                        hoveredNode: $hoveredNode
                    )

                    // Legend overlay (bottom-left) — dynamic based on active node types
                    graphLegend
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottomLeading)
                        .padding(MacSpacing.lg)

                    // Node count badge (top-right of graph area)
                    if graphViewModel.memoryCount > 0 {
                        nodeCountBadge
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                            .padding(MacSpacing.lg)
                    }

                    // Hover tooltip
                    if let hovered = hoveredNode, graphViewModel.selectedNode?.id != hovered.id {
                        hoverTooltip(hovered)
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                            .padding(.top, MacSpacing.xxxl)
                            .allowsHitTesting(false)
                    }

                    // Time slider indicator (bottom-center, facts mode with time travel)
                    if graphViewModel.graphMode == .facts && graphViewModel.timeSliderEnabled && graphViewModel.timeSliderValue < 0.99 {
                        timeIndicatorBadge
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .bottom)
                            .padding(.bottom, MacSpacing.lg)
                    }

                    // Graph control panel (top-left overlay — must be inside ZStack, not HStack sibling)
                    GraphControlPanel(viewModel: graphViewModel)
                        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
                        .padding(MacSpacing.lg)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)

                // Right: Detail panel (slides in when node selected)
                if let selected = graphViewModel.selectedNode {
                    NodeDetailPopover(
                        node: selected,
                        connectedNodes: graphViewModel.selectedConnectedNodes,
                        viewModel: graphViewModel,
                        onClose: {
                            withAnimation(.easeInOut(duration: 0.15)) {
                                graphViewModel.selectedNode = nil
                            }
                        },
                        onSelectNode: { node in
                            withAnimation(.easeInOut(duration: 0.15)) {
                                graphViewModel.selectedNode = node
                            }
                        }
                    )
                    .frame(width: 300)
                    .transition(.move(edge: .trailing).combined(with: .opacity))
                }
            }
            .animation(.easeInOut(duration: 0.25), value: graphViewModel.selectedNode)
        }
    }

    // MARK: - Time Indicator Badge

    private var timeIndicatorBadge: some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: "clock.arrow.circlepath")
                .font(.system(size: 12))
            Text("Viewing: \(graphViewModel.timeSliderLabel)")
                .font(.system(size: 11, weight: .medium))
        }
        .foregroundStyle(MacColors.amberAccent)
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(
            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                .fill(Color(red: 17/255, green: 11/255, blue: 3/255).opacity(0.92))
                .overlay(
                    RoundedRectangle(cornerRadius: MacCornerRadius.search)
                        .strokeBorder(MacColors.amberAccent.opacity(0.2), lineWidth: 1)
                )
        )
    }

    // MARK: - Hover Tooltip

    private func hoverTooltip(_ node: MacNeuralNetViewModel.GraphNode) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: node.displayIcon)
                .font(.system(size: 11))
                .foregroundStyle(node.swiftUIColor)
            Text(node.label.isEmpty ? node.content : node.label)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(1)
            Text(node.displayName)
                .font(.system(size: 9))
                .foregroundStyle(MacColors.textFaint)
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(
            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                .fill(Color(red: 17/255, green: 11/255, blue: 3/255).opacity(0.92))
                .overlay(
                    RoundedRectangle(cornerRadius: MacCornerRadius.search)
                        .strokeBorder(node.swiftUIColor.opacity(0.2), lineWidth: 1)
                )
        )
    }

    // MARK: - Loading & Empty States

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

    // MARK: - Dynamic Legend

    /// Legend entry metadata for each node type.
    private static let legendEntries: [String: (label: String, icon: String, color: Color)] = [
        "memory":    ("Memory",    "brain",                   Color(red: 0.5, green: 0.5, blue: 0.5)),
        "topic":     ("Topic",     "tag",                     Color(red: 1.0, green: 0.84, blue: 0.04)),
        "entity":    ("Entity",    "person.text.rectangle",   Color(red: 0.19, green: 0.82, blue: 0.35)),
        "principle": ("Principle", "lightbulb",               Color(red: 0.75, green: 0.35, blue: 0.95)),
        "community": ("Community", "person.3",                Color(red: 1.0, green: 0.22, blue: 0.37)),
        "episode":   ("Episode",   "clock",                   Color(red: 0.35, green: 0.78, blue: 0.98)),
        "fact":      ("Fact",      "link",                    Color(red: 0.39, green: 0.82, blue: 1.0)),
    ]

    private var graphLegend: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            // Show entries for node types actually present in the graph
            ForEach(graphViewModel.activeNodeTypes, id: \.self) { nodeType in
                if let entry = Self.legendEntries[nodeType] {
                    legendDot(color: entry.color, icon: entry.icon, label: entry.label)
                }
            }

            // Also show memory chunk type breakdown when memory nodes are present
            if graphViewModel.activeNodeTypes.contains("memory") {
                MacColors.divider
                    .frame(height: 1)
                    .padding(.vertical, 2)
                Text("Memory types:")
                    .font(.system(size: 9).italic())
                    .foregroundStyle(MacColors.textFaint)
                legendColorDot(color: Color(red: 0.353, green: 0.784, blue: 0.980), label: "Chat")
                legendColorDot(color: Color(red: 0.557, green: 0.557, blue: 0.576), label: "Insight")
                legendColorDot(color: Color(red: 1.0, green: 0.584, blue: 0.0), label: "Preference")
                legendColorDot(color: Color(red: 0.298, green: 0.851, blue: 0.392), label: "Fact")
                legendColorDot(color: Color(red: 1.0, green: 0.231, blue: 0.188), label: "Decision")
                legendColorDot(color: Color(red: 0.686, green: 0.322, blue: 0.871), label: "Action")
                legendColorDot(color: Color(red: 0.0, green: 0.478, blue: 1.0), label: "Research")
            }

            MacColors.divider
                .frame(height: 1)
                .padding(.vertical, 2)
            Text("Node size = importance")
                .font(.system(size: 10).italic())
                .foregroundStyle(MacColors.textFaint)
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

    private func legendDot(color: Color, icon: String, label: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 9))
                .foregroundStyle(color)
                .frame(width: 12)
            Text(label)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textSecondary)
        }
    }

    private func legendColorDot(color: Color, label: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(label)
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textSecondary)
        }
    }

    private var nodeCountBadge: some View {
        Text("\(graphViewModel.nodes.count) nodes \u{00B7} \(graphViewModel.edges.count) edges")
            .font(.system(size: 10, weight: .medium))
            .foregroundStyle(MacColors.textSecondary)
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs)
            .background(
                RoundedRectangle(cornerRadius: MacCornerRadius.search)
                    .fill(Color(red: 17/255, green: 11/255, blue: 3/255).opacity(0.85))
            )
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

            // Refresh button (graph mode) or time range picker (principles mode); memory mode has no trailing control
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
                .buttonStyle(.hestia)
            } else if selectedMode == .principles {
                timeRangePicker(compact: compact)
            }
        }
        .padding(.horizontal, MacSpacing.xl)
        .padding(.vertical, MacSpacing.md)
    }

    private func modeToggle(compact: Bool) -> some View {
        HStack(spacing: 2) {
            modeButton(.graph,      icon: "point.3.connected.trianglepath.dotted", label: "Graph",      compact: compact)
            modeButton(.principles, icon: "lightbulb",                              label: "Principles", compact: compact)
            modeButton(.memory,     icon: "brain.head.profile",                    label: "Memory",     compact: compact)
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
        .buttonStyle(.hestia)
        .accessibilityLabel("\(label) mode")
        .accessibilityAddTraits(selectedMode == mode ? .isSelected : [])
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

    // MARK: - Filter Bar (both modes)

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
                .buttonStyle(.hestia)
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
        let isActive = graphViewModel.activeDataSources.contains(source.apiValue)

        return Button {
            withAnimation(.easeInOut(duration: 0.15)) {
                if isActive {
                    graphViewModel.activeDataSources.remove(source.apiValue)
                } else {
                    graphViewModel.activeDataSources.insert(source.apiValue)
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
        .buttonStyle(.hestia)
        .accessibilityLabel("\(source.label) filter, \(isActive ? "active" : "inactive")")
        .accessibilityAddTraits(isActive ? .isSelected : [])
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

// MARK: - Flow Layout (for tag pills)

struct FlowLayout: Layout {
    var spacing: CGFloat = 4

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let result = arrangeSubviews(proposal: proposal, subviews: subviews)
        return result.size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let result = arrangeSubviews(proposal: proposal, subviews: subviews)
        for (index, position) in result.positions.enumerated() {
            subviews[index].place(
                at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y),
                proposal: .unspecified
            )
        }
    }

    private func arrangeSubviews(proposal: ProposedViewSize, subviews: Subviews) -> ArrangementResult {
        let maxWidth = proposal.width ?? .infinity
        var positions: [CGPoint] = []
        var currentX: CGFloat = 0
        var currentY: CGFloat = 0
        var lineHeight: CGFloat = 0

        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            if currentX + size.width > maxWidth, currentX > 0 {
                currentX = 0
                currentY += lineHeight + spacing
                lineHeight = 0
            }
            positions.append(CGPoint(x: currentX, y: currentY))
            lineHeight = max(lineHeight, size.height)
            currentX += size.width + spacing
        }

        return ArrangementResult(
            positions: positions,
            size: CGSize(width: maxWidth, height: currentY + lineHeight)
        )
    }

    struct ArrangementResult {
        var positions: [CGPoint]
        var size: CGSize
    }
}

// MARK: - Principles View (replaces Explorer placeholder)

struct ResearchPrinciplesView: View {
    @ObservedObject var viewModel: MacNeuralNetViewModel

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Principles")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)

                Spacer()

                // Distill button
                Button {
                    Task { await viewModel.distillPrinciples() }
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        if viewModel.isDistilling {
                            ProgressView()
                                .controlSize(.mini)
                                .tint(MacColors.amberAccent)
                        } else {
                            Image(systemName: "sparkles")
                                .font(.system(size: 12))
                        }
                        Text(viewModel.isDistilling ? "Distilling..." : "Distill New")
                            .font(.system(size: 12, weight: .medium))
                    }
                    .foregroundStyle(MacColors.buttonTextDark)
                    .padding(.horizontal, MacSpacing.md)
                    .padding(.vertical, MacSpacing.sm)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.plain)
                .disabled(viewModel.isDistilling)
                .accessibilityLabel("Distill new principles from recent conversations")
            }
            .padding(.horizontal, MacSpacing.xl)
            .padding(.vertical, MacSpacing.md)

            // Content
            if viewModel.isLoadingPrinciples && viewModel.principles.isEmpty {
                Spacer()
                ProgressView()
                    .controlSize(.regular)
                Spacer()
            } else if viewModel.principles.isEmpty {
                principlesEmptyState
            } else {
                principlesList
            }
        }
        .task {
            await viewModel.loadPrinciples()
        }
    }

    // MARK: - Empty State

    private var principlesEmptyState: some View {
        VStack(spacing: MacSpacing.md) {
            Spacer()
            Image(systemName: "lightbulb")
                .font(.system(size: 48))
                .foregroundStyle(MacColors.textSecondary.opacity(0.3))
            Text("No principles yet")
                .font(.system(size: 18, weight: .medium))
                .foregroundStyle(MacColors.textSecondary)
            Text("Chat more to build your knowledge base,\nthen tap \"Distill New\" to extract patterns.")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textFaint)
                .multilineTextAlignment(.center)
            Spacer()
        }
    }

    // MARK: - Principles List

    private var principlesList: some View {
        ScrollView {
            LazyVStack(spacing: MacSpacing.md) {
                // Pending section
                let pending = viewModel.principles.filter(\.isPending)
                if !pending.isEmpty {
                    sectionHeader("Pending Review", count: pending.count, color: MacColors.statusWarning)
                    ForEach(pending) { principle in
                        principleCard(principle, showActions: true)
                    }
                }

                // Approved section
                let approved = viewModel.principles.filter(\.isApproved)
                if !approved.isEmpty {
                    sectionHeader("Approved", count: approved.count, color: MacColors.healthGreen)
                    ForEach(approved) { principle in
                        principleCard(principle, showActions: false)
                    }
                }

                // Rejected section
                let rejected = viewModel.principles.filter(\.isRejected)
                if !rejected.isEmpty {
                    sectionHeader("Rejected", count: rejected.count, color: MacColors.healthRed)
                    ForEach(rejected) { principle in
                        principleCard(principle, showActions: false)
                    }
                }
            }
            .padding(.horizontal, MacSpacing.xl)
            .padding(.bottom, MacSpacing.xl)
        }
    }

    private func sectionHeader(_ title: String, count: Int, color: Color) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Circle()
                .fill(color)
                .frame(width: 8, height: 8)
            Text(title)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(MacColors.textSecondary)
            Text("(\(count))")
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textFaint)
            Spacer()
        }
        .padding(.top, MacSpacing.md)
    }

    private func principleCard(_ principle: ResearchPrinciple, showActions: Bool) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            // Domain badge + confidence
            HStack {
                Text(principle.domain.capitalized)
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(MacColors.amberAccent)
                    .padding(.horizontal, MacSpacing.sm)
                    .padding(.vertical, 2)
                    .background(MacColors.amberAccent.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 4))

                Spacer()

                Text("\(Int(principle.confidence * 100))% confidence")
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textFaint)
            }

            // Content
            Text(principle.content)
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textPrimary)
                .fixedSize(horizontal: false, vertical: true)

            // Source info
            HStack(spacing: MacSpacing.sm) {
                if !principle.sourceChunkIds.isEmpty {
                    HStack(spacing: 2) {
                        Image(systemName: "link")
                            .font(.system(size: 9))
                        Text("\(principle.sourceChunkIds.count) sources")
                            .font(.system(size: 10))
                    }
                    .foregroundStyle(MacColors.textFaint)
                }

                if !principle.topics.isEmpty {
                    HStack(spacing: 2) {
                        Image(systemName: "tag")
                            .font(.system(size: 9))
                        Text(principle.topics.prefix(3).joined(separator: ", "))
                            .font(.system(size: 10))
                            .lineLimit(1)
                    }
                    .foregroundStyle(MacColors.textFaint)
                }

                Spacer()

                if let dateStr = principle.createdAt,
                   let date = ISO8601DateFormatter().date(from: dateStr) {
                    Text(date, style: .relative)
                        .font(.system(size: 10))
                        .foregroundStyle(MacColors.textFaint)
                }
            }

            // Approve/Reject buttons (pending only)
            if showActions {
                HStack(spacing: MacSpacing.sm) {
                    Button {
                        Task { await viewModel.approvePrinciple(principle.id) }
                    } label: {
                        HStack(spacing: MacSpacing.xs) {
                            Image(systemName: "checkmark")
                                .font(.system(size: 11))
                            Text("Approve")
                                .font(.system(size: 12, weight: .medium))
                        }
                        .foregroundStyle(MacColors.buttonTextDark)
                        .padding(.horizontal, MacSpacing.md)
                        .padding(.vertical, MacSpacing.sm)
                        .background(MacColors.healthGreen)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                    }
                    .buttonStyle(.plain)

                    Button {
                        Task { await viewModel.rejectPrinciple(principle.id) }
                    } label: {
                        HStack(spacing: MacSpacing.xs) {
                            Image(systemName: "xmark")
                                .font(.system(size: 11))
                            Text("Reject")
                                .font(.system(size: 12, weight: .medium))
                        }
                        .foregroundStyle(MacColors.healthRed)
                        .padding(.horizontal, MacSpacing.md)
                        .padding(.vertical, MacSpacing.sm)
                        .overlay(
                            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                                .strokeBorder(MacColors.healthRed.opacity(0.3), lineWidth: 1)
                        )
                    }
                    .buttonStyle(.plain)

                    Spacer()
                }
            }
        }
        .padding(MacSpacing.lg)
        .background(MacColors.cardGradient)
        .overlay(
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .accessibilityElement(children: .contain)
        .accessibilityLabel("\(principle.domain) principle: \(principle.content)")
    }
}

// MARK: - Research Models

enum ResearchMode {
    case graph
    case principles
    case memory
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

    /// API parameter value matching backend MemorySource enum.
    var apiValue: String {
        switch self {
        case .chat: return "conversation"
        case .email: return "mail"
        case .notes: return "notes"
        case .calendar: return "calendar"
        case .reminders: return "reminders"
        case .health: return "health"
        }
    }
}
