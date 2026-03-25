import SwiftUI

/// Generic detail pane with a fixed header, scrollable content body, and optional footer.
///
/// Handles the three universal states (loading, error, empty) so individual detail
/// views only need to provide their content. Matches the structural pattern shared by
/// MacWikiDetailPane, MacWorkflowDetailPane, NodeDetailPopover, and
/// ResearchCanvasDetailPane.
struct HestiaDetailPane<Header: View, Content: View, Footer: View>: View {
    @ViewBuilder let header: () -> Header
    @ViewBuilder let content: () -> Content
    @ViewBuilder let footer: () -> Footer
    var isLoading: Bool = false
    var errorMessage: String? = nil
    var onRetry: (() -> Void)? = nil
    var isEmpty: Bool = false
    var emptyMessage: String = "Nothing selected"
    var width: CGFloat? = nil

    var body: some View {
        VStack(spacing: 0) {
            header()
                .padding(MacSpacing.md)
                .background(MacColors.windowBackground)

            MacColors.divider.frame(height: 1)

            bodyContent

            footer()
        }
        .frame(width: width)
        .background(MacColors.windowBackground)
    }

    @ViewBuilder
    private var bodyContent: some View {
        if isLoading {
            Spacer()
            ProgressView()
                .scaleEffect(0.8)
                .tint(MacColors.amberAccent)
            Spacer()
        } else if let error = errorMessage {
            Spacer()
            VStack(spacing: MacSpacing.sm) {
                Text(error)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.healthRed)
                    .multilineTextAlignment(.center)
                if let onRetry {
                    Button("Retry") { onRetry() }
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.amberAccent)
                        .buttonStyle(.plain)
                }
            }
            .padding(MacSpacing.md)
            Spacer()
        } else if isEmpty {
            Spacer()
            Text(emptyMessage)
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textFaint)
                .multilineTextAlignment(.center)
                .padding(MacSpacing.md)
            Spacer()
        } else {
            ScrollView {
                content()
                    .padding(MacSpacing.md)
            }
        }
    }
}

// MARK: - Convenience init (no footer)

extension HestiaDetailPane where Footer == EmptyView {
    init(
        @ViewBuilder header: @escaping () -> Header,
        @ViewBuilder content: @escaping () -> Content,
        isLoading: Bool = false,
        errorMessage: String? = nil,
        onRetry: (() -> Void)? = nil,
        isEmpty: Bool = false,
        emptyMessage: String = "Nothing selected",
        width: CGFloat? = nil
    ) {
        self.header = header
        self.content = content
        self.footer = { EmptyView() }
        self.isLoading = isLoading
        self.errorMessage = errorMessage
        self.onRetry = onRetry
        self.isEmpty = isEmpty
        self.emptyMessage = emptyMessage
        self.width = width
    }
}
