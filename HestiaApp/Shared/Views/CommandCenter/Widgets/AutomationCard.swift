import SwiftUI

/// Card for an automation/standing order toggle
struct AutomationCard: View {
    let automation: Automation
    let onToggle: () -> Void

    @State private var isEnabled: Bool

    init(automation: Automation, onToggle: @escaping () -> Void) {
        self.automation = automation
        self.onToggle = onToggle
        _isEnabled = State(initialValue: automation.isEnabled)
    }

    var body: some View {
        HStack(spacing: Spacing.md) {
            // Icon
            ZStack {
                Circle()
                    .fill(isEnabled ? Color.white.opacity(0.2) : Color.white.opacity(0.1))
                    .frame(width: 44, height: 44)

                Image(systemName: automation.icon)
                    .font(.system(size: 20))
                    .foregroundColor(isEnabled ? .white : .white.opacity(0.5))
            }

            // Name and alert count
            VStack(alignment: .leading, spacing: 2) {
                Text(automation.name)
                    .cardTitleStyle()

                if automation.alertCount > 0 {
                    Text("\(automation.alertCount) Alert\(automation.alertCount == 1 ? "" : "s")")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.6))
                } else {
                    Text("No alerts")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.4))
                }
            }

            Spacer()

            // Toggle
            Toggle("", isOn: $isEnabled)
                .labelsHidden()
                .tint(Color.white.opacity(0.6))
                .onChange(of: isEnabled) { _ in
                    onToggle()
                }
        }
        .padding(Spacing.md)
        .background(Color.cardBackground)
        .cornerRadius(CornerRadius.card)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(automation.name), \(automation.alertCount) alerts")
        .accessibilityValue(isEnabled ? "Enabled" : "Disabled")
        .accessibilityAddTraits(.isButton)
    }
}

// MARK: - Preview

struct AutomationCard_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: Spacing.md) {
                AutomationCard(
                    automation: Automation(
                        id: "1",
                        name: "Home Security",
                        icon: "shield.fill",
                        alertCount: 0,
                        isEnabled: false
                    ),
                    onToggle: {}
                )

                AutomationCard(
                    automation: Automation(
                        id: "2",
                        name: "Market Monitor",
                        icon: "chart.line.uptrend.xyaxis",
                        alertCount: 3,
                        isEnabled: true
                    ),
                    onToggle: {}
                )
            }
            .padding()
        }
    }
}
