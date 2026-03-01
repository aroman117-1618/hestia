import SwiftUI
import HestiaShared

struct MacWikiView: View {
    @StateObject private var viewModel = WikiViewModel()
    @State private var showingGenerateAllAlert = false

    var body: some View {
        HStack(spacing: 0) {
            // Sidebar: tab buttons + article list
            MacWikiSidebarView(viewModel: viewModel)
                .frame(minWidth: 200, idealWidth: MacSize.fileSidebarWidth, maxWidth: 320)
                .background(MacColors.panelBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
                .overlay {
                    RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                        .strokeBorder(MacColors.cardBorder, lineWidth: 1)
                }

            // Detail pane
            MacWikiDetailPane(viewModel: viewModel)
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
            await viewModel.loadArticles()
        }
        .alert("Generate All Articles", isPresented: $showingGenerateAllAlert) {
            Button("Generate") {
                Task { await viewModel.generateAll() }
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This will generate all AI-written articles using the cloud LLM. Existing articles will be regenerated.")
        }
    }
}
