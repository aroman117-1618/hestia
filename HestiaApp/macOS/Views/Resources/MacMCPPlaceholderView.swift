import SwiftUI
import HestiaShared

struct MacMCPPlaceholderView: View {
    var body: some View {
        VStack(spacing: MacSpacing.lg) {
            Spacer()

            Image(systemName: "cpu")
                .font(.system(size: 40))
                .foregroundStyle(MacColors.textFaint)

            Text("Model Context Protocol")
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(MacColors.textPrimary)

            Text("MCP server management coming in a future update.")
                .font(.system(size: 13))
                .foregroundStyle(MacColors.textSecondary)

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
