import Foundation
import HestiaShared

extension APIClient {
    func getTools() async throws -> ToolsResponseAPI {
        return try await get("/v1/tools")
    }
}
