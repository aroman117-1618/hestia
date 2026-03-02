import SwiftUI

struct DiagramLegendItem {
    let color: Color
    let label: String
}

struct DiagramLegendView: View {
    let items: [DiagramLegendItem]

    var body: some View {
        HStack(spacing: MacSpacing.lg) {
            ForEach(items.indices, id: \.self) { index in
                HStack(spacing: 4) {
                    Circle()
                        .fill(items[index].color)
                        .frame(width: 6, height: 6)
                    Text(items[index].label)
                        .font(.system(size: 9))
                        .foregroundStyle(MacColors.textFaint)
                }
            }
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.xs)
    }
}
