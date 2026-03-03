import SwiftUI

// MARK: - Command Palette (⌘K)

/// Modal overlay with fuzzy command search, keyboard navigation, and instant execution.
struct CommandPaletteView: View {
    @Environment(CommandPaletteState.self) private var palette
    @State private var selectedIndex: Int = 0
    @FocusState private var isSearchFocused: Bool

    var body: some View {
        if palette.isOpen {
            ZStack {
                // Dimmed background
                Color.black.opacity(0.4)
                    .ignoresSafeArea()
                    .onTapGesture { palette.close() }

                // Palette panel
                VStack(spacing: 0) {
                    searchField
                    Divider()
                        .background(MacColors.divider)
                    commandList
                }
                .frame(width: 500, height: 380)
                .background(MacColors.panelBackground)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay {
                    RoundedRectangle(cornerRadius: 12)
                        .strokeBorder(MacColors.cardBorder, lineWidth: 1)
                }
                .shadow(color: .black.opacity(0.4), radius: 24, y: 8)
            }
            .transition(.opacity.combined(with: .scale(scale: 0.95)))
            .onAppear {
                selectedIndex = 0
                isSearchFocused = true
            }
            .onKeyPress(.escape) {
                palette.close()
                return .handled
            }
            .onKeyPress(.downArrow) {
                moveSelection(by: 1)
                return .handled
            }
            .onKeyPress(.upArrow) {
                moveSelection(by: -1)
                return .handled
            }
            .onKeyPress(.return) {
                executeSelected()
                return .handled
            }
        }
    }

    // MARK: - Search Field

    private var searchField: some View {
        HStack(spacing: MacSpacing.md) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 16))
                .foregroundStyle(MacColors.textSecondary)

            TextField("Type a command...", text: Binding(
                get: { palette.searchText },
                set: { palette.searchText = $0; selectedIndex = 0 }
            ))
            .font(.system(size: 16))
            .textFieldStyle(.plain)
            .foregroundStyle(MacColors.textPrimary)
            .focused($isSearchFocused)

            if !palette.searchText.isEmpty {
                Button {
                    palette.searchText = ""
                    selectedIndex = 0
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 14))
                        .foregroundStyle(MacColors.textSecondary)
                }
                .buttonStyle(.hestiaIcon)
                .accessibilityLabel("Clear search")
            }

            // Escape hint
            Text("esc")
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(MacColors.textFaint)
                .padding(.horizontal, 6)
                .padding(.vertical, 3)
                .background(MacColors.searchInputBackground)
                .clipShape(RoundedRectangle(cornerRadius: 4))
        }
        .padding(.horizontal, MacSpacing.xl)
        .padding(.vertical, MacSpacing.lg)
    }

    // MARK: - Command List

    private var commandList: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 2) {
                    ForEach(Array(palette.filteredCommands.enumerated()), id: \.element.id) { index, command in
                        commandRow(command, isSelected: index == selectedIndex)
                            .id(command.id)
                            .onTapGesture {
                                palette.execute(command)
                            }
                            .hoverCursor()
                    }

                    if palette.filteredCommands.isEmpty {
                        VStack(spacing: MacSpacing.md) {
                            Image(systemName: "questionmark.circle")
                                .font(.system(size: 24))
                                .foregroundStyle(MacColors.textFaint)
                            Text("No matching commands")
                                .font(MacTypography.body)
                                .foregroundStyle(MacColors.textSecondary)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, MacSpacing.xxxl)
                    }
                }
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, MacSpacing.sm)
            }
            .onChange(of: selectedIndex) { _, newIndex in
                if let cmd = palette.filteredCommands[safe: newIndex] {
                    withAnimation(.easeOut(duration: 0.1)) {
                        proxy.scrollTo(cmd.id, anchor: .center)
                    }
                }
            }
        }
    }

    // MARK: - Command Row

    private func commandRow(_ command: PaletteCommand, isSelected: Bool) -> some View {
        HStack(spacing: MacSpacing.md) {
            Image(systemName: command.icon)
                .font(.system(size: 14))
                .foregroundStyle(isSelected ? MacColors.amberAccent : MacColors.textSecondary)
                .frame(width: 24)

            Text(command.title)
                .font(MacTypography.body)
                .foregroundStyle(isSelected ? MacColors.textPrimary : MacColors.textSecondary)

            Spacer()

            if let shortcut = command.shortcut {
                Text(shortcut)
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                    .foregroundStyle(MacColors.textFaint)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 4))
            }
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm + 2)
        .background(
            isSelected
                ? MacColors.activeTabBackground
                : Color.clear
        )
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .accessibilityLabel(command.title)
        .accessibilityHint(command.shortcut.map { "Shortcut: \($0)" } ?? "")
    }

    // MARK: - Navigation

    private func moveSelection(by delta: Int) {
        let count = palette.filteredCommands.count
        guard count > 0 else { return }
        selectedIndex = (selectedIndex + delta + count) % count
    }

    private func executeSelected() {
        guard let cmd = palette.filteredCommands[safe: selectedIndex] else { return }
        palette.execute(cmd)
    }
}

// MARK: - Safe Collection Subscript

private extension Collection {
    subscript(safe index: Index) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}
