import SwiftUI
import PhotosUI

/// View for customizing agent personas
struct AgentCustomizationView: View {
    @State private var selectedMode: HestiaMode = .tia
    @State private var agentName: String = ""
    @State private var agentNickname: String = ""
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var selectedPhotoData: Data?
    @State private var customColors: [Color] = []
    @State private var hasChanges = false
    @State private var showingSaveConfirmation = false

    var body: some View {
        ZStack {
            // Background with selected mode's gradient
            GradientBackground(mode: selectedMode)

            ScrollView {
                VStack(spacing: Spacing.xl) {
                    // Mode selector
                    modeSelector
                        .padding(.top, Spacing.md)

                    // Avatar section
                    avatarSection

                    // Name fields
                    nameSection

                    // Color customization
                    colorSection

                    // Personality traits (read-only)
                    traitsSection

                    // Save button
                    if hasChanges {
                        saveButton
                    }

                    Spacer()
                        .frame(height: Spacing.xxl)
                }
                .padding(.horizontal, Spacing.lg)
            }
        }
        .navigationTitle("Customize Agent")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            loadAgentSettings(for: selectedMode)
        }
        .onChange(of: selectedMode) { newMode in
            loadAgentSettings(for: newMode)
        }
        .alert("Changes Saved", isPresented: $showingSaveConfirmation) {
            Button("OK") {}
        } message: {
            Text("Your customizations for \(selectedMode.displayName) have been saved.")
        }
    }

    // MARK: - Mode Selector

    private var modeSelector: some View {
        HStack(spacing: Spacing.sm) {
            ForEach(HestiaMode.allCases) { mode in
                Button {
                    withAnimation(.hestiaStandard) {
                        selectedMode = mode
                    }
                } label: {
                    VStack(spacing: Spacing.xs) {
                        Circle()
                            .fill(mode == selectedMode ?
                                  mode.gradientColors.first ?? .gray :
                                  Color.white.opacity(0.2))
                            .frame(width: 50, height: 50)
                            .overlay(
                                Text(mode.displayName.prefix(1))
                                    .font(.system(size: 20, weight: .bold))
                                    .foregroundColor(.white)
                            )

                        Text(mode.displayName)
                            .font(.caption)
                            .foregroundColor(mode == selectedMode ? .white : .white.opacity(0.6))
                    }
                    .padding(Spacing.sm)
                    .background(mode == selectedMode ? Color.white.opacity(0.15) : Color.clear)
                    .cornerRadius(CornerRadius.small)
                }
            }
        }
    }

    // MARK: - Avatar Section

    private var avatarSection: some View {
        VStack(spacing: Spacing.md) {
            Text("Profile Photo")
                .font(.headline)
                .foregroundColor(.white)

            PhotosPicker(selection: $selectedPhotoItem, matching: .images) {
                ZStack {
                    if let photoData = selectedPhotoData,
                       let uiImage = UIImage(data: photoData) {
                        Image(uiImage: uiImage)
                            .resizable()
                            .scaledToFill()
                    } else {
                        Circle()
                            .fill(Color.white.opacity(0.2))
                            .overlay(
                                Text(selectedMode.displayName.prefix(1))
                                    .font(.system(size: 40, weight: .bold))
                                    .foregroundColor(.white)
                            )
                    }
                }
                .frame(width: Size.Avatar.xlarge, height: Size.Avatar.xlarge)
                .clipShape(Circle())
                .overlay(
                    Circle()
                        .stroke(Color.white.opacity(0.3), lineWidth: 3)
                )
                .overlay(
                    Image(systemName: "camera.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.white)
                        .padding(Spacing.sm)
                        .background(Color.black.opacity(0.6))
                        .clipShape(Circle())
                        .offset(x: 40, y: 40)
                )
            }
            .onChange(of: selectedPhotoItem) { newItem in
                Task {
                    if let data = try? await newItem?.loadTransferable(type: Data.self) {
                        selectedPhotoData = data
                        hasChanges = true
                    }
                }
            }
        }
    }

    // MARK: - Name Section

    private var nameSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text("Full Name")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))

                TextField("Hestia", text: $agentName)
                    .customTextField()
                    .onChange(of: agentName) { _ in
                        hasChanges = true
                    }
            }

            VStack(alignment: .leading, spacing: Spacing.xs) {
                Text("Nickname")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.7))

                TextField("Tia", text: $agentNickname)
                    .customTextField()
                    .onChange(of: agentNickname) { _ in
                        hasChanges = true
                    }
            }
        }
    }

    // MARK: - Color Section

    private var colorSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Color Palette")
                .font(.headline)
                .foregroundColor(.white)

            VStack(spacing: Spacing.sm) {
                ForEach(Array(customColors.enumerated()), id: \.offset) { index, color in
                    HStack {
                        Text("Color \(index + 1)")
                            .foregroundColor(.white.opacity(0.7))

                        Spacer()

                        ColorPicker("", selection: $customColors[index])
                            .labelsHidden()
                            .onChange(of: customColors[index]) { _ in
                                hasChanges = true
                            }

                        // Color preview
                        RoundedRectangle(cornerRadius: 4)
                            .fill(customColors[index])
                            .frame(width: 30, height: 30)
                    }
                    .padding(Spacing.sm)
                    .background(Color.white.opacity(0.1))
                    .cornerRadius(CornerRadius.small)
                }
            }
        }
    }

    // MARK: - Traits Section

    private var traitsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.md) {
            Text("Personality Traits")
                .font(.headline)
                .foregroundColor(.white)

            VStack(alignment: .leading, spacing: Spacing.sm) {
                ForEach(selectedMode.traits, id: \.self) { trait in
                    HStack {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.white.opacity(0.5))

                        Text(trait)
                            .font(.body)
                            .foregroundColor(.white.opacity(0.8))
                    }
                }
            }
            .padding(Spacing.md)
            .background(Color.white.opacity(0.1))
            .cornerRadius(CornerRadius.small)

            Text("Traits are defined by the system and cannot be customized.")
                .font(.caption)
                .foregroundColor(.white.opacity(0.5))
        }
    }

    // MARK: - Save Button

    private var saveButton: some View {
        Button {
            saveSettings()
        } label: {
            Text("Save Changes")
                .font(.buttonText)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(Spacing.md)
                .background(Color.white.opacity(0.2))
                .cornerRadius(CornerRadius.button)
        }
    }

    // MARK: - Helpers

    private func loadAgentSettings(for mode: HestiaMode) {
        agentName = mode.fullName
        agentNickname = mode.displayName
        customColors = mode.gradientColors
        hasChanges = false
    }

    private func saveSettings() {
        // In production, save to UserDefaults or backend
        // For now, just show confirmation
        showingSaveConfirmation = true
        hasChanges = false
    }
}

// MARK: - Custom Text Field Style

extension View {
    func customTextField() -> some View {
        self
            .font(.body)
            .foregroundColor(.white)
            .padding(Spacing.md)
            .background(Color.white.opacity(0.15))
            .cornerRadius(CornerRadius.input)
    }
}

// MARK: - Preview

struct AgentCustomizationView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            AgentCustomizationView()
        }
    }
}
