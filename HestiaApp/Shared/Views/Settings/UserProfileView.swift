import SwiftUI
import HestiaShared
import PhotosUI

/// View for editing user profile information
struct UserProfileView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = UserProfileViewModel()

    @State private var showingPhotoPicker = false
    @State private var selectedPhotoItem: PhotosPickerItem?
    @State private var hasUnsavedChanges = false

    var body: some View {
        ZStack {
            GradientBackground(mode: appState.currentMode)

            ScrollView {
                VStack(spacing: Spacing.xl) {
                    // Profile Photo Section
                    photoSection
                        .padding(.top, Spacing.lg)

                    // Name Section
                    nameSection

                    // Description Section
                    descriptionSection

                    // Push Notifications Section
                    notificationsSection

                    // Save Button
                    if hasUnsavedChanges {
                        saveButton
                    }

                    Spacer()
                        .frame(height: Spacing.xxl)
                }
                .padding(.horizontal, Spacing.lg)
            }
            .scrollContentBackground(.hidden)
        }
        .navigationTitle("Profile")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear {
            viewModel.loadProfile()
        }
        .alert("Profile Saved", isPresented: $viewModel.showSaveConfirmation) {
            Button("OK") {
                hasUnsavedChanges = false
            }
        } message: {
            Text("Your profile has been updated.")
        }
    }

    // MARK: - Photo Section

    private var photoSection: some View {
        VStack(spacing: Spacing.md) {
            PhotosPicker(selection: $selectedPhotoItem, matching: .images) {
                ZStack {
                    if let photoData = viewModel.photoData,
                       let uiImage = UIImage(data: photoData) {
                        Image(uiImage: uiImage)
                            .resizable()
                            .scaledToFill()
                    } else {
                        Circle()
                            .fill(Color.white.opacity(0.2))
                            .overlay(
                                Text(viewModel.profile.initial)
                                    .font(.system(size: 48, weight: .bold))
                                    .foregroundColor(.textPrimary)
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
                        .foregroundColor(.textPrimary)
                        .padding(Spacing.sm)
                        .background(Color.black.opacity(0.6))
                        .clipShape(Circle())
                        .offset(x: 40, y: 40)
                )
            }
            .onChange(of: selectedPhotoItem) { newItem in
                Task {
                    if let data = try? await newItem?.loadTransferable(type: Data.self) {
                        await MainActor.run {
                            viewModel.updatePhoto(data)
                            hasUnsavedChanges = true
                        }
                    }
                }
            }

            Text("Tap to change photo")
                .font(.caption)
                .foregroundColor(.textSecondary)
        }
    }

    // MARK: - Name Section

    private var nameSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Text("Name")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
                .textCase(.uppercase)

            TextField("Your name", text: $viewModel.profile.name)
                .customTextField()
                .onChange(of: viewModel.profile.name) { _ in
                    hasUnsavedChanges = true
                }
        }
    }

    // MARK: - Description Section

    private var descriptionSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Text("About")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
                .textCase(.uppercase)

            TextEditor(text: Binding(
                get: { viewModel.profile.description ?? "" },
                set: { viewModel.profile.description = $0.isEmpty ? nil : $0 }
            ))
            .font(.body)
            .foregroundColor(.textPrimary)
            .scrollContentBackground(.hidden)
            .frame(minHeight: 100)
            .padding(Spacing.md)
            .background(Color.white.opacity(0.15))
            .cornerRadius(CornerRadius.input)
            .onChange(of: viewModel.profile.description) { _ in
                hasUnsavedChanges = true
            }

            Text("Optional description that Hestia can use to personalize responses")
                .font(.caption)
                .foregroundColor(.textSecondary)
        }
    }

    // MARK: - Notifications Section

    private var notificationsSection: some View {
        VStack(alignment: .leading, spacing: Spacing.sm) {
            Text("Notifications")
                .font(.caption)
                .foregroundColor(.white.opacity(0.7))
                .textCase(.uppercase)

            Toggle(isOn: $viewModel.profile.pushNotificationsEnabled) {
                HStack {
                    Image(systemName: "bell.fill")
                        .foregroundColor(.textPrimary)
                    Text("Push Notifications")
                        .foregroundColor(.textPrimary)
                }
            }
            .toggleStyle(SwitchToggleStyle(tint: appState.currentMode.gradientColors.first ?? .orange))
            .padding(Spacing.md)
            .background(Color.white.opacity(0.05))
            .cornerRadius(CornerRadius.small)
            .onChange(of: viewModel.profile.pushNotificationsEnabled) { _ in
                hasUnsavedChanges = true
            }

            Text("Receive notifications for order failures and important alerts")
                .font(.caption)
                .foregroundColor(.textSecondary)
        }
    }

    // MARK: - Save Button

    private var saveButton: some View {
        Button {
            viewModel.saveProfile()
        } label: {
            Text("Save Changes")
                .font(.buttonText)
                .foregroundColor(.textPrimary)
                .frame(maxWidth: .infinity)
                .padding(Spacing.md)
                .background(appState.currentMode.gradientColors.first?.opacity(0.8) ?? Color.white.opacity(0.2))
                .cornerRadius(CornerRadius.button)
        }
        .padding(.top, Spacing.lg)
    }
}

// MARK: - User Profile ViewModel

@MainActor
class UserProfileViewModel: ObservableObject {
    @Published var profile: UserProfile = .default
    @Published var photoData: Data?
    @Published var showSaveConfirmation = false
    @Published var isLoading = false
    @Published var isOffline = false
    @Published var errorMessage: String?

