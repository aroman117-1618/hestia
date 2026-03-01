import SwiftUI
import HestiaShared

struct HeroSection: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel
    var isCompact: Bool = false

    var body: some View {
        Group {
            if isCompact {
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
                if !isCompact {
                    Text("Last updated 2 min ago")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                }
            }

            // Hero text
            Text(greetingText)
                .font(MacTypography.heroHeading)
                .foregroundStyle(MacColors.textPrimaryAlt)
                .padding(.top, MacSpacing.sm)

            // Subtitle
            Text("Stonehurst is running smoothly. 12 updates since your last session.")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textSecondary)
                .padding(.top, 2)
                .lineLimit(isCompact ? 2 : nil)

            // Action buttons
            HStack(spacing: MacSpacing.md) {
                Button {
                    // New Order action
                } label: {
                    HStack(spacing: MacSpacing.sm) {
                        Image(systemName: "bolt.fill")
                            .font(.system(size: 14))
                        if !isCompact {
                            Text("New Order")
                                .font(MacTypography.bodyMedium)
                        }
                    }
                    .foregroundStyle(MacColors.buttonTextDark)
                    .padding(.horizontal, isCompact ? MacSpacing.md : MacSpacing.lg)
                    .padding(.vertical, MacSpacing.sm)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.plain)

                Button {
                    // View Reports action
                } label: {
                    Text("View Reports")
                        .font(MacTypography.bodyMedium)
                        .foregroundStyle(MacColors.textPrimary)
                        .padding(.horizontal, isCompact ? MacSpacing.md : MacSpacing.lg)
                        .padding(.vertical, MacSpacing.sm)
                        .background(MacColors.searchInputBackground)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.plain)
            }
            .padding(.top, MacSpacing.md)
        }
    }

    private var progressRings: some View {
        HStack(spacing: isCompact ? MacSpacing.lg : MacSpacing.xl) {
            ProgressRing(value: 0.992, label: "99.2%", title: "Accuracy", subtitle: "E-commerce Engine", color: MacColors.healthGreen, isCompact: isCompact)
            ProgressRing(value: 0.87, label: "87%", title: "Uptime", subtitle: "Agent Fleet", color: MacColors.amberAccent, isCompact: isCompact)
            ProgressRing(value: 0.18, label: "18%", title: "Improved", subtitle: "Response Time", color: Color(hex: "00D7FF"), isCompact: isCompact)
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
    var isCompact: Bool = false

    var body: some View {
        VStack(spacing: MacSpacing.sm) {
            ZStack {
                Circle()
                    .stroke(color.opacity(0.15), lineWidth: isCompact ? 4 : 6)
                Circle()
                    .trim(from: 0, to: value)
                    .stroke(color, style: StrokeStyle(lineWidth: isCompact ? 4 : 6, lineCap: .round))
                    .rotationEffect(.degrees(-90))
                Text(label)
                    .font(.system(size: isCompact ? 14 : 20, weight: .bold))
                    .foregroundStyle(.white)
            }
            .frame(
                width: isCompact ? MacSize.progressRingSize * 0.7 : MacSize.progressRingSize,
                height: isCompact ? MacSize.progressRingSize * 0.7 : MacSize.progressRingSize
            )

            if !isCompact {
                VStack(spacing: 2) {
                    Text(title)
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textPrimary)
                    Text(subtitle)
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textSecondary)
                }
            }
        }
    }
}
