import SwiftUI

// MARK: - Multi-Tier Responsive Layout

/// Three-tier responsive breakpoint system replacing the binary `isCompact` flag.
/// Injected via environment from WorkspaceRootView's GeometryReader.
enum LayoutMode: Equatable {
    /// < 600px content width — single-column, icons only, minimal text
    case compact
    /// 600-900px — standard two-column, medium-sized elements
    case regular
    /// >= 900px — full layout, all labels visible, maximum information density
    case wide

    static func from(width: CGFloat) -> LayoutMode {
        if width < 600 { return .compact }
        else if width < 900 { return .regular }
        else { return .wide }
    }

    var isCompact: Bool { self == .compact }
    var isWide: Bool { self == .wide }
}

// MARK: - Environment Key

private struct LayoutModeKey: EnvironmentKey {
    static let defaultValue: LayoutMode = .regular
}

extension EnvironmentValues {
    var layoutMode: LayoutMode {
        get { self[LayoutModeKey.self] }
        set { self[LayoutModeKey.self] = newValue }
    }
}
