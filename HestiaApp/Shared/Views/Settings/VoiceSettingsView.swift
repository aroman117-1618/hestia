#if os(iOS)
import SwiftUI
import AVFoundation
import HestiaShared

/// Settings for voice conversation: TTS voice, VAD sensitivity, auto-continue.
struct VoiceSettingsView: View {
    @StateObject private var ttsService = TTSService()
    @State private var selectedVoiceId: String = ""
    @State private var silenceDuration: Double = 1.5
    @State private var autoContinue: Bool = true
    @State private var voices: [AVSpeechSynthesisVoice] = []

    private static let silenceDurationKey = "hestia_vad_silence_duration"
    private static let autoContinueKey = "hestia_voice_auto_continue"

    var body: some View {
        List {
            Section {
                ForEach(voices, id: \.identifier) { voice in
                    Button {
                        selectedVoiceId = voice.identifier
                        ttsService.selectVoice(identifier: voice.identifier)
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(voice.name)
                                    .foregroundColor(.white)
                                Text(qualityLabel(voice.quality))
                                    .font(.caption)
                                    .foregroundColor(.white.opacity(0.4))
                            }
                            Spacer()
                            if voice.identifier == selectedVoiceId {
                                Image(systemName: "checkmark")
                                    .foregroundColor(.blue)
                            }
                        }
                    }
                }
            } header: {
                Text("Hestia's Voice")
            } footer: {
                Text("Premium voices sound most natural. Download more in Settings > Accessibility > Spoken Content > Voices.")
            }

            Section {
                Button("Preview Voice") {
                    ttsService.speak("Hello, I'm Hestia. How can I help you today?")
                }
            }

            Section {
                VStack(alignment: .leading) {
                    Text("Pause Detection: \(String(format: "%.1f", silenceDuration))s")
                    Slider(value: $silenceDuration, in: 0.8...3.0, step: 0.1)
                        .onChange(of: silenceDuration) { value in
                            UserDefaults.standard.set(value, forKey: Self.silenceDurationKey)
                        }
                }
            } header: {
                Text("Sensitivity")
            } footer: {
                Text("How long to wait after you stop speaking before Hestia responds. Shorter = snappier, longer = more room for natural pauses.")
            }

            Section {
                Toggle("Auto-Continue", isOn: $autoContinue)
                    .onChange(of: autoContinue) { value in
                        UserDefaults.standard.set(value, forKey: Self.autoContinueKey)
                    }
            } header: {
                Text("Conversation")
            } footer: {
                Text("When enabled, Hestia automatically listens for your next message after speaking. When disabled, conversation ends after each response.")
            }
        }
        .navigationTitle("Voice & Audio")
        .listStyle(.insetGrouped)
        .onAppear {
            voices = ttsService.availableVoices()
            selectedVoiceId = UserDefaults.standard.string(forKey: "hestia_tts_voice_identifier") ?? ""
            silenceDuration = UserDefaults.standard.object(forKey: Self.silenceDurationKey) as? Double ?? 1.5
            autoContinue = UserDefaults.standard.object(forKey: Self.autoContinueKey) as? Bool ?? true
        }
    }

    private func qualityLabel(_ quality: AVSpeechSynthesisVoiceQuality) -> String {
        switch quality {
        case .premium: return "Premium"
        case .enhanced: return "Enhanced"
        default: return "Default"
        }
    }
}
#endif
