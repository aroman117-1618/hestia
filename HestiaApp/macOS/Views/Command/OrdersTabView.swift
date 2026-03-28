import SwiftUI
import HestiaShared

struct OrdersTabView: View {
    @StateObject private var viewModel = WorkflowViewModel()

    var body: some View {
        HStack(spacing: 0) {
            MacWorkflowSidebarView(viewModel: viewModel)
                .frame(minWidth: 200, idealWidth: MacSize.fileSidebarWidth, maxWidth: 280)
                .hestiaPanel()

            MacWorkflowDetailPane(viewModel: viewModel)
                .hestiaPanel()
        }
        .task {
            viewModel.showCanvas = true
            await viewModel.loadWorkflows()
        }
        .sheet(isPresented: $viewModel.showingNewWorkflowSheet) {
            MacNewWorkflowSheet(viewModel: viewModel)
        }
    }
}
