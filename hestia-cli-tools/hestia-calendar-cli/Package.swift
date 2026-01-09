// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "hestia-calendar-cli",
    platforms: [
        .macOS(.v12)
    ],
    targets: [
        .executableTarget(
            name: "hestia-calendar-cli",
            dependencies: [],
            path: "Sources/hestia-calendar-cli"
        )
    ]
)
