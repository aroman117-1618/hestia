import SwiftUI
import HestiaShared

// MARK: - File Content Sheet (Preview & Editor)

struct FileContentSheet: View {
    @ObservedObject var viewModel: MacExplorerFilesViewModel

    var body: some View {
        VStack(spacing: 0) {
            if let file = viewModel.selectedFile {
                // Header
                fileHeader(file)

                MacColors.divider.frame(height: 1)

                // Content area
                if viewModel.isLoadingContent {
                    loadingContent
                } else if viewModel.isEditing {
                    editingContent
                } else if let content = viewModel.fileContent {
                    readOnlyContent(content, file: file)
                } else {
                    unsupportedContent(file)
                }
            }
        }
        .background(MacColors.panelBackground)
    }

    // MARK: - File Header

    private func fileHeader(_ file: FileEntryResponse) -> some View {
        HStack(spacing: MacSpacing.md) {
            // File icon and name
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: file.icon)
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(fileIconColor(for: file))

                VStack(alignment: .leading, spacing: 1) {
                    Text(file.name)
                        .font(MacTypography.cardTitle)
                        .foregroundStyle(MacColors.textPrimary)
                        .lineLimit(1)

                    HStack(spacing: MacSpacing.sm) {
                        Text(file.formattedSize)
                            .font(MacTypography.metadata)
                            .foregroundStyle(MacColors.textFaint)
                        Text(file.formattedDate)
                            .font(MacTypography.metadata)
                            .foregroundStyle(MacColors.textFaint)
                    }
                }
            }

            Spacer()

            // Action buttons
            if viewModel.isEditing {
                // Save / Cancel in edit mode
                Button {
                    viewModel.cancelEditing()
                } label: {
                    Text("Cancel")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                        .padding(.horizontal, MacSpacing.md)
                        .padding(.vertical, MacSpacing.xs)
                        .background(MacColors.searchInputBackground)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.hestia)

                Button {
                    viewModel.saveEdit()
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "checkmark")
                            .font(MacTypography.captionMedium)
                        Text("Save")
                            .font(MacTypography.labelMedium)
                    }
                    .foregroundStyle(MacColors.buttonTextDark)
                    .padding(.horizontal, MacSpacing.md)
                    .padding(.vertical, MacSpacing.xs)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.hestia)
                .accessibilityLabel("Save file changes")
            } else {
                // Edit button (only for text files with content)
                if file.isTextFile && viewModel.fileContent != nil {
                    Button {
                        viewModel.startEditing()
                    } label: {
                        HStack(spacing: MacSpacing.xs) {
                            Image(systemName: "pencil")
                                .font(MacTypography.caption)
                            Text("Edit")
                                .font(MacTypography.label)
                        }
                        .foregroundStyle(MacColors.amberAccent)
                        .padding(.horizontal, MacSpacing.md)
                        .padding(.vertical, MacSpacing.xs)
                        .background(MacColors.activeTabBackground)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                    }
                    .buttonStyle(.hestia)
                    .accessibilityLabel("Edit file")
                }

                // Open in Finder
                Button {
                    viewModel.openInFinder(file)
                } label: {
                    Image(systemName: "arrow.up.forward.square")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                }
                .buttonStyle(.hestia)
                .accessibilityLabel("Open in Finder")

                // Close preview
                Button {
                    viewModel.selectedFile = nil
                    viewModel.fileContent = nil
                    viewModel.isEditing = false
                } label: {
                    Image(systemName: "xmark")
                        .font(MacTypography.smallMedium)
                        .foregroundStyle(MacColors.textSecondary)
                        .frame(width: 24, height: 24)
                }
                .buttonStyle(.hestia)
                .accessibilityLabel("Close preview")
            }
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.md)
    }

    // MARK: - Content States

    private var loadingContent: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            ProgressView()
                .controlSize(.regular)
                .tint(MacColors.amberAccent)
            Text("Loading content...")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private func readOnlyContent(_ content: String, file: FileEntryResponse) -> some View {
        ScrollView {
            Text(content)
                .font(file.isCodeFile ? MacTypography.code : MacTypography.body)
                .foregroundStyle(MacColors.textPrimary)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(MacSpacing.lg)
        }
    }

    private var editingContent: some View {
        TextEditor(text: $viewModel.editContent)
            .font(MacTypography.code)
            .foregroundStyle(MacColors.textPrimary)
            .scrollContentBackground(.hidden)
            .padding(MacSpacing.sm)
            .background(MacColors.windowBackground)
    }

    private func unsupportedContent(_ file: FileEntryResponse) -> some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: file.icon)
                .font(.system(size: 40, weight: .light))
                .foregroundStyle(MacColors.textFaint)

            VStack(spacing: MacSpacing.sm) {
                Text("Preview not available")
                    .font(MacTypography.bodyMedium)
                    .foregroundStyle(MacColors.textPrimary)

                if let ext = file.extension_ {
                    Text(".\(ext) files cannot be previewed here")
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textSecondary)
                } else {
                    Text("This file type cannot be previewed")
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textSecondary)
                }
            }

            Button {
                viewModel.openInFinder(file)
            } label: {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: "arrow.up.forward.square")
                        .font(MacTypography.label)
                    Text("Open in Finder")
                        .font(MacTypography.bodyMedium)
                }
                .foregroundStyle(MacColors.buttonTextDark)
                .padding(.horizontal, MacSpacing.xxl)
                .padding(.vertical, MacSpacing.md)
                .background(MacColors.amberAccent)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            }
            .buttonStyle(.hestia)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
