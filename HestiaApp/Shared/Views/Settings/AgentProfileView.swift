import SwiftUI
import HestiaShared
import PhotosUI
import CoreData

/// View for editing a single agent profile
struct AgentProfileView: View {
    @Environment(\.managedObjectContext) private var viewContext
    @Environment(\.dismiss) private var dismiss
    @EnvironmentObject var appState: AppState

    let slotIndex: Int
    let isEditing: Bool

    @StateObject private var viewModel: AgentProfileEditViewModel

    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var showingDeleteConfirmation = false
    @State private var deleteConfirmationText = ""
    @State private var hasUnsavedChanges = false
    @State private var showingRecoverySheet = false

    init(slotIndex: Int, profile: AgentProfile? = nil) {
        self.slotIndex = slotIndex
        self.isEditing = profile != nil
        _viewModel = StateObject(wrappedValue: AgentProfileEditViewModel(
            profile: profile ?? AgentProfile.defaults[safe: slotIndex] ?? AgentProfile.tiaDefault
        ))
    }

    var body: some View {
        ZStack {
            // Use the profile's gradient for background
            LinearGradient(
                colors: [viewModel.primaryColor, viewModel.secondaryColor],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            ScrollView {
                VStack(spacing: Spacing.xl) {
                    // Avatar Section
                    avatarSection
                        .padding(.top, Spacing.lg)

                    // Name Section
                    nameSection

                    // Instructions/Anima Section
                    instructionsSection

                    // Visual Vibes Section
                    visualVibesSection

                    // Validation Errors
                    if !viewModel.validationErrors.isEmpty {
                        validationErrorsSection
                    }

                    // Action Buttons
                    actionButtons

                    // Delete Section (for non-primary agents)
                    if viewModel.profile.canBeDeleted && isEditing {
                        deleteSection
                    }

                    // Recovery Section (if snapshots exist)
                    if isEditing {
                        recoverySection
                    }

                    Spacer()
                        .frame(height: Spacing.xxl)
                }
                .padding(.horizontal, Spacing.lg)
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle(isEditing ? "Edit \(viewModel.profile.name)" : "New Agent")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                if hasUnsavedChanges {
                    Button("Save") {
                        saveProfile()
                    }
                    .foregroundColor(.white)
                }
            }
        }
        .alert("Delete Agent?", isPresented: $showingDeleteConfirmation) {
            TextField("Type \"\(viewModel.profile.name)\" to confirm", text: $deleteConfirmationText)
            Button("Delete", role: .destructive) {
                if deleteConfirmationText.lowercased() == viewModel.profile.name.lowercased() {
                    deleteProfile()
                }
            }
            Button("Cancel", role: .cancel) {
                deleteConfirmationText = ""
            }
        } message: {
            Text("This will delete \(viewModel.profile.name). Type the agent name to confirm.")
        }
        .sheet(isPresented: $showingRecoverySheet) {
            AgentRecoverySheet(agentId: viewModel.profile.id) { recoveredProfile in
                viewModel.restoreFrom(recoveredProfile)
                hasUnsavedChanges = true
                showingRecoverySheet = false
            }
        }
    }

    // MARK: - Avatar Section

    private var avatarSection: some View {
        VStack(spacing: Spacing.md) {
            PhotosPicker(selection: $selectedPhotoItem, matching: .images) {
                ZStack {
                    if let photoData = viewModel.photoData,
                       let uiImage = UIImage(data: photoData) {
                        Image(uiImage: uiImage)
                            .resizable()
                            .scaledToFill()
                    } else {
                        Circle()
                            .fill(Color.white.opacity(0.2))
                            .overlay(
                                Text(viewModel.profile.initial)
                                    .font(.system(size: 48, weight: .bold))
                                    .foregroundColor(.white)
                            )
                    }
                }
                .frame(width: Size.Avatar.xlarge, height: Size.Avatar.xlarge)
                .clipShape(Circle())
                .overlay(
                    Circle()
                        .stroke(Color.white.opacity(0.3), lineWidth: 3)
                )
                .overlay(
                    Image(systemName: "camera.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.white)
                        .padding(Spacing.sm)
                        .background(Color.black.opacity(0.6))
                        .clipShape(Circle())
                        .offset(x: 40, y: 40)
                )
            }
            .onChange(of: selectedPhotoItem) { newItem in
                Task {
                    if let data = try? await newItem?.loadTransferable(type: Data.self) {
                        await MainActor.run {
                            viewModel.updatePhoto(data)
                            hasUnsavedChanges = true
                        }
                    }
                }
            }

            Text("Agent Avatar")
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
        }
    }

    // MARK: - Name Section

    private var nameSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Text("Name")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
                .textCase(.uppercase)

            TextField("Agent name", text: $viewModel.profile.name)
                .customTextField()
                .onChange(of: viewModel.profile.name) { _ in
                    hasUnsavedChanges = true
                }
        }
    }

