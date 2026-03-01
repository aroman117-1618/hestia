import SwiftUI
import HestiaShared

// MARK: - API Models

struct UserProfileConfigResponse: Codable {
    let name: String
    let identity: UserIdentityInfo
    let hasSetup: Bool
    let configVersion: String
    let createdAt: String
    let updatedAt: String
    let files: [String: Bool]
}

struct UserIdentityInfo: Codable {
    let name: String
    let timezone: String
    let job: String
    let avatarPath: String?
    let contacts: [String]
}

struct FileContentResponse: Codable {
    let fileName: String
    let content: String
    let exists: Bool
}

struct CommandInfo: Codable, Identifiable {
    let name: String
    let description: String
    let resources: [String]
    let hasSystemInstructions: Bool

    var id: String { name }
}

struct CommandListResponse: Codable {
    let commands: [CommandInfo]
    let count: Int
}

struct DailyNoteInfo: Codable, Identifiable {
    let date: String
    let content: String

    var id: String { date }
}

struct DailyNoteListResponse: Codable {
    let notes: [DailyNoteInfo]
    let count: Int
}

// MARK: - ViewModel

@MainActor
class MacUserProfileViewModel: ObservableObject {
    @Published var profile: UserProfileConfigResponse?
    @Published var commands: [CommandInfo] = []
    @Published var dailyNotes: [DailyNoteInfo] = []
    @Published var selectedFile: String?
    @Published var fileContent: String = ""
    @Published var isLoading = false
    @Published var isEditing = false
    @Published var editedContent: String = ""
    @Published var showError = false
    @Published var errorMessage = ""

    // Known file types for display
    static let fileDisplayNames: [(key: String, label: String, icon: String)] = [
        ("USER-IDENTITY.md", "Identity", "person.crop.circle"),
        ("MIND.md", "Mind", "brain.head.profile"),
        ("TOOLS.md", "Tools", "wrench.and.screwdriver"),
        ("MEMORY.md", "Memory", "memorychip"),
        ("BODY.md", "Body", "figure.run"),
        ("SPIRIT.md", "Spirit", "sparkles"),
        ("VITALS.md", "Vitals", "heart.text.square"),
        ("SETUP.md", "Setup", "checklist"),
    ]

    func loadAll() async {
        isLoading = true
        defer { isLoading = false }

        async let profileTask: () = loadProfile()
        async let commandsTask: () = loadCommands()
        async let notesTask: () = loadDailyNotes()
        _ = await (profileTask, commandsTask, notesTask)
    }

    func loadProfile() async {
        do {
            let response: UserProfileConfigResponse = try await APIClient.shared.get(
                "/v1/user-profile"
            )
            profile = response
        } catch {
            #if DEBUG
            print("[MacUserProfileVM] Failed to load profile: \(error)")
            #endif
        }
    }

    func loadCommands() async {
        do {
            let response: CommandListResponse = try await APIClient.shared.get(
                "/v1/user-profile/commands"
            )
            commands = response.commands
        } catch {
            #if DEBUG
            print("[MacUserProfileVM] Failed to load commands: \(error)")
            #endif
        }
    }

    func loadDailyNotes() async {
        do {
            let response: DailyNoteListResponse = try await APIClient.shared.get(
                "/v1/user-profile/notes?limit=7"
            )
            dailyNotes = response.notes
        } catch {
            #if DEBUG
            print("[MacUserProfileVM] Failed to load notes: \(error)")
            #endif
        }
    }

    func loadFile(_ fileName: String) async {
        selectedFile = fileName
        isEditing = false
        do {
            let response: FileContentResponse = try await APIClient.shared.get(
                "/v1/user-profile/files/\(fileName)"
            )
            fileContent = response.content
            editedContent = response.content
        } catch {
            fileContent = "(Failed to load)"
            #if DEBUG
            print("[MacUserProfileVM] Failed to load file \(fileName): \(error)")
            #endif
        }
    }

    func saveFile() async {
        guard let fileName = selectedFile else { return }
        do {
            struct UpdateBody: Codable {
                let content: String
                let source: String
            }
            let _: EmptyResponse = try await APIClient.shared.put(
                "/v1/user-profile/files/\(fileName)",
                body: UpdateBody(content: editedContent, source: "user")
            )
            fileContent = editedContent
            isEditing = false
        } catch {
            showError = true
            errorMessage = "Failed to save file"
            #if DEBUG
            print("[MacUserProfileVM] Failed to save \(fileName): \(error)")
            #endif
        }
    }
}