    private let userDefaults = UserDefaults.standard
    private let photoFileName = "user_profile_photo.jpg"
    private let apiClient = APIClient.shared

    // MARK: - Public Methods

    func loadProfile() {
        Task {
            isLoading = true
            defer { isLoading = false }

            do {
                // Try to load from backend first
                let response = try await apiClient.getUserProfile()
                isOffline = false

                // Update local profile from backend
                profile.name = response.name
                profile.description = response.description

                // Cache locally
                saveToLocalCache()

                // Load photo from backend if available
                if response.photoUrl != nil {
                    do {
                        let photoData = try await apiClient.getUserPhoto()
                        self.photoData = photoData
                        // Cache photo locally
                        savePhotoToCache(photoData)
                    } catch {
                        #if DEBUG
                        print("[UserProfileViewModel] Failed to load photo from backend: \(error)")
                        #endif
                    }
                }

                // Load settings
                let settings = try await apiClient.getUserSettings()
                profile.pushNotificationsEnabled = settings.pushNotifications.enabled
                saveToLocalCache()

            } catch {
                // Fall back to local cache
                #if DEBUG
                print("[UserProfileViewModel] Backend load failed, using cache: \(error)")
                #endif
                isOffline = true
                loadFromLocalCache()
            }
        }
    }

    func saveProfile() {
        Task {
            isLoading = true
            defer { isLoading = false }

            do {
                // Save profile to backend
                let profileRequest = UserProfileUpdateRequest(
                    name: profile.name,
                    description: profile.description
                )
                _ = try await apiClient.updateUserProfile(profileRequest)

                // Save settings to backend
                let settingsRequest = UserSettingsUpdateRequest(
                    pushNotifications: PushNotificationSettings(
                        enabled: profile.pushNotificationsEnabled,
                        orderAlerts: true,
                        proactiveBriefings: true,
                        quietHours: QuietHours()
                    ),
                    defaultMode: nil,
                    autoLockTimeoutMinutes: nil
                )
                _ = try await apiClient.updateUserSettings(settingsRequest)

                isOffline = false
                showSaveConfirmation = true

                // Update local cache
                saveToLocalCache()

            } catch {
                #if DEBUG
                print("[UserProfileViewModel] Backend save failed: \(error)")
                #endif
                isOffline = true
                errorMessage = "Changes saved locally. Will sync when online."

                // Save locally anyway
                saveToLocalCache()
                showSaveConfirmation = true
            }
        }
    }

    func updatePhoto(_ data: Data) {
        // Resize and compress image
        guard let image = UIImage(data: data),
              let resizedImage = resizeImage(image, targetSize: CGSize(width: 256, height: 256)),
              let compressedData = resizedImage.jpegData(compressionQuality: 0.8) else {
            return
        }

        // Update local state immediately
        photoData = compressedData
        profile.photoPath = photoFileName

        // Save locally
        savePhotoToCache(compressedData)

        // Upload to backend
        Task {
            do {
                _ = try await apiClient.uploadUserPhoto(imageData: compressedData)
                isOffline = false
                #if DEBUG
                print("[UserProfileViewModel] Photo uploaded to backend")
                #endif
            } catch {
                #if DEBUG
                print("[UserProfileViewModel] Failed to upload photo: \(error)")
                #endif
                isOffline = true
            }
        }
    }

    // MARK: - Private Methods

    private func loadFromLocalCache() {
        // Load name
        if let name = userDefaults.string(forKey: "userProfile.name") {
            profile.name = name
        }

        // Load description
        profile.description = userDefaults.string(forKey: "userProfile.description")

        // Load push notification preference
        profile.pushNotificationsEnabled = userDefaults.bool(forKey: "userProfile.pushNotificationsEnabled")

        // Load photo
        if let photoPath = userDefaults.string(forKey: "userProfile.photoPath") {
            let url = getDocumentsDirectory().appendingPathComponent(photoPath)
            photoData = try? Data(contentsOf: url)
            profile.photoPath = photoPath
        }
    }

    private func saveToLocalCache() {
        userDefaults.set(profile.name, forKey: "userProfile.name")
        userDefaults.set(profile.description, forKey: "userProfile.description")
        userDefaults.set(profile.pushNotificationsEnabled, forKey: "userProfile.pushNotificationsEnabled")
        if let path = profile.photoPath {
            userDefaults.set(path, forKey: "userProfile.photoPath")
        }
    }

    private func savePhotoToCache(_ data: Data) {
        let url = getDocumentsDirectory().appendingPathComponent(photoFileName)
        do {
            try data.write(to: url)
            profile.photoPath = photoFileName
            userDefaults.set(photoFileName, forKey: "userProfile.photoPath")
        } catch {
            #if DEBUG
            print("[UserProfileViewModel] Failed to save photo to cache: \(error)")
            #endif
        }
    }

    private func getDocumentsDirectory() -> URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
    }

    private func resizeImage(_ image: UIImage, targetSize: CGSize) -> UIImage? {
        let size = image.size
        let widthRatio = targetSize.width / size.width
        let heightRatio = targetSize.height / size.height
        let ratio = min(widthRatio, heightRatio)

        let newSize = CGSize(width: size.width * ratio, height: size.height * ratio)

        UIGraphicsBeginImageContextWithOptions(newSize, false, 1.0)
        image.draw(in: CGRect(origin: .zero, size: newSize))
        let newImage = UIGraphicsGetImageFromCurrentImageContext()
        UIGraphicsEndImageContext()

        return newImage
    }
}

// MARK: - Preview

struct UserProfileView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            UserProfileView()
                .environmentObject(AppState())
        }
    }
}