    // MARK: - Instructions Section

    private var instructionsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                Text("Instructions / Anima")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))
                    .textCase(.uppercase)

                Spacer()

                Text("\(viewModel.profile.instructions.count) chars")
                    .font(.caption2)
                    .foregroundColor(.white.opacity(0.4))
            }

            TextEditor(text: $viewModel.profile.instructions)
                .font(.body)
                .foregroundColor(.white)
                .scrollContentBackground(.hidden)
                .frame(minHeight: 150)
                .padding(Spacing.md)
                .background(Color.white.opacity(0.15))
                .cornerRadius(CornerRadius.input)
                .onChange(of: viewModel.profile.instructions) { _ in
                    hasUnsavedChanges = true
                }

            Text("This prompt context is sent with every interaction. Define the agent's focus, tone, and goals.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
        }
    }

    // MARK: - Visual Vibes Section

    private var visualVibesSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Visual Vibes")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
                .textCase(.uppercase)

            VStack(spacing: Spacing.sm) {
                // Primary Color
                HStack {
                    Text("Primary Color")
                        .foregroundColor(.white.opacity(0.7))

                    Spacer()

                    ColorPicker("", selection: $viewModel.primaryColor)
                        .labelsHidden()
                        .onChange(of: viewModel.primaryColor) { newColor in
                            viewModel.updateGradientColor1(from: newColor)
                            hasUnsavedChanges = true
                        }

                    RoundedRectangle(cornerRadius: 4)
                        .fill(viewModel.primaryColor)
                        .frame(width: 30, height: 30)
                }
                .padding(Spacing.sm)
                .background(Color.white.opacity(0.1))
                .cornerRadius(CornerRadius.small)

                // Secondary Color
                HStack {
                    Text("Secondary Color")
                        .foregroundColor(.white.opacity(0.7))

                    Spacer()

                    ColorPicker("", selection: $viewModel.secondaryColor)
                        .labelsHidden()
                        .onChange(of: viewModel.secondaryColor) { newColor in
                            viewModel.updateGradientColor2(from: newColor)
                            hasUnsavedChanges = true
                        }

                    RoundedRectangle(cornerRadius: 4)
                        .fill(viewModel.secondaryColor)
                        .frame(width: 30, height: 30)
                }
                .padding(Spacing.sm)
                .background(Color.white.opacity(0.1))
                .cornerRadius(CornerRadius.small)
            }

            // Preview gradient
            RoundedRectangle(cornerRadius: CornerRadius.small)
                .fill(
                    LinearGradient(
                        colors: [viewModel.primaryColor, viewModel.secondaryColor],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(height: 60)
                .overlay(
                    Text("Gradient Preview")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.7))
                )

            Text("These colors form the gradient theme when this agent is active")
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
        }
    }

    // MARK: - Validation Errors

    private var validationErrorsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.xs) {
            ForEach(viewModel.validationErrors, id: \.self) { error in
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.errorRed)
                    Text(error)
                        .font(.caption)
                        .foregroundColor(.errorRed)
                }
            }
        }
        .padding(Spacing.md)
        .background(Color.errorRed.opacity(0.1))
        .cornerRadius(CornerRadius.small)
    }

    // MARK: - Action Buttons

    private var actionButtons: some View {
        VStack(spacing: Spacing.md) {
            if hasUnsavedChanges {
                Button {
                    saveProfile()
                } label: {
                    Text("Save Changes")
                        .font(.buttonText)
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(Spacing.md)
                        .background(Color.white.opacity(0.2))
                        .cornerRadius(CornerRadius.button)
                }
                .disabled(!viewModel.profile.isValid)
            }
        }
    }

    // MARK: - Delete Section

    private var deleteSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Danger Zone")
                .font(.caption)
                .foregroundColor(.errorRed.opacity(0.7))
                .textCase(.uppercase)

            Button {
                showingDeleteConfirmation = true
            } label: {
                HStack {
                    Image(systemName: "trash")
                    Text("Delete Agent")
                }
                .foregroundColor(.errorRed)
                .frame(maxWidth: .infinity)
                .padding(Spacing.md)
                .background(Color.errorRed.opacity(0.1))
                .cornerRadius(CornerRadius.small)
            }

            Text("Deleted agents can be recovered for 90 days")
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
        }
        .padding(.top, Spacing.xl)
    }

    // MARK: - Recovery Section

    private var recoverySection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Button {
                showingRecoverySheet = true
            } label: {
                HStack {
                    Image(systemName: "clock.arrow.circlepath")
                    Text("View Previous Versions")
                    Spacer()
                    Image(systemName: "chevron.right")
                }
                .foregroundColor(.white.opacity(0.7))
                .padding(Spacing.md)
                .background(Color.white.opacity(0.05))
                .cornerRadius(CornerRadius.small)
            }
        }
    }

    // MARK: - Actions

    private func saveProfile() {
        guard viewModel.profile.isValid else { return }

        // Create snapshot before saving
        if isEditing {
            viewModel.createSnapshot(reason: .edited, context: viewContext)
        }

        viewModel.save(slotIndex: Int16(slotIndex), context: viewContext)
        hasUnsavedChanges = false
        dismiss()
    }

    private func deleteProfile() {
        // Create snapshot before deleting
        viewModel.createSnapshot(reason: .deleted, context: viewContext)

        viewModel.delete(context: viewContext)
        dismiss()
    }
}

