import SwiftUI
import HestiaShared

/// View for reviewing and approving staged memory updates (ADR-002)
struct MemoryReviewView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = MemoryReviewViewModel()
    @State private var showingApprovalSheet = false
    @State private var reviewerNotes = ""

    var body: some View {
        ZStack {
            // Background
            GradientBackground(mode: appState.currentMode)

            if viewModel.isLoading && viewModel.pendingReviews.isEmpty {
                loadingState
            } else if viewModel.pendingReviews.isEmpty {
                emptyState
            } else {
                reviewList
            }
        }
        .navigationTitle("Memory Review")
        .navigationBarTitleDisplayMode(.large)
        .onAppear {
            Task {
                await viewModel.loadPendingReviews()
            }
        }
        .refreshable {
            await viewModel.loadPendingReviews()
        }
        .alert("Error", isPresented: $viewModel.showError) {
            Button("OK") {
                viewModel.dismissError()
            }
        } message: {
            Text(viewModel.error?.userMessage ?? "An error occurred")
        }
        .sheet(isPresented: $showingApprovalSheet) {
            approvalSheet
        }
    }

    // MARK: - States

    private var loadingState: some View {
        VStack(spacing: Spacing.md) {
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .accent))
                .scaleEffect(1.5)

            Text("Loading pending reviews...")
                .foregroundColor(.textSecondary)
        }
    }

    private var emptyState: some View {
        VStack(spacing: Spacing.lg) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 60))
                .foregroundColor(.healthyGreen)

            Text("All Caught Up")
                .font(.title2.weight(.semibold))
                .foregroundColor(.textPrimary)

            Text("No pending memory updates to review")
                .font(.subheadline)
                .foregroundColor(.textSecondary)
        }
    }

    // MARK: - Review List

    private var reviewList: some View {
        ScrollView {
            LazyVStack(spacing: Spacing.md) {
                // Header
                HStack {
                    Text("\(viewModel.pendingCount) Pending Review\(viewModel.pendingCount == 1 ? "" : "s")")
                        .font(.headline)
                        .foregroundColor(.textPrimary)

                    Spacer()
                }
                .padding(.horizontal, Spacing.lg)
                .padding(.top, Spacing.md)

                // Review cards
                ForEach(viewModel.pendingReviews) { chunk in
                    MemoryReviewCard(
                        chunk: chunk,
                        onApprove: {
                            viewModel.selectChunk(chunk)
                            showingApprovalSheet = true
                        },
                        onReject: {
                            Task {
                                await viewModel.rejectChunk(chunk)
                            }
                        }
                    )
                }
            }
            .padding(.bottom, Spacing.xl)
        }
        .scrollContentBackground(.hidden)
    }

    // MARK: - Approval Sheet

    private var approvalSheet: some View {
        NavigationView {
            ZStack {
                Color.bgBase.opacity(0.95)
                    .ignoresSafeArea()

                VStack(spacing: Spacing.lg) {
                    if let chunk = viewModel.selectedChunk {
                        // Chunk preview
                        VStack(alignment: .leading, spacing: Spacing.md) {
                            Text("Approving Memory")
                                .font(.headline)
                                .foregroundColor(.textPrimary)

                            Text(chunk.content)
                                .font(.body)
                                .foregroundColor(.textPrimary.opacity(0.8))
                                .padding()
                                .background(Color.bgOverlay)
                                .cornerRadius(CornerRadius.small)

                            // Confidence score
                            HStack {
                                Text("Confidence:")
                                    .foregroundColor(.textSecondary)
                                Text("\(Int(chunk.metadata.confidence * 100))%")
                                    .foregroundColor(confidenceColor(chunk.metadata.confidence))
                            }
                            .font(.caption)
                        }

                        // Notes field
                        VStack(alignment: .leading, spacing: Spacing.sm) {
                            Text("Reviewer Notes (Optional)")
                                .font(.caption)
                                .foregroundColor(.textSecondary)

                            TextEditor(text: $reviewerNotes)
                                .font(.body)
                                .foregroundColor(.textPrimary)
                                .frame(height: 100)
                                .padding(Spacing.sm)
                                .background(Color.bgOverlay)
                                .cornerRadius(CornerRadius.small)
                        }

                        Spacer()

                        // Approve button
                        Button {
                            Task {
                                await viewModel.approveChunk(
                                    chunk,
                                    notes: reviewerNotes.isEmpty ? nil : reviewerNotes
                                )
                                reviewerNotes = ""
                                showingApprovalSheet = false
                            }
                        } label: {
                            Text("Approve & Commit")
                                .font(.buttonText)
                                .foregroundColor(.textPrimary)
                                .frame(maxWidth: .infinity)
                                .padding(Spacing.md)
                                .background(Color.healthyGreen)
                                .cornerRadius(CornerRadius.button)
                        }
                    }
                }
                .padding(Spacing.lg)
            }
            .navigationTitle("Approve Memory")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        reviewerNotes = ""
                        showingApprovalSheet = false
                    }
                    .foregroundColor(.textPrimary)
                }
            }
        }
    }

    private func confidenceColor(_ confidence: Double) -> Color {
        if confidence >= 0.8 {
            return .healthyGreen
        } else if confidence >= 0.5 {
            return .warningYellow
        } else {
            return .errorRed
        }
    }
}

