import Foundation

// MARK: - Content Cleaning Extensions

extension String {
    /// Strips leading bracket prefixes from imported content.
    /// Handles patterns like: `[IMPORTED CLAUDE HISTORY — Session]: [User]: actual content`
    /// Strips iteratively until no more leading bracket prefixes remain.
    func strippingBracketPrefixes() -> String {
        var result = self
        let pattern = #"^\[[^\]]+\]:\s*"#
        while let range = result.range(of: pattern, options: .regularExpression) {
            result.removeSubrange(range)
        }
        return result.isEmpty ? self : result
    }
}