// MARK: - Agent Profile Edit ViewModel

@MainActor
class AgentProfileEditViewModel: ObservableObject {
    @Published var profile: AgentProfile
    @Published var photoData: Data?
    @Published var primaryColor: Color
    @Published var secondaryColor: Color
    @Published var isLoading = false
    @Published var isOffline = false
    @Published var errorMessage: String?

    private let apiClient = APIClient.shared

    var validationErrors: [String] {
        profile.validationErrors
    }

    init(profile: AgentProfile) {
        self.profile = profile
        self.primaryColor = Color(hex: profile.gradientColor1)
        self.secondaryColor = Color(hex: profile.gradientColor2)

        // Load photo if exists
        if let photoPath = profile.photoPath {
            let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                .appendingPathComponent(photoPath)
            photoData = try? Data(contentsOf: url)
        }
    }

    func updatePhoto(_ data: Data) {
        guard let image = UIImage(data: data),
              let resizedImage = resizeImage(image, targetSize: CGSize(width: 256, height: 256)),
              let compressedData = resizedImage.jpegData(compressionQuality: 0.8) else {
            return
        }

        let fileName = "agent_\(profile.id.uuidString)_photo.jpg"
        let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent(fileName)

        do {
            try compressedData.write(to: url)
            photoData = compressedData
            profile = AgentProfile(
                id: profile.id,
                name: profile.name,
                photoPath: fileName,
                instructions: profile.instructions,
                gradientColor1: profile.gradientColor1,
                gradientColor2: profile.gradientColor2,
                isDefault: profile.isDefault,
                canBeDeleted: profile.canBeDeleted,
                createdAt: profile.createdAt,
                updatedAt: Date()
            )
        } catch {
            #if DEBUG
            print("[AgentProfileEditViewModel] Failed to save photo locally: \(error)")
            #endif
        }
    }

    func updateGradientColor1(from color: Color) {
        let hex = color.toHex() ?? profile.gradientColor1
        profile = AgentProfile(
            id: profile.id,
            name: profile.name,
            photoPath: profile.photoPath,
            instructions: profile.instructions,
            gradientColor1: hex,
            gradientColor2: profile.gradientColor2,
            isDefault: profile.isDefault,
            canBeDeleted: profile.canBeDeleted,
            createdAt: profile.createdAt,
            updatedAt: Date()
        )
    }

