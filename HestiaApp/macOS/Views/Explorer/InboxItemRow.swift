import SwiftUI

// MARK: - Icon Helpers (internal — used by InboxItemRow + InboxDetailSheet)

func inboxItemIconColor(for item: InboxItemResponse) -> Color {
    switch item.source {
    case "mail": return MacColors.amberAccent
    case "reminders": return MacColors.healthGreen
    case "calendar": return Color(red: 90/255, green: 200/255, blue: 250/255)
    default: return MacColors.textSecondary
    }
}

func inboxItemIcon(for item: InboxItemResponse) -> String {
    switch item.source {
    case "mail": return "envelope.fill"
    case "reminders": return "checklist"
    case "calendar": return "calendar"
    default: return "bell.fill"
    }
}

func inboxSourceBadge(for item: InboxItemResponse) -> String {
    // Show folder/list from metadata, fallback to source name
    if let folder = item.metadataString("folder") {
        return "[\(folder)]"
    }
    if let list = item.metadataString("list_name") {
        return "[\(list)]"
    }
    if let calendar = item.metadataString("calendar_name") {
        return "[\(calendar)]"
    }
    switch item.source {
    case "mail": return "[Mail]"
    case "reminders": return "[Reminders]"
    case "calendar": return "[Calendar]"
    default: return "[\(item.source)]"
    }
}

// MARK: - Inbox Item Row

struct InboxItemRow: View {
    let item: InboxItemResponse
    let isSelected: Bool
    var onSelect: () -> Void
    var onMarkRead: () -> Void
    var onArchive: () -> Void

    @State private var isHovered = false

    var body: some View {
        Button {
            onSelect()
        } label: {
            HStack(spacing: MacSpacing.md) {
                // Source icon
                ZStack {
                    Circle()
                        .fill(inboxItemIconColor(for: item).opacity(0.15))
                        .frame(width: MacSize.feedItemIconSize, height: MacSize.feedItemIconSize)
                    Image(systemName: inboxItemIcon(for: item))
                        .font(.system(size: 14))
                        .foregroundStyle(inboxItemIconColor(for: item))
                }

                // Unread dot
                if !item.isRead {
                    Circle()
                        .fill(MacColors.unreadDot)
                        .frame(width: MacSize.statusDotSize, height: MacSize.statusDotSize)
                } else {
                    Spacer().frame(width: MacSize.statusDotSize)
                }

                // Title + sender + body preview
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: MacSpacing.sm) {
                        // Sender or title
                        if let sender = item.sender {
                            Text(sender)
                                .font(item.isRead ? MacTypography.label : MacTypography.labelMedium)
                                .foregroundStyle(MacColors.textPrimary)
                                .lineLimit(1)
                        }

                        Text(item.title)
                            .font(item.isRead ? MacTypography.label : MacTypography.labelMedium)
                            .foregroundStyle(item.sender != nil ? MacColors.textSecondary : MacColors.textPrimary)
                            .lineLimit(1)

                        // Priority badge for HIGH/URGENT
                        if item.priority == "high" || item.priority == "urgent" {
                            Text(item.priority.uppercased())
                                .font(MacTypography.micro)
                                .foregroundStyle(MacColors.healthRed)
                                .padding(.horizontal, MacSpacing.xs)
                                .padding(.vertical, 1)
                                .background(MacColors.healthRedBg)
                                .clipShape(RoundedRectangle(cornerRadius: 3))
                        }

                        // Attachment indicator
                        if item.hasAttachments {
                            Image(systemName: "paperclip")
                                .font(.system(size: 10))
                                .foregroundStyle(MacColors.textFaint)
                        }
                    }

                    // Body preview
                    if let body = item.body, !body.isEmpty {
                        Text(body)
                            .font(MacTypography.caption)
                            .foregroundStyle(MacColors.textFaint)
                            .lineLimit(1)
                    }
                }

                Spacer()

                // Source badge + timestamp
                VStack(alignment: .trailing, spacing: 2) {
                    Text(item.relativeTime)
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)

                    Text(inboxSourceBadge(for: item))
                        .font(MacTypography.micro)
                        .foregroundStyle(MacColors.textFaint)
                }
            }
            .frame(minHeight: MacSize.feedItemHeight)
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, MacSpacing.xs)
            .background(
                isSelected ? MacColors.activeTabBackground
                : isHovered ? MacColors.searchInputBackground
                : Color.clear
            )
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
        }
        .buttonStyle(.hestia)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.1)) {
                isHovered = hovering
            }
        }
        .contextMenu {
            contextMenuItems
        }
        .accessibilityLabel("\(item.isRead ? "" : "Unread, ")\(item.source) from \(item.sender ?? "unknown"): \(item.title)")
    }

    // MARK: - Context Menu

    @ViewBuilder
    private var contextMenuItems: some View {
        if !item.isRead {
            Button {
                onMarkRead()
            } label: {
                Label("Mark as Read", systemImage: "envelope.open")
            }
        }

        Button {
            onArchive()
        } label: {
            Label("Archive", systemImage: "archivebox")
        }
    }
}
