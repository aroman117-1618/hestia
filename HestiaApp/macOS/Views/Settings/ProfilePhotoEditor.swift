import SwiftUI
import AppKit

/// Photo picker and editor for profile/agent photos.
/// Opens NSOpenPanel, shows circular preview, compresses to JPEG, and calls upload/delete callbacks.
struct ProfilePhotoEditor: View {
    let currentPhotoData: Data?
    let initialLetter: String
    let size: CGFloat
    var onUpload: ((Data) -> Void)?
    var onDelete: (() -> Void)?

    @State private var isHovering: Bool = false
    @State private var showingDeleteConfirm: Bool = false

    var body: some View {
        ZStack {
            // Photo or initials
            if let data = currentPhotoData, let nsImage = NSImage(data: data) {
                Image(nsImage: nsImage)
                    .resizable()
                    .scaledToFill()
                    .frame(width: size, height: size)
                    .clipShape(Circle())
            } else {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [MacColors.amberDark.opacity(0.6), MacColors.amberAccent.opacity(0.3)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: size, height: size)
                    .overlay(
                        Text(initialLetter)
                            .font(.system(size: size * 0.4, weight: .medium))
                            .foregroundStyle(MacColors.textPrimary)
                    )
            }

            // Border
            Circle()
                .strokeBorder(
                    isHovering ? MacColors.amberAccent : MacColors.amberAccent.opacity(0.3),
                    lineWidth: isHovering ? 2 : 1
                )
                .frame(width: size, height: size)

            // Hover overlay with camera icon
            if isHovering {
                Circle()
                    .fill(Color.black.opacity(0.5))
                    .frame(width: size, height: size)
                    .overlay(
                        Image(systemName: "camera.fill")
                            .font(.system(size: size * 0.2))
                            .foregroundStyle(.white)
                    )
                    .transition(.opacity)
            }
        }
        .animation(MacAnimation.fastSpring, value: isHovering)
        .onHover { hovering in
            isHovering = hovering
        }
        .onTapGesture {
            openPhotoPicker()
        }
        .contextMenu {
            Button("Choose Photo...") {
                openPhotoPicker()
            }
            if currentPhotoData != nil {
                Button("Remove Photo", role: .destructive) {
                    showingDeleteConfirm = true
                }
            }
        }
        .alert("Remove Photo", isPresented: $showingDeleteConfirm) {
            Button("Remove", role: .destructive) {
                onDelete?()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("Are you sure you want to remove your profile photo?")
        }
        .accessibilityLabel(currentPhotoData != nil ? "Profile photo. Click to change." : "No photo. Click to add.")
        .accessibilityHint("Opens file picker to select a photo")
    }

    // MARK: - Photo Picker

    private func openPhotoPicker() {
        let panel = NSOpenPanel()
        panel.title = "Choose Profile Photo"
        panel.allowedContentTypes = [.jpeg, .png, .heic]
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false

        guard panel.runModal() == .OK, let url = panel.url else { return }

        guard let nsImage = NSImage(contentsOf: url) else { return }

        // Compress to JPEG, max 1024x1024, quality 0.8
        guard let compressed = compressImage(nsImage, maxSize: 1024, quality: 0.8) else { return }

        onUpload?(compressed)
    }

    // MARK: - Image Compression

    private func compressImage(_ image: NSImage, maxSize: CGFloat, quality: CGFloat) -> Data? {
        let originalSize = image.size

        // Calculate scale to fit within maxSize x maxSize
        let scale: CGFloat
        if originalSize.width > maxSize || originalSize.height > maxSize {
            scale = min(maxSize / originalSize.width, maxSize / originalSize.height)
        } else {
            scale = 1.0
        }

        let targetSize = NSSize(
            width: originalSize.width * scale,
            height: originalSize.height * scale
        )

        // Draw resized image
        let resized = NSImage(size: targetSize)
        resized.lockFocus()
        NSGraphicsContext.current?.imageInterpolation = .high
        image.draw(
            in: NSRect(origin: .zero, size: targetSize),
            from: NSRect(origin: .zero, size: originalSize),
            operation: .copy,
            fraction: 1.0
        )
        resized.unlockFocus()

        // Convert to JPEG data
        guard let tiffData = resized.tiffRepresentation,
              let bitmap = NSBitmapImageRep(data: tiffData) else { return nil }

        return bitmap.representation(using: .jpeg, properties: [.compressionFactor: quality])
    }
}
