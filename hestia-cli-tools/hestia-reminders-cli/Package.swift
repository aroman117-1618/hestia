// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "hestia-reminders-cli",
    platforms: [
        .macOS(.v12)
    ],
    targets: [
        .executableTarget(
            name: "hestia-reminders-cli",
            dependencies: [],
            path: "Sources/hestia-reminders-cli"
        )
    ]
)
