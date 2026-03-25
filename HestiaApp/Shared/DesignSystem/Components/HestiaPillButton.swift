import SwiftUI
import HestiaShared

/// Tinted pill-shaped button for quick actions and settings actions.
struct HestiaPillButton: View {
    let title: String
    let icon: String
    let tint: Color
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: Spacing.xs) {
                Image(systemName: icon)
                    .font(.system(size: 14, weight: .medium))
                Text(title)
                    .font(.caption.weight(.semibold))
            }
            .foregroundColor(tint)
            .padding(.horizontal, Spacing.md)
            .padding(.vertical, Spacing.sm)
            .background(tint.opacity(0.12))
            .cornerRadius(CornerRadius.small)
        }
        .buttonStyle(.plain)
        .accessibilityLabel(title)
    }
}

/// Settings block component — icon + title + subtitle, navigable with chevron.
struct HestiaSettingsBlock<Destination: View>: View {
    let icon: String
    let iconColor: Color
    let title: String
    let subtitle: String?
    let destination: Destination?

    init(
        icon: String,
        iconColor: Color,
        title: String,
        subtitle: String? = nil,
        @ViewBuilder destination: () -> Destination
    ) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.subtitle = subtitle
        self.destination = destination()
    }

    var body: some View {
        if let destination = destination {
            NavigationLink(destination: destination) {
                blockContent
            }
            .buttonStyle(.plain)
        } else {
            blockContent
        }
    }

    private var blockContent: some View {
        HStack(spacing: Spacing.md) {
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(iconColor)
                .frame(width: 36, height: 36)
                .background(iconColor.opacity(0.12))
                .cornerRadius(8)

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.body.weight(.medium))
                    .foregroundColor(.white)
                if let subtitle = subtitle {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.5))
                }
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.caption.weight(.semibold))
                .foregroundColor(.white.opacity(0.3))
        }
        .padding(Spacing.md)
        .background(Color.iosCardBackground)
        .cornerRadius(14)
        .overlay(
            RoundedRectangle(cornerRadius: 14)
                .stroke(Color.iosCardBorder, lineWidth: 0.5)
        )
    }
}

// Non-navigable overload
extension HestiaSettingsBlock where Destination == EmptyView {
    init(icon: String, iconColor: Color, title: String, subtitle: String? = nil) {
        self.icon = icon
        self.iconColor = iconColor
        self.title = title
        self.subtitle = subtitle
        self.destination = nil
    }
}
