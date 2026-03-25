import SwiftUI
import HestiaShared

/// Sheet for creating a new scheduled order from the Hero section.
struct NewOrderSheet: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(ErrorState.self) private var errorState

    @State private var name = ""
    @State private var prompt = ""
    @State private var scheduledTime = "09:00"
    @State private var frequency: OrderFrequencyType = .daily
    @State private var isSaving = false

    enum OrderFrequencyType: String, CaseIterable {
        case once, daily, weekly, monthly

        var apiValue: OrderFrequencyAPI {
            switch self {
            case .once: OrderFrequencyAPI(type: .once, minutes: nil)
            case .daily: OrderFrequencyAPI(type: .daily, minutes: nil)
            case .weekly: OrderFrequencyAPI(type: .weekly, minutes: nil)
            case .monthly: OrderFrequencyAPI(type: .monthly, minutes: nil)
            }
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xl) {
            // Header
            HStack {
                Text("New Order")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark")
                        .font(MacTypography.smallMedium)
                        .foregroundStyle(MacColors.textSecondary)
                        .frame(width: 24, height: 24)
                        .background(MacColors.searchInputBackground)
                        .clipShape(Circle())
                }
                .buttonStyle(.hestiaIcon)
            }

            // Name field
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                Text("Name")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
                TextField("e.g. Morning Briefing", text: $name)
                    .textFieldStyle(.roundedBorder)
            }

            // Prompt field
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                Text("Prompt")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
                TextEditor(text: $prompt)
                    .font(MacTypography.body)
                    .frame(minHeight: 80, maxHeight: 120)
                    .padding(MacSpacing.sm)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            }

            // Time + Frequency row
            HStack(spacing: MacSpacing.lg) {
                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    Text("Time")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                    TextField("HH:MM", text: $scheduledTime)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 80)
                }

                VStack(alignment: .leading, spacing: MacSpacing.xs) {
                    Text("Frequency")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.textSecondary)
                    Picker("", selection: $frequency) {
                        ForEach(OrderFrequencyType.allCases, id: \.self) { freq in
                            Text(freq.rawValue.capitalized).tag(freq)
                        }
                    }
                    .labelsHidden()
                    .pickerStyle(.segmented)
                }
            }

            Spacer()

            // Action buttons
            HStack {
                Spacer()
                Button("Cancel") {
                    dismiss()
                }
                .buttonStyle(.hestia)

                Button {
                    Task { await saveOrder() }
                } label: {
                    HStack(spacing: MacSpacing.sm) {
                        if isSaving {
                            ProgressView()
                                .controlSize(.small)
                        }
                        Text("Create Order")
                    }
                    .foregroundStyle(MacColors.buttonTextDark)
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
        .frame(width: 460, height: 420)
        .background(MacColors.panelBackground)
    }

    private var canSave: Bool {
        !name.trimmingCharacters(in: .whitespaces).isEmpty &&
        !prompt.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private func saveOrder() async {
        isSaving = true
        defer { isSaving = false }

        let request = OrderCreateRequest(
            name: name.trimmingCharacters(in: .whitespaces),
            prompt: prompt.trimmingCharacters(in: .whitespaces),
            scheduledTime: scheduledTime,
            frequency: frequency.apiValue,
            resources: []
        )

        do {
            _ = try await APIClient.shared.createOrder(request)
            dismiss()
        } catch {
            errorState.show("Failed to create order", severity: .error)
            #if DEBUG
            print("[NewOrderSheet] Save failed: \(error)")
            #endif
        }
    }
}
