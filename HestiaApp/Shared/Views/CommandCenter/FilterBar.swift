import SwiftUI
import HestiaShared

/// Horizontal scrolling filter chips for newsfeed item types
struct FilterBar: View {
    @Binding var selectedFilter: NewsfeedItemType?
    let unreadByType: [String: Int]

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Spacing.sm) {
                // "All" chip
                filterChip(label: "All", isSelected: selectedFilter == nil, count: nil) {
                    selectedFilter = nil
                }

                // Type chips
                ForEach(NewsfeedItemType.allCases, id: \.self) { type in
                    let count = unreadByType[type.rawValue]
                    filterChip(
                        label: type.displayName,
                        isSelected: selectedFilter == type,
                        count: count
                    ) {
                        selectedFilter = (selectedFilter == type) ? nil : type
                    }
                }
            }
            .padding(.horizontal, Spacing.lg)
        }
    }

    private func filterChip(
        label: String,
        isSelected: Bool,
        count: Int?,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 4) {
                Text(label)
                    .font(.caption.weight(.semibold))

                if let count = count, count > 0 {
                    Text("\(count)")
                        .font(.caption2.weight(.bold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 1)
                        .background(Color.errorRed)
                        .cornerRadius(6)
                }
            }
            .foregroundColor(isSelected ? .white : .white.opacity(0.6))
            .padding(.vertical, Spacing.xs)
            .padding(.horizontal, Spacing.sm)
            .background(isSelected ? Color.white.opacity(0.2) : Color.white.opacity(0.05))
            .cornerRadius(CornerRadius.small)
        }
        .buttonStyle(.plain)
    }
}
