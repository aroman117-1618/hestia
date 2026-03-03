import SwiftUI
import HestiaShared

struct MacProfileView: View {
    @StateObject private var vm = MacSettingsProfileViewModel()
    @State private var selectedFile: String?
    @State private var fileContent: String = ""
    @State private var isLoadingFile: Bool = false

    // Editable files (open in markdown editor on tap)
    private let editableFiles: Set<String> = ["MIND.md", "BODY.md", "SPIRIT.md", "VITALS.md", "SETUP.md"]

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xl) {
            // Profile header: avatar + name/description
            profileHeader

            Divider()
                .background(MacColors.divider)

            // Profile files grid (tappable)
            profileFilesGrid

            // Markdown editor (if a file is selected)
            if let fileName = selectedFile {
                VStack(alignment: .leading, spacing: MacSpacing.sm) {
                    HStack {
                        Text(fileName)
                            .font(MacTypography.cardSubtitle)
                            .foregroundStyle(MacColors.amberAccent)

                        Spacer()

                        Button {
                            selectedFile = nil
                            fileContent = ""
                        } label: {
                            Image(systemName: "xmark.circle")
                                .foregroundStyle(MacColors.textSecondary)
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Close file editor")
                    }

                    if isLoadingFile {
                        ProgressView()
                            .frame(maxWidth: .infinity, minHeight: 200)
                    } else {
                        MarkdownEditorView(
                            text: $fileContent,
                            isEditable: editableFiles.contains(fileName),
                            onSave: { content in
                                Task {
                                    _ = await vm.saveFile(fileName, content: content)
                                }
                            }
                        )
                        .frame(minHeight: 300, maxHeight: 500)
                        .onChange(of: fileContent) { _, newValue in
                            // Auto-save after 2s of inactivity
                            autoSaveFile(fileName, content: newValue)
                        }
                    }
                }
            }

            // Preferences note
            settingsSection
        }
        .task {
            await vm.loadProfile()
        }
    }

    // MARK: - Auto-save debounce

    @State private var autoSaveTask: Task<Void, Never>?

    private func autoSaveFile(_ fileName: String, content: String) {
        autoSaveTask?.cancel()
        autoSaveTask = Task {
            try? await Task.sleep(for: .seconds(2))
            guard !Task.isCancelled else { return }
            _ = await vm.saveFile(fileName, content: content)
        }
    }

    // MARK: - Profile Header

    private var profileHeader: some View {
        HStack(spacing: MacSpacing.xl) {
            ProfilePhotoEditor(
                currentPhotoData: vm.photoData,
                initialLetter: String(vm.name.prefix(1)).uppercased(),
                size: MacSize.profilePhotoSize,
                onUpload: { data in
                    Task { await vm.uploadPhoto(data) }
                },
                onDelete: {
                    Task { await vm.deletePhoto() }
                }
            )

            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                TextField("Name", text: $vm.name)
                    .font(MacTypography.pageTitle)
                    .foregroundStyle(MacColors.textPrimary)
                    .textFieldStyle(.plain)
                    .onChange(of: vm.name) { _, _ in
                        vm.scheduleProfileSave()
                    }
                    .accessibilityLabel("Display name")

                TextField("Description (e.g., job title)", text: $vm.userDescription)
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textSecondary)
                    .textFieldStyle(.plain)
                    .onChange(of: vm.userDescription) { _, _ in
                        vm.scheduleProfileSave()
                    }
                    .accessibilityLabel("Description")

                HStack(spacing: MacSpacing.sm) {
                    if vm.isSaving {
                        ProgressView()
                            .controlSize(.small)
                        Text("Saving...")
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.amberAccent)
                    }

                    Button {
                        Task { await vm.saveProfile() }
                    } label: {
                        Text("Save")
                            .font(MacTypography.labelMedium)
                            .foregroundStyle(MacColors.buttonTextDark)
                            .padding(.horizontal, MacSpacing.lg)
                            .padding(.vertical, MacSpacing.xs)
                            .background(MacColors.amberAccent)
                            .clipShape(RoundedRectangle(cornerRadius: 6))
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("Save profile changes")
                }
            }

            Spacer()
        }
    }

    // MARK: - Profile Files Grid

    private var profileFilesGrid: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("Profile Files")
                .font(MacTypography.cardSubtitle)
                .foregroundStyle(MacColors.textSecondary)

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: MacSpacing.sm),
                GridItem(.flexible(), spacing: MacSpacing.sm),
                GridItem(.flexible(), spacing: MacSpacing.sm),
                GridItem(.flexible(), spacing: MacSpacing.sm),
            ], spacing: MacSpacing.sm) {
                ForEach(MacSettingsProfileViewModel.profileFiles, id: \.key) { file in
                    ProfileFileChip(
                        label: file.label,
                        icon: file.icon,
                        exists: vm.fileManifest[file.key] ?? false,
                        isSelected: selectedFile == file.key
                    ) {
                        Task {
                            if selectedFile == file.key {
                                selectedFile = nil
                                fileContent = ""
                            } else {
                                selectedFile = file.key
                                isLoadingFile = true
                                fileContent = await vm.loadFile(file.key) ?? ""
                                isLoadingFile = false
                            }
                        }
                    }
                }
            }
        }
    }

    // MARK: - Settings Section

    private var settingsSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("Preferences")
                .font(MacTypography.cardSubtitle)
                .foregroundStyle(MacColors.textSecondary)

            Text("Notification settings, auto-lock timeout, and device management are available in the Resources section.")
                .font(MacTypography.smallBody)
                .foregroundStyle(MacColors.textFaint)
        }
    }
}

// MARK: - Profile File Chip

struct ProfileFileChip: View {
    let label: String
    let icon: String
    let exists: Bool
    var isSelected: Bool = false
    var onTap: (() -> Void)?

    var body: some View {
        Button {
            onTap?()
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: icon)
                    .font(.system(size: 12))
                    .foregroundStyle(isSelected ? MacColors.amberBright : (exists ? MacColors.amberAccent : MacColors.textFaint))
                    .frame(width: 16)

                Text(label)
                    .font(MacTypography.label)
                    .foregroundStyle(isSelected ? MacColors.textPrimary : (exists ? MacColors.textPrimary : MacColors.textFaint))

                Spacer()

                if exists {
                    Circle()
                        .fill(MacColors.healthGreen)
                        .frame(width: 6, height: 6)
                }
            }
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, MacSpacing.sm)
            .background(
                RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                    .fill(isSelected ? MacColors.activeNavBackground : MacColors.searchInputBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                    .strokeBorder(isSelected ? MacColors.amberAccent.opacity(0.3) : Color.clear, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
        .accessibilityLabel("\(label): \(exists ? "configured" : "not configured")")
    }
}
