// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "hestia-keychain-cli",
    platforms: [
        .macOS(.v12)
    ],
    targets: [
        .executableTarget(
            name: "hestia-keychain-cli",
            dependencies: [],
            path: "Sources/hestia-keychain-cli"
        )
    ]
)
