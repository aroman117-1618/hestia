import SwiftUI
import HestiaShared

/// Right-side detail pane for the Research Canvas — shown when an entity is selected on the canvas.
struct ResearchCanvasDetailPane: View {
    @ObservedObject var viewModel: ResearchCanvasViewModel

    var body: some View {
        if let entity = viewModel.selectedEntity {
            VStack(spacing: 0) {
                // Header
                entityHeader(entity)

                Divider()
                    .overlay(MacColors.divider)

                // Scrollable content
                ScrollView {
                    VStack(alignment: .leading, spacing: MacSpacing.lg) {
                        descriptionSection(entity)
                        factsSection
                        referencesSection
                    }
                    .padding(MacSpacing.lg)
                }
            }
            .frame(width: 300)
            .background(MacColors.windowBackground)
            .overlay(
                Rectangle()
                    .frame(width: 1)
                    .foregroundStyle(MacColors.sidebarBorder),
                alignment: .leading
            )
            .transition(.move(edge: .trailing).combined(with: .opacity))
        }
    }

    // MARK: - Header

    private func entityHeader(_ entity: ResearchCanvasEntity) -> some View {
        HStack(spacing: MacSpacing.md) {
            // Type dot
            Circle()
                .fill(entityTypeColor(entity.entityType))
                .frame(width: 10, height: 10)

            VStack(alignment: .leading, spacing: 2) {
                Text(entity.name)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(2)

                Text(entity.entityType.capitalized)
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textSecondary)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 1)
                    .background(entityTypeColor(entity.entityType).opacity(0.15))
                    .clipShape(Capsule())
            }

            Spacer()

