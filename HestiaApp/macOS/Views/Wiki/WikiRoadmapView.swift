import SwiftUI

struct WikiRoadmapView: View {
    @ObservedObject var viewModel: WikiViewModel
    @State private var expandedGroups: Set<String> = []

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: MacSpacing.md) {
                // "What's Next" banner
                if !viewModel.roadmapWhatsNext.isEmpty {
                    whatsNextBanner
                }

                // Milestone groups
                if viewModel.roadmapGroups.isEmpty {
                    emptyState
                } else {
                    ForEach(viewModel.roadmapGroups) { group in
                        milestoneGroupView(group)
                    }
                }
            }
            .padding(.horizontal, MacSpacing.xl)
            .padding(.vertical, MacSpacing.lg)
        }
        .onAppear {
            // Expand first group by default
            if let first = viewModel.roadmapGroups.first {
                expandedGroups.insert(first.id)
            }
        }
    }

    // MARK: - What's Next Banner

    private var whatsNextBanner: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "arrow.forward.circle.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(MacColors.amberAccent)
                Text("What's Next")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(MacColors.amberAccent)
            }

            Text(viewModel.roadmapWhatsNext)
                .font(.system(size: 12))
                .foregroundStyle(MacColors.textSecondary)
                .lineSpacing(4)
        }
        .padding(MacSpacing.md)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(MacColors.amberAccent.opacity(0.08))
        .overlay(
            RoundedRectangle(cornerRadius: MacCornerRadius.treeItem)
                .strokeBorder(MacColors.amberAccent.opacity(0.2), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
    }

    // MARK: - Milestone Group

    private func milestoneGroupView(_ group: WikiRoadmapMilestoneGroup) -> some View {
        DisclosureGroup(
            isExpanded: Binding(
                get: { expandedGroups.contains(group.id) },
                set: { isExpanded in
                    if isExpanded {
                        expandedGroups.insert(group.id)
                    } else {
                        expandedGroups.remove(group.id)
                    }
                }
            )
        ) {
            VStack(spacing: 2) {
                ForEach(group.milestones) { milestone in
                    milestoneRow(milestone)
                }
            }
            .padding(.top, MacSpacing.xs)
        } label: {
            HStack(spacing: MacSpacing.sm) {
                Text(group.title)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(MacColors.textPrimary)

                Text("\(group.milestones.count)")
                    .font(.system(size: 10, weight: .medium))
                    .foregroundStyle(MacColors.textFaint)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(MacColors.innerPillBackground)
                    .cornerRadius(4)

                Spacer()

                groupStatusSummary(group)
            }
        }
        .tint(MacColors.amberAccent)
    }

    // MARK: - Milestone Row

    private func milestoneRow(_ milestone: WikiRoadmapMilestone) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Circle()
                .fill(statusColor(for: milestone.status))
                .frame(width: 6, height: 6)

            Text(milestone.title)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(1)

            Spacer()

            Text(milestone.scope)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textFaint)
                .lineLimit(1)
                .frame(maxWidth: 250, alignment: .trailing)
        }
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, 4)
    }

    // MARK: - Helpers

    private func groupStatusSummary(_ group: WikiRoadmapMilestoneGroup) -> some View {
        let complete = group.milestones.filter { $0.status == "complete" }.count
        let total = group.milestones.count

        return HStack(spacing: 4) {
            if complete == total {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.healthGreen)
            }
            Text("\(complete)/\(total)")
                .font(.system(size: 10))
                .foregroundStyle(complete == total ? MacColors.healthGreen : MacColors.textFaint)
        }
    }

    private func statusColor(for status: String) -> Color {
        switch status {
        case "complete": return MacColors.healthGreen
        case "in_progress": return MacColors.amberAccent
        default: return MacColors.textFaint
        }
    }

    private var emptyState: some View {
        VStack(spacing: MacSpacing.md) {
            Spacer()
            Image(systemName: "flag.checkered")
                .font(.system(size: 32))
                .foregroundStyle(MacColors.textFaint)
            Text("No roadmap data")
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(MacColors.textSecondary)
            Text("Refresh static content to load the development timeline")
                .font(.system(size: 12))
                .foregroundStyle(MacColors.textFaint)
            Spacer()
        }
        .frame(maxWidth: .infinity)
    }
}
