import SwiftUI

/// 3-state detail pane with sticky header, scrollable content,
/// and loading/error/empty states. Glass-styled with platform tokens.
struct HestiaGlassDetailPane<Header: View, Content: View>: View {
    @ViewBuilder let header: () -> Header
    @ViewBuilder let content: () -> Content
    var isLoading: Bool = false
    var errorMessage: String? = nil
    var isEmpty: Bool = false
    var emptyMessage: String = "Nothing selected"
    var onRetry: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: 0) {
            // Sticky header
            header()
                .padding(GlassSpacing.md)
                .frame(maxWidth: .infinity)
                .background(glassSurface)
                .overlay(alignment: .bottom) {
                    Rectangle()
                        .fill(glassDivider)
                        .frame(height: 0.5)
                }

            // Body — state-driven
            bodyContent
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .background(glassSurface)
        }
    }

    @ViewBuilder
    private var bodyContent: some View {
        if isLoading {
            loadingState
        } else if let error = errorMessage {
            errorState(error)
        } else if isEmpty {
            emptyState
        } else {
            ScrollView {
                content()
                    .padding(GlassSpacing.md)
            }
        }
    }

    // MARK: - States

    private var loadingState: some View {
        VStack {
            Spacer()
            ProgressView()
                .tint(glassAccent)
                .scaleEffect(0.8)
            Spacer()
        }
    }

    private func errorState(_ message: String) -> some View {
        VStack(spacing: GlassSpacing.md) {
            Spacer()
            Text(message)
                .font(.system(size: 13))
                .foregroundStyle(glassError)
                .multilineTextAlignment(.center)

            if let onRetry {
                HestiaGlassPill(title: "Retry", icon: "arrow.clockwise", tint: glassError, action: onRetry)
            }
            Spacer()
        }
        .padding(GlassSpacing.lg)
    }

    private var emptyState: some View {
        VStack {
            Spacer()
            Text(emptyMessage)
                .font(.system(size: 14))
                .foregroundStyle(glassTextTertiary)
                .multilineTextAlignment(.center)
            Spacer()
        }
        .padding(GlassSpacing.lg)
    }

    // MARK: - Platform-Resolved Colors

    private var glassSurface: Color {
        #if os(macOS)
        MacColors.windowBackground
        #else
        Color(hex: "1C1C1E")
        #endif
    }

    private var glassDivider: Color {
        #if os(macOS)
        MacColors.divider
        #else
        Color.white.opacity(0.08)
        #endif
    }

    private var glassAccent: Color {
        #if os(macOS)
        MacColors.amberAccent
        #else
        Color.agentAmber
        #endif
    }

    private var glassError: Color {
        #if os(macOS)
        MacColors.healthRed
        #else
        Color.errorRed
        #endif
    }

    private var glassTextTertiary: Color {
        #if os(macOS)
        MacColors.textPlaceholder
        #else
        Color.white.opacity(0.4)
        #endif
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 0) {
        // Loading state
        HestiaGlassDetailPane(
            header: { Text("Loading").foregroundStyle(.white) },
            content: { EmptyView() },
            isLoading: true
        )
        .frame(height: 200)

        // Error state
        HestiaGlassDetailPane(
            header: { Text("Error").foregroundStyle(.white) },
            content: { EmptyView() },
            errorMessage: "Failed to load data",
            onRetry: {}
        )
        .frame(height: 200)

        // Content state
        HestiaGlassDetailPane(
            header: { Text("Detail").foregroundStyle(.white).font(.headline) },
            content: {
                Text("Scrollable content goes here")
                    .foregroundStyle(.white)
            }
        )
        .frame(height: 200)
    }
    .background(Color.black)
}
