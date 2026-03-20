import SwiftUI
import HestiaShared

// MARK: - Settings Section Identifier

enum SettingsSection: String, CaseIterable, Identifiable {
    case profile
    case agents
    case resources
    case fieldGuide

    var id: String { rawValue }

    var title: String {
        switch self {
        case .profile: return "Profile"
        case .agents: return "Agents"
        case .resources: return "Resources"
        case .fieldGuide: return "Field Guide"
        }
    }

    var icon: String {
        switch self {
        case .profile: return "person.circle"
        case .agents: return "person.3.fill"
        case .resources: return "wrench.and.screwdriver"
        case .fieldGuide: return "map"
        }
    }
}

// MARK: - Settings View

struct MacSettingsView: View {
    @State private var expandedSection: SettingsSection? = {
        if let saved = UserDefaults.standard.string(forKey: "hestia.settings.expandedSection"),
           let section = SettingsSection(rawValue: saved) {
            return section
        }
        return .profile
    }()

    @State private var showFeedbackSheet = false

    var body: some View {
        ScrollView {
            VStack(spacing: MacSpacing.md) {
                // Page header
                HStack {
                    Text("Settings")
                        .font(MacTypography.pageTitle)
                        .foregroundStyle(MacColors.textPrimary)
                    Spacer()
                    feedbackButton
                }
                .padding(.bottom, MacSpacing.sm)

                // Accordion sections
                ForEach(SettingsSection.allCases) { section in
                    AccordionSection(
                        section: section,
                        isExpanded: expandedSection == section,
                        onToggle: {
                            withAnimation(MacAnimation.normalSpring) {
                                if expandedSection == section {
                                    expandedSection = nil
                                } else {
                                    expandedSection = section
                                }
                            }
                        }
                    ) {
                        sectionContent(for: section)
                    }
                }
            }
            .padding(MacSpacing.xxl)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(MacColors.windowBackground)
        .onChange(of: expandedSection) { _, newValue in
            UserDefaults.standard.set(newValue?.rawValue, forKey: "hestia.settings.expandedSection")
        }
    }

    // MARK: - Section Content

    @ViewBuilder
    private func sectionContent(for section: SettingsSection) -> some View {
        switch section {
        case .profile:
            MacProfileView()
        case .agents:
            MacAgentsView()
        case .resources:
            MacResourcesView()
        case .fieldGuide:
            MacWikiView()
        }
    }

    // MARK: - Feedback Button

    private var feedbackButton: some View {
        Button {
            showFeedbackSheet = true
        } label: {
            HStack(spacing: MacSpacing.xs) {
                Image(systemName: "exclamationmark.bubble")
                    .font(.system(size: 13))
                Text("Feedback")
                    .font(MacTypography.label)
            }
            .foregroundStyle(MacColors.textSecondary)
            .padding(.horizontal, MacSpacing.md)
            .padding(.vertical, MacSpacing.xs)
            .background(MacColors.searchInputBackground)
            .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        }
        .buttonStyle(.hestia)
        .hoverCursor(.pointingHand)
        .sheet(isPresented: $showFeedbackSheet) {
            FeedbackSheet()
        }
    }
}

// MARK: - Feedback Sheet

struct FeedbackSheet: View {
    @Environment(\.dismiss) private var dismiss

    enum FeedbackType: String, CaseIterable {
        case bug = "Bug Report"
        case feature = "Feature Request"
        case feedback = "General Feedback"

        var ghLabel: String {
            switch self {
            case .bug: return "bug"
            case .feature: return "enhancement"
            case .feedback: return "feedback"
            }
        }

        var icon: String {
            switch self {
            case .bug: return "ladybug"
            case .feature: return "lightbulb"
            case .feedback: return "text.bubble"
            }
        }
    }

