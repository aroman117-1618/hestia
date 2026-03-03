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
        case .agents: return "theatermasks"
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

    var body: some View {
        ScrollView {
            VStack(spacing: MacSpacing.md) {
                // Page header
                HStack {
                    Text("Settings")
                        .font(MacTypography.pageTitle)
                        .foregroundStyle(MacColors.textPrimary)
                    Spacer()
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
            .frame(maxWidth: MacSize.settingsMaxWidth)
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
