// swift-tools-version:5.7
import PackageDescription

let package = Package(
    name: "hestia-notes-cli",
    platforms: [
        .macOS(.v12)
    ],
    targets: [
        .executableTarget(
            name: "hestia-notes-cli",
            dependencies: [],
            path: "Sources/hestia-notes-cli"
        )
    ]
)
