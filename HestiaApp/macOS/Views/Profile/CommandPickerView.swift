import SwiftUI
import HestiaShared

struct CommandPickerView: View {
    @StateObject private var viewModel = MacUserProfileViewModel()
    @State private var searchText = ""
    let onSelect: (String) -> Void

    private var filteredCommands: [CommandInfo] {
        if searchText.isEmpty {
            return viewModel.commands
        }
        let query = searchText.lowercased()
        return viewModel.commands.filter {
            $0.name.lowercased().contains(query) ||
            $0.description.lowercased().contains(query)
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            // Search
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 12))
                    .foregroundStyle(MacColors.textSecondary)

                TextField("Search commands...", text: $searchText)
                    .font(MacTypography.label)
                    .textFieldStyle(.plain)
                    .foregroundStyle(MacColors.textPrimary)
            }
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, MacSpacing.sm)
            .background(MacColors.searchInputBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            .padding(MacSpacing.sm)

            Divider()
                .background(MacColors.divider)

            // Command list
            if filteredCommands.isEmpty {
                VStack(spacing: MacSpacing.sm) {
                    Text("No commands found")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                }
                .frame(maxWidth: .infinity, minHeight: 60)
            } else {
                ScrollView {
                    VStack(spacing: 2) {
                        ForEach(filteredCommands) { cmd in
                            Button {
                                onSelect("/\(cmd.name) ")
                            } label: {
                                HStack(spacing: MacSpacing.sm) {
                                    Image(systemName: "terminal")
                                        .font(.system(size: 12))
                                        .foregroundStyle(MacColors.amberAccent)
                                        .frame(width: 18)

                                    VStack(alignment: .leading, spacing: 2) {
                                        Text("/\(cmd.name)")
                                            .font(MacTypography.code)
                                            .foregroundStyle(MacColors.textPrimary)

                                        Text(cmd.description)
                                            .font(MacTypography.caption)
                                            .foregroundStyle(MacColors.textSecondary)
                                            .lineLimit(1)
                                    }

                                    Spacer()

                                    if !cmd.resources.isEmpty {
                                        Text("\(cmd.resources.count)")
                                            .font(MacTypography.metadata)
                                            .foregroundStyle(MacColors.textFaint)
                                            .padding(.horizontal, 6)
                                            .padding(.vertical, 2)
                                            .background(MacColors.innerPillBackground)
                                            .clipShape(Capsule())
                                    }
                                }
                                .padding(.horizontal, MacSpacing.md)
                                .padding(.vertical, MacSpacing.sm)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.hestia)
                            .background(Color.clear)
                        }
                    }
                    .padding(.vertical, MacSpacing.xs)
                }
            }
        }
        .frame(maxWidth: 280, maxHeight: 320)
        .background(MacColors.panelBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorderStrong, lineWidth: 1)
        }
        .task {
            await viewModel.loadCommands()
        }
    }
}