    @State private var feedbackType: FeedbackType = .bug
    @State private var title = ""
    @State private var details = ""

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.xl) {
            // Header
            HStack {
                Image(systemName: "exclamationmark.bubble")
                    .font(.system(size: 16))
                    .foregroundStyle(MacColors.amberAccent)
                Text("Report Issue / Provide Feedback")
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()
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

            // Type picker
            HStack(spacing: MacSpacing.md) {
                ForEach(FeedbackType.allCases, id: \.self) { type in
                    Button {
                        feedbackType = type
                    } label: {
                        HStack(spacing: MacSpacing.xs) {
                            Image(systemName: type.icon)
                                .font(.system(size: 12))
                            Text(type.rawValue)
                                .font(MacTypography.label)
                        }
                        .foregroundStyle(feedbackType == type ? MacColors.amberAccent : MacColors.textSecondary)
                        .padding(.horizontal, MacSpacing.md)
                        .padding(.vertical, MacSpacing.sm)
                        .background(feedbackType == type ? MacColors.amberAccent.opacity(0.15) : MacColors.searchInputBackground)
                        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                    }
                    .buttonStyle(.plain)
                }
            }

            // Title
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                Text("Title")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
                TextField("Brief description", text: $title)
                    .textFieldStyle(.roundedBorder)
            }

            // Description
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                Text("Details")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textSecondary)
                TextEditor(text: $details)
                    .font(MacTypography.body)
                    .frame(minHeight: 100, maxHeight: 160)
                    .padding(MacSpacing.sm)
                    .background(MacColors.searchInputBackground)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
            }

            Spacer()

            // Actions
            HStack {
                Text("Opens GitHub in your browser")
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textFaint)
                Spacer()
                Button("Cancel") { dismiss() }
                    .buttonStyle(.hestia)
                Button {
                    openGitHubIssue()
                    dismiss()
                } label: {
                    HStack(spacing: MacSpacing.sm) {
                        Image(systemName: "arrow.up.right.square")
                            .font(.system(size: 12))
                        Text("Create Issue")
                    }
                    .foregroundStyle(MacColors.buttonTextDark)
                    .padding(.horizontal, MacSpacing.lg)
                    .padding(.vertical, MacSpacing.sm)
                    .background(canSubmit ? MacColors.amberAccent : MacColors.amberAccent.opacity(0.4))
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
                }
                .buttonStyle(.hestia)
                .disabled(!canSubmit)
            }
        }
        .padding(MacSpacing.xxl)
        .frame(width: 520, height: 480)
        .background(MacColors.panelBackground)
    }

    private var canSubmit: Bool {
        !title.trimmingCharacters(in: .whitespaces).isEmpty
    }

    private func openGitHubIssue() {
        let encodedTitle = title.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        let bodyText = details.isEmpty ? "" : details
        let encodedBody = bodyText.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? ""
        let label = feedbackType.ghLabel
        let urlString = "https://github.com/aroman117-1618/hestia/issues/new?title=\(encodedTitle)&body=\(encodedBody)&labels=\(label)"

        if let url = URL(string: urlString) {
            NSWorkspace.shared.open(url)
        }
    }
}

// MARK: - Accordion Section Component

struct AccordionSection<Content: View>: View {
    let section: SettingsSection
    let isExpanded: Bool
    let onToggle: () -> Void
    @ViewBuilder let content: () -> Content

    var body: some View {
        VStack(spacing: 0) {
            // Header bar
            Button(action: onToggle) {
                HStack(spacing: MacSpacing.md) {
                    Image(systemName: section.icon)
                        .font(.system(size: 16))
                        .foregroundStyle(isExpanded ? MacColors.amberAccent : MacColors.textSecondary)
                        .frame(width: 24)

                    Text(section.title)
                        .font(MacTypography.sectionTitle)
                        .foregroundStyle(isExpanded ? MacColors.textPrimary : MacColors.textSecondary)

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(MacColors.textSecondary)
                        .rotationEffect(.degrees(isExpanded ? 90 : 0))
                        .animation(MacAnimation.fastSpring, value: isExpanded)
                }
                .padding(.horizontal, MacSpacing.lg)
                .padding(.vertical, MacSpacing.md)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("\(section.title) section")
            .accessibilityHint(isExpanded ? "Collapse" : "Expand")
            .accessibilityAddTraits(.isButton)

            // Expandable content
            if isExpanded {
                content()
                    .padding(.horizontal, MacSpacing.lg)
                    .padding(.bottom, MacSpacing.lg)
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .fill(isExpanded ? MacColors.panelBackground : Color.clear)
                .overlay(
                    RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                        .strokeBorder(isExpanded ? MacColors.cardBorder : Color.clear, lineWidth: 1)
                )
        )
    }
}
