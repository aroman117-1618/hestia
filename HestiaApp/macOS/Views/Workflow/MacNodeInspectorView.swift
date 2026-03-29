import SwiftUI
import HestiaShared

struct MacNodeInspectorView: View {
    @ObservedObject var viewModel: WorkflowViewModel
    let node: WorkflowNodeResponse

    @State private var label: String = ""

    // run_prompt
    @State private var prompt: String = ""
    @State private var model: String = ""
    @State private var memoryWrite: Bool = false
    @State private var inferenceRoute: String = ""  // "", "local", "smart_cloud", "full_cloud"
    @State private var selectedResources: Set<String> = []

    // call_tool
    @State private var toolName: String = ""
    @State private var toolArguments: String = ""

    // notify
    @State private var notifyMessage: String = ""
    @State private var notifyChannel: String = ""

    // log
    @State private var logMessage: String = ""
    @State private var logLevel: String = "info"

    // if_else / switch
    @State private var conditionField: String = ""
    @State private var conditionOperator: String = "eq"
    @State private var conditionValue: String = ""

    // delay
    @State private var delaySeconds: String = ""
    @State private var delayValue: Double = 0
    @State private var delayUnit: DelayUnit = .minutes

    enum DelayUnit: String, CaseIterable {
        case minutes = "Minutes"
        case hours = "Hours"
        case days = "Days"

        var multiplier: Double {
            switch self {
            case .minutes: return 60
            case .hours: return 3600
            case .days: return 86400
            }
        }

        var maxValue: Double {
            switch self {
            case .minutes: return 180 * 24 * 60  // 180 days in minutes
            case .hours: return 180 * 24          // 180 days in hours
            case .days: return 180
            }
        }
    }

    @State private var isSaving = false
    @State private var saveError: String?
    @State private var didSave = false

    // refine
    @State private var isRefining: Bool = false
    @State private var refineVariations: [PromptVariation] = []
    @State private var showRefinePanel: Bool = false
    @State private var refineError: String?

