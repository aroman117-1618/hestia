import SwiftUI
import HestiaShared

/// Widget showing pending memory reviews in Command Center
struct MemoryWidget: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = MemoryReviewViewModel()
    @State private var showingApprovalSheet = false
    @State private var reviewerNotes = ""

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            // Header
            HStack {
                Text("Memory Reviews")
                    .font(.headline)
                    .foregroundColor(.textPrimary)

                Spacer()

                if viewModel.isLoading {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .accent))
                        .scaleEffect(0.8)
                } else {
                    Button {
                        Task {
                            await viewModel.loadPendingReviews()
                        }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .font(.subheadline)
                            .foregroundColor(.textSecondary)
                    }
                }
            }
            .padding(.horizontal, Spacing.lg)

            if viewModel.isLoading && viewModel.pendingReviews.isEmpty {
                loadingState
            } else if viewModel.pendingReviews.isEmpty {
                emptyState
            } else {
                reviewCards
            }
        }
        .onAppear {
            Task {
                await viewModel.loadPendingReviews()
            }
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
        VStack(spacing: Spacing.sm) {
            ProgressView()
                .progressViewStyle(CircularProgressViewStyle(tint: .accent))

            Text("Loading reviews...")
                .font(.caption)
                .foregroundColor(.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(Spacing.xl)
        .background(Color.bgSurface)
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    private var emptyState: some View {
        VStack(spacing: Spacing.sm) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 32))
                .foregroundColor(.healthyGreen)

            Text("All Caught Up")
                .font(.subheadline.weight(.medium))
                .foregroundColor(.textPrimary)

            Text("No pending memory updates to review")
                .font(.caption)
                .foregroundColor(.textSecondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(Spacing.xl)
        .background(Color.bgSurface)
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Review Cards

    private var reviewCards: some View {
        VStack(spacing: Spacing.sm) {
            // Count badge
            HStack {
                Text("\(viewModel.pendingCount) pending")
                    .font(.caption)
                    .foregroundColor(.textSecondary)
                Spacer()
            }
            .padding(.horizontal, Spacing.lg)

            ForEach(viewModel.pendingReviews) { chunk in
                MemoryWidgetCard(
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

// MARK: - Memory Widget Card

struct MemoryWidgetCard: View {
    let chunk: MemoryChunk
    let onApprove: () -> Void
    let onReject: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            // Header with type badge
            HStack {
                // Type badge
                Text(chunk.chunkType.rawValue.capitalized)
                    .font(.caption2.weight(.semibold))
                    .foregroundColor(.textPrimary)
                    .padding(.horizontal, Spacing.xs)
                    .padding(.vertical, 2)
                    .background(typeColor.opacity(0.3))
                    .cornerRadius(4)

                Spacer()

                // Confidence
                HStack(spacing: 2) {
                    Image(systemName: "brain")
                        .font(.caption2)
                    Text("\(Int(chunk.metadata.confidence * 100))%")
                        .font(.caption2.weight(.medium))
                }
                .foregroundColor(confidenceColor)
            }

            // Content
            Text(chunk.content)
                .font(.subheadline)
                .foregroundColor(.textPrimary)
                .lineLimit(3)

            // Tags
            if !chunk.tags.topics.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 4) {
                        ForEach(chunk.tags.topics.prefix(3), id: \.self) { topic in
                            Text(topic)
                                .font(.caption2)
                                .foregroundColor(.textSecondary)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Color.bgOverlay)
                                .cornerRadius(4)
                        }
                    }
                }
            }

            // Action buttons
            HStack(spacing: Spacing.sm) {
                Button {
                    onReject()
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "xmark")
                        Text("Reject")
                    }
                    .font(.caption.weight(.medium))
                    .foregroundColor(.errorRed)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.xs)
                    .background(Color.errorRed.opacity(0.2))
                    .cornerRadius(CornerRadius.small)
                }

                Button {
                    onApprove()
                } label: {
                    HStack(spacing: 4) {
                        Image(systemName: "checkmark")
                        Text("Approve")
                    }
                    .font(.caption.weight(.medium))
                    .foregroundColor(.healthyGreen)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.xs)
                    .background(Color.healthyGreen.opacity(0.2))
                    .cornerRadius(CornerRadius.small)
                }
            }
        }
        .padding(Spacing.md)
        .background(Color.bgSurface)
        .cornerRadius(CornerRadius.card)
        .padding(.horizontal, Spacing.lg)
    }

    private var typeColor: Color {
        switch chunk.chunkType {
        case .preference: return .purple
        case .fact: return .blue
        case .decision: return .orange
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

struct MemoryWidget_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.bgBase.ignoresSafeArea()

            ScrollView {
                MemoryWidget()
                    .environmentObject(AppState())
            }
        }
    }
}
