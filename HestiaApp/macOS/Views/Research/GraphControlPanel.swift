import SwiftUI

/// Floating control panel for graph filtering and display options.
/// Overlays the top-left of the graph area.
struct GraphControlPanel: View {
    @ObservedObject var viewModel: MacNeuralNetViewModel
    @State private var isExpanded = false

    /// All available node types with display metadata.
    private static let allNodeTypes: [(key: String, label: String, icon: String)] = [
        ("memory",    "Memories",    "brain"),
        ("topic",     "Topics",      "tag"),
        ("entity",    "Entities",    "person.text.rectangle"),
        ("principle", "Principles",  "lightbulb"),
        ("community", "Communities", "person.3"),
        ("episode",   "Episodes",    "clock"),
        ("fact",      "Facts",       "link"),
    ]

    /// Node types relevant to the current graph mode.
    private var visibleNodeTypes: [(key: String, label: String, icon: String)] {
        switch viewModel.graphMode {
        case .legacy:
            return Self.allNodeTypes.filter { ["memory", "topic", "entity", "principle"].contains($0.key) }
        case .facts:
            return Self.allNodeTypes.filter { ["entity", "community", "episode", "fact"].contains($0.key) }
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // Toggle header
            Button {
                withAnimation(.easeInOut(duration: MacColors.animationNormal)) {
                    isExpanded.toggle()
                }
            } label: {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: "slider.horizontal.3")
                        .font(.system(size: 12))
                    Text("Filters")
                        .font(.system(size: 12, weight: .medium))
                    Spacer()
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 10))
                }
                .foregroundStyle(MacColors.textSecondary)
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, MacSpacing.sm)
            }
            .buttonStyle(.plain)

            if isExpanded {
                MacColors.divider.frame(height: 1)
                    .padding(.horizontal, MacSpacing.sm)

                VStack(alignment: .leading, spacing: MacSpacing.md) {
                    // Graph mode toggle
                    graphModeSection

                    MacColors.divider.frame(height: 1)

                    // Node type toggles
                    nodeTypesSection

                    MacColors.divider.frame(height: 1)

                    // Focus topic / center entity
                    searchSection

                    // Time slider (facts mode only)
                    if viewModel.graphMode == .facts {
                        MacColors.divider.frame(height: 1)
                        timeSliderSection
                    }

                    // Durability filter (facts mode)
                    if viewModel.graphMode == .facts {
                        MacColors.divider.frame(height: 1)
                        durabilitySection
                    }

                    // Source category filter (facts mode)
                    if viewModel.graphMode == .facts {
                        MacColors.divider.frame(height: 1)
                        sourceCategorySection
                    }

                    // Apply button
                    Button {
                        Task { await viewModel.loadGraph() }
                    } label: {
                        Text("Apply Filters")
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(MacColors.buttonTextDark)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, MacSpacing.sm)
                            .background(MacColors.amberAccent)
                            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                    }
                    .buttonStyle(.plain)
                }
                .padding(MacSpacing.md)
            }
        }
        .frame(width: 200)
        .background(
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .fill(Color(red: 17/255, green: 11/255, blue: 3/255).opacity(0.92))
                .overlay(
                    RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                        .strokeBorder(MacColors.cardBorder, lineWidth: 1)
                )
        )
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Graph filters")
    }

    // MARK: - Graph Mode Toggle

    private var graphModeSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("GRAPH MODE")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(MacColors.textFaint)
                .tracking(1)

            HStack(spacing: 2) {
                ForEach(GraphMode.allCases, id: \.rawValue) { mode in
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            viewModel.graphMode = mode
                        }
                    } label: {
                        HStack(spacing: MacSpacing.xs) {
                            Image(systemName: mode.icon)
                                .font(.system(size: 11))
                            Text(mode.label)
                                .font(.system(size: 11, weight: .medium))
                        }
                        .foregroundStyle(viewModel.graphMode == mode ? MacColors.amberAccent : MacColors.textSecondary)
                        .padding(.horizontal, MacSpacing.sm)
                        .padding(.vertical, MacSpacing.xs + 1)
                        .background(viewModel.graphMode == mode ? MacColors.amberAccent.opacity(0.15) : Color.clear)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("\(mode.label) graph mode")
                    .accessibilityAddTraits(viewModel.graphMode == mode ? .isSelected : [])
                }
            }
            .padding(2)
            .background(MacColors.textPrimary.opacity(0.04))
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
        }
    }

    // MARK: - Node Types

    private var nodeTypesSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("NODE TYPES")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(MacColors.textFaint)
                .tracking(1)

            ForEach(visibleNodeTypes, id: \.key) { type in
                nodeTypeToggle(key: type.key, label: type.label, icon: type.icon)
            }
        }
    }

    // MARK: - Search / Focus

    private var searchSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            if viewModel.graphMode == .legacy {
                Text("FOCUS TOPIC")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(MacColors.textFaint)
                    .tracking(1)

                searchField(text: $viewModel.focusTopic, placeholder: "Filter by topic...")
            } else {
                Text("CENTER ENTITY")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(MacColors.textFaint)
                    .tracking(1)

                searchField(text: $viewModel.centerEntity, placeholder: "Center on entity...")
            }
        }
    }

    private func searchField(text: Binding<String>, placeholder: String) -> some View {
        HStack(spacing: MacSpacing.xs) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textPlaceholder)
            TextField(placeholder, text: text)
                .textFieldStyle(.plain)
                .font(.system(size: 12))
                .foregroundStyle(MacColors.textPrimary)
                .onSubmit {
                    Task { await viewModel.loadGraph() }
                }
        }
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, MacSpacing.xs + 1)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Time Slider (Facts Mode)

    private var timeSliderSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack {
                Text("TIME TRAVEL")
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(MacColors.textFaint)
                    .tracking(1)

                Spacer()

                Toggle("", isOn: $viewModel.timeSliderEnabled)
                    .toggleStyle(.switch)
                    .controlSize(.mini)
                    .labelsHidden()
            }

            if viewModel.timeSliderEnabled {
                Slider(value: $viewModel.timeSliderValue, in: 0...1)
                    .controlSize(.mini)
                    .tint(MacColors.amberAccent)
                    .onChange(of: viewModel.timeSliderValue) { _, newValue in
                        viewModel.timeSliderDate = viewModel.dateFromSliderValue(newValue)
                        viewModel.onTimeSliderChanged()
                    }

                HStack(spacing: MacSpacing.xs) {
                    Text(viewModel.timeSliderLabel)
                        .font(.system(size: 10))
                        .foregroundStyle(MacColors.textSecondary)
                    if viewModel.isLoading {
                        ProgressView()
                            .controlSize(.mini)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .center)
            }
        }
    }

    // MARK: - Durability Filter (Sprint 20A)

    private static let durabilityLabels = [
        "All",          // 0
        "Contextual+",  // 1 (DIKW: Information+)
        "Durable+",     // 2 (DIKW: Knowledge+)
        "Principled",   // 3 (DIKW: Wisdom)
    ]

    private var durabilitySection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("SIGNIFICANCE")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(MacColors.textFaint)
                .tracking(1)

            Picker("", selection: $viewModel.minDurabilityFilter) {
                ForEach(0..<4, id: \.self) { level in
                    Text(Self.durabilityLabels[level]).tag(level)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()
            .controlSize(.small)

            Text(durabilityDescription)
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textFaint)
                .lineLimit(2)
        }
    }

    private var durabilityDescription: String {
        switch viewModel.minDurabilityFilter {
        case 0: return "Showing all non-ephemeral nodes"
        case 1: return "Hiding ephemeral, showing contextual+"
        case 2: return "Only durable and principled facts"
        case 3: return "Only permanent principles"
        default: return ""
        }
    }

    // MARK: - Source Categories (Sprint 20B)

    private var sourceCategorySection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("SOURCES")
                .font(.system(size: 9, weight: .bold))
                .foregroundStyle(MacColors.textFaint)
                .tracking(1)

            // Wrap pills in a flow layout
            let columns = [GridItem(.flexible()), GridItem(.flexible())]
            LazyVGrid(columns: columns, spacing: 4) {
                ForEach(SourceCategoryFilter.allCases, id: \.rawValue) { category in
                    sourceCategoryPill(category)
                }
            }
        }
    }

    private func sourceCategoryPill(_ category: SourceCategoryFilter) -> some View {
        let isActive = viewModel.activeSourceCategories.contains(category.rawValue)

        return Button {
            if isActive {
                viewModel.activeSourceCategories.remove(category.rawValue)
            } else {
                viewModel.activeSourceCategories.insert(category.rawValue)
            }
        } label: {
            HStack(spacing: 3) {
                Image(systemName: category.icon)
                    .font(.system(size: 9))
                Text(category.label)
                    .font(.system(size: 10, weight: .medium))
            }
            .foregroundStyle(isActive ? MacColors.amberAccent : MacColors.textFaint)
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, 3)
            .background(isActive ? MacColors.amberAccent.opacity(0.15) : MacColors.textPrimary.opacity(0.04))
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(category.label) source, \(isActive ? "active" : "inactive")")
        .accessibilityAddTraits(isActive ? .isSelected : [])
    }

    // MARK: - Helpers

    private func nodeTypeToggle(key: String, label: String, icon: String) -> some View {
        let isActive = viewModel.nodeTypeFilter.contains(key)

        return Button {
            if isActive {
                viewModel.nodeTypeFilter.remove(key)
            } else {
                viewModel.nodeTypeFilter.insert(key)
            }
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: isActive ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 12))
                    .foregroundStyle(isActive ? MacColors.amberAccent : MacColors.textFaint)
                Image(systemName: icon)
                    .font(.system(size: 11))
                    .foregroundStyle(isActive ? MacColors.textPrimary : MacColors.textSecondary)
                    .frame(width: 16)
                Text(label)
                    .font(.system(size: 12))
                    .foregroundStyle(isActive ? MacColors.textPrimary : MacColors.textSecondary)
                Spacer()
            }
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(label), \(isActive ? "active" : "inactive")")
        .accessibilityAddTraits(isActive ? .isSelected : [])
    }
}