    // MARK: - Body

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.lg) {
            inspectorHeader

            Divider()
                .background(MacColors.cardBorder)

            ScrollView {
                VStack(alignment: .leading, spacing: MacSpacing.lg) {
                    // Label — all node types
                    fieldGroup("Label") {
                        TextField("Node label", text: $label)
                            .textFieldStyle(.roundedBorder)
                    }

                    // Type badge (read-only)
                    fieldGroup("Type") {
                        Text(nodeTypeLabel)
                            .font(MacTypography.label)
                            .foregroundStyle(MacColors.textSecondary)
                    }

                    // Per-type config section
                    configSection
                }
                .padding(.bottom, MacSpacing.lg)
            }

            Spacer()

            saveBar
        }
        .padding(MacSpacing.lg)
        .frame(minWidth: 340, idealWidth: 400)
        .background(MacColors.panelBackground)
        .onAppear {
            loadFromNode()
            Task { await viewModel.fetchToolCategories() }
        }
        .onChange(of: node.id) { _, _ in loadFromNode() }
    }

    // MARK: - Header

    private var inspectorHeader: some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: node.iconName)
                .font(MacTypography.body)
                .foregroundStyle(MacColors.amberAccent)
            Text("Node Inspector")
                .font(MacTypography.cardTitle)
                .foregroundStyle(MacColors.textPrimary)
            Spacer()
            // Close inspector
            Button {
                viewModel.selectedNodeId = nil
            } label: {
                Image(systemName: "xmark")
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.textSecondary)
                    .frame(width: 20, height: 20)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 4))
            }
            .buttonStyle(.hestia)
            .help("Close inspector")
        }
    }

    // MARK: - Config Section (per type)

    @ViewBuilder
    private var configSection: some View {
        switch node.nodeTypeEnum {
        case .runPrompt:
            fieldGroup("Prompt") {
                TextEditor(text: $prompt)
                    .font(MacTypography.smallBody)
                    .frame(minHeight: 80)
                    .padding(MacSpacing.xs)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(MacColors.cardBorder, lineWidth: 1)
                    )
            }
            // Refine button
            HStack(spacing: MacSpacing.xs) {
                Button {
                    Task { await refineCurrentPrompt() }
                } label: {
                    HStack(spacing: 4) {
                        if isRefining {
                            ProgressView()
                                .controlSize(.small)
                        } else {
                            Image(systemName: "wand.and.stars")
                                .font(.system(size: 11))
                        }
                        Text("Refine")
                            .font(MacTypography.caption)
                    }
                    .padding(.horizontal, MacSpacing.sm)
                    .padding(.vertical, 4)
                    .background(MacColors.amberAccent)
                    .foregroundStyle(MacColors.panelBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                }
                .buttonStyle(.plain)
                .disabled(prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isRefining)
                .help("Refine prompt using local AI with your personal context")

                Text("Local")
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textFaint)
            }
            refinePanel
            fieldGroup("Inference") {
                Picker("", selection: $inferenceRoute) {
                    Text("Local").tag("local")
                    Text("Smart").tag("smart_cloud")
                    Text("Cloud").tag("full_cloud")
                }
                .labelsHidden()
                .pickerStyle(.segmented)
                .help("Local: device only — Smart: local-first, cloud fallback — Cloud: always cloud")
            }
            HStack {
                Toggle("Save to Memory", isOn: $memoryWrite)
                    .font(MacTypography.caption)
                    .toggleStyle(.switch)
                    .tint(MacColors.amberAccent)
                Spacer()
            }
            .foregroundStyle(MacColors.textSecondary)
            if !viewModel.toolCategories.isEmpty {
                fieldGroup("Resources") {
                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 90))], spacing: 6) {
                        ForEach(viewModel.toolCategories) { category in
                            let isSelected = selectedResources.contains(category.id)
                            Button {
                                if isSelected {
                                    selectedResources.remove(category.id)
                                } else {
                                    selectedResources.insert(category.id)
                                }
                            } label: {
                                HStack(spacing: 4) {
                                    Image(systemName: category.icon)
                                        .font(MacTypography.metadata)
                                    Text(category.label)
                                        .font(MacTypography.metadata)
                                        .lineLimit(1)
                                }
                                .foregroundStyle(isSelected ? MacColors.buttonTextDark : MacColors.textSecondary)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 4)
                                .background(isSelected ? MacColors.amberAccent : Color.clear)
                                .clipShape(RoundedRectangle(cornerRadius: 5))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 5)
                                        .stroke(isSelected ? MacColors.amberAccent : MacColors.cardBorder, lineWidth: 1)
                                )
                            }
                            .buttonStyle(.hestia)
                        }
                    }
                }
            }

        case .callTool:
            fieldGroup("Tool Name") {
                TextField("e.g. read_file", text: $toolName)
                    .textFieldStyle(.roundedBorder)
            }
            fieldGroup("Arguments (JSON)") {
                TextEditor(text: $toolArguments)
                    .font(MacTypography.smallBody)
                    .frame(minHeight: 60)
                    .padding(MacSpacing.xs)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(MacColors.cardBorder, lineWidth: 1)
                    )
            }

        case .notify:
            fieldGroup("Message") {
                TextEditor(text: $notifyMessage)
                    .font(MacTypography.smallBody)
                    .frame(minHeight: 60)
                    .padding(MacSpacing.xs)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(MacColors.cardBorder, lineWidth: 1)
                    )
            }
            fieldGroup("Channel") {
                Picker("", selection: $notifyChannel) {
                    Text("macOS (local)").tag("macos")
                    Text("Push (APNs)").tag("push")
                    Text("Both").tag("both")
                }
                .labelsHidden()
                .pickerStyle(.segmented)
            }

        case .log:
            fieldGroup("Message") {
                TextEditor(text: $logMessage)
                    .font(MacTypography.smallBody)
                    .frame(minHeight: 60)
                    .padding(MacSpacing.xs)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay(
                        RoundedRectangle(cornerRadius: 6)
                            .stroke(MacColors.cardBorder, lineWidth: 1)
                    )
            }
            fieldGroup("Level") {
                Picker("Level", selection: $logLevel) {
                    Text("Info").tag("info")
                    Text("Warning").tag("warning")
                    Text("Error").tag("error")
                }
                .pickerStyle(.segmented)
                .labelsHidden()
            }

        case .ifElse:
            fieldGroup("Condition Field") {
                TextField("e.g. result.status", text: $conditionField)
                    .textFieldStyle(.roundedBorder)
            }
            fieldGroup("Operator") {
                Picker("Operator", selection: $conditionOperator) {
                    Text("equals").tag("eq")
                    Text("not equals").tag("neq")
                    Text("greater than").tag("gt")
                    Text("less than").tag("lt")
                    Text("contains").tag("contains")
                    Text("is empty").tag("is_empty")
                    Text("is not empty").tag("is_not_empty")
                }
                .pickerStyle(.menu)
                .labelsHidden()
            }
            fieldGroup("Value") {
                TextField("Compare value", text: $conditionValue)
                    .textFieldStyle(.roundedBorder)
            }

        case .schedule, .manual:
            // Trigger nodes: label only (no additional config)
            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                Text("Trigger nodes have no additional configuration.")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)
                    .multilineTextAlignment(.leading)
            }

        case .delay:
            fieldGroup("Duration") {
                HStack(spacing: MacSpacing.sm) {
                    TextField("1", value: $delayValue, format: .number)
                        .textFieldStyle(.roundedBorder)
                        .frame(maxWidth: 70)
                        .onChange(of: delayValue) {
                            delayValue = max(1, min(delayValue, delayUnit.maxValue))
                        }
                    Picker("Unit", selection: $delayUnit) {
                        ForEach(DelayUnit.allCases, id: \.self) { unit in
                            Text(unit.rawValue).tag(unit)
                        }
                    }
                    .pickerStyle(.segmented)
                    .labelsHidden()
                }
            }
            Text("Min: 1, Max: 180 days")
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textFaint)

        case .switchNode:
            fieldGroup("Switch Field") {
                TextField("e.g. result.status", text: $conditionField)
                    .textFieldStyle(.roundedBorder)
            }
        }
    }

    // MARK: - Save Bar

    private var saveBar: some View {
        VStack(alignment: .trailing, spacing: 4) {
            if let error = saveError {
                Text(error)
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.healthRed)
                    .multilineTextAlignment(.trailing)
            }
            if didSave {
                Text("Saved")
                    .font(MacTypography.metadata)
                    .foregroundStyle(MacColors.healthGreen)
                    .transition(.opacity)
            }
            HStack {
                Spacer()
                Button {
                    Task { await saveChanges() }
                } label: {
                    HStack(spacing: 4) {
                        if isSaving {
                            ProgressView()
                                .controlSize(.small)
                        }
                        Text("Save")
                    }
                    .font(MacTypography.smallMedium)
                    .foregroundStyle(MacColors.buttonTextDark)
                    .padding(.horizontal, MacSpacing.lg)
                    .padding(.vertical, 6)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.treeItem))
                }
                .buttonStyle(.hestia)
                .disabled(isSaving)
            }
        }
    }

    // MARK: - Helpers

    private var nodeTypeLabel: String {
        node.nodeType.replacingOccurrences(of: "_", with: " ").capitalized
    }

    private func fieldGroup<Content: View>(_ title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(MacTypography.metadata)
                .foregroundStyle(MacColors.textFaint)
                .textCase(.uppercase)
            content()
        }
    }

    // MARK: - Refine Panel

    @ViewBuilder
    private var refinePanel: some View {
        if showRefinePanel && !refineVariations.isEmpty {
            VStack(alignment: .leading, spacing: MacSpacing.sm) {
                HStack {
                    Text("Refined Variations")
                        .font(MacTypography.label)
                        .foregroundStyle(MacColors.amberAccent)
                    Spacer()
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            showRefinePanel = false
                        }
                    } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 10))
                            .foregroundStyle(MacColors.textSecondary)
                    }
                    .buttonStyle(.plain)
                }

                ForEach(refineVariations) { variation in
                    variationCard(variation)
                }

                if let error = refineError {
                    Text(error)
                        .font(.system(size: 10))
                        .foregroundStyle(.red)
                }
            }
            .padding(MacSpacing.sm)
            .background(MacColors.panelBackground.opacity(0.95))
            .clipShape(RoundedRectangle(cornerRadius: 8))
            .overlay(
                RoundedRectangle(cornerRadius: 8)
                    .stroke(MacColors.amberAccent.opacity(0.3), lineWidth: 1)
            )
            .transition(.opacity.combined(with: .move(edge: .trailing)))
        }
    }

    @ViewBuilder
    private func variationCard(_ variation: PromptVariation) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.xs) {
            HStack {
                Text(variation.label)
                    .font(MacTypography.caption.bold())
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()
                let badgeColor = suitabilityColor(variation.modelSuitability)
                Text(variation.suitabilityBadge)
                    .font(.system(size: 9))
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(badgeColor.opacity(0.15))
                    .foregroundStyle(badgeColor)
                    .clipShape(RoundedRectangle(cornerRadius: 3))
            }

            Text(variation.prompt)
                .font(MacTypography.smallBody)
                .foregroundStyle(MacColors.textPrimary)
                .lineLimit(4)

            Text(variation.explanation)
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textFaint)
                .italic()

            HStack {
                Spacer()
                Button("Apply") {
                    prompt = variation.prompt
                    withAnimation(.easeInOut(duration: 0.2)) {
                        showRefinePanel = false
                    }
                }
                .font(MacTypography.caption)
                .padding(.horizontal, MacSpacing.sm)
                .padding(.vertical, 3)
                .background(MacColors.amberAccent)
                .foregroundStyle(MacColors.panelBackground)
                .clipShape(RoundedRectangle(cornerRadius: 4))
                .buttonStyle(.plain)
            }
        }
        .padding(MacSpacing.sm)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .overlay(
            RoundedRectangle(cornerRadius: 6)
                .stroke(MacColors.cardBorder, lineWidth: 1)
        )
    }

    private func suitabilityColor(_ suitability: String) -> Color {
        switch suitability {
        case "cloud_optimized": return .green
        case "local_friendly": return MacColors.amberAccent
        default: return MacColors.textSecondary
        }
    }

    private func refineCurrentPrompt() async {
        isRefining = true
        refineError = nil
        refineVariations = []

        do {
            let response = try await APIClient.shared.refinePrompt(
                prompt,
                inferenceRoute: inferenceRoute
            )
            refineVariations = response.variations
            withAnimation(.easeInOut(duration: 0.2)) {
                showRefinePanel = true
            }
        } catch {
            refineError = "Refinement failed — is the local model running?"
            #if DEBUG
            print("[Refine] Error: \(error)")
            #endif
        }

        isRefining = false
    }

    // MARK: - Load / Save

    private func loadFromNode() {
        label = node.label
        saveError = nil
        didSave = false

        switch node.nodeTypeEnum {
        case .runPrompt:
            prompt = stringConfig("prompt")
            model = stringConfig("model")
            if case .bool(let mw) = node.config["memory_write"] { memoryWrite = mw } else { memoryWrite = false }
            // Load inference_route; fall back to legacy force_local mapping
            if case .string(let ir) = node.config["inference_route"] {
                inferenceRoute = ir
            } else if case .bool(let fl) = node.config["force_local"], fl {
                inferenceRoute = "local"
            } else {
                inferenceRoute = "smart_cloud"
            }
            // Reverse-map allowed_tools back to category IDs
            if case .array(let tools) = node.config["allowed_tools"] {
                let toolNames = tools.compactMap { if case .string(let s) = $0 { return s } else { return nil } }
                selectedResources = Set(
                    viewModel.toolCategories
                        .filter { cat in cat.tools.contains { toolNames.contains($0.name) } }
                        .map(\.id)
                )
            } else {
                selectedResources = []
            }
        case .callTool:
            toolName = stringConfig("tool_name")
            toolArguments = jsonConfig("arguments")
        case .notify:
            notifyMessage = stringConfig("message")
            let ch = stringConfig("channel")
            notifyChannel = ch.isEmpty ? "macos" : ch
        case .log:
            logMessage = stringConfig("message")
            logLevel = stringConfig("level").isEmpty ? "info" : stringConfig("level")
        case .ifElse:
            // config may have nested condition dict
            if case .dict(let cond) = node.config["condition"] {
                conditionField = cond["field"].flatMap { if case .string(let s) = $0 { return s } else { return nil } } ?? ""
                conditionOperator = cond["operator"].flatMap { if case .string(let s) = $0 { return s } else { return nil } } ?? "eq"
                conditionValue = cond["value"].flatMap { if case .string(let s) = $0 { return s } else { return nil } } ?? ""
            } else {
                conditionField = ""
                conditionOperator = "eq"
                conditionValue = ""
            }
        case .schedule, .manual:
            break
        case .delay:
            delaySeconds = stringConfig("delay_seconds")
            // Parse delay_seconds and pick the most readable unit
            let rawSeconds: Double
            if case .double(let d) = node.config["delay_seconds"] { rawSeconds = d }
            else if case .int(let i) = node.config["delay_seconds"] { rawSeconds = Double(i) }
            else { rawSeconds = 0 }
            if rawSeconds >= 86400, rawSeconds.truncatingRemainder(dividingBy: 86400) == 0 {
                delayUnit = .days
                delayValue = rawSeconds / 86400
            } else if rawSeconds >= 3600, rawSeconds.truncatingRemainder(dividingBy: 3600) == 0 {
                delayUnit = .hours
                delayValue = rawSeconds / 3600
            } else if rawSeconds >= 60 {
                delayUnit = .minutes
                delayValue = rawSeconds / 60
            } else {
                delayUnit = .minutes
                delayValue = max(1, rawSeconds / 60)
            }
        case .switchNode:
            conditionField = stringConfig("field")
        }
    }

    private func stringConfig(_ key: String) -> String {
        guard let val = node.config[key] else { return "" }
        if case .string(let s) = val { return s }
        return ""
    }

    private func jsonConfig(_ key: String) -> String {
        guard let val = node.config[key] else { return "{}" }
        // Try to encode back to JSON string for display
        switch val {
        case .dict:
            if let data = try? JSONEncoder().encode(val),
               let str = String(data: data, encoding: .utf8) {
                return str
            }
            return "{}"
        case .string(let s):
            return s
        default:
            return "{}"
        }
    }

    private func saveChanges() async {
        isSaving = true
        saveError = nil
        didSave = false

        var config: [String: AnyCodableValue] = [:]

        switch node.nodeTypeEnum {
        case .runPrompt:
            config["prompt"] = .string(prompt)
            if !model.isEmpty { config["model"] = .string(model) }
            // Expand selected category IDs to individual tool names
            let allowedTools = viewModel.toolCategories
                .filter { selectedResources.contains($0.id) }
                .flatMap(\.tools)
                .map { AnyCodableValue.string($0.name) }
            if !allowedTools.isEmpty {
                config["allowed_tools"] = .array(allowedTools)
            }
            config["memory_write"] = .bool(memoryWrite)
            config["inference_route"] = .string(inferenceRoute)
            config["force_local"] = .bool(inferenceRoute == "local")
        case .callTool:
            config["tool_name"] = .string(toolName)
            // Parse arguments back to dict if valid JSON, else store as string
            if let data = toolArguments.data(using: .utf8),
               let decoded = try? JSONDecoder().decode([String: AnyCodableValue].self, from: data) {
                config["arguments"] = .dict(decoded)
            } else if !toolArguments.isEmpty {
                config["arguments"] = .string(toolArguments)
            }
        case .notify:
            config["message"] = .string(notifyMessage)
            if !notifyChannel.isEmpty { config["channel"] = .string(notifyChannel) }
        case .log:
            config["message"] = .string(logMessage)
            config["level"] = .string(logLevel)
        case .ifElse:
            config["condition"] = .dict([
                "field": .string(conditionField),
                "operator": .string(conditionOperator),
                "value": .string(conditionValue)
            ])
        case .schedule, .manual:
            break
        case .delay:
            let totalSeconds = max(60, min(delayValue * delayUnit.multiplier, 180 * 86400))
            config["delay_seconds"] = .double(totalSeconds)
        case .switchNode:
            if !conditionField.isEmpty { config["field"] = .string(conditionField) }
        }

        let request = NodeUpdateRequest(label: label.isEmpty ? nil : label, config: config.isEmpty ? nil : config)

        do {
            try await APIClient.shared.patchNode(
                node.workflowId,
                nodeId: node.id,
                request: request
            )
            didSave = true
            // Close inspector and refresh detail after a brief delay
            try? await Task.sleep(nanoseconds: 500_000_000)
            viewModel.selectedNodeId = nil
            if let wfId = viewModel.selectedWorkflowId {
                await viewModel.loadWorkflowDetail(wfId)
            }
        } catch {
            saveError = "Save failed: \(error.localizedDescription)"
            #if DEBUG
            print("[NodeInspector] Failed to save node \(node.id): \(error)")
            #endif
        }

        isSaving = false
    }
}
