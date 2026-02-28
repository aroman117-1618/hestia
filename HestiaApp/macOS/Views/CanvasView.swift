import SwiftUI

struct CanvasView: View {
    @Bindable var selectedTab: SelectedTab

    var body: some View {
        VStack(spacing: 0) {
            // Tab bar
            HStack(spacing: 0) {
                ForEach(WorkspaceTab.allCases) { tab in
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            selectedTab.current = tab
                        }
                    } label: {
                        VStack(spacing: 4) {
                            Image(systemName: tab.icon)
                                .font(.system(size: 14))
                            Text(tab.title)
                                .font(.caption2)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 8)
                        .background(
                            selectedTab.current == tab
                                ? Color.accentColor.opacity(0.15)
                                : Color.clear
                        )
                        .cornerRadius(6)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(.bar)

            Divider()

            // Content area
            PlaceholderContent(tab: selectedTab.current)
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }
}

// MARK: - Placeholder Content

private struct PlaceholderContent: View {
    let tab: WorkspaceTab

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: tab.icon)
                .font(.system(size: 48, weight: .light))
                .foregroundStyle(.secondary)

            Text(tab.title)
                .font(.title2)
                .fontWeight(.medium)

            Text("Coming in \(tab.phaseLabel)")
                .font(.subheadline)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}
