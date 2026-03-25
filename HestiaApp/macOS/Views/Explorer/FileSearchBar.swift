import SwiftUI

struct FileSearchBar: View {
    @Binding var searchText: String
    var onDebouncedSearch: ((String) -> Void)?
    @State private var localText: String = ""

    var body: some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: "magnifyingglass")
                .font(MacTypography.body)
                .foregroundStyle(MacColors.textFaint)

            TextField("Search files...", text: $localText)
                .font(MacTypography.label)
                .textFieldStyle(.plain)
                .foregroundStyle(MacColors.textPrimary)

            if !localText.isEmpty {
                Button {
                    localText = ""
                    searchText = ""
                    onDebouncedSearch?("")
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(MacTypography.smallBody)
                        .foregroundStyle(MacColors.textSecondary)
                }
                .buttonStyle(.hestiaIcon)
                .accessibilityLabel("Clear search")
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
        .onAppear { localText = searchText }
        .debounced(localText) { debounced in
            searchText = debounced
            onDebouncedSearch?(debounced)
        }
    }
}
