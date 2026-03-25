#if os(iOS)
import SwiftUI
import HestiaShared

/// Row cell for a single explorer resource
struct ExplorerResourceRow: View {
    let resource: ExplorerResource

    var body: some View {
        HStack(alignment: .top, spacing: Spacing.md) {
            // Type icon
            Image(systemName: iconName)
                .font(.system(size: 20))
                .foregroundColor(iconColor)
                .frame(width: 32, height: 32)

            // Content
            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: Spacing.xs) {
                    Text(resource.title)
                        .font(.body.weight(.medium))
                        .foregroundColor(.textPrimary)
                        .lineLimit(1)

                    Spacer()

                    // Flags
                    flagIcons
                }

                if let preview = resource.preview, !preview.isEmpty {
                    Text(preview)
                        .font(.caption)
                        .foregroundColor(.textSecondary)
                        .lineLimit(2)
                }

                // Metadata row
                HStack(spacing: Spacing.sm) {
                    Text(sourceLabel)
                        .font(.caption2)
                        .foregroundColor(.textTertiary)

                    if let date = formattedDate {
                        Text(date)
                            .font(.caption2)
                            .foregroundColor(.textTertiary)
                    }

                    if let extra = metadataExtra {
                        Text(extra)
                            .font(.caption2)
                            .foregroundColor(.textTertiary)
                    }
                }
            }
        }
        .padding(.vertical, 4)
    }

    // MARK: - Icon

    private var iconName: String {
        switch resource.type {
        case .draft: return "doc.text.fill"
        case .mail: return "envelope.fill"
        case .task: return "checklist"
        case .note: return "note.text"
        case .file: return "doc.fill"
        }
    }

    private var iconColor: Color {
        switch resource.type {
        case .draft: return .blue
        case .mail: return .cyan
        case .task: return .accent
        case .note: return .yellow
        case .file: return .statusNeutral
        }
    }

    // MARK: - Flags

    @ViewBuilder
    private var flagIcons: some View {
        HStack(spacing: 4) {
            if resource.flags.contains(.unread) {
                Circle()
                    .fill(Color.blue)
                    .frame(width: 8, height: 8)
            }
            if resource.flags.contains(.flagged) {
                Image(systemName: "flag.fill")
                    .font(.caption2)
                    .foregroundColor(.accent)
            }
            if resource.flags.contains(.urgent) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.caption2)
                    .foregroundColor(.red)
            }
        }
    }

    // MARK: - Metadata

    private var sourceLabel: String {
        switch resource.source {
        case .hestia: return "Hestia"
        case .mail: return "Mail"
        case .notes: return "Notes"
        case .reminders: return "Reminders"
        case .files: return "Files"
        }
    }

    private var formattedDate: String? {
        guard let dateStr = resource.modifiedAt ?? resource.createdAt else { return nil }
        let formatter = ISO8601DateFormatter()
        guard let date = formatter.date(from: dateStr) else { return nil }

        let relative = RelativeDateTimeFormatter()
        relative.unitsStyle = .abbreviated
        return relative.localizedString(for: date, relativeTo: Date())
    }

    private var metadataExtra: String? {
        if let sender = resource.metadata["sender"], !sender.isEmpty {
            return sender
        }
        if let folder = resource.metadata["folder"], !folder.isEmpty {
            return folder
        }
        if let list = resource.metadata["list"], !list.isEmpty {
            return list
        }
        return nil
    }
}

// MARK: - Preview

struct ExplorerResourceRow_Previews: PreviewProvider {
    static var previews: some View {
        VStack {
            ExplorerResourceRow(resource: ExplorerResource(
                id: "mail:123",
                type: .mail,
                title: "Weekly standup notes",
                source: .mail,
                modifiedAt: "2026-03-01T10:00:00",
                preview: "Hi team, here are the notes from today's standup...",
                flags: [.unread],
                metadata: ["sender": "alice@example.com"]
            ))
            ExplorerResourceRow(resource: ExplorerResource(
                id: "drafts:abc",
                type: .draft,
                title: "Project ideas",
                source: .hestia,
                preview: "Some thoughts about the next feature..."
            ))
        }
        .padding()
        .background(Color.black)
    }
}
#endif
