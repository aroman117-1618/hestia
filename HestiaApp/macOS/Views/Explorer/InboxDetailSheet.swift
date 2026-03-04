import SwiftUI
import HestiaShared

// MARK: - Inbox Detail Sheet (right panel in split view)

struct InboxDetailSheet: View {
    @ObservedObject var viewModel: MacInboxViewModel

    var body: some View {
        if let item = viewModel.selectedItem {
            VStack(alignment: .leading, spacing: 0) {
                // Header
                detailHeader(item)

                MacColors.divider.frame(height: 1)

                // Body content
                ScrollView {
                    VStack(alignment: .leading, spacing: MacSpacing.lg) {
                        // Metadata section (type-specific)
                        metadataSection(item)

                        // Body text
                        if let body = item.body, !body.isEmpty {
                            bodyContent(body, item: item)
                        } else {
                            Text("No content available")
                                .font(MacTypography.body)
                                .foregroundStyle(MacColors.textFaint)
                                .italic()
                        }
                    }
                    .padding(MacSpacing.xl)
                }

                MacColors.divider.frame(height: 1)

                // Action bar
                actionBar(item)
            }
            .background(MacColors.panelBackground)
        } else {
            // No selection placeholder
            VStack(spacing: MacSpacing.md) {
                Image(systemName: "envelope.open")
                    .font(.system(size: 36, weight: .light))
                    .foregroundStyle(MacColors.textFaint)
                Text("Select an item to view details")
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textSecondary)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(MacColors.panelBackground)
        }
    }

    // MARK: - Header

    private func detailHeader(_ item: InboxItemResponse) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack(spacing: MacSpacing.md) {
                // Source icon
                ZStack {
                    Circle()
                        .fill(inboxItemIconColor(for: item).opacity(0.15))
                        .frame(width: 40, height: 40)
                    Image(systemName: inboxItemIcon(for: item))
                        .font(.system(size: 18))
                        .foregroundStyle(inboxItemIconColor(for: item))
                }

                VStack(alignment: .leading, spacing: 2) {
                    Text(item.title)
                        .font(MacTypography.cardTitle)
                        .foregroundStyle(MacColors.textPrimary)
                        .lineLimit(2)

                    HStack(spacing: MacSpacing.sm) {
                        if let sender = item.sender {
                            Text(sender)
                                .font(MacTypography.label)
                                .foregroundStyle(MacColors.textSecondary)

                            if let detail = item.senderDetail {
                                Text(detail)
                                    .font(MacTypography.caption)
                                    .foregroundStyle(MacColors.textFaint)
                            }
                        }
                    }
                }

                Spacer()

                // Close button
                Button {
                    viewModel.selectedItem = nil
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(MacColors.textFaint)
                        .frame(width: 24, height: 24)
                        .background(MacColors.searchInputBackground)
                        .clipShape(Circle())
                }
                .buttonStyle(.hestia)
                .accessibilityLabel("Close detail panel")
            }

            // Date + priority + attachment indicators
            HStack(spacing: MacSpacing.md) {
                Text(item.formattedDate)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)

                if item.priority == "high" || item.priority == "urgent" {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .font(.system(size: 10))
                        Text(item.priority.capitalized)
                            .font(MacTypography.captionMedium)
                    }
                    .foregroundStyle(MacColors.healthRed)
                }

                if item.hasAttachments {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "paperclip")
                            .font(.system(size: 10))
                        Text("Attachments")
                            .font(MacTypography.caption)
                    }
                    .foregroundStyle(MacColors.textFaint)
                }

                Text(inboxSourceBadge(for: item))
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)

                Spacer()
            }
        }
        .padding(MacSpacing.xl)
    }

    // MARK: - Metadata Section (type-specific)

    @ViewBuilder
    private func metadataSection(_ item: InboxItemResponse) -> some View {
        switch item.source {
        case "reminders":
            reminderMetadata(item)
        case "calendar":
            calendarMetadata(item)
        default:
            EmptyView()
        }
    }

    private func reminderMetadata(_ item: InboxItemResponse) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            if let dueDate = item.metadataString("due_date") {
                metadataRow(icon: "clock", label: "Due", value: dueDate)
            }
            if let listName = item.metadataString("list_name") {
                metadataRow(icon: "list.bullet", label: "List", value: listName)
            }
            metadataRow(icon: "flag", label: "Priority", value: item.priority.capitalized)
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    private func calendarMetadata(_ item: InboxItemResponse) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            if let startTime = item.metadataString("start_time") {
                metadataRow(icon: "clock", label: "Time", value: startTime)
            }
            if let endTime = item.metadataString("end_time") {
                metadataRow(icon: "clock.arrow.circlepath", label: "End", value: endTime)
            }
            if let location = item.metadataString("location") {
                metadataRow(icon: "mappin", label: "Location", value: location)
            }
            if let attendees = item.metadataString("attendees") {
                metadataRow(icon: "person.2", label: "Attendees", value: attendees)
            }
            if let calendarName = item.metadataString("calendar_name") {
                metadataRow(icon: "calendar", label: "Calendar", value: calendarName)
            }
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    private func metadataRow(icon: String, label: String, value: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.amberAccent)
                .frame(width: 16)

            Text(label)
                .font(MacTypography.captionMedium)
                .foregroundStyle(MacColors.textSecondary)
                .frame(width: 70, alignment: .leading)

            Text(value)
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textPrimary)

            Spacer()
        }
    }

    // MARK: - Body Content

    private func bodyContent(_ body: String, item: InboxItemResponse) -> some View {
        Group {
            if item.source == "mail" {
                // Email: monospace for plain text
                Text(body)
                    .font(MacTypography.code)
                    .foregroundStyle(MacColors.textPrimary)
                    .textSelection(.enabled)
            } else {
                // Other sources: body font
                Text(body)
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textPrimary)
                    .textSelection(.enabled)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Action Bar

    private func actionBar(_ item: InboxItemResponse) -> some View {
        HStack(spacing: MacSpacing.md) {
            if !item.isRead {
                Button {
                    Task { [weak viewModel] in
                        await viewModel?.selectItem(item)
                    }
                } label: {
                    HStack(spacing: MacSpacing.xs) {
                        Image(systemName: "envelope.open")
                            .font(.system(size: 12))
                        Text("Mark Read")
                            .font(MacTypography.label)
                    }
                    .foregroundStyle(MacColors.amberAccent)
                    .padding(.horizontal, MacSpacing.md)
                    .padding(.vertical, MacSpacing.xs)
                }
                .buttonStyle(.hestia)
                .accessibilityLabel("Mark item as read")
            }

            Button {
                Task { [weak viewModel] in
                    await viewModel?.archiveItem(item)
                }
            } label: {
                HStack(spacing: MacSpacing.xs) {
                    Image(systemName: "archivebox")
                        .font(.system(size: 12))
                    Text("Archive")
                        .font(MacTypography.label)
                }
                .foregroundStyle(MacColors.textSecondary)
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, MacSpacing.xs)
            }
            .buttonStyle(.hestia)
            .accessibilityLabel("Archive this item")

            Spacer()

            if viewModel.isLoadingDetail {
                ProgressView()
                    .controlSize(.small)
                    .tint(MacColors.amberAccent)
            }
        }
        .padding(.horizontal, MacSpacing.lg)
        .padding(.vertical, MacSpacing.sm)
    }
}