            // Close button
            Button {
                withAnimation(.easeInOut(duration: 0.15)) {
                    viewModel.clearSelection()
                }
            } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textSecondary)
                    .padding(MacSpacing.xs)
                    .background(MacColors.textPrimary.opacity(0.06))
                    .clipShape(Circle())
            }
            .buttonStyle(.plain)
        }
        .padding(MacSpacing.lg)
    }

    // MARK: - Description

    private func descriptionSection(_ entity: ResearchCanvasEntity) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            detailSectionTitle("Details")

            HStack(spacing: MacSpacing.sm) {
                detailLabel("Connections")
                Spacer()
                Text("\(entity.connectionCount)")
                    .font(.system(size: 12))
                    .foregroundStyle(MacColors.textPrimary)
            }

            if let created = entity.createdAt {
                HStack(spacing: MacSpacing.sm) {
                    detailLabel("Created")
                    Spacer()
                    Text(formatDate(created))
                        .font(.system(size: 12))
                        .foregroundStyle(MacColors.textSecondary)
                }
            }
        }
        .padding(MacSpacing.md)
        .hestiaPanel(cornerRadius: MacCornerRadius.tab)
    }

    // MARK: - Temporal Facts

    private var factsSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            detailSectionTitle("Temporal Facts")

            if viewModel.selectedEntityFacts.isEmpty {
                Text("No facts recorded")
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textFaint)
                    .padding(.vertical, MacSpacing.xs)
            } else {
                ForEach(viewModel.selectedEntityFacts) { fact in
                    factRow(fact)
                }
            }
        }
        .padding(MacSpacing.md)
        .hestiaPanel(cornerRadius: MacCornerRadius.tab)
    }

    private func factRow(_ fact: ResearchTemporalFact) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(fact.predicate)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(MacColors.textPrimary)

            HStack(spacing: MacSpacing.xs) {
                if let from = fact.validFrom {
                    Text("from \(formatDate(from))")
                        .font(.system(size: 10))
                        .foregroundStyle(MacColors.textFaint)
                }
                if let to = fact.validTo {
                    Text("to \(formatDate(to))")
                        .font(.system(size: 10))
                        .foregroundStyle(MacColors.textFaint)
                }
            }

            // Confidence bar
            HStack(spacing: MacSpacing.xs) {
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        RoundedRectangle(cornerRadius: 2)
                            .fill(MacColors.textPrimary.opacity(0.06))
                            .frame(height: 3)
                        RoundedRectangle(cornerRadius: 2)
                            .fill(confidenceColor(fact.confidence))
                            .frame(width: geo.size.width * fact.confidence, height: 3)
                    }
                }
                .frame(height: 3)

                Text(String(format: "%.0f%%", fact.confidence * 100))
                    .font(.system(size: 9))
                    .foregroundStyle(MacColors.textFaint)
                    .frame(width: 28, alignment: .trailing)
            }
        }
        .padding(.vertical, MacSpacing.xs)
    }

    // MARK: - Cross-References

    private var referencesSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            detailSectionTitle("Cross-Links")

            if viewModel.selectedEntityReferences.isEmpty {
                Text("No cross-links found")
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textFaint)
                    .padding(.vertical, MacSpacing.xs)
            } else {
                ForEach(viewModel.selectedEntityReferences) { ref in
                    referenceRow(ref)
                }
            }
        }
        .padding(MacSpacing.md)
        .hestiaPanel(cornerRadius: MacCornerRadius.tab)
    }

    private func referenceRow(_ ref: ResearchEntityReference) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: referenceIcon(ref.referenceType))
                .font(.system(size: 10))
                .foregroundStyle(referenceColor(ref.referenceType))
                .frame(width: 16)

            VStack(alignment: .leading, spacing: 1) {
                Text(ref.referenceLabel ?? ref.referenceId)
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)
                Text(ref.referenceType.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.system(size: 9))
                    .foregroundStyle(MacColors.textFaint)
            }

            Spacer()

            Image(systemName: "arrow.up.right")
                .font(.system(size: 9))
                .foregroundStyle(MacColors.textFaint)
        }
        .padding(.vertical, 3)
    }

    // MARK: - Helpers

    private func detailSectionTitle(_ title: String) -> some View {
        Text(title)
            .font(.system(size: 11, weight: .semibold))
            .foregroundStyle(MacColors.textSecondary)
            .textCase(.uppercase)
    }

    private func detailLabel(_ label: String) -> some View {
        Text(label)
            .font(.system(size: 12))
            .foregroundStyle(MacColors.textSecondary)
    }

    private func entityTypeColor(_ type: String) -> Color {
        switch type.lowercased() {
        case "person": return Color(red: 0.19, green: 0.82, blue: 0.35)
        case "organization": return Color(red: 0.35, green: 0.78, blue: 0.98)
        case "location": return Color(red: 1.0, green: 0.84, blue: 0.04)
        case "concept": return Color(red: 0.75, green: 0.35, blue: 0.95)
        default: return MacColors.textSecondary
        }
    }

    private func confidenceColor(_ confidence: Double) -> Color {
        if confidence >= 0.8 { return MacColors.statusGreen }
        if confidence >= 0.5 { return MacColors.statusWarning }
        return MacColors.statusCritical
    }

    private func referenceIcon(_ type: String) -> String {
        switch type.lowercased() {
        case "workflow": return "arrow.triangle.branch"
        case "chat", "conversation": return "bubble.left.and.bubble.right"
        case "command": return "terminal"
        case "memory": return "brain"
        default: return "link"
        }
    }

    private func referenceColor(_ type: String) -> Color {
        switch type.lowercased() {
        case "workflow": return MacColors.cyanAccent
        case "chat", "conversation": return MacColors.amberAccent
        case "command": return MacColors.blueAccent
        case "memory": return Color(red: 0.75, green: 0.35, blue: 0.95)
        default: return MacColors.textSecondary
        }
    }

    private func formatDate(_ isoString: String) -> String {
        // Simple date formatting — full ISO to short display
        if isoString.count >= 10 {
            let prefix = String(isoString.prefix(10))
            return prefix
        }
        return isoString
    }
}
