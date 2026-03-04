import SwiftUI

/// Floating control panel for graph filtering and display options.
/// Overlays the top-left of the graph area.
struct GraphControlPanel: View {
    @ObservedObject var viewModel: MacNeuralNetViewModel
    @State private var isExpanded = false

    private let nodeTypes: [(key: String, label: String, icon: String)] = [
        ("memory", "Memories", "brain"),
        ("topic", "Topics", "tag"),
        ("entity", "Entities", "person.text.rectangle"),
    ]

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
                    // Node type toggles
                    VStack(alignment: .leading, spacing: MacSpacing.sm) {
                        Text("NODE TYPES")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundStyle(MacColors.textFaint)
                            .tracking(1)

                        ForEach(nodeTypes, id: \.key) { type in
                            nodeTypeToggle(key: type.key, label: type.label, icon: type.icon)
                        }
                    }

                    MacColors.divider.frame(height: 1)

                    // Focus topic
                    VStack(alignment: .leading, spacing: MacSpacing.sm) {
                        Text("FOCUS TOPIC")
                            .font(.system(size: 9, weight: .bold))
                            .foregroundStyle(MacColors.textFaint)
                            .tracking(1)

                        HStack(spacing: MacSpacing.xs) {
                            Image(systemName: "magnifyingglass")
                                .font(.system(size: 11))
                                .foregroundStyle(MacColors.textPlaceholder)
                            TextField("Filter by topic...", text: $viewModel.focusTopic)
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
        .frame(width: 180)
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
