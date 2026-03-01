import Foundation

// MARK: - Tool API Response Types

struct ToolParameterAPI: Codable {
    let type: String
    let description: String
    let required: Bool
    let enumValues: [String]?

    enum CodingKeys: String, CodingKey {
        case type, description, required
        case enumValues = "enum_values"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        type = try container.decode(String.self, forKey: .type)
        description = try container.decode(String.self, forKey: .description)
        required = try container.decode(Bool.self, forKey: .required)
        enumValues = try container.decodeIfPresent([String].self, forKey: .enumValues)
        // Skip "default" field — not needed for display
    }
}

struct ToolDefinitionAPI: Codable {
    let name: String
    let description: String
    let category: String
    let requiresApproval: Bool
    let parameters: [String: ToolParameterAPI]

    enum CodingKeys: String, CodingKey {
        case name, description, category, parameters
        case requiresApproval = "requires_approval"
    }
}

struct ToolsResponseAPI: Codable {
    let tools: [ToolDefinitionAPI]
    let count: Int
}
