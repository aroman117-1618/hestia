import SwiftUI
import HestiaShared

// MARK: - Profile Config Models (user-profile endpoint, separate from user endpoint)

struct ProfileFileManifest: Codable {
    let name: String
    let files: [String: Bool]
}

struct ProfileFileContent: Codable {
    let fileName: String
    let content: String
    let exists: Bool
}

struct ProfileFileUpdate: Codable {
    let content: String
    let source: String
}

// MARK: - ViewModel

@MainActor
class MacSettingsProfileViewModel: ObservableObject {
    @Published var name: String = ""
    @Published var userDescription: String = ""
    @Published var photoData: Data?
    @Published var hasPhoto: Bool = false
    @Published var isLoading: Bool = false
    @Published var isSaving: Bool = false
    @Published var errorMessage: String?
    @Published var fileManifest: [String: Bool] = [:]

    private var saveTask: Task<Void, Never>?

    static let profileFiles: [(key: String, label: String, icon: String)] = [
        ("USER-IDENTITY.md", "Identity", "person.crop.circle"),
        ("MIND.md", "Mind", "brain.head.profile"),
        ("TOOLS.md", "Tools", "wrench.and.screwdriver"),
        ("MEMORY.md", "Memory", "memorychip"),
        ("BODY.md", "Body", "figure.run"),
        ("SPIRIT.md", "Spirit", "sparkles"),
        ("VITALS.md", "Vitals", "heart.text.square"),
        ("SETUP.md", "Setup", "checklist"),
    ]

    // MARK: - Load

    func loadProfile() async {
        isLoading = true
        defer { isLoading = false }

        // Try cache first
        if let cached = CacheManager.shared.get(UserProfileResponse.self, forKey: CacheKey.userProfile) {
            applyProfile(cached)
        }

        // Fetch fresh
        do {
            let response = try await APIClient.shared.getUserProfile()
            applyProfile(response)
            CacheManager.shared.cache(response, forKey: CacheKey.userProfile)
        } catch {
            #if DEBUG
            print("[SettingsProfile] Failed to load profile: \(error)")
            #endif
            if name.isEmpty { errorMessage = "Failed to load profile" }
        }

        // Load file manifest
        do {
            let manifest: ProfileFileManifest = try await APIClient.shared.get("/v1/user-profile")
            fileManifest = manifest.files
        } catch {
            #if DEBUG
            print("[SettingsProfile] Failed to load file manifest: \(error)")
            #endif
        }

        // Load photo
        await loadPhoto()
    }

    private func applyProfile(_ response: UserProfileResponse) {
        name = response.name
        userDescription = response.description ?? ""
        hasPhoto = response.photoUrl != nil
    }

    // MARK: - Save (debounced 1s)

    func scheduleProfileSave() {
        saveTask?.cancel()
        saveTask = Task {
            try? await Task.sleep(for: .seconds(1))
            guard !Task.isCancelled else { return }
            await saveProfile()
        }
    }

    func saveProfile() async {
        isSaving = true
        defer { isSaving = false }

        do {
            let request = UserProfileUpdateRequest(
                name: name.isEmpty ? nil : name,
                description: userDescription.isEmpty ? nil : userDescription
            )
            _ = try await APIClient.shared.updateUserProfile(request)
            CacheManager.shared.invalidate(forKey: CacheKey.userProfile)
        } catch {
            #if DEBUG
            print("[SettingsProfile] Failed to save profile: \(error)")
            #endif
            errorMessage = "Failed to save profile"
        }
    }

    // MARK: - Photo

    func loadPhoto() async {
        do {
            let data = try await APIClient.shared.getUserPhoto()
            photoData = data
            hasPhoto = true
        } catch {
            photoData = nil
            hasPhoto = false
        }
    }

    func uploadPhoto(_ imageData: Data) async {
        do {
            _ = try await APIClient.shared.uploadUserPhoto(imageData: imageData)
            photoData = imageData
            hasPhoto = true
            CacheManager.shared.invalidate(forKey: CacheKey.userProfile)
        } catch {
            #if DEBUG
            print("[SettingsProfile] Failed to upload photo: \(error)")
            #endif
            errorMessage = "Failed to upload photo"
        }
    }

    func deletePhoto() async {
        do {
            _ = try await APIClient.shared.deleteUserPhoto()
            photoData = nil
            hasPhoto = false
            CacheManager.shared.invalidate(forKey: CacheKey.userProfile)
        } catch {
            #if DEBUG
            print("[SettingsProfile] Failed to delete photo: \(error)")
            #endif
            errorMessage = "Failed to delete photo"
        }
    }

    // MARK: - File Operations

    func loadFile(_ fileName: String) async -> String? {
        do {
            let response: ProfileFileContent = try await APIClient.shared.get(
                "/v1/user-profile/files/\(fileName)"
            )
            return response.content
        } catch {
            #if DEBUG
            print("[SettingsProfile] Failed to load \(fileName): \(error)")
            #endif
            return nil
        }
    }

    func saveFile(_ fileName: String, content: String) async -> Bool {
        do {
            let body = ProfileFileUpdate(content: content, source: "user")
            let _: EmptyResponse = try await APIClient.shared.put(
                "/v1/user-profile/files/\(fileName)",
                body: body
            )
            return true
        } catch {
            #if DEBUG
            print("[SettingsProfile] Failed to save \(fileName): \(error)")
            #endif
            errorMessage = "Failed to save file"
            return false
        }
    }
}
