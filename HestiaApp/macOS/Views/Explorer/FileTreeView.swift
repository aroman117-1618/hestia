import SwiftUI

struct FileTreeView: View {
    let nodes: [FileNode]
    let selectedFile: FileNode?
    let onSelect: (FileNode) -> Void
    let onToggle: (UUID) -> Void

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 0) {
                ForEach(nodes) { node in
                    FileTreeNodeView(
                        node: node,
                        depth: 0,
                        selectedFile: selectedFile,
                        onSelect: onSelect,
                        onToggle: onToggle
                    )
                }
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs)
        }
    }
}

struct FileTreeNodeView: View {
    let node: FileNode
    let depth: Int
    let selectedFile: FileNode?
    let onSelect: (FileNode) -> Void
    let onToggle: (UUID) -> Void

    @State private var isHovered = false
    private var isSelected: Bool { selectedFile?.id == node.id }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Button {
                if node.isDirectory {
                    onToggle(node.id)
                } else {
                    onSelect(node)
                }
            } label: {
                HStack(spacing: 0) {
                    // Indent per level (20px each)
                    if depth > 0 {
                        Spacer()
                            .frame(width: CGFloat(depth) * MacSize.treeIndent)
                    }

                    // Chevron (20x20 container)
                    if node.isDirectory {
                        Image(systemName: node.isExpanded ? "chevron.down" : "chevron.right")
                            .font(.system(size: 14))
                            .opacity(0.7)
                            .frame(width: MacSize.treeChevronSize, height: MacSize.treeChevronSize)
                    } else {
                        Spacer().frame(width: MacSize.treeChevronSize)
                    }

                    // Icon (20x20 container, 16x16 icon)
                    Image(systemName: node.icon)
                        .font(.system(size: 16))
                        .foregroundStyle(node.iconColor)
                        .frame(width: MacSize.treeIconSize, height: MacSize.treeIconSize)
                        .padding(.leading, MacSpacing.xs)

                    // Label
                    Text(node.name)
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textPrimary)
                        .lineLimit(1)
                        .padding(.leading, MacSpacing.sm)

                    Spacer()
                }
                .frame(height: MacSize.treeItemHeight)
                .padding(.horizontal, MacSpacing.xs)
                .background(
                    isSelected ? MacColors.activeTabBackground
                    : isHovered ? MacColors.searchInputBackground
                    : Color.clear
                )
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
            }
            .buttonStyle(.plain)
            .onHover { isHovered = $0 }

            // Children
            if node.isDirectory && node.isExpanded, let children = node.children {
                ForEach(children) { child in
                    FileTreeNodeView(
                        node: child,
                        depth: depth + 1,
                        selectedFile: selectedFile,
                        onSelect: onSelect,
                        onToggle: onToggle
                    )
                }
            }
        }
    }
}
