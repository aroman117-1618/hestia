import SwiftUI
import HestiaShared

struct UserProfileView: View {
    @StateObject private var viewModel = MacUserProfileViewModel()

    var body: some View {
        HStack(spacing: 0) {
            // Left: File/command sidebar
            profileSidebar
                .frame(minWidth: 200, idealWidth: MacSize.fileSidebarWidth, maxWidth: 320)
                .background(MacColors.panelBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
                .overlay {
                    RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                        .strokeBorder(MacColors.cardBorder, lineWidth: 1)
                }

            // Right: Content editor
            contentArea
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
            await viewModel.loadAll()
        }
    }

    // MARK: - Sidebar

    private var profileSidebar: some View {
        VStack(spacing: 0) {
            // Header
            profileHeader

            Divider()
                .background(MacColors.divider)

            ScrollView {
                VStack(alignment: .leading, spacing: MacSpacing.md) {
                    // Identity section
                    sidebarSection("PROFILE FILES")

                    ForEach(MacUserProfileViewModel.fileDisplayNames, id: \.key) { item in
                        sidebarFileRow(
                            key: item.key,
                            label: item.label,
                            icon: item.icon,
                            isSelected: viewModel.selectedFile == item.key
                        )
                    }

                    // Commands section
                    if !viewModel.commands.isEmpty {
                        sidebarSection("COMMANDS")
                            .padding(.top, MacSpacing.md)

                        ForEach(viewModel.commands) { cmd in
                            sidebarCommandRow(cmd, isSelected: viewModel.selectedFile == "cmd:\(cmd.name)")
                        }
                    }

                    // Daily notes section
                    if !viewModel.dailyNotes.isEmpty {
                        sidebarSection("RECENT NOTES")
                            .padding(.top, MacSpacing.md)

                        ForEach(viewModel.dailyNotes) { note in
                            sidebarNoteRow(note, isSelected: viewModel.selectedFile == "note:\(note.date)")
                        }
                    }

                    // Devices section
                    sidebarSection("DEVICES")
                        .padding(.top, MacSpacing.md)

                    sidebarFileRow(
                        key: "devices",
                        label: "Manage Devices",
                        icon: "desktopcomputer",
                        isSelected: viewModel.selectedFile == "devices"
                    )
                }
                .padding(MacSpacing.md)
            }
        }
    }

    private var profileHeader: some View {
        HStack(spacing: MacSpacing.md) {
            // Avatar
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [
                                Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.8),
                                Color(red: 254/255, green: 154/255, blue: 0).opacity(0.3)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                Circle()
                    .strokeBorder(MacColors.avatarBorder, lineWidth: 1)
                Text(initials)
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(.white)
            }
            .frame(width: 36, height: 36)

            VStack(alignment: .leading, spacing: 2) {
                Text(viewModel.profile?.identity.name ?? "User Profile")
                    .font(MacTypography.cardTitle)
                    .foregroundStyle(MacColors.textPrimary)

                if let job = viewModel.profile?.identity.job, !job.isEmpty {
                    Text(job)
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textSecondary)
                }
            }

            Spacer()
        }
        .padding(MacSpacing.lg)
    }

    private var initials: String {
        guard let name = viewModel.profile?.identity.name else { return "?" }
        let parts = name.split(separator: " ")
        if parts.count >= 2 {
            return "\(parts[0].prefix(1))\(parts[1].prefix(1))"
        }
        return String(name.prefix(2)).uppercased()
    }

    // MARK: - Sidebar Rows

    private func sidebarSection(_ title: String) -> some View {
        Text(title)
            .font(MacTypography.metadata)
            .foregroundStyle(MacColors.textFaint)
            .tracking(1.2)
    }

    private func sidebarFileRow(key: String, label: String, icon: String, isSelected: Bool) -> some View {
        Button {
            Task { await viewModel.loadFile(key) }
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: icon)
                    .font(.system(size: 13))
                    .foregroundStyle(isSelected ? MacColors.amberAccent : MacColors.textSecondary)
                    .frame(width: 20)

                Text(label)
                    .font(MacTypography.label)
                    .foregroundStyle(isSelected ? MacColors.textPrimary : MacColors.textSecondary)

                Spacer()

                // File existence indicator
                if let files = viewModel.profile?.files, files[key] == true {
                    Circle()
                        .fill(MacColors.healthGreen)
                        .frame(width: 6, height: 6)
                }
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs + 2)
            .background(isSelected ? MacColors.activeTabBackground : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        }
        .buttonStyle(.hestia)
    }

    private func sidebarCommandRow(_ cmd: CommandInfo, isSelected: Bool) -> some View {
        Button {
            viewModel.selectedFile = "cmd:\(cmd.name)"
            viewModel.fileContent = cmd.description
            viewModel.isEditing = false
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "terminal")
                    .font(.system(size: 13))
                    .foregroundStyle(isSelected ? MacColors.amberAccent : MacColors.textSecondary)
                    .frame(width: 20)

                Text("/\(cmd.name)")
                    .font(MacTypography.code)
                    .foregroundStyle(isSelected ? MacColors.textPrimary : MacColors.textSecondary)

                Spacer()
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs + 2)
            .background(isSelected ? MacColors.activeTabBackground : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        }
        .buttonStyle(.hestia)
    }

    private func sidebarNoteRow(_ note: DailyNoteInfo, isSelected: Bool) -> some View {
        Button {
            viewModel.selectedFile = "note:\(note.date)"
            viewModel.fileContent = note.content
            viewModel.isEditing = false
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "calendar")
                    .font(.system(size: 13))
                    .foregroundStyle(isSelected ? MacColors.amberAccent : MacColors.textSecondary)
                    .frame(width: 20)

                Text(note.date)
                    .font(MacTypography.label)
                    .foregroundStyle(isSelected ? MacColors.textPrimary : MacColors.textSecondary)

                Spacer()
            }
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs + 2)
            .background(isSelected ? MacColors.activeTabBackground : Color.clear)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        }
        .buttonStyle(.hestia)
    }

    // MARK: - Content Area

    private var contentArea: some View {
        VStack(spacing: 0) {
            if let selected = viewModel.selectedFile {
                if selected == "devices" {
                    MacDeviceManagementView()
                } else {
                    // Top bar
                    contentTopBar(for: selected)

                    Divider()
                        .background(MacColors.divider)

                    // Content
                    if viewModel.isEditing {
                        editorView
                    } else {
                        readerView
                    }
                }
            } else {
                emptyState
            }
        }
    }

    private func contentTopBar(for file: String) -> some View {
        HStack {
            // File name
            Text(displayName(for: file))
                .font(MacTypography.cardTitle)
                .foregroundStyle(MacColors.textPrimary)

            Spacer()

            // Only show edit/save for profile files (not commands or notes)
            if !file.hasPrefix("cmd:") && !file.hasPrefix("note:") {
                if viewModel.isEditing {
                    Button("Cancel") {
                        viewModel.editedContent = viewModel.fileContent
                        viewModel.isEditing = false
                    }
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
                    .buttonStyle(.hestia)

                    Button("Save") {
                        Task { await viewModel.saveFile() }
                    }
                    .font(MacTypography.labelMedium)
                    .foregroundStyle(MacColors.buttonTextDark)
                    .padding(.horizontal, MacSpacing.md)
                    .padding(.vertical, MacSpacing.xs)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
                    .buttonStyle(.hestia)
                } else {
                    Button {
                        viewModel.editedContent = viewModel.fileContent
                        viewModel.isEditing = true
                    } label: {
                        Image(systemName: "pencil")
                            .font(.system(size: 14))
                            .foregroundStyle(MacColors.textSecondary)
                    }
                    .buttonStyle(.hestia)
                }
            }
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.md)
    }

    private var readerView: some View {
        ScrollView {
            Text(viewModel.fileContent)
                .font(MacTypography.code)
                .foregroundStyle(MacColors.textPrimary)
                .textSelection(.enabled)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(MacSpacing.lg)
        }
    }

    private var editorView: some View {
        TextEditor(text: $viewModel.editedContent)
            .font(MacTypography.code)
            .foregroundStyle(MacColors.textPrimary)
            .scrollContentBackground(.hidden)
            .padding(MacSpacing.sm)
    }

    private var emptyState: some View {
        VStack(spacing: MacSpacing.lg) {
            Image(systemName: "person.crop.circle")
                .font(.system(size: 48))
                .foregroundStyle(MacColors.textFaint)
            Text("Select a profile file to view")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Helpers

    private func displayName(for file: String) -> String {
        if file.hasPrefix("cmd:") {
            return "/\(file.dropFirst(4))"
        }
        if file.hasPrefix("note:") {
            return String(file.dropFirst(5))
        }
        return MacUserProfileViewModel.fileDisplayNames.first { $0.key == file }?.label ?? file
    }
}
