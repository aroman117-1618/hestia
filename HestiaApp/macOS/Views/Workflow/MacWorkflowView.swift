import SwiftUI
import HestiaShared

struct MacWorkflowView: View {
    @StateObject private var viewModel = WorkflowViewModel()

    var body: some View {
        HStack(spacing: 0) {
            // Sidebar: filter tabs + workflow list
            MacWorkflowSidebarView(viewModel: viewModel)
                .frame(minWidth: 200, idealWidth: MacSize.fileSidebarWidth, maxWidth: 320)
                .hestiaPanel()

            // Detail pane
            MacWorkflowDetailPane(viewModel: viewModel)
                .hestiaPanel()
        }
        .padding(MacSpacing.xl)
        .background(MacColors.windowBackground)
        .task {
            await viewModel.loadWorkflows()
        }
        .sheet(isPresented: $viewModel.showingNewWorkflowSheet) {
            MacNewWorkflowSheet(viewModel: viewModel)
        }
    }
}
