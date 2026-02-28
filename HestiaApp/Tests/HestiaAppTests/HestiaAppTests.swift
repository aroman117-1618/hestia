import XCTest
import HestiaShared
@testable import HestiaApp

@MainActor
final class HestiaAppTests: XCTestCase {

    // MARK: - Model Tests

    func testHestiaModeDisplayNames() {
        XCTAssertEqual(HestiaMode.tia.displayName, "Tia")
        XCTAssertEqual(HestiaMode.mira.displayName, "Mira")
        XCTAssertEqual(HestiaMode.olly.displayName, "Olly")
    }

    func testHestiaModeFullNames() {
        XCTAssertEqual(HestiaMode.tia.fullName, "Hestia")
        XCTAssertEqual(HestiaMode.mira.fullName, "Artemis")
        XCTAssertEqual(HestiaMode.olly.fullName, "Apollo")
    }

    func testHestiaModeGradientColors() {
        XCTAssertEqual(HestiaMode.tia.gradientColors.count, 3)
        XCTAssertEqual(HestiaMode.mira.gradientColors.count, 3)
        XCTAssertEqual(HestiaMode.olly.gradientColors.count, 3)
    }

    func testConversationMessageUserMessage() {
        let message = ConversationMessage.userMessage("Hello")
        XCTAssertEqual(message.role, .user)
        XCTAssertEqual(message.content, "Hello")
        XCTAssertNil(message.mode)
    }

    func testConversationMessageAssistantMessage() {
        let message = ConversationMessage.assistantMessage("Hi there", mode: .tia)
        XCTAssertEqual(message.role, .assistant)
        XCTAssertEqual(message.content, "Hi there")
        XCTAssertEqual(message.mode, .tia)
    }

    // MARK: - Error Tests

    func testHestiaErrorUserMessages() {
        XCTAssertFalse(HestiaError.networkUnavailable.userMessage.isEmpty)
        XCTAssertFalse(HestiaError.requestTimeout.userMessage.isEmpty)
        XCTAssertFalse(HestiaError.unauthorized.userMessage.isEmpty)
    }

    func testHestiaErrorRetryable() {
        XCTAssertTrue(HestiaError.requestTimeout.isRetryable)
        XCTAssertTrue(HestiaError.modelUnavailable.isRetryable)
        XCTAssertFalse(HestiaError.unauthorized.isRetryable)
        XCTAssertFalse(HestiaError.emptyInput.isRetryable)
    }

    // MARK: - Mock Client Tests

    func testMockClientSendMessage() async throws {
        let client = MockHestiaClient()
        client.networkDelayRange = 0.01...0.02  // Fast for testing

        let response = try await client.sendMessage("Hello", sessionId: nil)

        XCTAssertFalse(response.content.isEmpty)
        XCTAssertEqual(response.responseType, .text)
        XCTAssertNotNil(response.sessionId)
    }

    func testMockClientModeSwitch() async throws {
        let client = MockHestiaClient()

        let initialMode = try await client.getCurrentMode()
        XCTAssertEqual(initialMode, .tia)

        try await client.switchMode(to: .mira)
        let newMode = try await client.getCurrentMode()
        XCTAssertEqual(newMode, .mira)
    }

    func testMockClientHealthCheck() async throws {
        let client = MockHestiaClient()

        let health = try await client.getSystemHealth()
        XCTAssertEqual(health.status, .healthy)
    }
}
