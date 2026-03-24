import SwiftUI
import HestiaShared

struct MacNewWorkflowSheet: View {
    @ObservedObject var viewModel: WorkflowViewModel
    @Environment(\.dismiss) private var dismiss

    @State private var name = ""
    @State private var description = ""
    @State private var triggerType: WorkflowTriggerType = .manual
    @State private var sessionStrategy: WorkflowSessionStrategy = .ephemeral
    @State private var isSaving = false

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xl) {
            // Header
            HStack {
                Text("New Workflow")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()
                closeButton
            }

            // Form fields
            VStack(alignment: .leading, spacing: MacSpacing.lg) {
                nameField
                descriptionField
                triggerTypeSelector
                sessionStrategySelector
            }

            Spacer()

            // Action buttons
            HStack {
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(.hestia)

                Button {
                    Task { await saveWorkflow() }
                } label: {
                    HStack(spacing: MacSpacing.sm) {
                        if isSaving {
                            ProgressView().controlSize(.small)
                        }
                        Text("Create Workflow")
                    }
                    .foregroundStyle(canSave ? MacColors.buttonTextDark : MacColors.textFaint)
                    .padding(.horizontal, MacSpacing.lg)
                    .padding(.vertical, MacSpacing.sm)
                    .background(canSave ? MacColors.amberAccent : MacColors.amberAccent.opacity(0.4))
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.hestia)
                .disabled(!canSave || isSaving)
            }
        }
        .padding(MacSpacing.xxl)
        .frame(width: 460, height: 480)
        .background(MacColors.panelBackground)
    }

    // MARK: - Components

    private var closeButton: some View {
        Button { dismiss() } label: {
            Image(systemName: "xmark")
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(MacColors.textSecondary)
                .frame(width: 24, height: 24)
                .background(MacColors.searchInputBackground)
                .clipShape(Circle())
        }
        .buttonStyle(.hestiaIcon)
    }

    private var nameField: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            Text("Name")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)
            TextField("e.g. Daily Report Generator", text: $name)
                .textFieldStyle(.roundedBorder)
        }
    }

    private var descriptionField: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            Text("Description")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)
            TextEditor(text: $description)
                .font(MacTypography.body)
                .frame(minHeight: 60, maxHeight: 100)
                .padding(MacSpacing.sm)
                .background(MacColors.searchInputBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        }
    }

    private var triggerTypeSelector: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            Text("Trigger Type")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)
            Picker("", selection: $triggerType) {
                Text("Manual").tag(WorkflowTriggerType.manual)
                Text("Schedule").tag(WorkflowTriggerType.schedule)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
        }
    }

    private var sessionStrategySelector: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            Text("Session Strategy")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)
            Picker("", selection: $sessionStrategy) {
                Text("Ephemeral").tag(WorkflowSessionStrategy.ephemeral)
                Text("Per Run").tag(WorkflowSessionStrategy.perRun)
                Text("Persistent").tag(WorkflowSessionStrategy.persistent)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
        }
    }

    // MARK: - Logic

    private var canSave: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private func saveWorkflow() async {
        isSaving = true
        defer { isSaving = false }

        let success = await viewModel.createWorkflow(
            name: name.trimmingCharacters(in: .whitespaces),
            description: description.trimmingCharacters(in: .whitespaces),
            triggerType: triggerType,
            sessionStrategy: sessionStrategy
        )

        if success {
            dismiss()
        }
    }
}
