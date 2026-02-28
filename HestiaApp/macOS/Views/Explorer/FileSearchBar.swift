import SwiftUI

struct FileSearchBar: View {
    @Binding var searchText: String

    var body: some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 14))
                .foregroundStyle(MacColors.textFaint)

            TextField("Search files...", text: $searchText)
                .font(MacTypography.label)
                .textFieldStyle(.plain)
                .foregroundStyle(MacColors.textPrimary)

            if !searchText.isEmpty {
                Button { searchText = "" } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 12))
                        .foregroundStyle(MacColors.textSecondary)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
        .frame(height: MacSize.searchBarHeight)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        .padding(.horizontal, MacSpacing.md)
        .padding(.top, 14)
        .padding(.bottom, MacSpacing.sm)
    }
}
