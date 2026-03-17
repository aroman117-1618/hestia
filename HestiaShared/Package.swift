// swift-tools-version: 6.2

import PackageDescription

let package = Package(
    name: "HestiaShared",
    platforms: [
        .iOS(.v26),
        .macOS(.v15)
    ],
    products: [
        .library(
            name: "HestiaShared",
            targets: ["HestiaShared"]
        )
    ],
    targets: [
        .target(
            name: "HestiaShared",
            path: "Sources/HestiaShared"
        ),
        .testTarget(
            name: "HestiaSharedTests",
            dependencies: ["HestiaShared"],
            path: "Tests/HestiaSharedTests"
        )
    ]
)
