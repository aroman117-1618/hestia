import SwiftUI

/// Integration management — shows Calendar, Reminders, Notes, Mail with permission status
struct IntegrationsView: View {
    @StateObject private var viewModel = IntegrationsViewModel()

    var body: some View {
        ScrollView {
            VStack(spacing: Spacing.lg) {
                // Section header
                VStack(alignment: .leading, spacing: Spacing.sm) {
                    Text("Apple Integrations")
                        .font(.sectionHeader)
                        .foregroundColor(.white.opacity(0.6))
                        .textCase(.uppercase)
                        .padding(.horizontal, Spacing.lg)

                    Text("Manage connections to Apple services used by Hestia's tools.")
                        .font(.caption)
                        .foregroundColor(.white.opacity(0.4))
                        .padding(.horizontal, Spacing.lg)
                }

                // Integration cards
                VStack(spacing: Spacing.sm) {
                    ForEach(viewModel.integrations) { integration in
                        NavigationLink(
                            destination: IntegrationDetailView(
                                viewModel: viewModel,
                                integrationType: integration.id
                            )
                        ) {
                            integrationRow(integration)
                        }
                    }
                }
                .padding(.horizontal, Spacing.lg)

                // Footer
                Text("More integrations coming soon")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.3))
                    .padding(.top, Spacing.md)

                Spacer()
                    .frame(height: Spacing.xxl)
            }
            .padding(.top, Spacing.md)
        }
        .onAppear {
            viewModel.setup()
        }
    }

    // MARK: - Integration Row

    private func integrationRow(_ integration: Integration) -> some View {
        HStack(spacing: Spacing.md) {
            // Integration icon
            Image(systemName: integration.iconName)
                .foregroundColor(.white)
                .font(.title3)
                .frame(width: 32)

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: Spacing.xs) {
                    Text(integration.name)
                        .foregroundColor(.white)

                    // Status badge
                    Text(integration.status.displayName)
                        .font(.caption2)
                        .foregroundColor(integration.status.color)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(integration.status.color.opacity(0.15))
                        .cornerRadius(4)
                }

                Text("\(integration.toolCount) tools available")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.6))
            }

            Spacer()

            Image(systemName: "chevron.right")
                .foregroundColor(.white.opacity(0.5))
        }
        .settingsRow()
    }
}

// MARK: - Preview

struct IntegrationsView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            ZStack {
                Color.black.ignoresSafeArea()
                IntegrationsView()
            }
        }
    }
}
