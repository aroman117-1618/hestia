import SwiftUI
import HestiaShared

struct MacWorkflowView: View {
    @StateObject private var viewModel = WorkflowViewModel()

    var body: some View {
        HStack(spacing: 0) {
            // Sidebar: filter tabs + workflow list
            MacWorkflowSidebarView(viewModel: viewModel)
                .frame(minWidth: 200, idealWidth: MacSize.fileSidebarWidth, maxWidth: 320)
                .background(MacColors.panelBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
                .overlay {
                    RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                        .strokeBorder(MacColors.cardBorder, lineWidth: 1)
                }

            // Detail pane
            MacWorkflowDetailPane(viewModel: viewModel)
                .background(MacColors.panelBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
                .overlay {
                    RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                        .strokeBorder(MacColors.cardBorder, lineWidth: 1)
                }
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
