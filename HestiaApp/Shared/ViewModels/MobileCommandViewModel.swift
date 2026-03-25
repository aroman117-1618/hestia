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

        // Load sections individually — errors are per-section, not blocking
        do { summary = try await client.getMobileTradingSummary() }
        catch { failedSections.insert("trading") }

        do { let r = try await client.getMobileTradingBots(); bots = r.bots }
        catch { failedSections.insert("bots") }

        do { riskStatus = try await client.getMobileRiskStatus() }
        catch { failedSections.insert("risk") }

        do { let r = try await client.getMobileWorkflows(); workflows = r.workflows }
        catch { failedSections.insert("workflows") }

        do { let r = try await client.getMobileNewsfeed(); newsfeedItems = r.items }
        catch { failedSections.insert("newsfeed") }
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
