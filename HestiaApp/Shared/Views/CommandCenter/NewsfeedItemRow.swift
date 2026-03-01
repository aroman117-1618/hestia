import SwiftUI
import HestiaShared

/// Single row in the newsfeed timeline
struct NewsfeedItemRow: View {
    let item: NewsfeedItem
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(alignment: .top, spacing: Spacing.sm) {
                // Type icon
                Image(systemName: item.displayIcon)
                    .font(.system(size: 18))
                    .foregroundColor(item.displayColor)
                    .frame(width: 32, height: 32)
                    .background(item.displayColor.opacity(0.15))
                    .cornerRadius(8)

                // Content
                VStack(alignment: .leading, spacing: 2) {
                    HStack {
                        Text(item.title)
                            .font(.subheadline.weight(.medium))
                            .foregroundColor(.white)
                            .lineLimit(1)

                        Spacer()

                        // Unread dot
                        if !item.isRead {
                            Circle()
                                .fill(Color(hex: "007AFF"))
                                .frame(width: 8, height: 8)
                        }
                    }

                    if let body = item.body, !body.isEmpty {
                        Text(body)
                            .font(.caption)
                            .foregroundColor(.white.opacity(0.6))
                            .lineLimit(2)
                    }

                    // Timestamp
                    Text(item.relativeTime)
                        .font(.caption2)
                        .foregroundColor(.white.opacity(0.4))
                }
            }
            .padding(.vertical, Spacing.sm)
            .padding(.horizontal, Spacing.md)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}
