import SwiftUI
import HestiaShared

struct ExplorerView: View {
    @StateObject private var viewModel = MacExplorerViewModel()

    var body: some View {
        HStack(spacing: 0) {
            // File tree sidebar (280px)
            VStack(spacing: 0) {
                FileSearchBar(searchText: $viewModel.searchText)

                FileTreeView(
                    nodes: viewModel.filteredNodes,
                    selectedFile: viewModel.selectedFile,
                    onSelect: { viewModel.selectFile($0) },
                    onToggle: { viewModel.toggleExpansion($0) }
                )
            }
            .frame(width: MacSize.fileSidebarWidth)
            .background(MacColors.panelBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
            .overlay {
                RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                    .strokeBorder(MacColors.cardBorder, lineWidth: 1)
            }

            // Document preview (flex)
            FilePreviewArea(
                selectedFile: viewModel.selectedFile,
                content: viewModel.previewContent,
                isLoading: viewModel.isLoadingPreview,
                onSelectFolder: { viewModel.selectRootFolder() }
            )
            .background(MacColors.panelBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
            .overlay {
                RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                    .strokeBorder(MacColors.cardBorder, lineWidth: 1)
            }
        }
        .padding(MacSpacing.xl)
        .background(MacColors.windowBackground)
        .onAppear {
            if !viewModel.hasRootFolder {
                viewModel.selectRootFolder()
            }
        }
    }
}
