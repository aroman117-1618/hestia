import SwiftUI

struct PLLookbackToggle: View {
    @Binding var selection: NewsfeedTabViewModel.LookbackPeriod

    var body: some View {
        HStack(spacing: 2) {
            ForEach(NewsfeedTabViewModel.LookbackPeriod.allCases, id: \.self) { period in
                Button {
                    selection = period
                } label: {
                    Text(period.rawValue)
                        .font(.system(size: 10, weight: selection == period ? .semibold : .regular))
                        .foregroundStyle(selection == period ? Color(red: 0.051, green: 0.031, blue: 0.008) : MacColors.textSecondary)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(
                            RoundedRectangle(cornerRadius: 4)
                                .fill(selection == period ? MacColors.amberAccent : Color.clear)
                        )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(2)
        .background(
            RoundedRectangle(cornerRadius: 6)
                .fill(MacColors.searchInputBackground)
        )
    }
}
