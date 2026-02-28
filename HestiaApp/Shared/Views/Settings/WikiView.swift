import SwiftUI
import HestiaShared

/// Architecture Field Guide — explains how Hestia works internally
struct WikiView: View {
    @EnvironmentObject var appState: AppState
    @State private var selectedTopic: WikiTopic = .overview
    
    var body: some View {
        ZStack {
            GradientBackground(mode: appState.currentMode)
            
            ScrollView {
                VStack(spacing: Spacing.xl) {
                    // Topic selector
                    topicSelector
                        .padding(.top, Spacing.md)
                    
                    // Content based on selected topic
                    topicContent
                        .padding(.horizontal, Spacing.lg)
                    
                    Spacer()
                        .frame(height: Spacing.xxl)
                }
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Architecture Field Guide")
        .navigationBarTitleDisplayMode(.large)
    }
    
    // MARK: - Topic Selector
    
    private var topicSelector: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: Spacing.sm) {
                ForEach(WikiTopic.allCases) { topic in
                    Button {
                        withAnimation(.easeInOut(duration: 0.2)) {
                            selectedTopic = topic
                        }
                    } label: {
                        HStack(spacing: Spacing.xs) {
                            Image(systemName: topic.iconName)
                                .font(.caption)
                            
                            Text(topic.displayName)
                                .font(.subheadline.weight(.semibold))
                        }
                        .foregroundColor(selectedTopic == topic ? .white : .white.opacity(0.5))
                        .padding(.vertical, Spacing.sm)
                        .padding(.horizontal, Spacing.md)
                        .background(
                            selectedTopic == topic ?
                            Color.white.opacity(0.2) :
                            Color.clear
                        )
                        .cornerRadius(CornerRadius.small)
                    }
                }
            }
            .padding(.horizontal, Spacing.lg)
        }
    }
    
    // MARK: - Topic Content
    
    @ViewBuilder
    private var topicContent: some View {
        switch selectedTopic {
        case .overview:
            overviewContent
        case .architecture:
            architectureContent
        case .modes:
            modesContent
        case .agents:
            agentsContent
        case .memory:
            memoryContent
        case .tools:
            toolsContent
        case .resources:
            resourcesContent
        }
    }
    
    // MARK: - Content Sections
    
    private var overviewContent: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            sectionHeader("What is Hestia?")
            
            sectionText("""
Hestia is an intelligent personal assistant designed to help you manage your life across multiple domains. The name comes from the Greek goddess of home and hearth, reflecting its role as the center of your digital life.
""")
            
            sectionHeader("Core Principles")
            
            bulletPoint("Multi-Agent System", "Three specialized AI agents work together to handle different aspects of your life")
            bulletPoint("Context-Aware", "Maintains memory across conversations to provide personalized assistance")
            bulletPoint("Privacy-First", "Your data stays secure with local processing and encrypted cloud storage")
            bulletPoint("Mode-Based", "Adapts behavior and available tools based on your current mode (Work, Personal, Focus)")
        }
    }
    
    private var architectureContent: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            sectionHeader("System Architecture")
            
            sectionText("""
Hestia uses a client-server architecture with the following components:
""")
            
            bulletPoint("iOS Client", "Native SwiftUI interface with offline capabilities")
            bulletPoint("Backend Server", "Python-based server handling inference, memory, and tool execution")
            bulletPoint("Agent Orchestration", "Manages routing between specialized agents")
            bulletPoint("Memory System", "Vector-based storage for long-term context retention")
            bulletPoint("Tool Framework", "Extensible system for connecting to external services")
            
            sectionHeader("Data Flow")
            
            sectionText("""
1. User input captured on device
2. Sent to backend via secure API
3. Agent orchestrator selects appropriate agent
4. Agent processes with relevant memory context
5. Tools executed as needed
6. Response returned and memory updated
7. UI updates with results
""")
        }
    }
    
    private var modesContent: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            sectionHeader("Operating Modes")
            
            sectionText("""
Hestia adapts its behavior based on three primary modes:
""")
            
            modeCard("Work", "briefcase.fill", """
Professional context with access to:
• Calendar and scheduling tools
• Email management
• Project tracking
• Professional communication style
""", color: .blue)
            
            modeCard("Personal", "house.fill", """
Personal life management with:
• Shopping and orders
• Personal calendar
• Home automation
• Casual communication style
""", color: .orange)
            
            modeCard("Focus", "moon.stars.fill", """
Minimal distractions for:
• Deep work sessions
• Limited notifications
• Essential tools only
• Concise responses
""", color: .purple)
        }
    }
    
    private var agentsContent: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            sectionHeader("Agent System")
            
            sectionText("""
Hestia uses three specialized agents that can be customized for different roles:
""")
            
            bulletPoint("Agent 1 (Primary)", "Default general-purpose assistant, cannot be deleted")
            bulletPoint("Agent 2", "Customizable for specific domains or styles")
            bulletPoint("Agent 3", "Additional specialization as needed")
            
            sectionHeader("Agent Customization")
            
            sectionText("""
Each agent can be customized with:
• Name and visual identity
• System instructions and personality
• Specialized knowledge domains
• Tool access permissions
""")
            
            sectionHeader("Agent Selection")
            
            sectionText("""
The agent orchestrator automatically selects the most appropriate agent based on:
• Current mode (Work/Personal/Focus)
• Conversation context
• Required tools
• User preferences
""")
        }
    }
    
    private var memoryContent: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            sectionHeader("Memory System")
            
            sectionText("""
Hestia maintains context across conversations using a sophisticated memory system:
""")
            
            bulletPoint("Short-term Memory", "Recent conversation history for context")
            bulletPoint("Long-term Memory", "Vector embeddings of important information")
            bulletPoint("Semantic Search", "Retrieves relevant memories based on meaning")
            bulletPoint("Memory Decay", "Less relevant information naturally fades")
            
            sectionHeader("Memory Types")
            
            sectionText("""
Different types of memories are stored and retrieved:
• Facts and preferences
• Past decisions and reasoning
• Project context and status
• Relationship information
• Calendar events and deadlines
""")
            
            sectionHeader("Privacy")
            
            sectionText("""
All memories are:
• Encrypted at rest
• Scoped to your user account
• Never shared with other users
• Deletable at any time
""")
        }
    }
    
    private var toolsContent: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            sectionHeader("Tool System")
            
            sectionText("""
Hestia can execute actions in the real world through its tool framework:
""")
            
            bulletPoint("Calendar Tools", "View and create events")
            bulletPoint("Email Tools", "Read, search, and draft emails")
            bulletPoint("Web Search", "Find current information")
            bulletPoint("File Operations", "Read and write documents")
            bulletPoint("API Integrations", "Connect to external services")
            
            sectionHeader("Tool Execution")
            
            sectionText("""
Tools are executed securely:
1. Agent requests tool usage
2. System validates permissions
3. User confirms if needed
4. Tool executes on backend
5. Results returned to agent
6. Agent incorporates into response
""")
            
            sectionHeader("Extensibility")
            
            sectionText("""
The tool framework is designed for easy extension:
• Standard interface for new tools
• Automatic schema generation
• Built-in error handling
• Logging and monitoring
""")
        }
    }
    
    private var resourcesContent: some View {
        VStack(alignment: .leading, spacing: Spacing.lg) {
            sectionHeader("Resource Management")
            
            sectionText("""
Hestia connects to various external resources:
""")
            
            bulletPoint("LLM Providers", "OpenAI, Anthropic, local models")
            bulletPoint("Cloud Integrations", "Calendar, email, storage")
            bulletPoint("MCP Servers", "Model Context Protocol for extended capabilities")
            
            sectionHeader("Configuration")
            
            sectionText("""
Resources can be configured in Settings > Resources:
• Add API keys for LLM providers
• Connect cloud service accounts
• Configure MCP server endpoints
• Manage permissions and scopes
""")
            
            sectionHeader("Offline Mode")
            
            sectionText("""
When offline, Hestia gracefully degrades:
• Uses cached data where possible
• Queues actions for later sync
• Provides clear offline indicators
• Syncs automatically when reconnected
""")
        }
    }
    
    // MARK: - Helper Components
    
    private func sectionHeader(_ text: String) -> some View {
        Text(text)
            .font(.title3.weight(.bold))
            .foregroundColor(.white)
    }
    
    private func sectionText(_ text: String) -> some View {
        Text(text)
            .font(.body)
            .foregroundColor(.white.opacity(0.8))
            .lineSpacing(4)
    }
    
    private func bulletPoint(_ title: String, _ description: String) -> some View {
        HStack(alignment: .top, spacing: Spacing.md) {
            Image(systemName: "circle.fill")
                .font(.system(size: 6))
                .foregroundColor(.white.opacity(0.5))
                .padding(.top, 6)
            
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text(title)
                    .font(.body.weight(.semibold))
                    .foregroundColor(.white)
                
                Text(description)
                    .font(.body)
                    .foregroundColor(.white.opacity(0.7))
            }
        }
    }
    
    private func modeCard(_ title: String, _ icon: String, _ description: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            HStack {
                Image(systemName: icon)
                    .font(.title2)
                    .foregroundColor(color)
                
                Text(title)
                    .font(.headline)
                    .foregroundColor(.white)
                
                Spacer()
            }
            
            Text(description)
                .font(.body)
                .foregroundColor(.white.opacity(0.7))
                .lineSpacing(4)
        }
        .padding(Spacing.md)
        .background(Color.white.opacity(0.1))
        .cornerRadius(CornerRadius.medium)
    }
}

// MARK: - Wiki Topic

enum WikiTopic: String, CaseIterable, Identifiable {
    case overview = "Overview"
    case architecture = "Architecture"
    case modes = "Modes"
    case agents = "Agents"
    case memory = "Memory"
    case tools = "Tools"
    case resources = "Resources"
    
    var id: String { rawValue }
    
    var displayName: String { rawValue }
    
    var iconName: String {
        switch self {
        case .overview:
            return "book.fill"
        case .architecture:
            return "building.2.fill"
        case .modes:
            return "slider.horizontal.3"
        case .agents:
            return "person.3.fill"
        case .memory:
            return "brain.head.profile"
        case .tools:
            return "wrench.and.screwdriver.fill"
        case .resources:
            return "server.rack"
        }
    }
}

// MARK: - Preview

struct WikiView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            WikiView()
                .environmentObject(AppState())
        }
    }
}
