import SwiftUI

struct DiagramNodeView: View {
    let icon: String
    let label: String
    var sublabel: String? = nil
    var accentColor: Color = MacColors.amberAccent
    var width: CGFloat = 110

    var body: some View {
        VStack(spacing: 4) {
            Image(systemName: icon)
                .font(MacTypography.body)
                .foregroundStyle(accentColor)
            Text(label)
                .font(MacTypography.sectionLabel)
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            if let sublabel = sublabel {
                Text(sublabel)
                    .font(MacTypography.micro)
                    .foregroundStyle(MacColors.textFaint)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
            }
        }
        .frame(width: width, height: sublabel != nil ? 60 : 48)
        .background(MacColors.cardGradient)
        .overlay(
            RoundedRectangle(cornerRadius: MacCornerRadius.tab)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.tab))
    }
}
