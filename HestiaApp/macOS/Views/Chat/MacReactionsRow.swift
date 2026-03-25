import SwiftUI

struct MacReactionsRow: View {
    let messageId: String
    let activeReactions: Set<String>
    let onReaction: (String) -> Void

    private let reactionIcons = [
        ("hand.thumbsup", "like"),
        ("hand.thumbsdown", "dislike"),
        ("arrow.counterclockwise", "retry"),
        ("flag", "flag"),
        ("doc.on.doc", "copy")
    ]

    var body: some View {
        HStack(spacing: MacSpacing.xs) {
            ForEach(reactionIcons, id: \.1) { icon, name in
                Button {
                    onReaction(name)
                } label: {
                    Image(systemName: activeReactions.contains(name) ? "\(icon).fill" : icon)
                        .font(MacTypography.caption)
                        .foregroundStyle(
                            activeReactions.contains(name)
                                ? MacColors.amberAccent
                                : MacColors.textSecondary
                        )
                        .frame(width: 22, height: 22)
                }
                .buttonStyle(.hestiaIcon)
            }
        }
    }
}
