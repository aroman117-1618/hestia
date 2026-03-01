import SwiftUI
import HestiaShared

/// Unified newsfeed timeline with swipe-to-dismiss and auto-mark-read
struct NewsfeedTimeline: View {
    @ObservedObject var viewModel: NewsfeedViewModel
    let onItemTap: (NewsfeedItem) -> Void

    var body: some View {
        if viewModel.isLoading && viewModel.items.isEmpty {
            loadingState
        } else if !viewModel.hasItems {
            emptyState
        } else {
            itemsList
        }
    }

    // MARK: - Items List

    private var itemsList: some View {
        LazyVStack(spacing: 0) {
            ForEach(viewModel.filteredItems) { item in
                NewsfeedItemRow(item: item) {
                    onItemTap(item)
                }
                .swipeActions(edge: .trailing, allowsFullSwipe: true) {
                    Button(role: .destructive) {
                        Task {
                            await viewModel.dismiss(item.id)
                        }
                    } label: {
                        Label("Dismiss", systemImage: "xmark.circle")
                    }
                }
                .onAppear {
                    // Auto-mark as read when item becomes visible
                    if !item.isRead {
                        Task {
                            await viewModel.markRead(item.id)
                        }
                    }
                }

                if item.id != viewModel.filteredItems.last?.id {
                    Divider()
                        .background(Color.white.opacity(0.06))
                        .padding(.leading, 52)
                }
            }
        }
        .background(Color.white.opacity(0.05))
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Empty State [P1]

    private var emptyState: some View {
        VStack(spacing: Spacing.md) {
            Image(systemName: "tray")
                .font(.system(size: 40))
                .foregroundColor(.white.opacity(0.3))

            Text("Nothing to see here")
                .font(.headline)
                .foregroundColor(.white.opacity(0.6))

            Text("Your timeline will populate as Hestia works — orders run, memories form, tasks update.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.4))
                .multilineTextAlignment(.center)
                .padding(.horizontal, Spacing.xl)

            Button {
                Task {
                    await viewModel.refresh()
                }
            } label: {
                Text("Refresh")
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.white)
                    .padding(.horizontal, Spacing.md)
                    .padding(.vertical, Spacing.xs)
                    .background(Color.white.opacity(0.15))
                    .cornerRadius(CornerRadius.small)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.xl)
    }

    // MARK: - Loading State

    private var loadingState: some View {
        VStack(spacing: Spacing.sm) {
            ProgressView()
                .tint(.white)
            Text("Loading timeline...")
                .font(.caption)
                .foregroundColor(.white.opacity(0.4))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Spacing.xl)
    }
}
