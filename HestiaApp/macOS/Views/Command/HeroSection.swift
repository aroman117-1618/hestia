import SwiftUI
import HestiaShared

struct HeroSection: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel
    let currentMode: HestiaMode
    @Environment(\.layoutMode) private var layoutMode
    @State private var showNewOrderSheet = false

    var body: some View {
        Group {
            if layoutMode.isCompact {
                VStack(alignment: .leading, spacing: MacSpacing.lg) {
                    heroContent
                    progressRings
                }
            } else {
                HStack(alignment: .top) {
                    heroContent
                    Spacer()
                    progressRings
                        .layoutPriority(1)
                }
            }
        }
        .padding(MacSpacing.xxl)
        .background(MacColors.cardGradient)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    private var heroContent: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            // Status badge row
            HStack(spacing: MacSpacing.md) {
                statusBadge
                if !layoutMode.isCompact, let lastUpdated = viewModel.lastUpdated {
                    Text(lastUpdated, style: .relative)
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                }
            }

            // Hero text with agent avatar
            HStack(spacing: MacSpacing.md) {
                // Agent avatar
                agentAvatar

                VStack(alignment: .leading, spacing: 2) {
                    Text(greetingText)
                        .font(MacTypography.heroHeading)
                        .foregroundStyle(MacColors.textPrimaryAlt)

                    Text(heroSubtitle)
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textSecondary)
                        .lineLimit(layoutMode.isCompact ? 2 : nil)
                }
            }
            .padding(.top, MacSpacing.sm)

            // Action buttons
            HStack(spacing: MacSpacing.md) {
                Button {
                    showNewOrderSheet = true
                } label: {
                    HStack(spacing: MacSpacing.sm) {
                        Image(systemName: "bolt.fill")
                            .font(MacTypography.body)
                        if !layoutMode.isCompact {
                            Text("New Order")
                                .font(MacTypography.bodyMedium)
                        }
                    }
                    .foregroundStyle(MacColors.buttonTextDark)
                    .padding(.horizontal, layoutMode.isCompact ? MacSpacing.md : MacSpacing.lg)
                    .padding(.vertical, MacSpacing.sm)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.hestia)

                Button {
                    // Navigate to External > Investigations tab
                    NotificationCenter.default.post(
                        name: .activityTabSwitch,
                        object: nil,
                        userInfo: ["tab": ActivityFeedTab.external.rawValue]
                    )
                } label: {
                    Text("View Reports")
                        .font(MacTypography.bodyMedium)
                        .foregroundStyle(MacColors.textPrimary)
                        .padding(.horizontal, layoutMode.isCompact ? MacSpacing.md : MacSpacing.lg)
                        .padding(.vertical, MacSpacing.sm)
                        .background(MacColors.searchInputBackground)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.hestia)
            }
            .padding(.top, MacSpacing.md)
            .sheet(isPresented: $showNewOrderSheet) {
                NewOrderSheet()
            }
        }
    }

    @ViewBuilder
    private var agentAvatar: some View {
        if let avatarImage = currentMode.avatarImage {
            avatarImage
                .resizable()
                .scaledToFill()
                .frame(width: 44, height: 44)
                .clipShape(Circle())
                .overlay {
                    Circle().strokeBorder(MacColors.aiAvatarBorder, lineWidth: 1.5)
                }
        } else {
            Circle()
                .fill(MacColors.aiAvatarBackground)
                .frame(width: 44, height: 44)
                .overlay {
                    Text(currentMode.displayName.prefix(1))
                        .font(MacTypography.pageTitle)
                        .foregroundStyle(MacColors.amberAccent)
                }
                .overlay {
                    Circle().strokeBorder(MacColors.aiAvatarBorder, lineWidth: 1.5)
                }
        }
    }

    private var progressRings: some View {
        HStack(spacing: layoutMode.isCompact ? MacSpacing.lg : MacSpacing.xl) {
            ProgressRing(
                value: internalRingValue,
                label: "\(viewModel.todayEventCount)",
                title: "Internal",
                subtitle: "Your Day",
                color: MacColors.healthGreen,
                layoutMode: layoutMode
            )
            ProgressRing(
                value: externalRingValue,
                label: "\(viewModel.externalUnreadCount)",
                title: "External",
                subtitle: "World Activity",
                color: MacColors.amberAccent,
                layoutMode: layoutMode
            )
            ProgressRing(
                value: systemRingValue,
                label: systemRingLabel,
                title: "System",
                subtitle: "Hestia Health",
                color: systemRingColor,
                layoutMode: layoutMode
            )
        }
    }

    // MARK: - Ring Computations

    /// Internal ring: calendar event count today, normalized to 0-8 events
    private var internalRingValue: Double {
        min(Double(viewModel.todayEventCount) / 8.0, 1.0)
    }

    /// External ring: unread newsfeed items, normalized to 0-20
    private var externalRingValue: Double {
        min(Double(viewModel.externalUnreadCount) / 20.0, 1.0)
    }

    /// System ring: server health (binary — up or down)
    private var systemRingValue: Double {
        viewModel.serverIsReachable ? 1.0 : 0.0
    }

    private var systemRingLabel: String {
        viewModel.serverIsReachable ? "OK" : "Down"
    }

    private var systemRingColor: Color {
        viewModel.serverIsReachable ? MacColors.healthGreen : MacColors.healthRed
    }

    // MARK: - Status Badge

    private var statusBadge: some View {
        HStack(spacing: MacSpacing.sm) {
            Circle()
                .fill(statusBadgeColor)
                .frame(width: 8, height: 8)
            Text(statusBadgeText)
                .font(MacTypography.label)
                .foregroundStyle(statusBadgeColor)
                .lineLimit(1)
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.xs)
        .background(statusBadgeColor.opacity(0.15))
        .clipShape(Capsule())
    }

    private var statusBadgeText: String {
        if viewModel.isLoading { return "Loading..." }
        if !viewModel.serverIsReachable { return "Server unreachable" }
        if viewModel.failedSections.isEmpty { return "All systems operational" }
        return "\(viewModel.failedSections.count) services degraded"
    }

    private var statusBadgeColor: Color {
        if viewModel.isLoading { return MacColors.textSecondary }
        if !viewModel.serverIsReachable { return MacColors.healthRed }
        if viewModel.failedSections.isEmpty { return MacColors.healthGreen }
        return MacColors.amberAccent
    }

    // MARK: - Hero Subtitle

    private var heroSubtitle: String {
        let modeName = currentMode.displayName
        if !viewModel.serverIsReachable {
            return "\(modeName) is offline. Check your connection."
        }
        let updates = viewModel.pendingMemoryCount
        if updates > 0 {
            return "\(modeName) is running smoothly. \(updates) update\(updates == 1 ? "" : "s") pending."
        }
        return "\(modeName) is running smoothly. All caught up."
    }

    private var greetingText: String {
        let hour = Calendar.current.component(.hour, from: Date())
        if hour < 12 { return "Morning Boss," }
        else if hour < 17 { return "Afternoon Boss," }
        else { return "Evening Boss," }
    }
}

