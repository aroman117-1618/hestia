import SwiftUI
import HestiaShared

// MARK: - Explorer Files View (API-backed file browser)

struct ExplorerFilesView: View {
    @ObservedObject var viewModel: MacExplorerFilesViewModel
    @State private var columnVisibility: NavigationSplitViewVisibility = .all

    var body: some View {
        VStack(spacing: 0) {
            // Breadcrumb bar
            breadcrumbBar

            MacColors.divider.frame(height: 1)

            // Toolbar
            toolbarBar

            MacColors.divider.frame(height: 1)

            // Main content area
            HStack(spacing: 0) {
                // File list panel
                fileListPanel
                    .frame(minWidth: 280, idealWidth: 400, maxWidth: .infinity)

                // Content preview panel (shown when file selected)
                if viewModel.selectedFile != nil {
                    MacColors.divider.frame(width: 1)

                    FileContentSheet(viewModel: viewModel)
                        .frame(minWidth: 300, idealWidth: 500, maxWidth: .infinity)
                }
            }

            MacColors.divider.frame(height: 1)

            // Bottom bar
            bottomBar
        }
        .hestiaPanel()
        .padding(.horizontal, MacSpacing.xl)
        .padding(.bottom, MacSpacing.xl)
        .task {
            viewModel.loadDirectory()
        }
        .alert("New File", isPresented: $viewModel.showingCreateFile) {
            TextField("File name", text: $viewModel.newItemName)
            Button("Create") {
                let name = viewModel.newItemName
                viewModel.newItemName = ""
                viewModel.createFile(name: name, content: "", type: "file")
            }
            Button("Cancel", role: .cancel) { viewModel.newItemName = "" }
        }
        .alert("New Folder", isPresented: $viewModel.showingCreateFolder) {
            TextField("Folder name", text: $viewModel.newItemName)
            Button("Create") {
                let name = viewModel.newItemName
                viewModel.newItemName = ""
                viewModel.createFile(name: name, type: "directory")
            }
            Button("Cancel", role: .cancel) { viewModel.newItemName = "" }
        }
        .alert("Delete File", isPresented: $viewModel.showingDeleteConfirm) {
            Button("Delete", role: .destructive) {
                if let file = viewModel.fileToDelete {
                    viewModel.deleteFile(file)
                }
                viewModel.fileToDelete = nil
            }
            Button("Cancel", role: .cancel) { viewModel.fileToDelete = nil }
        } message: {
            if let file = viewModel.fileToDelete {
                Text("Are you sure you want to delete \"\(file.name)\"? It will be moved to the Trash.")
            }
        }
    }

    // MARK: - Breadcrumb Bar

