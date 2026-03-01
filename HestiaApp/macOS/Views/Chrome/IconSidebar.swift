import SwiftUI
import HestiaShared

struct IconSidebar: View {
    @Environment(WorkspaceState.self) private var workspace
    @State private var hoveredView: WorkspaceView?

    var body: some View {
        VStack(spacing: 0) {
            // Zap logo
            logoButton
                .padding(.top, MacSpacing.xl)

            // Nav icons
            VStack(spacing: 6) {
                navIcon(.command, systemName: "house", yOffset: 0)
                navIcon(.explorer, systemName: "map", yOffset: 1)
                    .padding(.top, MacSpacing.lg)
                navIcon(.resources, systemName: "server.rack", yOffset: 2)
                navIcon(.health, systemName: "heart", yOffset: 3)
                navIcon(.wiki, systemName: "book", yOffset: 4)
            }
            .padding(.top, MacSpacing.xxl)

            Spacer()

            // Bottom icons
            VStack(spacing: 7) {
                navIcon(.profile, systemName: "gearshape", yOffset: 5)

                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        workspace.currentView = .profile
                    }
                } label: {
                    userAvatar
                }
                .buttonStyle(.plain)
            }
            .padding(.bottom, MacSpacing.xxl)
        }
        .frame(width: MacSize.iconSidebarWidth)
        .background(MacColors.sidebarBackground)
        .overlay(alignment: .trailing) {
            MacColors.sidebarBorder.frame(width: 1)
        }
    }

    // MARK: - Logo

    private var logoButton: some View {
        ZStack {
            RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                .fill(MacColors.logoGradient)
                .frame(width: MacSize.logoSize, height: MacSize.logoSize)
            Image(systemName: "bolt.fill")
                .font(.system(size: MacSize.navIcon))
                .foregroundStyle(.white)
        }
    }

    // MARK: - Nav Icon

    private func navIcon(_ view: WorkspaceView, systemName: String, yOffset: Int) -> some View {
        let isActive = workspace.currentView == view
        let isHovered = hoveredView == view

        return Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                workspace.currentView = view
            }
        } label: {
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                    .fill(isActive ? MacColors.activeNavBackground : (isHovered ? MacColors.activeNavBackground.opacity(0.5) : Color.clear))
                    .overlay {
                        if isActive {
                            RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                                .strokeBorder(MacColors.activeNavBorder, lineWidth: 1)
                        }
                    }
                    .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)

                // Active indicator pill (left edge)
                if isActive {
                    UnevenRoundedRectangle(
                        topLeadingRadius: 0,
                        bottomLeadingRadius: 0,
                        bottomTrailingRadius: 8,
                        topTrailingRadius: 8
                    )
                    .fill(MacColors.activeIndicatorGradient)
                    .frame(width: MacSize.activeIndicatorWidth, height: MacSize.activeIndicatorHeight)
                    .offset(x: -1, y: 0)
                }

                Image(systemName: systemName)
                    .font(.system(size: MacSize.navIcon))
                    .foregroundStyle(isActive ? MacColors.amberAccent : (isHovered ? MacColors.textPrimary : MacColors.textSecondary))
                    .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)
            }
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.15)) {
                hoveredView = hovering ? view : nil
            }
        }
    }

    // MARK: - User Avatar

    private var userAvatar: some View {
        ZStack {
            Circle()
                .fill(
                    LinearGradient(
                        colors: [
                            Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.8),
                            Color(red: 254/255, green: 154/255, blue: 0).opacity(0.3)
                        ],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
            Circle()
                .strokeBorder(MacColors.avatarBorder, lineWidth: 1)
            Text("HS")
                .font(.system(size: 11))
                .tracking(0.065)
                .foregroundStyle(.white)
        }
        .frame(width: MacSize.userAvatarSize, height: MacSize.userAvatarSize)
    }
}
