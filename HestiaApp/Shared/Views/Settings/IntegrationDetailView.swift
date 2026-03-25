import SwiftUI
import HestiaShared
import UIKit
import EventKit

/// Detail view for a specific integration — permissions, tools, and configuration
struct IntegrationDetailView: View {
    @ObservedObject var viewModel: IntegrationsViewModel
    let integrationType: IntegrationType

    private var integration: Integration? {
        viewModel.integration(for: integrationType)
    }

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            ScrollView {
                VStack(spacing: Spacing.lg) {
                    // Permission status
                    permissionSection

                    // Tool list
                    toolListSection

                    // Configuration (Calendar only)
                    if integrationType == .calendar, integration?.status == .connected {
                        calendarConfigSection
                    }

                    // Health coaching preferences
                    if integrationType == .health, integration?.status == .connected {
                        healthConfigSection
                    }

                    Spacer()
                        .frame(height: Spacing.xxl)
                }
                .padding(.top, Spacing.md)
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle(integrationType.displayName)
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Permission Section

    @ViewBuilder
    private var permissionSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Status")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            if let integration = integration {
                switch integration.status {
                case .connected:
                    connectedRow

                case .notConnected:
                    notConnectedRow

                case .denied:
                    deniedRow

                case .backendOnly:
                    backendOnlyRow
                }
            }
        }
    }

    private var connectedRow: some View {
        HStack {
            Image(systemName: "checkmark.circle.fill")
                .foregroundColor(.healthyGreen)

            Text("Connected")
                .foregroundColor(.textPrimary)

            Spacer()

            Text("Permission Granted")
                .font(.caption)
                .foregroundColor(.healthyGreen)
        }
        .settingsRow()
        .padding(.horizontal, Spacing.lg)
    }

    private var notConnectedRow: some View {
        VStack(spacing: Spacing.sm) {
            HStack {
                Image(systemName: "exclamationmark.circle")
                    .foregroundColor(.textSecondary)

                Text("Not Connected")
                    .foregroundColor(.textPrimary)

                Spacer()
            }
            .settingsRow()

            Button {
                Task {
                    await viewModel.requestPermission(for: integrationType)
                }
            } label: {
                HStack {
                    Image(systemName: "lock.open.fill")
                    Text("Grant Access")
                }
                .foregroundColor(.textPrimary)
                .frame(maxWidth: .infinity)
                .padding(Spacing.md)
                .background(Color.white.opacity(0.15))
                .cornerRadius(CornerRadius.small)
            }

            Text("Hestia needs permission to access your \(integrationType.displayName.lowercased()) on this device.")
                .font(.caption)
                .foregroundColor(.textTertiary)
        }
        .padding(.horizontal, Spacing.lg)
    }

    private var deniedRow: some View {
        VStack(spacing: Spacing.sm) {
            HStack {
                Image(systemName: "xmark.circle.fill")
                    .foregroundColor(.errorRed)

                Text("Permission Denied")
                    .foregroundColor(.textPrimary)

                Spacer()
            }
            .settingsRow()

            Button {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    UIApplication.shared.open(url)
                }
            } label: {
                HStack {
                    Image(systemName: "gear")
                    Text("Open Settings")
                }
                .foregroundColor(.textPrimary)
                .frame(maxWidth: .infinity)
                .padding(Spacing.md)
                .background(Color.white.opacity(0.15))
                .cornerRadius(CornerRadius.small)
            }

            Text("Go to Settings > Privacy > \(integrationType.displayName) to grant access.")
                .font(.caption)
                .foregroundColor(.textTertiary)
        }
        .padding(.horizontal, Spacing.lg)
    }

    private var backendOnlyRow: some View {
        VStack(spacing: Spacing.sm) {
            HStack {
                Image(systemName: "server.rack")
                    .foregroundColor(.blue)

                Text("Available via Backend")
                    .foregroundColor(.textPrimary)

                Spacer()

                Text("Backend")
                    .font(.caption)
                    .foregroundColor(.blue)
            }
            .settingsRow()

            Text("This integration works through Hestia's backend server. No device permissions needed.")
                .font(.caption)
                .foregroundColor(.textTertiary)
        }
        .padding(.horizontal, Spacing.lg)
    }

    // MARK: - Tool List Section

    private var toolListSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Available Tools")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            if let tools = integration?.tools {
                VStack(spacing: Spacing.sm) {
                    ForEach(tools) { tool in
                        toolRow(tool)
                    }
                }
                .padding(.horizontal, Spacing.lg)
            }
        }
    }

    private func toolRow(_ tool: IntegrationTool) -> some View {
        HStack(spacing: Spacing.md) {
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: Spacing.xs) {
                    Text(tool.name)
                        .foregroundColor(.textPrimary)
                        .font(.subheadline)

                    if tool.requiresApproval {
                        Text("Approval")
                            .font(.caption2)
                            .foregroundColor(.warningYellow)
                            .padding(.horizontal, 5)
                            .padding(.vertical, 1)
                            .background(Color.warningYellow.opacity(0.15))
                            .cornerRadius(3)
                    }
                }

                Text(tool.description)
                    .font(.caption)
                    .foregroundColor(.textSecondary)
            }

            Spacer()
        }
        .settingsRow()
    }

    // MARK: - Health Configuration Section

    private var healthConfigSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Configuration")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            NavigationLink {
                HealthCoachingPreferencesView()
            } label: {
                HStack {
                    Image(systemName: "heart.text.square")
                        .foregroundColor(.pink)

                    Text("Coaching Preferences")
                        .foregroundColor(.textPrimary)

                    Spacer()

                    Image(systemName: "chevron.right")
                        .foregroundColor(.textTertiary)
                        .font(.caption)
                }
                .settingsRow()
            }
            .padding(.horizontal, Spacing.lg)

            Text("Configure health coaching domains, goals, notifications, and coaching tone.")
                .font(.caption)
                .foregroundColor(.textTertiary)
                .padding(.horizontal, Spacing.lg)
        }
    }

    // MARK: - Calendar Configuration Section

    private var calendarConfigSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Configuration")
                .font(.sectionHeader)
                .foregroundColor(.textSecondary)
                .textCase(.uppercase)
                .padding(.horizontal, Spacing.lg)

            VStack(spacing: Spacing.sm) {
                // Exclude all-day events toggle
                HStack {
                    Text("Exclude All-Day Events")
                        .foregroundColor(.textPrimary)

                    Spacer()

                    Toggle("", isOn: $viewModel.calendarExcludeAllDay)
                        .labelsHidden()
                        .tint(.healthyGreen)
                }
                .settingsRow()

                // Look-ahead days stepper
                HStack {
                    Text("Look-Ahead")
                        .foregroundColor(.textPrimary)

                    Spacer()

                    Stepper(
                        "\(viewModel.calendarLookAheadDays) days",
                        value: $viewModel.calendarLookAheadDays,
                        in: 1...30
                    )
                    .foregroundColor(.white.opacity(0.7))
                }
                .settingsRow()

                // Excluded calendars
                excludedCalendarsSection
            }
            .padding(.horizontal, Spacing.lg)

            Text("These settings affect the calendar widget in Command Center. Backend tools are unaffected.")
                .font(.caption)
                .foregroundColor(.textTertiary)
                .padding(.horizontal, Spacing.lg)
        }
    }

    private var excludedCalendarsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Text("Excluded Calendars")
                .foregroundColor(.white.opacity(0.7))
                .font(.caption)

            let available = viewModel.availableCalendarNames()

            if available.isEmpty {
                Text("No calendars found. Grant calendar access first.")
                    .font(.caption)
                    .foregroundColor(.textTertiary)
                    .settingsRow()
            } else {
                ForEach(available, id: \.self) { calendarName in
                    let isExcluded = viewModel.calendarExcludedNames.contains(calendarName)

                    Button {
                        toggleCalendarExclusion(calendarName)
                    } label: {
                        HStack {
                            Image(systemName: isExcluded ? "xmark.circle.fill" : "checkmark.circle.fill")
                                .foregroundColor(isExcluded ? .errorRed.opacity(0.7) : .healthyGreen)

                            Text(calendarName)
                                .foregroundColor(isExcluded ? .white.opacity(0.4) : .white)

                            Spacer()

                            if isExcluded {
                                Text("Excluded")
                                    .font(.caption2)
                                    .foregroundColor(.textTertiary)
                            }
                        }
                    }
                    .settingsRow()
                }
            }
        }
    }

    private func toggleCalendarExclusion(_ name: String) {
        if viewModel.calendarExcludedNames.contains(name) {
            viewModel.calendarExcludedNames.removeAll { $0 == name }
        } else {
            viewModel.calendarExcludedNames.append(name)
        }
    }
}

// MARK: - Preview

struct IntegrationDetailView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            IntegrationDetailView(
                viewModel: IntegrationsViewModel(),
                integrationType: .calendar
            )
        }
    }
}
