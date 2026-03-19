import SwiftUI
import HestiaShared

struct ExplorerView: View {
    @StateObject private var filesViewModel = MacExplorerFilesViewModel()
    @StateObject private var inboxViewModel = MacInboxViewModel()
    @State private var explorerMode: ExplorerMode = .files

    enum ExplorerMode: String, CaseIterable {
        case files = "Files"
        case inbox = "Inbox"
    }

    /// Sub-mode within Files tab: filesystem browser or resources aggregation.
    enum FilesSubMode: String, CaseIterable {
        case filesystem = "Filesystem"
        case resources = "Resources"
    }

    @State private var filesSubMode: FilesSubMode = .filesystem

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
                .frame(maxWidth: 200)

                // Files sub-mode picker (only when Files tab is active)
                if explorerMode == .files {
                    Picker("", selection: $filesSubMode) {
                        ForEach(FilesSubMode.allCases, id: \.self) { sub in
                            Text(sub.rawValue).tag(sub)
                        }
                    }
                    .pickerStyle(.segmented)
                    .tint(MacColors.amberAccent)
                    .frame(maxWidth: 220)
                }

                Spacer()
            }
            .padding(.horizontal, MacSpacing.xl)
            .padding(.top, MacSpacing.md)
            .padding(.bottom, MacSpacing.sm)

            // Content
            switch explorerMode {
            case .files:
                switch filesSubMode {
                case .filesystem:
                    ExplorerFilesView(viewModel: filesViewModel)
                case .resources:
                    MacExplorerResourcesView()
                }
            case .inbox:
                ExplorerInboxView(viewModel: inboxViewModel)
            }
        }
        .background(MacColors.windowBackground)
    }
}
