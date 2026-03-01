import SwiftUI
import HestiaShared
import Combine

/// ViewModel for the Memory Review screen (ADR-002)
@MainActor
class MemoryReviewViewModel: ObservableObject {
    // MARK: - Published State

    @Published var pendingReviews: [MemoryChunk] = []
    @Published var isLoading: Bool = false
    @Published var error: HestiaError?
    @Published var showError: Bool = false
    @Published var selectedChunk: MemoryChunk?

    // MARK: - Dependencies

    private let client: HestiaClientProtocol

    // MARK: - Computed Properties

    var pendingCount: Int {
        pendingReviews.count
    }

    var hasPendingReviews: Bool {
        !pendingReviews.isEmpty
    }

    // MARK: - Initialization

    init(client: HestiaClientProtocol = APIClient.shared) {
        self.client = client
    }

    // MARK: - Public Methods

    /// Load pending memory reviews
    func loadPendingReviews() async {
        isLoading = true
        error = nil

        do {
            let reviews = try await client.getPendingMemoryReviews()
            pendingReviews = reviews
        } catch let hestiaError as HestiaError {
            self.error = hestiaError
            self.showError = true
        } catch {
            self.error = .unknown(error.localizedDescription)
            self.showError = true
        }

        isLoading = false
    }

    /// Approve a memory chunk
    func approveChunk(_ chunk: MemoryChunk, notes: String? = nil) async {
        isLoading = true

        do {
            try await client.approveMemory(chunkId: chunk.id, notes: notes)
            // Remove from list
            pendingReviews.removeAll { $0.id == chunk.id }
        } catch let hestiaError as HestiaError {
            self.error = hestiaError
            self.showError = true
        } catch {
            self.error = .unknown(error.localizedDescription)
            self.showError = true
        }

        isLoading = false
    }

    /// Reject a memory chunk
    func rejectChunk(_ chunk: MemoryChunk) async {
        isLoading = true

        do {
            try await client.rejectMemory(chunkId: chunk.id)
            // Remove from list
            pendingReviews.removeAll { $0.id == chunk.id }
        } catch let hestiaError as HestiaError {
            self.error = hestiaError
            self.showError = true
        } catch {
            self.error = .unknown(error.localizedDescription)
            self.showError = true
        }

        isLoading = false
    }

    /// Dismiss error
    func dismissError() {
        showError = false
        error = nil
    }

    /// Select a chunk for detail view
    func selectChunk(_ chunk: MemoryChunk) {
        selectedChunk = chunk
    }

    /// Clear selection
    func clearSelection() {
        selectedChunk = nil
    }
}
