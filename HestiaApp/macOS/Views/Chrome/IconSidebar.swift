import SwiftUI
import HestiaShared

struct IconSidebar: View {
    @Environment(WorkspaceState.self) private var workspace
    @State private var hoveredView: WorkspaceView?

    var body: some View {
        VStack(spacing: 0) {
            // Logo (top, sticky — navigates to Command Center)
            logoButton
                .padding(.top, MacSpacing.xl)

            // Nav icons (middle section, fixed order per design spec)
            VStack(spacing: 6) {
                navIcon(.command, systemName: "house", yOffset: 0)
                    .padding(.top, MacSpacing.lg)
                navIcon(.health, systemName: "waveform.path.ecg", yOffset: 1)
                navIcon(.research, systemName: "point.3.connected.trianglepath.dotted", yOffset: 2)
                navIcon(.wiki, systemName: "map", yOffset: 3)
                navIcon(.explorer, systemName: "magnifyingglass", yOffset: 4)
            }
            .padding(.top, MacSpacing.xxl)

            Spacer()

            // Profile (bottom, sticky — merged settings + avatar)
            profileButton
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
        Image("HestiaLogo")
            .resizable()
            .scaledToFit()
            .frame(width: MacSize.logoSize, height: MacSize.logoSize)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.navIcon))
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

    // MARK: - Profile Button (merged gear + avatar)

    private var profileButton: some View {
        let isActive = workspace.currentView == .profile
        let isHovered = hoveredView == .profile

        return Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                workspace.currentView = .profile
            }
        } label: {
            ZStack {
                // Avatar circle with gradient
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
                    .strokeBorder(
                        isActive ? MacColors.amberAccent : MacColors.avatarBorder,
                        lineWidth: isActive ? 1.5 : 1
                    )

                Text("HS")
                    .font(.system(size: 11))
                    .tracking(0.065)
                    .foregroundStyle(.white)
            }
            .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)
            .opacity(isHovered && !isActive ? 0.85 : 1.0)
        }
        .buttonStyle(.plain)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.15)) {
                hoveredView = hovering ? .profile : nil
            }
        }
    }
}
