import Foundation
import SwiftUI
import HestiaShared

@MainActor
class ResearchCanvasViewModel: ObservableObject {

    // MARK: - Board State

    @Published var boards: [ResearchBoard] = []
    @Published var currentBoard: ResearchBoard?
    @Published var selectedNodeIds: [String] = []
    @Published var selectedEntity: ResearchCanvasEntity?
    @Published var isLoading = false
    @Published var errorMessage: String?

    // MARK: - Sidebar Expansion

    @Published var memoriesExpanded = true
    @Published var entitiesExpanded = true
    @Published var principlesExpanded = true
    @Published var pinnedExpanded = true
    @Published var collectionsExpanded = true
    @Published var investigationsExpanded = false

    // MARK: - Sidebar Data

    @Published var memories: [MemoryChunkItem] = []
    @Published var entities: [ResearchCanvasEntity] = []
    @Published var principles: [ResearchPrinciple] = []

    // MARK: - Search / Filter

    @Published var sidebarSearchText = ""
    @Published var entityTypeFilter: String?
    @Published var memoryTypeFilter: String?
    @Published var principleStatusFilter: String?

    // MARK: - Detail Pane Data

    @Published var selectedEntityFacts: [ResearchTemporalFact] = []
    @Published var selectedEntityReferences: [ResearchEntityReference] = []

    // MARK: - Dependencies

    private let client: APIClient

    init(client: APIClient = .shared) {
        self.client = client
    }

    // MARK: - Filtered Data

    var filteredMemories: [MemoryChunkItem] {
        var result = memories
        if let filter = memoryTypeFilter {
            result = result.filter { $0.chunkType == filter }
        }
        if !sidebarSearchText.isEmpty {
            let query = sidebarSearchText.lowercased()
            result = result.filter { $0.content.lowercased().contains(query) }
        }
        return result
    }

    var filteredEntities: [ResearchCanvasEntity] {
        var result = entities
        if let filter = entityTypeFilter {
            result = result.filter { $0.entityType == filter }
        }
        if !sidebarSearchText.isEmpty {
            let query = sidebarSearchText.lowercased()
            result = result.filter { $0.name.lowercased().contains(query) }
        }
        return result
    }

    var filteredPrinciples: [ResearchPrinciple] {
        var result = principles
        if let filter = principleStatusFilter {
            result = result.filter { $0.status == filter }
        }
        if !sidebarSearchText.isEmpty {
            let query = sidebarSearchText.lowercased()
            result = result.filter { $0.content.lowercased().contains(query) }
        }
        return result
    }

    // MARK: - Data Loading

    func loadSidebarData() async {
        isLoading = true
        errorMessage = nil

        async let memoriesTask: () = loadMemories()
        async let entitiesTask: () = loadEntities()
        async let principlesTask: () = loadPrinciples()

        _ = await (memoriesTask, entitiesTask, principlesTask)
        isLoading = false
    }

    private func loadMemories() async {
        do {
            let response = try await client.listMemoryChunks(limit: 100, sortBy: "importance")
            memories = response.chunks
        } catch {
            #if DEBUG
            print("[ResearchCanvasVM] Failed to load memories: \(error)")
            #endif
        }
    }

    private func loadEntities() async {
        do {
            let response: ResearchCanvasEntityListResponse = try await client.get("/research/entities?limit=100")
            entities = response.entities
        } catch {
            #if DEBUG
            print("[ResearchCanvasVM] Failed to load entities: \(error)")
            #endif
        }
    }

    private func loadPrinciples() async {
        do {
            let response = try await client.getPrinciples(limit: 100)
            principles = response.principles
        } catch {
            #if DEBUG
            print("[ResearchCanvasVM] Failed to load principles: \(error)")
            #endif
        }
    }

    // MARK: - Board CRUD (stubs — Task 7 provides backend)

    func loadBoards() async {
        #if DEBUG
        print("[ResearchCanvasVM] loadBoards stub — backend not yet available")
        #endif
    }

    func createBoard(name: String) async {
        #if DEBUG
        print("[ResearchCanvasVM] createBoard stub — backend not yet available")
        #endif
    }

    func saveBoard() async {
        #if DEBUG
        print("[ResearchCanvasVM] saveBoard stub — backend not yet available")
        #endif
    }

    // MARK: - Principle Actions

    func approvePrinciple(id: String) async {
        do {
            let response = try await client.approvePrinciple(id)
            if let index = principles.firstIndex(where: { $0.id == id }) {
                // Replace with updated status — create new instance from response
                principles[index] = ResearchPrinciple(
                    id: response.id,
                    content: response.content,
                    domain: response.domain,
                    confidence: response.confidence,
                    status: response.status,
                    sourceChunkIds: principles[index].sourceChunkIds,
                    topics: principles[index].topics,
                    entities: principles[index].entities,
                    validationCount: principles[index].validationCount,
                    contradictionCount: principles[index].contradictionCount,
                    createdAt: principles[index].createdAt,
                    updatedAt: principles[index].updatedAt
                )
            }
        } catch {
            #if DEBUG
            print("[ResearchCanvasVM] Failed to approve principle: \(error)")
            #endif
            errorMessage = "Failed to approve principle"
        }
    }

    func rejectPrinciple(id: String) async {
        do {
            let response = try await client.rejectPrinciple(id)
            if let index = principles.firstIndex(where: { $0.id == id }) {
                principles[index] = ResearchPrinciple(
                    id: response.id,
                    content: response.content,
                    domain: response.domain,
                    confidence: response.confidence,
                    status: response.status,
                    sourceChunkIds: principles[index].sourceChunkIds,
                    topics: principles[index].topics,
                    entities: principles[index].entities,
                    validationCount: principles[index].validationCount,
                    contradictionCount: principles[index].contradictionCount,
                    createdAt: principles[index].createdAt,
                    updatedAt: principles[index].updatedAt
                )
            }
        } catch {
            #if DEBUG
            print("[ResearchCanvasVM] Failed to reject principle: \(error)")
            #endif
            errorMessage = "Failed to reject principle"
        }
    }

    // MARK: - Distill (stub — Task 7 provides backend)

    func distillPrinciple(nodeIds: [String]) async {
        #if DEBUG
        print("[ResearchCanvasVM] distillPrinciple stub — endpoint not yet available, nodeIds: \(nodeIds)")
        #endif
    }

    // MARK: - Detail Pane

    func selectEntity(_ entity: ResearchCanvasEntity) {
        selectedEntity = entity
        Task { [weak self] in
            await self?.loadEntityDetail(entity.id)
        }
    }

    func clearSelection() {
        selectedEntity = nil
        selectedEntityFacts = []
        selectedEntityReferences = []
    }

    private func loadEntityDetail(_ entityId: String) async {
        // Load facts for this entity
        do {
            let facts: ResearchTemporalFactListResponse = try await client.get("/research/entities/\(entityId)/facts?limit=50")
            selectedEntityFacts = facts.facts
        } catch {
            #if DEBUG
            print("[ResearchCanvasVM] Failed to load entity facts: \(error)")
            #endif
            selectedEntityFacts = []
        }

        // Load cross-references
        do {
            let refs: ResearchEntityReferenceListResponse = try await client.get("/research/entities/\(entityId)/references?limit=50")
            selectedEntityReferences = refs.references
        } catch {
            #if DEBUG
            print("[ResearchCanvasVM] Failed to load entity references: \(error)")
            #endif
            selectedEntityReferences = []
        }
    }
}