    func updateGradientColor2(from color: Color) {
        let hex = color.toHex() ?? profile.gradientColor2
        profile = AgentProfile(
            id: profile.id,
            name: profile.name,
            photoPath: profile.photoPath,
            instructions: profile.instructions,
            gradientColor1: profile.gradientColor1,
            gradientColor2: hex,
            isDefault: profile.isDefault,
            canBeDeleted: profile.canBeDeleted,
            createdAt: profile.createdAt,
            updatedAt: Date()
        )
    }

    func restoreFrom(_ restoredProfile: AgentProfile) {
        profile = restoredProfile
        primaryColor = Color(hex: restoredProfile.gradientColor1)
        secondaryColor = Color(hex: restoredProfile.gradientColor2)

        if let photoPath = restoredProfile.photoPath {
            let url = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                .appendingPathComponent(photoPath)
            photoData = try? Data(contentsOf: url)
        }
    }

    func createSnapshot(reason: SnapshotReason, context: NSManagedObjectContext) {
        _ = AgentProfileSnapshotEntity.create(from: profile, reason: reason, in: context)
        try? context.save()
    }

    func save(slotIndex: Int16, context: NSManagedObjectContext) {
        isLoading = true

        // Save to backend first
        Task {
            defer { isLoading = false }

            do {
                // Build API request
                let request = AgentUpdateRequest(
                    name: profile.name,
                    instructions: profile.instructions,
                    gradientColor1: profile.gradientColor1,
                    gradientColor2: profile.gradientColor2
                )

                // Update on backend
                _ = try await apiClient.updateAgent(Int(slotIndex), request: request)
                isOffline = false

                // Upload photo if present
                if let photoData = photoData {
                    do {
                        _ = try await apiClient.uploadAgentPhoto(Int(slotIndex), imageData: photoData)
                    } catch {
                        #if DEBUG
                        print("[AgentProfileEditViewModel] Failed to upload photo: \(error)")
                        #endif
                    }
                }

            } catch {
                #if DEBUG
                print("[AgentProfileEditViewModel] Backend save failed: \(error)")
                #endif
                isOffline = true
                errorMessage = "Saved locally. Will sync when online."
            }

            // Always save to local Core Data as cache
            let fetchRequest = AgentProfileEntity.profileBySlotRequest(slot: slotIndex)
            if let existing = try? context.fetch(fetchRequest).first {
                existing.update(from: profile)
            } else {
                _ = AgentProfileEntity.create(from: profile, slotIndex: slotIndex, in: context)
            }

            try? context.save()
        }
    }

    func delete(context: NSManagedObjectContext) {
        // Note: Delete resets to default on backend, doesn't truly delete
        let fetchRequest = AgentProfileEntity.fetchRequest()
        fetchRequest.predicate = NSPredicate(format: "id == %@", profile.id as CVarArg)

        if let entity = try? context.fetch(fetchRequest).first {
            let slotIndex = entity.slotIndex

            // Try to delete on backend (resets to default)
            Task {
                do {
                    _ = try await apiClient.deleteAgent(Int(slotIndex))
                    isOffline = false
                } catch {
                    #if DEBUG
                    print("[AgentProfileEditViewModel] Backend delete failed: \(error)")
                    #endif
                    isOffline = true
                }
            }

            // Delete from local Core Data
            context.delete(entity)
            try? context.save()
        }
    }

