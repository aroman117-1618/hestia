import Testing
@testable import HestiaShared

@Test func packageImportWorks() async throws {
    // Verify the package compiles and basic types are accessible
    let mode = HestiaMode.tia
    #expect(mode.rawValue == "tia")
}
