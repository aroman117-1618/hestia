#if os(iOS)
import SwiftUI
import HestiaShared

/// Unified resource browser — mail, notes, tasks, drafts, files
struct ExplorerView: View {
    @StateObject private var viewModel = ExplorerViewModel()
    @State private var selectedTabIndex = 0
    @State private var showingNewDraft = false
    @State private var newDraftTitle = ""

    var body: some View {
        NavigationView {
            VStack(spacing: 0) {
                // Filter chips
                filterBar

                // Search
                searchBar

                // Resource list
                if viewModel.isLoading && viewModel.resources.isEmpty {
                    Spacer()
                    ProgressView()
                        .tint(.accent)
                    Spacer()
                } else if viewModel.resources.isEmpty {
                    emptyState
                } else {
                    resourceList
                }
            }
            .background(Color.bgBase)
            .navigationTitle("Explorer")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showingNewDraft = true
                    } label: {
                        Image(systemName: "square.and.pencil")
                            .foregroundColor(.textPrimary)
                    }
                }
            }
            .alert("New Draft", isPresented: $showingNewDraft) {
                TextField("Title", text: $newDraftTitle)
                Button("Create") {
                    guard !newDraftTitle.isEmpty else { return }
                    let title = newDraftTitle
                    newDraftTitle = ""
                    Task { await viewModel.createDraft(title: title) }
                }
                Button("Cancel", role: .cancel) { newDraftTitle = "" }
            }
            .task {
                await viewModel.loadResources()
            }
        }
    }

    // MARK: - Filter Bar

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Spacing.sm) {
                ForEach(Array(ExplorerViewModel.filterTabs.enumerated()), id: \.offset) { index, tab in
                    Button {
                        selectedTabIndex = index
                        Task { await viewModel.applyFilter(type: tab.type) }
                    } label: {
                        Text(tab.label)
                            .font(.subheadline.weight(selectedTabIndex == index ? .semibold : .regular))
                            .foregroundColor(selectedTabIndex == index ? .textPrimary : .textSecondary)
                            .padding(.horizontal, Spacing.md)
                            .padding(.vertical, Spacing.xs)
                            .background(
                                selectedTabIndex == index
                                    ? Color.bgOverlay
                                    : Color.clear
                            )
                            .cornerRadius(CornerRadius.button)
                    }
                }
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.vertical, Spacing.sm)
        }
    }

    // MARK: - Search

    private var searchBar: some View {
        HStack(spacing: Spacing.sm) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.textTertiary)

            TextField("Search resources...", text: $viewModel.searchText)
                .foregroundColor(.textPrimary)
                .autocapitalization(.none)
                .disableAutocorrection(true)
                .onSubmit {
                    Task { await viewModel.search() }
                }

            if !viewModel.searchText.isEmpty {
                Button {
                    viewModel.searchText = ""
                    Task { await viewModel.search() }
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.textTertiary)
                }
            }
        }
        .padding(Spacing.sm)
        .background(Color.bgSurface)
        .cornerRadius(CornerRadius.small)
        .padding(.horizontal, Spacing.lg)
        .padding(.bottom, Spacing.sm)
    }

    // MARK: - Resource List

    private var resourceList: some View {
        List {
            ForEach(viewModel.resources) { resource in
                ExplorerResourceRow(resource: resource)
                    .listRowBackground(Color.clear)
                    .listRowSeparatorTint(.iosCardBorder)
            }
            .onDelete { indexSet in
                guard let index = indexSet.first else { return }
                let resource = viewModel.resources[index]
                if resource.type == .draft {
                    Task { await viewModel.deleteDraft(resource) }
                }
            }
        }
        .listStyle(.plain)
        .refreshable {
            await viewModel.loadResources()
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()

            Image(systemName: selectedTabIcon)
                .font(.system(size: 48))
                .foregroundColor(.textTertiary)

            Text("No resources found")
                .font(.headline)
                .foregroundColor(.textSecondary)

            if !viewModel.searchText.isEmpty {
                Text("Try a different search term")
                    .font(.subheadline)
                    .foregroundColor(.textTertiary)
            }

            Spacer()
        }
    }

    private var selectedTabIcon: String {
        switch ExplorerViewModel.filterTabs[selectedTabIndex].type {
        case .draft: return "doc.text"
        case .mail: return "envelope"
        case .task: return "checklist"
        case .note: return "note.text"
        case .file: return "folder"
        case .none: return "square.grid.2x2"
        }
    }
}

// MARK: - Preview

struct ExplorerView_Previews: PreviewProvider {
    static var previews: some View {
        ExplorerView()
    }
}
#endif
