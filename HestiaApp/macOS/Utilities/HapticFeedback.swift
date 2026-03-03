import SwiftUI

/// Semantic haptic feedback patterns for Hestia interactions.
/// Uses SwiftUI's `.sensoryFeedback()` (available macOS 14+).
///
/// Usage:
///   .sensoryFeedback(.impact(weight: .light), trigger: workspace.currentView)
///   .sensoryFeedback(.selection, trigger: toggleCount)
///   .sensoryFeedback(.success, trigger: sendTrigger)
///
/// Guidelines:
/// - Navigation switches: `.impact(weight: .light)` — subtle orientation feedback
/// - Panel toggles: `.selection` — state change acknowledgment
/// - Message send: `.success` — positive completion
/// - Destructive actions: `.impact(weight: .heavy)` — caution signal
/// - Avoid haptics on hover or frequent events — haptic fatigue

// Note: macOS haptics require Force Touch trackpad (MacBook, Magic Trackpad 2+).
// On hardware without Force Touch, sensoryFeedback is silently ignored — no fallback needed.
