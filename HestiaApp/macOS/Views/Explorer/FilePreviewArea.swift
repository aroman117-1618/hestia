import SwiftUI
import HestiaShared

struct FilePreviewArea: View {
    let selectedFile: FileNode?
    let content: String
    let isLoading: Bool
    let onSelectFolder: () -> Void

    @State private var selectedFormat: String = "Markdown"

    var body: some View {
        VStack(spacing: 0) {
            if let file = selectedFile {
                // Header: file name + status + actions
                fileHeader(file)

                // Format tabs
                formatTabs

                // Content
                if isLoading {
                    Spacer()
                    ProgressView()
                    Spacer()
                } else {
                    ScrollView {
                        Text(content)
                            .font(isCodeFile(file) ? MacTypography.code : MacTypography.body)
                            .foregroundStyle(MacColors.textPrimary)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(MacSpacing.xxl)
                    }
                }
            } else {
                // Empty state
                Spacer()
                VStack(spacing: MacSpacing.xl) {
                    Image(systemName: "folder.badge.questionmark")
                        .font(.system(size: 48, weight: .light))
                        .foregroundStyle(MacColors.amberAccent.opacity(0.6))

                    VStack(spacing: MacSpacing.sm) {
                        Text("No folder selected")
                            .font(MacTypography.bodyMedium)
                            .foregroundStyle(MacColors.textPrimary)
                        Text("Open a project folder to browse and preview files")
                            .font(MacTypography.body)
                            .foregroundStyle(MacColors.textSecondary)
                    }

                    Button(action: onSelectFolder) {
                        HStack(spacing: MacSpacing.sm) {
                            Image(systemName: "folder.badge.plus")
                                .font(.system(size: 14))
                            Text("Open Folder")
                        }
                        .font(MacTypography.bodyMedium)
                        .foregroundStyle(MacColors.buttonTextDark)
                        .padding(.horizontal, MacSpacing.xxl)
                        .padding(.vertical, MacSpacing.md)
                        .background(MacColors.amberAccent)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                    }
                    .buttonStyle(.hestia)

                    Text("Cmd+2 to switch here anytime")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textInactive)
                }
                Spacer()
            }
        }
    }

    private func fileHeader(_ file: FileNode) -> some View {
        VStack(spacing: MacSpacing.lg) {
            HStack {
                // File name + chevron
                HStack(spacing: MacSpacing.sm) {
                    Text(file.name)
                        .font(.system(size: 28))
                        .foregroundStyle(MacColors.textPrimary)
                    Image(systemName: "chevron.down")
                        .font(.system(size: 14))
                        .foregroundStyle(MacColors.textSecondary)
                }

                // Status badge
                HStack(spacing: MacSpacing.sm) {
                    Circle()
                        .fill(MacColors.healthGreen)
                        .frame(width: 6, height: 6)
                    Text("Active")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textPrimary)
                }
                .padding(.horizontal, 9)
                .padding(.vertical, 1)
                .background(MacColors.aiBubbleBackground)
                .overlay {
                    RoundedRectangle(cornerRadius: MacCornerRadius.search)
                        .strokeBorder(MacColors.subtleBorder, lineWidth: 1)
                }
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))

                Spacer()

                // Share button
                Button {
                    // Share action
                } label: {
                    Text("Share")
                        .font(MacTypography.bodyMedium)
                        .foregroundStyle(MacColors.buttonTextDark)
                        .padding(.horizontal, MacSpacing.lg)
                        .padding(.vertical, MacSpacing.sm)
                        .background(MacColors.amberAccent)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.hestia)

                // More menu
                Button {} label: {
                    Image(systemName: "ellipsis")
                        .font(.system(size: 14))
                        .foregroundStyle(MacColors.textSecondary)
                        .frame(width: 38, height: 38)
                        .background(MacColors.panelBackground)
                        .overlay {
                            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                                .strokeBorder(MacColors.aiAvatarBorder, lineWidth: 1)
                        }
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.hestia)
            }
        }
        .padding(.top, MacSpacing.xl)
        .padding(.horizontal, MacSpacing.xxl)
    }

    private var formatTabs: some View {
        HStack(spacing: 0) {
            ForEach(["Markdown", "PDF", "CSV"], id: \.self) { format in
                Button {
                    selectedFormat = format
                } label: {
                    VStack(spacing: 0) {
                        Text(format)
                            .font(MacTypography.bodyMedium)
                            .foregroundStyle(
                                selectedFormat == format
                                    ? MacColors.amberAccent
                                    : MacColors.textInactive
                            )
                            .frame(height: 46)

                        // Active underline
                        Rectangle()
                            .fill(selectedFormat == format ? MacColors.amberAccent : Color.clear)
                            .frame(height: 2)
                    }
                    .padding(.horizontal, MacSpacing.lg)
                }
                .buttonStyle(.hestia)
            }
            Spacer()
        }
        .overlay(alignment: .bottom) {
            MacColors.divider.frame(height: 1)
        }
    }

    private func isCodeFile(_ file: FileNode) -> Bool {
        let codeExtensions = ["swift", "py", "js", "ts", "json", "yaml", "yml", "csv"]
        return codeExtensions.contains(file.path.pathExtension.lowercased())
    }
}
