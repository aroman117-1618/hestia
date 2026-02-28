import SwiftUI
import HestiaShared

struct TrendBadge: View {
    let value: String

    init(_ value: String) {
        self.value = value
    }

    var body: some View {
        HStack(spacing: 2) {
            Image(systemName: "arrow.up.right")
                .font(.system(size: 10, weight: .bold))
            Text(value)
                .font(MacTypography.label)
        }
        .foregroundStyle(MacColors.healthGreen)
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, MacSpacing.xs)
        .background(MacColors.healthGreenBg)
        .clipShape(Capsule())
    }
}