// MARK: - Progress Ring

struct ProgressRing: View {
    let value: Double
    let label: String
    let title: String
    let subtitle: String
    let color: Color
    var layoutMode: LayoutMode = .regular

    private var ringLineWidth: CGFloat {
        switch layoutMode {
        case .compact: 4
        case .regular: 5
        case .wide: 6
        }
    }

    private var ringSize: CGFloat {
        switch layoutMode {
        case .compact: MacSize.progressRingSize * 0.65
        case .regular: MacSize.progressRingSize * 0.85
        case .wide: MacSize.progressRingSize
        }
    }

    private var labelFontSize: CGFloat {
        switch layoutMode {
        case .compact: 13
        case .regular: 16
        case .wide: 20
        }
    }

    var body: some View {
        VStack(spacing: MacSpacing.sm) {
            ZStack {
                Circle()
                    .stroke(color.opacity(0.15), lineWidth: ringLineWidth)
                Circle()
                    .trim(from: 0, to: value)
                    .stroke(color, style: StrokeStyle(lineWidth: ringLineWidth, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                Text(label)
                    .font(.system(size: labelFontSize, weight: .bold))
                    .foregroundStyle(MacColors.textPrimary)
            }
            .frame(width: ringSize, height: ringSize)

            if !layoutMode.isCompact {
                VStack(spacing: 2) {
                    Text(title)
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textPrimary)
                    if layoutMode.isWide {
                        Text(subtitle)
                            .font(MacTypography.metadata)
                            .foregroundStyle(MacColors.textSecondary)
                    }
                }
            }
        }
    }
}
