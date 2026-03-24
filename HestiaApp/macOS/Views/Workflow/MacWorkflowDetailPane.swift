import SwiftUI
import HestiaShared

struct MacWorkflowDetailPane: View {
    @ObservedObject var viewModel: WorkflowViewModel

    var body: some View {
        Group {
            if let detail = viewModel.selectedDetail {
                detailContent(detail)
            } else if viewModel.isLoadingDetail {
                ProgressView()
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                landingView
            }
        }
    }

    // MARK: - Landing (no selection)

    private var landingView: some View {
        VStack(spacing: MacSpacing.lg) {
            Image(systemName: "arrow.triangle.branch")
                .font(.system(size: 40))
                .foregroundStyle(MacColors.textFaint)
            Text("Select a workflow")
                .font(MacTypography.sectionTitle)
                .foregroundStyle(MacColors.textSecondary)
            Text("Choose a workflow from the sidebar to view its details, nodes, and run history.")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textFaint)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 300)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Detail Content

    private func detailContent(_ detail: WorkflowDetail) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            // Header + action bar always visible
            VStack(alignment: .leading, spacing: MacSpacing.xl) {
                detailHeader(detail)
                actionBar(detail)
                Divider().foregroundStyle(MacColors.cardBorder)
            }
            .padding(MacSpacing.xl)
            .padding(.bottom, 0)

