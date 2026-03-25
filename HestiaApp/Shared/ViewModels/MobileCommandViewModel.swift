import SwiftUI
import HestiaShared
import Combine

/// ViewModel for the Mobile Command dashboard.
/// Loads trading, workflow, and newsfeed data with independent error handling per section.
@MainActor
class MobileCommandViewModel: ObservableObject {
    // MARK: - Published State

    @Published var summary: MobileTradingSummary?
    @Published var bots: [MobileTradingBot] = []
    @Published var riskStatus: MobileRiskStatus?
    @Published var workflows: [MobileWorkflow] = []
    @Published var newsfeedItems: [MobileNewsfeedItem] = []
    @Published var isLoading = false
    @Published var failedSections: Set<String> = []
    @Published var killSwitchConfirmation = false

    // MARK: - Private

    private var client: APIClient?
    private var refreshTimer: Timer?

    func configure(client: APIClient) {
        self.client = client
    }

    // MARK: - Loading

    /// Load all sections in parallel. Failures are per-section, not blocking.
    func loadAll() async {
        guard let client = client else { return }
        isLoading = true
        failedSections.removeAll()

        // Fire all requests in parallel
        async let s: MobileTradingSummary? = try? client.getMobileTradingSummary()
        async let b: MobileTradingBotList? = try? client.getMobileTradingBots()
        async let r: MobileRiskStatus? = try? client.getMobileRiskStatus()
        async let w: MobileWorkflowList? = try? client.getMobileWorkflows()
        async let n: MobileNewsfeedTimeline? = try? client.getMobileNewsfeed()

        let (sVal, bVal, rVal, wVal, nVal) = await (s, b, r, w, n)

        if let v = sVal { summary = v } else { failedSections.insert("trading") }
        if let v = bVal { bots = v.bots } else { failedSections.insert("bots") }
        if let v = rVal { riskStatus = v } else { failedSections.insert("risk") }
        if let v = wVal { workflows = v.workflows } else { failedSections.insert("workflows") }
        if let v = nVal { newsfeedItems = v.items } else { failedSections.insert("newsfeed") }
        isLoading = false
    }

    /// Toggle kill switch with confirmation.
    func toggleKillSwitch() async {
        guard let client = client else { return }
        do {
            if riskStatus?.killSwitch.active == true {
                let response = try await client.deactivateMobileKillSwitch()
                riskStatus = MobileRiskStatus(
                    killSwitch: MobileKillSwitchState(active: response.active, reason: response.reason, activatedAt: nil),
                    anyBreakerActive: riskStatus?.anyBreakerActive ?? false
                )
            } else {
                let response = try await client.activateMobileKillSwitch()
                riskStatus = MobileRiskStatus(
                    killSwitch: MobileKillSwitchState(active: response.active, reason: response.reason, activatedAt: nil),
                    anyBreakerActive: riskStatus?.anyBreakerActive ?? false
                )
            }
            // Reload summary to reflect new state
            if let newSummary = try? await client.getMobileTradingSummary() {
                summary = newSummary
            }
        } catch {
            #if DEBUG
            print("[MobileCommand] Kill switch toggle failed: \(error)")
            #endif
        }
    }
}