    /// Restore from a backend snapshot
    func restoreFromSnapshot(slotIndex: Int, snapshotId: String) {
        Task {
            isLoading = true
            defer { isLoading = false }

            do {
                // Restore on backend (returns minimal response)
                _ = try await apiClient.restoreAgentSnapshot(slotIndex, snapshotId: snapshotId)
                isOffline = false

                // Fetch the updated full profile
                let response = try await apiClient.getAgent(slotIndex)

                // Update local profile from full response
                profile = AgentProfile(
                    id: UUID(uuidString: response.agentId) ?? profile.id,
                    name: response.name,
                    photoPath: profile.photoPath,
                    instructions: response.instructions,
                    gradientColor1: response.gradientColor1,
                    gradientColor2: response.gradientColor2,
                    isDefault: response.isDefault,
                    canBeDeleted: response.canBeDeleted,
                    createdAt: response.createdAt,
                    updatedAt: response.updatedAt
                )

                primaryColor = Color(hex: response.gradientColor1)
                secondaryColor = Color(hex: response.gradientColor2)

            } catch {
                #if DEBUG
                print("[AgentProfileEditViewModel] Backend restore failed: \(error)")
                #endif
                isOffline = true
                errorMessage = "Failed to restore snapshot"
            }
        }
    }

    /// List snapshots from backend
    func listSnapshots(slotIndex: Int) async -> [AgentSnapshotDetail] {
        do {
            let response = try await apiClient.listAgentSnapshots(slotIndex)
            isOffline = false
            return response.snapshots
        } catch {
            #if DEBUG
            print("[AgentProfileEditViewModel] Failed to list snapshots: \(error)")
            #endif
            isOffline = true
            return []
        }
    }

    private func resizeImage(_ image: UIImage, targetSize: CGSize) -> UIImage? {
        let size = image.size
        let widthRatio = targetSize.width / size.width
        let heightRatio = targetSize.height / size.height
        let ratio = min(widthRatio, heightRatio)

        let newSize = CGSize(width: size.width * ratio, height: size.height * ratio)

        UIGraphicsBeginImageContextWithOptions(newSize, false, 1.0)
        image.draw(in: CGRect(origin: .zero, size: newSize))
        let newImage = UIGraphicsGetImageFromCurrentImageContext()
        UIGraphicsEndImageContext()

        return newImage
    }
}

// MARK: - Agent Recovery Sheet

struct AgentRecoverySheet: View {
    @Environment(\.managedObjectContext) private var viewContext
    @Environment(\.dismiss) private var dismiss

    let agentId: UUID
    let onRestore: (AgentProfile) -> Void

    @FetchRequest private var snapshots: FetchedResults<AgentProfileSnapshotEntity>

    init(agentId: UUID, onRestore: @escaping (AgentProfile) -> Void) {
        self.agentId = agentId
        self.onRestore = onRestore

        _snapshots = FetchRequest(
            sortDescriptors: [NSSortDescriptor(keyPath: \AgentProfileSnapshotEntity.snapshotDate, ascending: false)],
            predicate: NSPredicate(format: "originalAgentId == %@", agentId as CVarArg)
        )
    }

    var body: some View {
        NavigationView {
            List {
                if snapshots.isEmpty {
                    Text("No previous versions available")
                        .foregroundColor(.secondary)
                } else {
                    ForEach(snapshots, id: \.id) { snapshot in
                        if let profileSnapshot = snapshot.toAgentProfileSnapshot() {
                            Button {
                                onRestore(profileSnapshot.agentProfile)
                            } label: {
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(profileSnapshot.formattedDate)
                                        .font(.headline)
                                    HStack {
                                        Text(profileSnapshot.reason.displayName)
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                        Text("\u{2022}")
                                            .foregroundColor(.secondary)
                                        Text(profileSnapshot.agentProfile.name)
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            .navigationTitle("Previous Versions")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }
}

// MARK: - Color Extension for Hex Conversion

extension Color {
    func toHex() -> String? {
        guard let components = UIColor(self).cgColor.components else { return nil }

        let r = components[0]
        let g = components.count > 1 ? components[1] : r
        let b = components.count > 2 ? components[2] : r

        return String(format: "%02X%02X%02X", Int(r * 255), Int(g * 255), Int(b * 255))
    }
}

// MARK: - Safe Array Access

extension Array {
    subscript(safe index: Int) -> Element? {
        return indices.contains(index) ? self[index] : nil
    }
}

// MARK: - Preview

struct AgentProfileView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            AgentProfileView(slotIndex: 0, profile: AgentProfile.tiaDefault)
                .environmentObject(AppState())
                .environment(\.managedObjectContext, PersistenceController.preview.viewContext)
        }
    }
}
