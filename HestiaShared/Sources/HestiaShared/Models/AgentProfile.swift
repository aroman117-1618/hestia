import Foundation
import SwiftUI

/// Customizable agent profile with personality and visual settings
public struct AgentProfile: Identifiable, Codable, Equatable, Sendable {
    public let id: UUID
    public var name: String
    public var photoPath: String?
    public var instructions: String
    public var gradientColor1: String
    public var gradientColor2: String
    public let isDefault: Bool
    public let canBeDeleted: Bool
    public let createdAt: Date
    public var updatedAt: Date

    public init(id: UUID, name: String, photoPath: String?, instructions: String, gradientColor1: String, gradientColor2: String, isDefault: Bool, canBeDeleted: Bool, createdAt: Date, updatedAt: Date) {
        self.id = id
        self.name = name
        self.photoPath = photoPath
        self.instructions = instructions
        self.gradientColor1 = gradientColor1
        self.gradientColor2 = gradientColor2
        self.isDefault = isDefault
        self.canBeDeleted = canBeDeleted
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }

    // MARK: - Computed Properties

    /// First gradient color as SwiftUI Color
    public var primaryColor: Color {
        Color(hex: gradientColor1)
    }

    /// Second gradient color as SwiftUI Color
    public var secondaryColor: Color {
        Color(hex: gradientColor2)
    }

    /// Gradient colors array for compatibility with existing code
    public var gradientColors: [Color] {
        [primaryColor, secondaryColor]
    }

    /// Linear gradient for backgrounds
    public var gradient: LinearGradient {
        LinearGradient(
            colors: gradientColors,
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        )
    }

    /// First letter of name for avatar placeholder
    public var initial: String {
        String(name.prefix(1)).uppercased()
    }

    // MARK: - Validation

    public var isValid: Bool {
        !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty &&
        instructions.trimmingCharacters(in: .whitespacesAndNewlines).count >= 10
    }

    public var validationErrors: [String] {
        var errors: [String] = []

        if name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            errors.append("Name is required")
        }

        if instructions.trimmingCharacters(in: .whitespacesAndNewlines).count < 10 {
            errors.append("Instructions must be at least 10 characters")
        }

        return errors
    }
}

// MARK: - Default Agent Profiles

extension AgentProfile {
    /// Default Tia (Hestia) profile
    public static let tiaDefault = AgentProfile(
        id: UUID(uuidString: "00000000-0000-0000-0000-000000000001")!,
        name: "Tia",
        photoPath: nil,
        instructions: """
        You are Tia (short for Hestia), a personal AI assistant focused on daily operations and quick queries.

        Personality: Efficient and direct. Competent without being showy. Occasionally sardonic wit.

        Focus: Help with everyday tasks, answer quick questions, manage schedules, and keep things running smoothly.
        """,
        gradientColor1: "E0A050",
        gradientColor2: "8B3A0F",
        isDefault: true,
        canBeDeleted: false,
        createdAt: Date(),
        updatedAt: Date()
    )

    /// Default Mira (Artemis) profile
    public static let miraDefault = AgentProfile(
        id: UUID(uuidString: "00000000-0000-0000-0000-000000000002")!,
        name: "Mira",
        photoPath: nil,
        instructions: """
        You are Mira (short for Artemis), a learning-focused AI assistant using Socratic teaching methods.

        Personality: Curious and thoughtful. Asks clarifying questions. Encourages exploration and deeper understanding.

        Focus: Help with learning, research, and intellectual exploration. Guide discovery rather than just providing answers.
        """,
        gradientColor1: "090F26",
        gradientColor2: "00D7FF",
        isDefault: true,
        canBeDeleted: true,
        createdAt: Date(),
        updatedAt: Date()
    )

    /// Default Olly (Apollo) profile
    public static let ollyDefault = AgentProfile(
        id: UUID(uuidString: "00000000-0000-0000-0000-000000000003")!,
        name: "Olly",
        photoPath: nil,
        instructions: """
        You are Olly (short for Apollo), a project-focused AI assistant optimized for deep work.

        Personality: Focused and task-oriented. Minimal tangents. Project completion mindset.

        Focus: Help with complex projects, coding, analysis, and tasks requiring sustained concentration.
        """,
        gradientColor1: "03624C",
        gradientColor2: "2CC295",
        isDefault: true,
        canBeDeleted: true,
        createdAt: Date(),
        updatedAt: Date()
    )

    /// All default profiles
    public static let defaults: [AgentProfile] = [tiaDefault, miraDefault, ollyDefault]
}

// MARK: - Agent Profile Snapshot

/// Snapshot of an agent profile for recovery
public struct AgentProfileSnapshot: Codable, Sendable {
    public let agentProfile: AgentProfile
    public let snapshotDate: Date
    public let reason: SnapshotReason

    public init(agentProfile: AgentProfile, snapshotDate: Date, reason: SnapshotReason) {
        self.agentProfile = agentProfile
        self.snapshotDate = snapshotDate
        self.reason = reason
    }

    public var formattedDate: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: snapshotDate)
    }
}

/// Reason for creating a snapshot
public enum SnapshotReason: String, Codable, Sendable {
    case edited
    case deleted

    public var displayName: String {
        switch self {
        case .edited: return "Edited"
        case .deleted: return "Deleted"
        }
    }
}
