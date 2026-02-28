import SwiftUI

struct SidebarView: View {
    @Bindable var selectedTab: SelectedTab

    var body: some View {
        List(WorkspaceTab.allCases, selection: Binding(
            get: { selectedTab.current },
            set: { selectedTab.current = $0 }
        )) { tab in
            Label(tab.title, systemImage: tab.icon)
                .tag(tab)
        }
        .listStyle(.sidebar)
        .frame(minWidth: 200)
    }
}
