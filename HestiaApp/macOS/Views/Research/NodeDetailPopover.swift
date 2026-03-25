import SwiftUI
import HestiaShared

/// Type-appropriate detail panel for a selected graph node.
/// Memory nodes show chunk content; topic/entity nodes show connected counts;
/// principle nodes show approve/reject buttons; community/episode/fact nodes
/// show their specific metadata.
struct NodeDetailPopover: View {
    let node: MacNeuralNetViewModel.GraphNode
    let connectedNodes: [MacNeuralNetViewModel.GraphNode]
    @ObservedObject var viewModel: MacNeuralNetViewModel
    let onClose: () -> Void
    let onSelectNode: (MacNeuralNetViewModel.GraphNode) -> Void
    var onReviewMemory: ((String) -> Void)? = nil

    @State private var crossLinks: [ResearchEntityReference] = []
    @State private var isLoadingCrossLinks = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: MacSpacing.lg) {
                header
                confidenceBar
                contentSection
                metadataSection
                tagsSection
                connectedSection
                crossLinksSection
                Spacer(minLength: MacSpacing.md)
                actionButtons
            }
            .padding(MacSpacing.lg)
        }
        .hestiaPanel(cornerRadius: 0)
        .overlay(alignment: .leading) {
            Rectangle()
                .fill(MacColors.amberAccent.opacity(0.1))
                .frame(width: 1)
        }
        .task(id: node.id) {
            await loadCrossLinks()
        }
    }

    // MARK: - Cross-Link Loading

    private func loadCrossLinks() async {
        // Only load for entity nodes — they are the ones registered in entity_references
        guard node.nodeType == "entity" || node.nodeType == "topic" || node.nodeType == "fact" || node.nodeType == "principle" else {
            crossLinks = []
            return
        }
        isLoadingCrossLinks = true
        defer { isLoadingCrossLinks = false }
        do {
            let response: ResearchEntityReferenceListResponse = try await APIClient.shared.get("/research/entities/\(node.id)/references?limit=50")
            crossLinks = response.references
        } catch {
            crossLinks = []
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack {
            Image(systemName: node.displayIcon)
                .font(MacTypography.body)
                .foregroundStyle(node.swiftUIColor)
            Text(node.displayName)
                .font(MacTypography.labelMedium)
                .foregroundStyle(node.swiftUIColor)

            if node.nodeType == "topic" || node.nodeType == "entity" || node.nodeType == "community" {
                Text("(\(connectedNodes.count) connected)")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)
            }

            Spacer()

            Button(action: onClose) {
                Image(systemName: "xmark")
                    .font(MacTypography.captionMedium)
                    .foregroundStyle(MacColors.textSecondary)
                    .frame(width: 24, height: 24)
                    .background(MacColors.textPrimary.opacity(0.06))
                    .clipShape(Circle())
            }
            .buttonStyle(.hestia)
            .accessibilityLabel("Close detail panel")
        }
    }

    // MARK: - Confidence

    private var confidenceBar: some View {
        HStack(spacing: MacSpacing.xs) {
            Text(node.nodeType == "memory" ? "Importance" : "Confidence")
                .font(MacTypography.caption)
                .foregroundStyle(MacColors.textFaint)
            Spacer()

            // Visual bar
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(MacColors.textPrimary.opacity(0.06))
                    RoundedRectangle(cornerRadius: 2)
                        .fill(node.swiftUIColor.opacity(0.6))
                        .frame(width: geo.size.width * node.confidence)
                }
            }
            .frame(width: 60, height: 4)

            Text("\(Int(node.confidence * 100))%")
                .font(MacTypography.smallMedium)
                .foregroundStyle(MacColors.textSecondary)
        }
    }

    // MARK: - Content

    private var contentSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            if node.nodeType == "topic" || node.nodeType == "entity" || node.nodeType == "community" {
                Text(node.label)
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)
                Text(node.content)
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.textSecondary)
            } else {
                Text(node.content.strippingBracketPrefixes())
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                    .fixedSize(horizontal: false, vertical: true)
                    .textSelection(.enabled)
            }
        }
    }

    // MARK: - Type-specific metadata

    @ViewBuilder
    private var metadataSection: some View {
        switch node.nodeType {
        case "community":
            communityMetadata
        case "episode":
            episodeMetadata
        case "fact":
            factMetadata
        default:
            EmptyView()
        }
    }

    private var communityMetadata: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("Community Details")
                .font(MacTypography.captionMedium)
                .foregroundStyle(MacColors.textFaint)

            HStack(spacing: MacSpacing.md) {
                metadataChip(icon: "person.3", label: "\(connectedNodes.count) members")
            }
        }
    }

    private var episodeMetadata: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("Episode Details")
                .font(MacTypography.captionMedium)
                .foregroundStyle(MacColors.textFaint)

            HStack(spacing: MacSpacing.md) {
                metadataChip(icon: "person.text.rectangle", label: "\(connectedNodes.count) entities")
            }
        }
    }

    private var factMetadata: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            Text("Fact Details")
                .font(MacTypography.captionMedium)
                .foregroundStyle(MacColors.textFaint)

            HStack(spacing: MacSpacing.md) {
                metadataChip(icon: "link", label: "Relationship")
                metadataChip(icon: "percent", label: "\(Int(node.confidence * 100))% conf.")
            }
        }
    }

    private func metadataChip(icon: String, label: String) -> some View {
        HStack(spacing: 3) {
            Image(systemName: icon)
                .font(MacTypography.micro)
            Text(label)
                .font(MacTypography.metadata)
        }
        .foregroundStyle(MacColors.textSecondary)
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, 3)
        .background(MacColors.textPrimary.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: 4))
    }

    // MARK: - Tags

    @ViewBuilder
    private var tagsSection: some View {
        if !node.topics.isEmpty || !node.entities.isEmpty {
            VStack(alignment: .leading, spacing: MacSpacing.md) {
                if !node.topics.isEmpty {
                    VStack(alignment: .leading, spacing: MacSpacing.sm) {
                        Text("Topics")
                            .font(MacTypography.captionMedium)
                            .foregroundStyle(MacColors.textFaint)

                        FlowLayout(spacing: MacSpacing.xs) {
                            ForEach(node.topics, id: \.self) { topic in
                                tagPill(topic, color: MacColors.amberAccent, backgroundOpacity: 0.15)
                            }
                        }
                    }
                }

                if !node.entities.isEmpty {
                    VStack(alignment: .leading, spacing: MacSpacing.sm) {
                        Text("Entities")
                            .font(MacTypography.captionMedium)
                            .foregroundStyle(MacColors.textFaint)

                        FlowLayout(spacing: MacSpacing.xs) {
                            ForEach(node.entities, id: \.self) { entity in
                                entityPill(entity)
                            }
                        }
                    }
                }
            }
        }
    }

    // MARK: - Connected Nodes

    @ViewBuilder
    private var connectedSection: some View {
        if !connectedNodes.isEmpty {
            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                Text("Connected (\(connectedNodes.count))")
                    .font(MacTypography.captionMedium)
                    .foregroundStyle(MacColors.textFaint)

                ForEach(connectedNodes.prefix(10)) { connectedNode in
                    Button {
                        onSelectNode(connectedNode)
                    } label: {
                        HStack(spacing: MacSpacing.sm) {
                            Image(systemName: connectedNode.displayIcon)
                                .font(MacTypography.caption)
                                .foregroundStyle(connectedNode.swiftUIColor)
                                .frame(width: 20)

                            VStack(alignment: .leading, spacing: 1) {
                                Text((connectedNode.label.isEmpty ? connectedNode.content : connectedNode.label).strippingBracketPrefixes())
                                    .font(MacTypography.caption)
                                    .foregroundStyle(MacColors.textPrimary)
                                    .lineLimit(1)
                                Text(connectedNode.displayName)
                                    .font(MacTypography.metadata)
                                    .foregroundStyle(MacColors.textFaint)
                            }

                            Spacer()

                            RoundedRectangle(cornerRadius: 1.5)
                                .fill(connectedNode.swiftUIColor.opacity(0.4))
                                .frame(width: 24, height: 3)
                        }
                        .padding(.vertical, MacSpacing.xs)
                        .padding(.horizontal, MacSpacing.sm)
                        .background(MacColors.textPrimary.opacity(0.03))
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
                    }
                    .buttonStyle(.hestia)
                }

                if connectedNodes.count > 10 {
                    Text("+\(connectedNodes.count - 10) more")
                        .font(MacTypography.metadata)
                        .foregroundStyle(MacColors.textFaint)
                }
            }
        } else {
            HStack {
                Image(systemName: "circle.dotted")
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.textFaint)
                Text("No connections")
                    .font(MacTypography.smallBody)
                    .foregroundStyle(MacColors.textFaint)
            }
            .padding(.vertical, MacSpacing.sm)
        }
    }

    // MARK: - Cross-Links

    @ViewBuilder
    private var crossLinksSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack {
                Text("Cross-Links")
                    .font(MacTypography.captionMedium)
                    .foregroundStyle(MacColors.textFaint)
                if isLoadingCrossLinks {
                    ProgressView()
                        .scaleEffect(0.5)
                        .frame(width: 12, height: 12)
                }
            }

            if crossLinks.isEmpty && !isLoadingCrossLinks {
                Text("No cross-links")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)
                    .padding(.vertical, MacSpacing.xs)
            } else {
                FlowLayout(spacing: MacSpacing.xs) {
                    ForEach(crossLinks) { ref in
                        HestiaCrossLinkBadge(
                            module: ref.referenceType,
                            itemId: ref.referenceId,
                            context: ref.referenceLabel ?? ref.referenceId
                        )
                    }
                }
            }
        }
    }

    // MARK: - Actions

    private var actionButtons: some View {
        VStack(spacing: MacSpacing.sm) {
            // For principle nodes: approve/reject
            if node.nodeType == "principle" {
                HStack(spacing: MacSpacing.sm) {
                    Button {
                        Task { await viewModel.approvePrinciple(node.id) }
                    } label: {
                        HStack {
                            Image(systemName: "checkmark")
                            Text("Approve")
                        }
                        .font(MacTypography.smallMedium)
                        .foregroundStyle(MacColors.buttonTextDark)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, MacSpacing.sm)
                        .background(MacColors.healthGreen)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                    }
                    .buttonStyle(.plain)

                    Button {
                        Task { await viewModel.rejectPrinciple(node.id) }
                    } label: {
                        HStack {
                            Image(systemName: "xmark")
                            Text("Reject")
                        }
                        .font(MacTypography.smallMedium)
                        .foregroundStyle(MacColors.healthRed)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, MacSpacing.sm)
                        .overlay(
                            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                                .strokeBorder(MacColors.healthRed.opacity(0.3), lineWidth: 1)
                        )
                    }
                    .buttonStyle(.plain)
                }
            }

            // For fact nodes: mark outdated
            if node.nodeType == "fact" {
                Button {
                    Task { await viewModel.markFactOutdated(node.id) }
                } label: {
                    HStack {
                        Image(systemName: "clock.badge.xmark")
                        Text("Mark Outdated")
                    }
                    .font(MacTypography.smallMedium)
                    .foregroundStyle(MacColors.healthAmber)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, MacSpacing.sm)
                    .overlay(
                        RoundedRectangle(cornerRadius: MacCornerRadius.search)
                            .strokeBorder(MacColors.healthAmber.opacity(0.3), lineWidth: 1)
                    )
                }
                .buttonStyle(.plain)
            }

            // Review in Memory Browser button (all node types)
            Button {
                onReviewMemory?(node.id)
            } label: {
                HStack {
                    Text("Review Memory")
                    Spacer()
                    Image(systemName: "arrow.right")
                        .font(MacTypography.caption)
                }
                .font(MacTypography.labelMedium)
                .foregroundStyle(MacColors.buttonTextDark)
                .padding(.horizontal, MacSpacing.md)
                .padding(.vertical, MacSpacing.sm + 2)
                .background(MacColors.amberAccent)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            }
            .buttonStyle(.hestia)
        }
    }

    // MARK: - Helpers

    // strippingBracketPrefixes moved to String extension (StringExtensions.swift)

    private func tagPill(_ text: String, color: Color, backgroundOpacity: Double = 0.12) -> some View {
        Text(text)
            .font(MacTypography.metadata)
            .foregroundStyle(color)
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, 3)
            .background(color.opacity(backgroundOpacity))
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    private func entityPill(_ text: String) -> some View {
        Text(text)
            .font(MacTypography.metadata)
            .foregroundStyle(MacColors.textSecondary)
            .padding(.horizontal, MacSpacing.sm)
            .padding(.vertical, 3)
            .background(MacColors.searchInputBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }
}
