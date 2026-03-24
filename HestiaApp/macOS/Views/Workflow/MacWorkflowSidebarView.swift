import SwiftUI
import HestiaShared

struct MacWorkflowSidebarView: View {
    @ObservedObject var viewModel: WorkflowViewModel

    var body: some View {
        VStack(spacing: 0) {
            // Header
            header
                .padding(.horizontal, MacSpacing.lg)
                .padding(.top, MacSpacing.lg)
                .padding(.bottom, MacSpacing.md)

            // Filter tabs
            filterTabs
                .padding(.horizontal, MacSpacing.md)
                .padding(.bottom, MacSpacing.sm)

            Divider()
                .foregroundStyle(MacColors.cardBorder)

            // Workflow list
            workflowList
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack {
            Text("Workflows")
                .font(MacTypography.sectionTitle)
                .foregroundStyle(MacColors.textPrimary)

            Spacer()

            Button {
                viewModel.showingNewWorkflowSheet = true
            } label: {
                Image(systemName: "plus")
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(MacColors.amberAccent)
                    .frame(width: 28, height: 28)
                    .background(MacColors.activeTabBackground)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
            }
            .buttonStyle(.hestia)
            .help("Create new workflow")
        }
    }

    // MARK: - Filter Tabs

    private var filterTabs: some View {
        HStack(spacing: 4) {
            filterTab(nil, label: "All")
            filterTab(.active, label: "Active")
            filterTab(.draft, label: "Draft")
            filterTab(.archived, label: "Archived")
        }
    }

    private func filterTab(_ status: WorkflowStatus?, label: String) -> some View {
        let isActive = viewModel.statusFilter == status
        return Button {
            withAnimation(.easeInOut(duration: 0.15)) {
                viewModel.statusFilter = status
            }
        } label: {
            Text(label)
                .font(.system(size: 11, weight: isActive ? .semibold : .regular))
                .foregroundStyle(isActive ? MacColors.amberAccent : MacColors.textSecondary)
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, 4)
                .background(isActive ? MacColors.activeTabBackground : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        }
        .buttonStyle(.hestia)
    }

    // MARK: - Workflow List

    private var workflowList: some View {
        ScrollView {
            LazyVStack(spacing: 2) {
                ForEach(viewModel.filteredWorkflows) { workflow in
                    MacWorkflowRow(
                        workflow: workflow,
                        isSelected: viewModel.selectedWorkflowId == workflow.id
                    )
                    .contentShape(Rectangle())
                    .onTapGesture {
                        withAnimation(.easeInOut(duration: 0.15)) {
                            viewModel.selectWorkflow(workflow)
                        }
                    }
                }

                if viewModel.filteredWorkflows.isEmpty && !viewModel.isLoading {
                    if let error = viewModel.errorMessage {
                        errorState(error)
                    } else {
                        emptyState
                    }
                }

                if viewModel.isLoading {
                    ProgressView()
                        .controlSize(.small)
                        .padding(.top, MacSpacing.xxxl)
                }
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.top, MacSpacing.sm)
        }
    }

    // MARK: - Empty / Error States

    private var emptyState: some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "arrow.triangle.branch")
                .font(.system(size: 28))
                .foregroundStyle(MacColors.textFaint)
            Text("No workflows yet")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textSecondary)
            Text("Create one to automate tasks")
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textFaint)
                .multilineTextAlignment(.center)
        }
        .padding(.top, MacSpacing.xxxl)
    }

    private func errorState(_ message: String) -> some View {
        VStack(spacing: MacSpacing.md) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 28))
                .foregroundStyle(MacColors.healthRed)
            Text(message)
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textSecondary)
                .multilineTextAlignment(.center)
            Button {
                Task { await viewModel.loadWorkflows() }
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: "arrow.clockwise")
                    Text("Retry")
                }
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(MacColors.amberAccent)
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, 4)
                .background(MacColors.activeTabBackground)
                .cornerRadius(MacCornerRadius.treeItem)
            }
            .buttonStyle(.hestia)
        }
        .padding(.top, MacSpacing.xxxl)
    }
}
