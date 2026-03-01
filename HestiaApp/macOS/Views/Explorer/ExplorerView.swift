import SwiftUI
import HestiaShared

struct ExplorerView: View {
    @StateObject private var viewModel = MacExplorerViewModel()
    @State private var explorerMode: ExplorerMode = .files

    enum ExplorerMode: String, CaseIterable {
        case files = "Files"
        case resources = "Resources"
    }

    var body: some View {
        VStack(spacing: 0) {
            // Mode picker
            HStack {
                Picker("", selection: $explorerMode) {
                    ForEach(ExplorerMode.allCases, id: \.self) { mode in
                        Text(mode.rawValue).tag(mode)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 200)

                Spacer()
            }
            .padding(.horizontal, MacSpacing.xl)
            .padding(.top, MacSpacing.md)
            .padding(.bottom, MacSpacing.sm)

            // Content
            switch explorerMode {
            case .files:
                filesView
            case .resources:
                MacExplorerResourcesView()
            }
        }
        .background(MacColors.windowBackground)
    }

    // MARK: - Files View (original)

    private var filesView: some View {
        HStack(spacing: 0) {
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
        .padding(.horizontal, MacSpacing.xl)
        .padding(.bottom, MacSpacing.xl)
    }
}
