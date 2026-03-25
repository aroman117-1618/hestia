import SwiftUI
import HestiaShared

/// Sheet for editing an existing workflow's name and description.
struct MacEditWorkflowSheet: View {
    @ObservedObject var viewModel: WorkflowViewModel
    let detail: WorkflowDetail

    @Environment(\.dismiss) private var dismiss

    @State private var name: String = ""
    @State private var description: String = ""
    @State private var isSaving = false
    @State private var saveError: String?

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            // Title
            Text("Edit Order")
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(MacColors.textPrimary)

            // Name field
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                Text("Name")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
                TextField("Order name", text: $name)
                    .textFieldStyle(.roundedBorder)
            }

            // Description field
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                Text("Description")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
                TextEditor(text: $description)
                    .font(.system(size: 13))
                    .frame(minHeight: 60, maxHeight: 120)
                    .padding(4)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(MacColors.cardBorder, lineWidth: 1)
                    )
            }

            if let error = saveError {
                Text(error)
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.healthRed)
            }

            // Buttons
            HStack {
                Spacer()
                Button("Cancel") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button("Save") {
                    Task { await save() }
                }
                .keyboardShortcut(.defaultAction)
                .disabled(name.trimmingCharacters(in: .whitespaces).isEmpty || isSaving)
            }
        }
        .padding(MacSpacing.xl)
        .frame(width: 400)
        .onAppear {
            name = detail.name
            description = detail.description
        }
    }

    private func save() async {
        isSaving = true
        saveError = nil
        let trimmedName = name.trimmingCharacters(in: .whitespaces)
        let trimmedDesc = description.trimmingCharacters(in: .whitespaces)
        let success = await viewModel.updateWorkflow(
            detail.id,
            name: trimmedName,
            description: trimmedDesc
        )
        isSaving = false
        if success {
            dismiss()
        } else {
            saveError = "Failed to save changes"
        }
    }
}
