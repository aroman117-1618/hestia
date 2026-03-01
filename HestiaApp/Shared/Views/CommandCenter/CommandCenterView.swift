import SwiftUI
import HestiaShared
import CoreData

/// Command Center view: BriefingCard > FilterBar > NewsfeedTimeline > NeuralNet
struct CommandCenterView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.managedObjectContext) private var viewContext
    @StateObject private var viewModel = NewsfeedViewModel()

    // Detail sheet for item actions
    @State private var selectedItem: NewsfeedItem? = nil
    @State private var showMemorySheet = false

    var body: some View {
        ZStack {
            GradientBackground(mode: appState.currentMode)

            ScrollView {
                VStack(spacing: Spacing.lg) {
                    // Header
                    header

                    // Briefing Card (persistent, above timeline)
                    BriefingCard(
                        briefing: viewModel.briefing,
                        isLoading: viewModel.isBriefingLoading,
                        isExpanded: $viewModel.isBriefingExpanded
                    )

                    // Filter Bar
                    FilterBar(
                        selectedFilter: $viewModel.selectedFilter,
                        unreadByType: viewModel.unreadByType
                    )

                    // Newsfeed Timeline
                    NewsfeedTimeline(viewModel: viewModel) { item in
                        handleItemTap(item)
                    }

                    // Neural Net Graph (collapsible section)
                    NeuralNetView()

                    Spacer()
                        .frame(height: Spacing.xl)
                }
                .padding(.top, Spacing.md)
            }
            .scrollContentBackground(.hidden)
            .refreshable {
                await viewModel.refresh()
                await viewModel.loadBriefing()
            }
        }
        .onAppear {
            Task {
                await viewModel.loadTimeline()
                await viewModel.loadUnreadCounts()
                await viewModel.loadBriefing()
            }
        }
        .sheet(isPresented: $showMemorySheet) {
            MemoryWidget()
        }
    }

    // MARK: - Header

    private var header: some View {
        HStack {
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text("Hello, Andrew")
                    .greetingStyle()

                if viewModel.unreadCount > 0 {
                    Text("You have \(viewModel.unreadCount) unread item\(viewModel.unreadCount == 1 ? "" : "s")")
                        .subheadingStyle()
                } else {
                    Text("All caught up")
                        .subheadingStyle()
                }
            }

            Spacer()

            // Avatar
            if let image = appState.currentMode.avatarImage {
                image
                    .resizable()
                    .scaledToFill()
                    .frame(width: Size.Avatar.small, height: Size.Avatar.small)
                    .clipShape(Circle())
            } else {
                Circle()
                    .fill(Color.white.opacity(0.2))
                    .frame(width: Size.Avatar.small, height: Size.Avatar.small)
                    .overlay(
                        Text(appState.currentMode.displayName.prefix(1))
                            .font(.system(size: 16, weight: .bold))
                            .foregroundColor(.white)
                    )
            }
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Item Tap Handling

    private func handleItemTap(_ item: NewsfeedItem) {
        switch item.type {
        case .memoryReview:
            showMemorySheet = true
        case .orderExecution:
            // Could navigate to order detail in future
            break
        case .taskUpdate:
            // Could navigate to task detail in future
            break
        case .healthInsight:
            // Could navigate to health tab in future
            break
        default:
            break
        }
    }
}

// MARK: - Preview

struct CommandCenterView_Previews: PreviewProvider {
    static var previews: some View {
        CommandCenterView()
            .environmentObject(AppState())
            .environment(\.managedObjectContext, PersistenceController.preview.viewContext)
    }
}
