import Foundation

/// Deep link destinations within the Hestia workspace.
///
/// Used by `WorkspaceRootView.navigate(to:)` to switch tabs and highlight
/// specific items across modules.
enum HestiaDeepLink: Hashable {
    case entity(id: String)
    case fact(id: String)
    case workflow(id: String, stepId: String? = nil)
    case chat(conversationId: String, messageId: String? = nil)
    case researchCanvas(boardId: String, entityId: String? = nil)
}
