import Foundation
import HestiaShared

/// Tool discovery API methods.
extension APIClient {
    func getTools() async throws -> ToolsResponseAPI {
        return try await get("/v1/tools")
    }
}
