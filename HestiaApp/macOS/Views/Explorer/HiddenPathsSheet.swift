import SwiftUI

// MARK: - Hidden Paths Configuration Sheet

struct HiddenPathsSheet: View {
    @Binding var isPresented: Bool
    @State private var patterns: [String] = [
        ".DS_Store",
        ".git",
        "__pycache__",
        "*.pyc",
        ".env",
        "node_modules",
        ".venv"
    ]
    @State private var newPattern: String = ""

    var body: some View {
        VStack(spacing: 0) {
            // Header
            header

            MacColors.divider.frame(height: 1)

            // Pattern list
            patternList

            MacColors.divider.frame(height: 1)

            // Add new pattern
            addPatternBar

            MacColors.divider.frame(height: 1)

            // Footer
            footer
        }
        .frame(width: 380, height: 420)
        .background(MacColors.panelBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: 2) {
                Text("Hidden Patterns")
                    .font(MacTypography.cardTitle)
                    .foregroundStyle(MacColors.textPrimary)
                Text("Files matching these patterns are hidden by default")
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.textSecondary)
            }

            Spacer()

            Button {
                isPresented = false
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(MacColors.textSecondary)
                    .frame(width: 22, height: 22)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            }
            .buttonStyle(.hestia)
            .accessibilityLabel("Close sheet")
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.md)
    }

    // MARK: - Pattern List

    private var patternList: some View {
        ScrollView(.vertical) {
            LazyVStack(spacing: 2) {
                ForEach(patterns, id: \.self) { pattern in
                    patternRow(pattern)
                }
            }
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, MacSpacing.sm)
        }
    }

    private func patternRow(_ pattern: String) -> some View {
        HStack(spacing: MacSpacing.md) {
            Image(systemName: "eye.slash")
                .font(.system(size: 12))
                .foregroundStyle(MacColors.textFaint)
                .frame(width: 20)

            Text(pattern)
                .font(MacTypography.code)
                .foregroundStyle(MacColors.textPrimary)

            Spacer()

            Button {
                withAnimation(.easeInOut(duration: MacAnimation.fast)) {
                    if let idx = patterns.firstIndex(of: pattern) {
                        patterns.remove(at: idx)
                    }
                }
            } label: {
                Image(systemName: "minus.circle.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(MacColors.healthRed.opacity(0.6))
            }
            .buttonStyle(.hestiaIcon)
            .accessibilityLabel("Remove pattern \(pattern)")
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
    }

    // MARK: - Add Pattern Bar

    private var addPatternBar: some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: "plus.circle")
                .font(.system(size: 14))
                .foregroundStyle(MacColors.amberAccent)

            TextField("Add pattern (e.g., *.log, .hidden)", text: $newPattern)
                .textFieldStyle(.plain)
                .font(MacTypography.code)
                .foregroundStyle(MacColors.textPrimary)
                .onSubmit {
                    addPattern()
                }

            if !newPattern.isEmpty {
                Button {
                    addPattern()
                } label: {
                    Text("Add")
                        .font(MacTypography.labelMedium)
                        .foregroundStyle(MacColors.amberAccent)
                }
                .buttonStyle(.hestia)
            }
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.md)
    }

    // MARK: - Footer

    private var footer: some View {
        HStack {
            Text("\(patterns.count) patterns")
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textFaint)

            Spacer()

            Button {
                isPresented = false
            } label: {
                Text("Done")
                    .font(MacTypography.labelMedium)
                    .foregroundStyle(MacColors.buttonTextDark)
                    .padding(.horizontal, MacSpacing.xl)
                    .padding(.vertical, MacSpacing.sm)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            }
            .buttonStyle(.hestia)
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.md)
    }

    // MARK: - Helpers

    private func addPattern() {
        let trimmed = newPattern.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !patterns.contains(trimmed) else { return }
        withAnimation(.easeInOut(duration: MacAnimation.fast)) {
            patterns.append(trimmed)
        }
        newPattern = ""
    }
}
