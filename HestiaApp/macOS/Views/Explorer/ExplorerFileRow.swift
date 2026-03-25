import SwiftUI

// MARK: - Icon Color Helper (internal — used by ExplorerFileRow + FileContentSheet)

func fileIconColor(for file: FileEntryResponse) -> Color {
    if file.isDirectory { return MacColors.amberAccent }
    guard let ext = file.extension_?.lowercased() else { return MacColors.textSecondary }
    switch ext {
    case "md", "markdown": return Color(red: 2/255, green: 109/255, blue: 255/255)
    case "pdf": return Color(red: 255/255, green: 59/255, blue: 48/255)
    case "swift": return Color(red: 240/255, green: 81/255, blue: 56/255)
    case "py": return Color(red: 55/255, green: 118/255, blue: 171/255)
    case "json", "yaml", "yml": return MacColors.healthGreen
    case "png", "jpg", "jpeg", "gif": return Color(red: 90/255, green: 200/255, blue: 250/255)
    default: return MacColors.textSecondary
    }
}

// MARK: - Explorer File Row (API-backed)

struct ExplorerFileRow: View {
    let file: FileEntryResponse
    let isSelected: Bool
    var onSelect: () -> Void
    var onOpenInFinder: () -> Void
    var onRename: (String) -> Void
    var onDelete: () -> Void

    @State private var isHovered = false
    @State private var isRenaming = false
    @State private var renameText = ""

    var body: some View {
        Button {
            onSelect()
        } label: {
            HStack(spacing: MacSpacing.md) {
                // File icon
                Image(systemName: file.icon)
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(fileIconColor(for: file))
                    .frame(width: MacSize.treeIconSize, height: MacSize.treeIconSize)

                // Name (or rename field)
                if isRenaming {
                    TextField("Name", text: $renameText, onCommit: {
                        commitRename()
                    })
                    .textFieldStyle(.plain)
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textPrimary)
                    .onExitCommand {
                        cancelRename()
                    }
                } else {
                    Text(file.name)
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textPrimary)
                        .lineLimit(1)
                }

                Spacer()

                // Size
                if !file.isDirectory {
                    Text(file.formattedSize)
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)
                        .frame(width: 60, alignment: .trailing)
                }

                // Modified date
                Text(file.formattedDate)
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.textFaint)
                    .frame(width: 60, alignment: .trailing)

                // Directory chevron
                if file.isDirectory {
                    Image(systemName: "chevron.right")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)
                        .frame(width: 14)
                } else {
                    Spacer().frame(width: 14)
                }
            }
            .frame(height: MacSize.treeItemHeight)
            .padding(.horizontal, MacSpacing.sm)
            .background(
                isSelected ? MacColors.activeTabBackground
                : isHovered ? MacColors.searchInputBackground
                : Color.clear
            )
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        }
        .buttonStyle(.hestia)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.1)) {
                isHovered = hovering
            }
        }
        .contextMenu {
            contextMenuItems
        }
        .accessibilityLabel("\(file.isDirectory ? "Folder" : "File"): \(file.name)")
    }

    // MARK: - Context Menu

    @ViewBuilder
    private var contextMenuItems: some View {
        if !file.isDirectory {
            Button {
                onSelect()
            } label: {
                Label("Open", systemImage: "doc.text")
            }
        }

        Button {
            onOpenInFinder()
        } label: {
            Label("Show in Finder", systemImage: "folder")
        }

        Divider()

        Button {
            startRename()
        } label: {
            Label("Rename", systemImage: "pencil")
        }

        Divider()

        Button(role: .destructive) {
            onDelete()
        } label: {
            Label("Delete", systemImage: "trash")
        }
    }

    // MARK: - Rename Helpers

    private func startRename() {
        renameText = file.name
        isRenaming = true
    }

    private func commitRename() {
        let newName = renameText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !newName.isEmpty, newName != file.name else {
            cancelRename()
            return
        }
        isRenaming = false
        onRename(newName)
    }

    private func cancelRename() {
        isRenaming = false
        renameText = ""
    }
}
