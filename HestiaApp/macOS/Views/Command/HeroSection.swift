import SwiftUI
import HestiaShared

struct HeroSection: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel
    let currentMode: HestiaMode
    @Environment(\.layoutMode) private var layoutMode

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
                if !layoutMode.isCompact {
                    Text("Last updated 2 min ago")
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

                    Text("Stonehurst is running smoothly. 12 updates since your last session.")
                        .font(MacTypography.body)
                        .foregroundStyle(MacColors.textSecondary)
                        .lineLimit(layoutMode.isCompact ? 2 : nil)
                }
            }
            .padding(.top, MacSpacing.sm)

            // Action buttons
            HStack(spacing: MacSpacing.md) {
                Button {
                    // New Order action
                } label: {
                    HStack(spacing: MacSpacing.sm) {
                        Image(systemName: "bolt.fill")
                            .font(.system(size: 14))
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
                    // View Reports action
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
                        .font(.system(size: 18, weight: .bold))
                        .foregroundStyle(MacColors.amberAccent)
                }
                .overlay {
                    Circle().strokeBorder(MacColors.aiAvatarBorder, lineWidth: 1.5)
                }
        }
    }

    private var progressRings: some View {
        HStack(spacing: layoutMode.isCompact ? MacSpacing.lg : MacSpacing.xl) {
            ProgressRing(value: 0.992, label: "99.2%", title: "Accuracy", subtitle: "E-commerce Engine", color: MacColors.healthGreen, layoutMode: layoutMode)
            ProgressRing(value: 0.87, label: "87%", title: "Uptime", subtitle: "Agent Fleet", color: MacColors.amberAccent, layoutMode: layoutMode)
            ProgressRing(value: 0.18, label: "18%", title: "Improved", subtitle: "Response Time", color: Color(hex: "00D7FF"), layoutMode: layoutMode)
        }
    }

    private var statusBadge: some View {
        HStack(spacing: MacSpacing.sm) {
            Circle()
                .fill(MacColors.healthGreen)
                .frame(width: 8, height: 8)
            Text("All systems operational")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.healthGreen)
                .lineLimit(1)
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.xs)
        .background(MacColors.healthGreenBg)
        .clipShape(Capsule())
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
                    .foregroundStyle(.white)
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
