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

    // Schedule state
    @State private var scheduleDate = Date()
    @State private var scheduleTime = Date()
    @State private var isRecurring = false
    @State private var recurringDays: Set<Weekday> = []

    enum Weekday: String, CaseIterable, Identifiable {
        case mon = "Mon", tue = "Tue", wed = "Wed", thu = "Thu"
        case fri = "Fri", sat = "Sat", sun = "Sun"
        var id: String { rawValue }
        var cronValue: String {
            switch self {
            case .mon: "1"
            case .tue: "2"
            case .wed: "3"
            case .thu: "4"
            case .fri: "5"
            case .sat: "6"
            case .sun: "0"
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
                closeButton
            }

            ScrollView {
                VStack(alignment: .leading, spacing: MacSpacing.lg) {
                    nameField
                    descriptionField
                    triggerTypeSelector
                    if triggerType == .schedule {
                        scheduleSection
                    }
                    sessionStrategySelector
                }
            }

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
                        Text("Create Order")
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
        .frame(width: 500, height: triggerType == .schedule ? 600 : 460)
        .background(MacColors.panelBackground)
        .animation(.easeInOut(duration: 0.2), value: triggerType)
    }

    // MARK: - Components

    private var closeButton: some View {
        Button { dismiss() } label: {
            Image(systemName: "xmark")
                .font(MacTypography.smallMedium)
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
            TextField("e.g. Evening Research, Daily Briefing", text: $name)
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
                .frame(minHeight: 50, maxHeight: 80)
                .padding(MacSpacing.sm)
                .background(MacColors.searchInputBackground)
                .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        }
    }

    private var triggerTypeSelector: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            Text("Trigger")
                .font(MacTypography.label)
                .foregroundStyle(MacColors.textSecondary)
            Picker("", selection: $triggerType) {
                Label("Manual", systemImage: "hand.tap").tag(WorkflowTriggerType.manual)
                Label("Scheduled", systemImage: "clock").tag(WorkflowTriggerType.schedule)
            }
            .pickerStyle(.segmented)
            .labelsHidden()
        }
    }

    // MARK: - Schedule Section

    private var scheduleSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            // Recurring toggle
            HStack {
                Text("Recurring")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
                Spacer()
                Toggle("", isOn: $isRecurring)
                    .toggleStyle(.switch)
                    .labelsHidden()
                    .tint(MacColors.amberAccent)
            }

            if isRecurring {
                // Day picker
                VStack(alignment: .leading, spacing: MacSpacing.sm) {
                    Text("Repeat on")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    HStack(spacing: 4) {
                        ForEach(Weekday.allCases) { day in
                            dayPill(day)
                        }
                    }
                }

                // Time picker
                VStack(alignment: .leading, spacing: MacSpacing.sm) {
                    Text("At time")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    DatePicker("", selection: $scheduleTime, displayedComponents: .hourAndMinute)
                        .datePickerStyle(.field)
                        .labelsHidden()
                        .frame(width: 100)
                }
            } else {
                // One-time: date + time picker
                VStack(alignment: .leading, spacing: MacSpacing.sm) {
                    Text("Run on")
                        .font(MacTypography.caption)
                        .foregroundStyle(MacColors.textFaint)
                    HStack(spacing: MacSpacing.md) {
                        DatePicker("", selection: $scheduleDate, displayedComponents: .date)
                            .datePickerStyle(.field)
                            .labelsHidden()
                        DatePicker("", selection: $scheduleTime, displayedComponents: .hourAndMinute)
                            .datePickerStyle(.field)
                            .labelsHidden()
                            .frame(width: 100)
                    }
                }
            }

            // Preview
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: "info.circle")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)
                Text(schedulePreview)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)
            }
            .padding(.top, MacSpacing.xs)
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
    }

    private func dayPill(_ day: Weekday) -> some View {
        let isSelected = recurringDays.contains(day)
        return Button {
            if isSelected {
                recurringDays.remove(day)
            } else {
                recurringDays.insert(day)
            }
        } label: {
            Text(day.rawValue)
                .font(.system(size: 11, weight: isSelected ? .semibold : .regular))
                .foregroundStyle(isSelected ? MacColors.amberAccent : MacColors.textSecondary)
                .frame(width: 38, height: 28)
                .background(isSelected ? MacColors.activeTabBackground : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: 6))
                .overlay {
                    RoundedRectangle(cornerRadius: 6)
                        .strokeBorder(isSelected ? MacColors.amberAccent.opacity(0.3) : MacColors.cardBorder, lineWidth: 1)
                }
        }
        .buttonStyle(.hestia)
    }

    private var schedulePreview: String {
        let timeFormatter = DateFormatter()
        timeFormatter.dateFormat = "h:mm a"
        let timeStr = timeFormatter.string(from: scheduleTime)

        if isRecurring {
            if recurringDays.isEmpty {
                return "Select days to repeat"
            }
            let sorted = Weekday.allCases.filter { recurringDays.contains($0) }
            if sorted.count == 7 {
                return "Every day at \(timeStr)"
            }
            if sorted.count == 5 && !recurringDays.contains(.sat) && !recurringDays.contains(.sun) {
                return "Weekdays at \(timeStr)"
            }
            let dayNames = sorted.map(\.rawValue).joined(separator: ", ")
            return "Every \(dayNames) at \(timeStr)"
        } else {
            let dateFormatter = DateFormatter()
            dateFormatter.dateStyle = .medium
            return "\(dateFormatter.string(from: scheduleDate)) at \(timeStr)"
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
        let hasName = !name.trimmingCharacters(in: .whitespaces).isEmpty
        if triggerType == .schedule && isRecurring {
            return hasName && !recurringDays.isEmpty
        }
        return hasName
    }

    private func buildCronExpression() -> String {
        let calendar = Calendar.current
        let minute = calendar.component(.minute, from: scheduleTime)
        let hour = calendar.component(.hour, from: scheduleTime)

        if isRecurring {
            let days = Weekday.allCases
                .filter { recurringDays.contains($0) }
                .map(\.cronValue)
                .joined(separator: ",")
            return "\(minute) \(hour) * * \(days)"
        } else {
            let day = calendar.component(.day, from: scheduleDate)
            let month = calendar.component(.month, from: scheduleDate)
            return "\(minute) \(hour) \(day) \(month) *"
        }
    }

    private func saveWorkflow() async {
        isSaving = true
        defer { isSaving = false }

        var triggerConfig: [String: AnyCodableValue] = [:]
        if triggerType == .schedule {
            triggerConfig["cron"] = .string(buildCronExpression())
        }

        let success = await viewModel.createWorkflow(
            name: name.trimmingCharacters(in: .whitespaces),
            description: description.trimmingCharacters(in: .whitespaces),
            triggerType: triggerType,
            triggerConfig: triggerConfig,
            sessionStrategy: sessionStrategy
        )

        if success {
            dismiss()
        }
    }
}
