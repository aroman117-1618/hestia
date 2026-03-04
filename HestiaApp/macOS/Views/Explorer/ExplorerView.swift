import SwiftUI
import HestiaShared

struct ExplorerView: View {
    @StateObject private var filesViewModel = MacExplorerFilesViewModel()
    @StateObject private var inboxViewModel = MacInboxViewModel()
    @State private var explorerMode: ExplorerMode = .files

    enum ExplorerMode: String, CaseIterable {
        case files = "Files"
        case inbox = "Inbox"
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
                .tint(MacColors.amberAccent)
                .frame(maxWidth: 300)

                Spacer()
            }
            .padding(.horizontal, MacSpacing.xl)
            .padding(.top, MacSpacing.md)
            .padding(.bottom, MacSpacing.sm)

            // Content
            switch explorerMode {
            case .files:
                ExplorerFilesView(viewModel: filesViewModel)
            case .inbox:
                ExplorerInboxView(viewModel: inboxViewModel)
            case .resources:
                MacExplorerResourcesView()
            }
        }
        .background(MacColors.windowBackground)
    }
}