            // Canvas / List content
            if viewModel.showCanvas {
                HStack(spacing: 0) {
                    WorkflowCanvasWebView(
                        workflowDetail: detail,
                        nodeStatuses: viewModel.nodeStatuses,
                        onNodeSelected: { viewModel.handleNodeSelected($0) },
                        onNodesMoved: { viewModel.handleNodesMoved($0) },
                        onEdgeCreated: { s, t, h in viewModel.handleEdgeCreated(s, t, h) },
                        onNodeDeleted: { viewModel.handleNodeDeleted($0) },
                        onEdgeDeleted: { viewModel.handleEdgeDeleted($0) }
                    )
                    .frame(maxWidth: .infinity, maxHeight: .infinity)

                    // Node inspector sidebar — shown when a node is selected
                    if let nodeId = viewModel.selectedNodeId,
                       let node = detail.nodes.first(where: { $0.id == nodeId }) {
                        Divider()
                        MacNodeInspectorView(viewModel: viewModel, node: node)
                            .transition(.move(edge: .trailing).combined(with: .opacity))
                    }
                }
                .animation(.easeInOut(duration: 0.15), value: viewModel.selectedNodeId)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: MacSpacing.xl) {
                        // Metadata
                        metadataSection(detail)

                        // Nodes
                        if !detail.nodes.isEmpty {
                            nodesSection(detail)
                        }

                        // Run history
                        if !viewModel.runs.isEmpty {
                            runsSection
                        }
                    }
                    .padding(MacSpacing.xl)
                    .padding(.top, MacSpacing.md)
                }
            }
        }
    }

    // MARK: - Header

    private func detailHeader(_ detail: WorkflowDetail) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack {
                Text(detail.name)
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)

                Spacer()

                // Status badge
                Text(detail.status.capitalized)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(statusColor(detail.statusEnum))
                    .padding(.horizontal, MacSpacing.sm)
                    .padding(.vertical, 4)
                    .background(statusColor(detail.statusEnum).opacity(0.15))
                    .clipShape(RoundedRectangle(cornerRadius: 6))

                // Canvas/List toggle
                Button {
                    withAnimation(.easeInOut(duration: 0.15)) {
                        viewModel.showCanvas.toggle()
                    }
                } label: {
                    Image(systemName: viewModel.showCanvas ? "list.bullet" : "square.grid.3x3")
                        .font(.system(size: 13))
                        .foregroundStyle(MacColors.textSecondary)
                        .frame(width: 28, height: 28)
                        .background(MacColors.searchInputBackground)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
                }
                .buttonStyle(.hestia)
                .help(viewModel.showCanvas ? "Switch to list view" : "Switch to canvas view")
            }

            if !detail.description.isEmpty {
                Text(detail.description)
                    .font(.system(size: 13))
                    .foregroundStyle(MacColors.textSecondary)
                    .lineLimit(3)
            }
        }
    }

    // MARK: - Action Bar

    private func actionBar(_ detail: WorkflowDetail) -> some View {
        HStack(spacing: MacSpacing.md) {
            // Trigger / Run
            if detail.statusEnum == .active {
                actionButton("Run Now", icon: "play.fill", color: MacColors.healthGreen) {
                    Task { await viewModel.triggerWorkflow(detail.id) }
                }
            }

            // Activate / Deactivate
            switch detail.statusEnum {
            case .draft, .inactive:
                actionButton("Activate", icon: "bolt.fill", color: MacColors.amberAccent) {
                    Task { await viewModel.activateWorkflow(detail.id) }
                }
            case .active:
                actionButton("Deactivate", icon: "pause.fill", color: MacColors.textSecondary) {
                    Task { await viewModel.deactivateWorkflow(detail.id) }
                }
            case .archived:
                EmptyView()
            }

            Spacer()

            // Delete
            actionButton("Delete", icon: "trash", color: MacColors.healthRed) {
                Task { await viewModel.deleteWorkflow(detail.id) }
            }
        }
    }

    private func actionButton(_ label: String, icon: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Image(systemName: icon)
                    .font(.system(size: 11))
                Text(label)
                    .font(.system(size: 12, weight: .medium))
            }
            .foregroundStyle(color)
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, 6)
            .background(color.opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        }
        .buttonStyle(.hestia)
    }

    // MARK: - Metadata

    private func metadataSection(_ detail: WorkflowDetail) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            Text("Details")
                .font(MacTypography.cardTitle)
                .foregroundStyle(MacColors.textPrimary)

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: MacSpacing.lg),
                GridItem(.flexible(), spacing: MacSpacing.lg),
                GridItem(.flexible(), spacing: MacSpacing.lg),
            ], spacing: MacSpacing.md) {
                metadataItem("Trigger", detail.triggerType.capitalized, icon: "bolt")
                metadataItem("Strategy", detail.sessionStrategy.replacingOccurrences(of: "_", with: " ").capitalized, icon: "gearshape")
                metadataItem("Version", "v\(detail.version)", icon: "number")
                metadataItem("Nodes", "\(detail.nodes.count)", icon: "circle.grid.3x3")
                metadataItem("Runs", "\(detail.runCount)", icon: "play.circle")
                metadataItem("Success", detail.runCount > 0 ? "\(Int(detail.successRate * 100))%" : "—", icon: "checkmark.circle")
            }
        }
    }

    private func metadataItem(_ label: String, _ value: String, icon: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textFaint)
                .frame(width: 16)
            VStack(alignment: .leading, spacing: 1) {
                Text(label)
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textFaint)
                Text(value)
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(MacColors.textPrimary)
            }
        }
    }

    // MARK: - Nodes Section

    private func nodesSection(_ detail: WorkflowDetail) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            Text("Nodes")
                .font(MacTypography.cardTitle)
                .foregroundStyle(MacColors.textPrimary)

            ForEach(detail.nodes) { node in
                MacWorkflowNodeRow(node: node)
            }
        }
    }

    // MARK: - Runs Section

    private var runsSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            Text("Recent Runs")
                .font(MacTypography.cardTitle)
                .foregroundStyle(MacColors.textPrimary)

            ForEach(viewModel.runs.prefix(10)) { run in
                runRow(run)
            }
        }
    }

    private func runRow(_ run: WorkflowRunResponse) -> some View {
        HStack(spacing: MacSpacing.md) {
            // Status icon
            Image(systemName: runStatusIcon(run.statusEnum))
                .font(.system(size: 12))
                .foregroundStyle(runStatusColor(run.statusEnum))
                .frame(width: 20)

            VStack(alignment: .leading, spacing: 1) {
                Text("Run \(run.id.suffix(8))")
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(MacColors.textPrimary)
                Text(run.startedAt)
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textFaint)
            }

            Spacer()

            if let duration = run.durationText {
                Text(duration)
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textSecondary)
            }

            Text(run.status.capitalized)
                .font(.system(size: 10, weight: .medium))
                .foregroundStyle(runStatusColor(run.statusEnum))
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
                .background(runStatusColor(run.statusEnum).opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 4))
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
    }

    // MARK: - Helpers

    private func statusColor(_ status: WorkflowStatus) -> Color {
        switch status {
        case .active: return MacColors.healthGreen
        case .draft: return MacColors.amberAccent
        case .inactive: return MacColors.textFaint
        case .archived: return MacColors.textFaint.opacity(0.5)
        }
    }

    private func runStatusIcon(_ status: WorkflowRunStatus) -> String {
        switch status {
        case .pending: return "clock"
        case .running: return "play.circle.fill"
        case .success: return "checkmark.circle.fill"
        case .failed: return "xmark.circle.fill"
        case .cancelled: return "minus.circle.fill"
        }
    }

    private func runStatusColor(_ status: WorkflowRunStatus) -> Color {
        switch status {
        case .pending: return MacColors.textFaint
        case .running: return MacColors.amberAccent
        case .success: return MacColors.healthGreen
        case .failed: return MacColors.healthRed
        case .cancelled: return MacColors.textFaint
        }
    }
}