    private var breadcrumbBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: MacSpacing.xs) {
                // Navigate up button
                if viewModel.parentPath != nil {
                    Button {
                        viewModel.navigateUp()
                    } label: {
                        Image(systemName: "chevron.left")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(MacColors.amberAccent)
                            .frame(width: 24, height: 24)
                    }
                    .buttonStyle(.hestia)
                    .accessibilityLabel("Navigate to parent directory")
                }

                ForEach(Array(viewModel.breadcrumbs.enumerated()), id: \.element.id) { index, segment in
                    if index > 0 {
                        Image(systemName: "chevron.right")
                            .font(.system(size: 10))
                            .foregroundStyle(MacColors.textFaint)
                    }

                    Button {
                        viewModel.navigateToDirectory(segment.fullPath)
                    } label: {
                        HStack(spacing: MacSpacing.xs) {
                            if index == 0 {
                                Image(systemName: "folder.fill")
                                    .font(.system(size: 12))
                                    .foregroundStyle(MacColors.amberAccent)
                            }
                            Text(segment.name)
                                .font(index == viewModel.breadcrumbs.count - 1
                                      ? MacTypography.bodyMedium
                                      : MacTypography.body)
                                .foregroundStyle(index == viewModel.breadcrumbs.count - 1
                                                 ? MacColors.textPrimary
                                                 : MacColors.textSecondary)
                        }
                        .padding(.horizontal, MacSpacing.xs)
                        .padding(.vertical, 2)
                        .background(
                            index == viewModel.breadcrumbs.count - 1
                                ? MacColors.activeTabBackground
                                : Color.clear
                        )
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
                    }
                    .buttonStyle(.hestia)
                }

                Spacer()
            }
            .padding(.horizontal, MacSpacing.lg)
            .padding(.vertical, MacSpacing.sm)
        }
        .frame(height: 36)
    }

    // MARK: - Toolbar

    private var toolbarBar: some View {
        HStack(spacing: MacSpacing.md) {
            // Search field
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 12))
                    .foregroundStyle(MacColors.textPlaceholder)

                TextField("Search files...", text: $viewModel.searchText)
                    .textFieldStyle(.plain)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)

                if !viewModel.searchText.isEmpty {
                    Button {
                        viewModel.searchText = ""
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .font(.system(size: 12))
                            .foregroundStyle(MacColors.textPlaceholder)
                    }
                    .buttonStyle(.hestiaIcon)
                    .accessibilityLabel("Clear search")
                }
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, 5)
            .background(MacColors.searchInputBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            .frame(maxWidth: 240)

            // Sort picker
            Menu {
                ForEach(FileSortOption.allCases, id: \.self) { option in
                    Button {
                        viewModel.sortBy = option
                        viewModel.refresh()
                    } label: {
                        HStack {
                            Text(option.label)
                            if viewModel.sortBy == option {
                                Image(systemName: "checkmark")
                            }
                        }
                    }
                }
            } label: {
                HStack(spacing: MacSpacing.xs) {
                    Text("Sort: \(viewModel.sortBy.label)")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                    Image(systemName: "chevron.down")
                        .font(.system(size: 9))
                        .foregroundStyle(MacColors.textFaint)
                }
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, 5)
                .background(MacColors.searchInputBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            }
            .menuStyle(.borderlessButton)
            .fixedSize()

            // Show hidden toggle
            Button {
                viewModel.showHidden.toggle()
                viewModel.refresh()
            } label: {
                HStack(spacing: MacSpacing.xs) {
                    Image(systemName: viewModel.showHidden ? "eye.fill" : "eye.slash")
                        .font(.system(size: 12))
                    Text("Hidden")
                        .font(MacTypography.label)
                }
                .foregroundStyle(viewModel.showHidden ? MacColors.amberAccent : MacColors.textSecondary)
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, 5)
                .background(viewModel.showHidden ? MacColors.activeTabBackground : MacColors.searchInputBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            }
            .buttonStyle(.hestia)
            .accessibilityLabel(viewModel.showHidden ? "Hide hidden files" : "Show hidden files")

            Spacer()

            // Refresh button
            Button {
                viewModel.refresh()
            } label: {
                Image(systemName: "arrow.clockwise")
                    .font(.system(size: 13))
                    .foregroundStyle(MacColors.textSecondary)
            }
            .buttonStyle(.hestia)
            .accessibilityLabel("Refresh file list")
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.sm)
    }

    // MARK: - File List Panel

    private var fileListPanel: some View {
        Group {
            if viewModel.isLoading && viewModel.files.isEmpty {
                loadingState
            } else if viewModel.hasError {
                errorState
            } else if viewModel.filteredFiles.isEmpty {
                emptyState
            } else {
                fileList
            }
        }
    }

    private var fileList: some View {
        ScrollView {
            LazyVStack(spacing: 1) {
                ForEach(viewModel.filteredFiles) { file in
                    ExplorerFileRow(
                        file: file,
                        isSelected: viewModel.selectedFile?.path == file.path,
                        onSelect: { viewModel.selectFile(file) },
                        onOpenInFinder: { viewModel.openInFinder(file) },
                        onRename: { newName in viewModel.renameFile(file, newName: newName) },
                        onDelete: {
                            viewModel.fileToDelete = file
                            viewModel.showingDeleteConfirm = true
                        }
                    )
                }
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs)
        }
        .refreshable {
            viewModel.refresh()
        }
    }

    // MARK: - States

    private var loadingState: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            ProgressView()
                .controlSize(.regular)
                .tint(MacColors.amberAccent)
            Text("Loading files...")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var errorState: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 36))
                .foregroundStyle(MacColors.statusWarning)

            Text(viewModel.error ?? "Something went wrong")
                .font(MacTypography.bodyMedium)
                .foregroundStyle(MacColors.textPrimary)

            Text("Check that the server is running and try again.")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
                .multilineTextAlignment(.center)

            Button {
                viewModel.error = nil
                viewModel.refresh()
            } label: {
                HStack(spacing: MacSpacing.sm) {
                    Image(systemName: "arrow.clockwise")
                        .font(.system(size: 13))
                    Text("Retry")
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

    private var emptyState: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()
            Image(systemName: "folder")
                .font(.system(size: 36, weight: .light))
                .foregroundStyle(MacColors.amberAccent.opacity(0.5))

            if viewModel.searchText.isEmpty {
                Text("No files in this directory")
                    .font(MacTypography.bodyMedium)
                    .foregroundStyle(MacColors.textPrimary)
                Text("Create a file or folder to get started")
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textSecondary)
            } else {
                Text("No files matching \"\(viewModel.searchText)\"")
                    .font(MacTypography.bodyMedium)
                    .foregroundStyle(MacColors.textPrimary)
                Text("Try a different search term")
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textSecondary)
            }
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Bottom Bar

    private var bottomBar: some View {
        HStack(spacing: MacSpacing.md) {
            Button {
                viewModel.showingCreateFile = true
            } label: {
                HStack(spacing: MacSpacing.xs) {
                    Image(systemName: "plus")
                        .font(.system(size: 12))
                    Text("New File")
                        .font(MacTypography.label)
                }
                .foregroundStyle(MacColors.amberAccent)
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, MacSpacing.xs)
            }
            .buttonStyle(.hestia)
            .accessibilityLabel("Create new file")

            Button {
                viewModel.showingCreateFolder = true
            } label: {
                HStack(spacing: MacSpacing.xs) {
                    Image(systemName: "folder.badge.plus")
                        .font(.system(size: 12))
                    Text("New Folder")
                        .font(MacTypography.label)
                }
                .foregroundStyle(MacColors.amberAccent)
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, MacSpacing.xs)
            }
            .buttonStyle(.hestia)
            .accessibilityLabel("Create new folder")

            Spacer()

            // File count
            Text("\(viewModel.filteredFiles.count) items")
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textFaint)
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.sm)
    }
}
