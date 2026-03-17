import SwiftUI

/// Collapsible reasoning steps section displayed above AI message content.
/// Shows a compact header (agent + model) that expands to reveal all pipeline decisions.
public struct ReasoningStepsSection: View {
    public let steps: [ReasoningStep]
    @State private var isExpanded: Bool = false

    public init(steps: [ReasoningStep]) {
        self.steps = steps
    }

    /// Build a compact header from the most important steps
    private var headerText: String {
        let agentStep = steps.first { $0.aspect == "agent" }
        let modelStep = steps.first { $0.aspect == "model" }

        if let agent = agentStep {
            return agent.summary
        } else if let model = modelStep {
            return model.summary
        } else if let first = steps.first {
            return "\(first.icon) \(first.summary)"
        }
        return "Reasoning"
    }

    public var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            // Compact header — always visible, tappable
            Button {
                withAnimation(.easeInOut(duration: 0.2)) {
                    isExpanded.toggle()
                }
            } label: {
                HStack(spacing: 4) {
                    Image(systemName: isExpanded ? "chevron.down" : "chevron.right")
                        .font(.system(size: 9, weight: .medium))
                    Text(headerText)
                        .font(.system(size: 11))
                        .lineLimit(1)
                }
                .foregroundStyle(.secondary)
                .padding(.horizontal, 6)
                .padding(.vertical, 2)
            }
            .buttonStyle(.plain)

            // Expanded: all reasoning steps
            if isExpanded {
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(0..<steps.count, id: \.self) { index in
                        HStack(spacing: 4) {
                            Text(steps[index].icon)
                                .font(.system(size: 10))
                            Text(steps[index].summary)
                                .font(.system(size: 11))
                                .lineLimit(2)
                        }
                        .foregroundStyle(.tertiary)
                    }
                }
                .padding(.leading, 16)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
    }
}