// MARK: - Memory Review Card

struct MemoryReviewCard: View {
    let chunk: MemoryChunk
    let onApprove: () -> Void
    let onReject: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            // Header with type badge
            HStack {
                // Type badge
                Text(chunk.chunkType.rawValue.capitalized)
                    .font(.caption.weight(.semibold))
                    .foregroundColor(.textPrimary)
                    .padding(.horizontal, Spacing.sm)
                    .padding(.vertical, Spacing.xs)
                    .background(typeColor.opacity(0.3))
                    .cornerRadius(CornerRadius.small)

                Spacer()

                // Confidence
                HStack(spacing: 4) {
                    Image(systemName: "brain")
                        .font(.caption)
                    Text("\(Int(chunk.metadata.confidence * 100))%")
                        .font(.caption.weight(.medium))
                }
                .foregroundColor(confidenceColor)
            }

            // Content
            Text(chunk.content)
                .font(.body)
                .foregroundColor(.textPrimary)
                .lineLimit(4)

            // Tags
            if !chunk.tags.topics.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: Spacing.xs) {
                        ForEach(chunk.tags.topics, id: \.self) { topic in
                            Text(topic)
                                .font(.caption2)
                                .foregroundColor(.textSecondary)
                                .padding(.horizontal, Spacing.sm)
                                .padding(.vertical, 2)
                                .background(Color.bgOverlay)
                                .cornerRadius(8)
                        }
                    }
                }
            }

            // Action buttons
            HStack(spacing: Spacing.md) {
                Button {
                    onReject()
                } label: {
                    HStack {
                        Image(systemName: "xmark")
                        Text("Reject")
                    }
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.errorRed)
                    .frame(maxWidth: .infinity)
                    .padding(Spacing.sm)
                    .background(Color.errorRed.opacity(0.2))
                    .cornerRadius(CornerRadius.small)
                }

                Button {
                    onApprove()
                } label: {
                    HStack {
                        Image(systemName: "checkmark")
                        Text("Approve")
                    }
                    .font(.subheadline.weight(.medium))
                    .foregroundColor(.healthyGreen)
                    .frame(maxWidth: .infinity)
                    .padding(Spacing.sm)
                    .background(Color.healthyGreen.opacity(0.2))
                    .cornerRadius(CornerRadius.small)
                }
            }
        }
        .padding(Spacing.md)
        .background(Color.cardBackground)
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    private var typeColor: Color {
        switch chunk.chunkType {
        case .preference: return .purple
        case .fact: return .blue
        case .decision: return .accent
        case .actionItem: return .red
        default: return .statusNeutral
        }
    }

    private var confidenceColor: Color {
        if chunk.metadata.confidence >= 0.8 {
            return .healthyGreen
        } else if chunk.metadata.confidence >= 0.5 {
            return .warningYellow
        } else {
            return .errorRed
        }
    }
}

// MARK: - Preview

struct MemoryReviewView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            MemoryReviewView()
                .environmentObject(AppState())
        }
    }
}
