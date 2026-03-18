import SwiftUI
import HestiaShared

struct MemoryChunkRow: View {
    let chunk: MemoryChunkItem
    @ObservedObject var viewModel: MacMemoryBrowserViewModel
    var onChunkEdited: (() -> Void)? = nil

    @State private var isEditing = false
    @State private var editContent = ""
    @State private var editChunkType = ""
    @State private var isHovered = false

    var body: some View {
        if isEditing {
            editView
        } else {
            readView
                .onHover { isHovered = $0 }
        }
    }

    // MARK: - Read View

    private var readView: some View {
        HStack(spacing: MacSpacing.md) {
            // Type badge
            chunkTypeBadge
                .frame(width: 60)

            // Content + topics
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                Text(chunk.content)
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(2)

                if !chunk.topics.isEmpty {
                    topicPills
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)

            // Pencil edit button — visible on hover
            if isHovered {
                Button {
                    editContent = chunk.content
                    editChunkType = chunk.chunkType
                    isEditing = true
                } label: {
                    Image(systemName: "pencil")
                        .foregroundStyle(MacColors.textSecondary)
                }
                .buttonStyle(.plain)
            }

            // Importance indicator
            importanceIndicator
        }
        .padding(MacSpacing.md)
        .background(MacColors.cardGradient)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    // MARK: - Edit View

    private var editView: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            TextEditor(text: $editContent)
                .font(MacTypography.body)
                .frame(minHeight: 80)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(MacColors.amberAccent, lineWidth: 1))

            let chunkTypes: [(String, String)] = [
                ("fact", "Fact"), ("preference", "Preference"), ("decision", "Decision"),
                ("action_item", "Action Item"), ("research", "Research"),
                ("system", "System"), ("insight", "Insight")
            ]
            Picker("Type", selection: $editChunkType) {
                ForEach(chunkTypes, id: \.0) { value, label in
                    Text(label).tag(value)
                }
            }
            .pickerStyle(.menu)
            .frame(maxWidth: 160)

            HStack {
                Button("Save") {
                    Task {
                        await viewModel.updateChunk(
                            id: chunk.id,
                            content: editContent != chunk.content ? editContent : nil,
                            chunkType: editChunkType != chunk.chunkType ? editChunkType : nil,
                            tags: nil
                        )
                        isEditing = false
                        onChunkEdited?()
                    }
                }
                .buttonStyle(.borderedProminent)

                Button("Cancel") { isEditing = false }
                    .buttonStyle(.bordered)
            }
        }
        .padding(MacSpacing.sm)
        .background(MacColors.cardGradient)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    // MARK: - Type Badge

    private var chunkTypeBadge: some View {
        Text(chunk.chunkType.replacingOccurrences(of: "_", with: " ").capitalized)
            .font(MacTypography.micro)
            .fontWeight(.semibold)
            .padding(.horizontal, 6)
            .padding(.vertical, 3)
            .background(typeColor.opacity(0.15))
            .foregroundStyle(typeColor)
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    // MARK: - Topic Pills

    private var topicPills: some View {
        HStack(spacing: 4) {
            ForEach(chunk.topics.prefix(3), id: \.self) { topic in
                Text(topic)
                    .font(MacTypography.micro)
                    .foregroundStyle(MacColors.textFaint)
                    .padding(.horizontal, 4)
                    .padding(.vertical, 1)
                    .background(MacColors.innerPillBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 3))
            }
            if chunk.topics.count > 3 {
                Text("+\(chunk.topics.count - 3)")
                    .font(MacTypography.micro)
                    .foregroundStyle(MacColors.textFaint)
            }
        }
    }

    // MARK: - Importance Indicator

    private var importanceIndicator: some View {
        VStack(alignment: .trailing, spacing: 4) {
            Text(String(format: "%.0f%%", chunk.importance * 100))
                .font(MacTypography.captionMedium)
                .foregroundStyle(MacColors.textSecondary)

            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(MacColors.searchInputBackground)
                    RoundedRectangle(cornerRadius: 2)
                        .fill(importanceColor)
                        .frame(width: geo.size.width * CGFloat(min(chunk.importance, 1.0)))
                }
            }
            .frame(width: 60, height: 4)

            if let date = formattedDate {
                Text(date)
                    .font(MacTypography.micro)
                    .foregroundStyle(MacColors.textFaint)
            }
        }
        .frame(width: 70)
    }

    // MARK: - Helpers

    private var typeColor: Color {
        switch chunk.chunkType {
        case "preference": return .purple
        case "fact": return MacColors.diagramApple
        case "decision": return .orange
        case "action_item": return MacColors.healthGreen
        case "research": return MacColors.diagramCloud
        case "system": return MacColors.textSecondary
        case "insight": return MacColors.amberAccent
        default: return MacColors.textSecondary
        }
    }

    private var importanceColor: Color {
        if chunk.importance > 0.7 { return MacColors.healthGreen }
        if chunk.importance > 0.4 { return MacColors.healthAmber }
        return MacColors.healthRed
    }

    private var formattedDate: String? {
        guard !chunk.createdAt.isEmpty else { return nil }
        return String(chunk.createdAt.prefix(10))
    }
}
