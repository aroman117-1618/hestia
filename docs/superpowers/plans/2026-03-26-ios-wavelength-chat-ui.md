# iOS Chat View Redesign — "Wavelength UI" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the iOS chat view with a wavelength-centered UI that morphs between idle (centered wavelength + greeting) and conversation (header wavelength + messages), with tap/hold mic interactions and hidden tab bar.

**Architecture:** REVISED — Particle wave system (NOT sphere). `HestiaWavelengthView` renders 3500 particles as a horizontal energy field using `UIGraphicsImageRenderer` + `CGContext` with additive blending (`CGBlendMode.plusLighter`). Pre-rendered particle texture sprites. 3 ribbon layers with distinct wave equations. Listening = calm symmetric waves. Speaking = asymmetric peaks (triggered during streaming responses). Layout morphs between idle (centered wave + greeting) and conversation (scaled wave in top half, messages in bottom half with fade-to-background at top). Approved mockup: `docs/superpowers/specs/wavelength-prototype.html`. Figma source: `ParticleWave.tsx` from Figma Make export.

**DESIGN PIVOT (2026-03-26):** Original plan used 3D sphere with ribbon bands — WRONG. Andrew approved the horizontal particle wave design matching Figma nodes 369:647 (listening) and 369:710 (speaking). See `memory/wavelength-design-decisions.md` for all approved specs.

**Tech Stack:** CGContext, UIGraphicsImageRenderer, SwiftUI TimelineView, CoreGraphics, AVFoundation

**Revised Estimate:** 27-39 hours (revised up from 19-27h after second opinion audit)

**Second Opinion:** `docs/plans/ios-wavelength-chat-ui-second-opinion-2026-03-26.md` — APPROVED WITH CONDITIONS (all conditions incorporated below)

**References:**
- Visual mockup: `docs/superpowers/specs/chat-ui-orb-mockup.html`
- Discovery: `docs/discoveries/ios-orb-chat-redesign-2026-03-26.md`
- Figma: node 359:614 in UidQy7gdb1DVSQeDKPhmrg

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `Shared/Views/Common/HestiaWavelengthView.swift` | SwiftUI wrapper: TimelineView + Image(cgImage:), @StateObject ViewModel for frame timing |
| `Shared/Views/Common/WavelengthRenderer.swift` | Core renderer: CGContext-based 3D geometry, 5-pass glow arcs, 7-layer compositing → CGImage |
| `Shared/Views/Common/WavelengthState.swift` | State enum, parameter targets, lerp interpolation |
| `Shared/Views/Chat/ChatIdleView.swift` | Idle layout: centered wavelength + greeting + input bar |
| `Shared/Views/Chat/ConversationStatusView.swift` | Live transcript display + state label for conversation mode (replaces VoiceConversationOverlay) |

### Modified Files
| File | Changes |
|------|---------|
| `Shared/Views/Chat/ChatView.swift` | Replace monolithic layout with idle/conversation morph; remove old voice mode cycling |
| `Shared/Views/Chat/ChatInputBar.swift` | Replace mode cycle button with tap/hold mic; remove journal mode toggle |
| `Shared/Models/ChatInputMode.swift` | Simplify to 2 modes: `.chat`, `.transcription` (remove `.voice`, `.journal`) |
| `Shared/Views/Chat/VoiceConversationOverlay.swift` | Delete — conversation mode goes inline |
| `Shared/App/ContentView.swift` | Hide tab bar, add swipe-up gesture |
| `Shared/Services/VoiceConversationManager.swift` | Fix async race condition in audio handoff |

### Removed Files
| File | Reason |
|------|--------|
| `Shared/Views/Common/HestiaOrbView.swift` | Replaced by HestiaWavelengthView (remove at end, after all references updated) |
| `Shared/Views/Chat/VoiceConversationOverlay.swift` | Conversation mode goes inline |

---

## Task 1: WavelengthState — State Enum & Parameter Interpolation

**Files:**
- Create: `HestiaApp/Shared/Views/Common/WavelengthState.swift`

This is the data layer — no rendering, just math and state definitions.

- [ ] **Step 1: Create the state enum and band definitions**

```swift
// WavelengthState.swift
import Foundation

// MARK: - Wavelength State

enum WavelengthMode: Equatable {
    case idle
    case listening
    case speaking
    case thinking
}

// MARK: - Band Definition

struct WavelengthBand {
    let tx: Double      // X-axis rotation (radians)
    let ty: Double      // Y-axis rotation (radians)
    let off: Double     // Phase offset (radians)
    let w: Double       // Width multiplier (0–1)
    let b: Double       // Base brightness (0–1)
    let wv: (Double, Double, Double) // Waviness frequencies

    static let bands: [WavelengthBand] = [
        WavelengthBand(tx:  0.52, ty:  0.28, off: 0.00, w: 1.00, b: 1.00, wv: (3.0, 5.2, 7.8)),
        WavelengthBand(tx: -0.38, ty:  0.84, off: 2.09, w: 0.76, b: 0.82, wv: (2.4, 4.7, 8.3)),
        WavelengthBand(tx:  0.72, ty: -0.52, off: 4.19, w: 0.48, b: 0.62, wv: (3.6, 6.1, 9.0)),
    ]
}
```

- [ ] **Step 2: Add the animation parameters struct and target calculation**

```swift
// MARK: - Animation Parameters

struct WavelengthParams {
    var spd: Double     // Rotation speed
    var bloom: Double   // Glow bloom factor
    var pulse: Double   // Radial breathing
    var bw: Double      // Bandwidth multiplier
    var glow: Double    // Glow intensity
    var bg: Double      // Background opacity
    var rim: Double     // Rim highlight opacity
    var sph: Double     // Sphere fill opacity
    var wave: Double    // Waviness amplitude
    var wSpd: Double    // Wave animation speed

    static func target(for mode: WavelengthMode, level: Double, time: Double) -> WavelengthParams {
        switch mode {
        case .idle:
            return WavelengthParams(
                spd: 0.30,
                bloom: 0.80 + level * 0.10,
                pulse: 0.003 + 0.003 * sin(time * 0.7),
                bw: 0.90 + level * 0.05,
                glow: 0.85 + level * 0.08,
                bg: 0.30 + level * 0.08,
                rim: 0.40 + level * 0.08,
                sph: 0.85,
                wave: 0.045,
                wSpd: 0.8
            )
        case .listening:
            return WavelengthParams(
                spd: 0.45,
                bloom: 0.92 + level * 0.18,
                pulse: 0.005 + 0.004 * sin(time * 0.9),
                bw: 1.00 + level * 0.08,
                glow: 1.00 + level * 0.12,
                bg: 0.38 + level * 0.10,
                rim: 0.50 + level * 0.10,
                sph: 0.82,
                wave: 0.055,
                wSpd: 1.0
            )
        case .thinking:
            return WavelengthParams(
                spd: 0.65,
                bloom: 1.20 + 0.15 * sin(time * 2.0),
                pulse: 0.010 + 0.008 * sin(time * 1.8),
                bw: 1.15 + 0.05 * sin(time * 2.2),
                glow: 1.25 + 0.12 * sin(time * 2.5),
                bg: 0.50 + 0.10 * sin(time * 1.5),
                rim: 0.65 + 0.08 * sin(time * 2.0),
                sph: 0.72,
                wave: 0.065,
                wSpd: 1.4
            )
        case .speaking:
            return WavelengthParams(
                spd: 0.90 + level * 0.25,
                bloom: 1.55 + level * 0.50 + 0.28 * sin(time * 3.2),
                pulse: 0.016 + 0.012 * sin(time * 2.5),
                bw: 1.30 + level * 0.18 + 0.06 * sin(time * 2.8),
                glow: 1.50 + level * 0.35 + 0.18 * sin(time * 3.5),
                bg: 0.62 + level * 0.28 + 0.12 * sin(time * 2.2),
                rim: 0.80 + level * 0.20 + 0.08 * sin(time * 3.0),
                sph: 0.62 - level * 0.10,
                wave: 0.08 + level * 0.03,
                wSpd: 1.8 + level * 0.6
            )
        }
    }

    /// Linearly interpolate all parameters toward target
    func lerped(toward target: WavelengthParams, alpha: Double) -> WavelengthParams {
        let a = min(max(alpha, 0), 1)
        return WavelengthParams(
            spd:   spd   + (target.spd   - spd)   * a,
            bloom: bloom + (target.bloom - bloom) * a,
            pulse: pulse + (target.pulse - pulse) * a,
            bw:    bw    + (target.bw    - bw)    * a,
            glow:  glow  + (target.glow  - glow)  * a,
            bg:    bg    + (target.bg    - bg)    * a,
            rim:   rim   + (target.rim   - rim)   * a,
            sph:   sph   + (target.sph   - sph)   * a,
            wave:  wave  + (target.wave  - wave)  * a,
            wSpd:  wSpd  + (target.wSpd  - wSpd)  * a
        )
    }
}
```

- [ ] **Step 3: Add the 3D point type**

```swift
// MARK: - 3D Point

struct WavelengthPoint {
    let x: Double
    let y: Double
    let z: Double
    let depth: Double  // Normalized 0–1 (back-to-front)
}
```

- [ ] **Step 4: Verify the file compiles**

Run: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

- [ ] **Step 5: Commit**

```bash
git add HestiaApp/Shared/Views/Common/WavelengthState.swift
git commit -m "feat(ios): add WavelengthState — mode enum, band definitions, parameter interpolation"
```

---

## Task 2: WavelengthRenderer — Core 3D Geometry & Arc Drawing

**Files:**
- Create: `HestiaApp/Shared/Views/Common/WavelengthRenderer.swift`

This is the pure rendering engine — no SwiftUI, just CGContext drawing functions.

- [ ] **Step 1: Create the renderer struct with great circle path generation**

```swift
// WavelengthRenderer.swift
import CoreGraphics
import Foundation

struct WavelengthRenderer {

    // MARK: - Great Circle Path Generation

    /// Generate points along a great circle on a sphere with multi-frequency waviness.
    /// Returns 101 points (0...N inclusive) for smooth Catmull-Rom interpolation.
    static func greatCircle(
        band: WavelengthBand,
        radius R: Double,
        rotation rot: Double,
        wobbleX wobX: Double,
        wobbleY wobY: Double,
        params p: WavelengthParams,
        time t: Double
    ) -> [WavelengthPoint] {
        let N = 100
        var pts: [WavelengthPoint] = []
        pts.reserveCapacity(N + 1)

        let tX = band.tx + wobX
        let tY = band.ty + wobY
        let cosX = cos(tX), sinX = sin(tX)
        let cosY = cos(tY), sinY = sin(tY)

        let wAmp = p.wave * R
        let wSpd = p.wSpd
        let (f1, f2, f3) = band.wv

        for i in 0...N {
            let u = Double(i) / Double(N)
            let a = u * .pi * 2 + rot + band.off

            // Base great circle in XY plane
            var x = cos(a) * R
            var y = sin(a) * R
            var z = 0.0

            // 3 harmonic waves in Z (depth)
            z += sin(u * .pi * 2 * f1 + t * wSpd * 1.3) * wAmp
            z += sin(u * .pi * 2 * f2 - t * wSpd * 0.9) * wAmp * 0.5
            z += sin(u * .pi * 2 * f3 + t * wSpd * 1.8) * wAmp * 0.22

            // 2 harmonic waves in Y (lateral meander)
            y += cos(u * .pi * 2 * (f1 + 0.5) + t * wSpd * 0.7) * wAmp * 0.6
            y += cos(u * .pi * 2 * (f2 - 0.3) - t * wSpd * 1.1) * wAmp * 0.25

            // Rotate around X axis
            let y1 = y * cosX - z * sinX
            let z1 = y * sinX + z * cosX

            // Rotate around Y axis
            let x1 = x * cosY + z1 * sinY
            let z2 = -x * sinY + z1 * cosY

            // Normalize back onto sphere surface
            let len = sqrt(x1 * x1 + y1 * y1 + z2 * z2)
            let nx = (x1 / len) * R
            let ny = (y1 / len) * R
            let nz = (z2 / len) * R

            let depth = (nz / R + 1) * 0.5

            pts.append(WavelengthPoint(x: nx, y: ny, z: nz, depth: depth))
        }

        return pts
    }
}
```

- [ ] **Step 2: Add front/back arc splitting**

```swift
    // MARK: - Z-Split

    /// Split path into front (z >= 0) and back (z < 0) contiguous arcs.
    static func splitByDepth(_ pts: [WavelengthPoint]) -> (front: [[WavelengthPoint]], back: [[WavelengthPoint]]) {
        var front: [[WavelengthPoint]] = []
        var back: [[WavelengthPoint]] = []
        var currentArc: [WavelengthPoint] = []
        var isFront: Bool?

        for pt in pts {
            let above = pt.z >= 0
            if above != isFront {
                if currentArc.count > 1 {
                    if isFront == true { front.append(currentArc) }
                    else { back.append(currentArc) }
                }
                isFront = above
                currentArc = [pt]
            } else {
                currentArc.append(pt)
            }
        }
        if currentArc.count > 1 {
            if isFront == true { front.append(currentArc) }
            else { back.append(currentArc) }
        }

        return (front, back)
    }
```

- [ ] **Step 3: Add Catmull-Rom arc tracing as CGPath**

```swift
    // MARK: - Path Tracing

    /// Create a smooth CGPath from points using Catmull-Rom → cubic bezier conversion.
    static func tracePath(points pts: [WavelengthPoint], centerX ox: Double, centerY oy: Double) -> CGPath {
        let path = CGMutablePath()
        path.move(to: CGPoint(x: ox + pts[0].x, y: oy + pts[0].y))

        for i in 0..<pts.count - 1 {
            let p0 = pts[max(0, i - 1)]
            let p1 = pts[i]
            let p2 = pts[i + 1]
            let p3 = pts[min(pts.count - 1, i + 2)]

            let cp1 = CGPoint(
                x: ox + p1.x + (p2.x - p0.x) / 6,
                y: oy + p1.y + (p2.y - p0.y) / 6
            )
            let cp2 = CGPoint(
                x: ox + p2.x - (p3.x - p1.x) / 6,
                y: oy + p2.y - (p3.y - p1.y) / 6
            )

            path.addCurve(
                to: CGPoint(x: ox + p2.x, y: oy + p2.y),
                control1: cp1,
                control2: cp2
            )
        }

        return path
    }
```

- [ ] **Step 4: Add 5-pass glow arc drawing**

```swift
    // MARK: - Arc Drawing (5-Pass Glow)

    /// Draw an arc with 5 concentric glow passes (darkest/widest → brightest/thinnest).
    static func drawArc(
        in ctx: CGContext,
        centerX ox: Double,
        centerY oy: Double,
        points pts: [WavelengthPoint],
        baseWidth: Double,
        brightness: Double,
        params p: WavelengthParams
    ) {
        guard pts.count >= 3 else { return }

        let w = baseWidth * p.bw
        let b = min(max(brightness * p.glow, 0), 6)
        let path = tracePath(points: pts, centerX: ox, centerY: oy)

        ctx.setLineCap(.round)
        ctx.setLineJoin(.round)

        // Pass 1: Wide bloom (dark brown, large shadow)
        ctx.saveGState()
        ctx.addPath(path)
        ctx.setStrokeColor(CGColor(
            red: 155/255, green: 50/255, blue: 0,
            alpha: min(0.055 * b, 1)
        ))
        ctx.setLineWidth(w * 7)
        ctx.setShadow(
            offset: .zero, blur: w * 12,
            color: CGColor(red: 1, green: 90/255, blue: 0, alpha: min(0.09 * b, 1))
        )
        ctx.strokePath()
        ctx.restoreGState()

        // Pass 2: Outer glow (orange)
        ctx.saveGState()
        ctx.addPath(path)
        ctx.setStrokeColor(CGColor(
            red: 1, green: 115/255, blue: 5/255,
            alpha: min(0.13 * b, 1)
        ))
        ctx.setLineWidth(w * 3.5)
        ctx.setShadow(
            offset: .zero, blur: w * 6,
            color: CGColor(red: 1, green: 105/255, blue: 0, alpha: min(0.10 * b, 1))
        )
        ctx.strokePath()
        ctx.restoreGState()

        // Pass 3: Inner glow (amber) — no shadow
        ctx.addPath(path)
        ctx.setStrokeColor(CGColor(
            red: 1, green: 168/255, blue: 38/255,
            alpha: min(0.32 * b, 1)
        ))
        ctx.setLineWidth(w * 1.7)
        ctx.strokePath()

        // Pass 4: Core (light amber)
        ctx.addPath(path)
        ctx.setStrokeColor(CGColor(
            red: 1, green: 212/255, blue: 125/255,
            alpha: min(0.52 * b, 1)
        ))
        ctx.setLineWidth(w * 0.7)
        ctx.strokePath()

        // Pass 5: Hot center (near-white)
        ctx.addPath(path)
        ctx.setStrokeColor(CGColor(
            red: 1, green: 248/255, blue: 228/255,
            alpha: min(0.40 * b, 1)
        ))
        ctx.setLineWidth(w * 0.22)
        ctx.strokePath()
    }
```

- [ ] **Step 5: Add the full compositing pipeline using CGContext**

**IMPORTANT:** This uses `UIGraphicsImageRenderer` + `CGContext` — NOT SwiftUI `GraphicsContext`.
SwiftUI Canvas lacks `setShadow()`, `CGBlendMode.plusLighter`, `drawLayer`, and per-pass blur.
CGContext supports all of these natively. The renderer produces a `CGImage` per frame.

```swift
    // MARK: - Full Render Pipeline (CGContext)

    /// Render the complete wavelength to a CGImage using UIGraphicsImageRenderer.
    /// This is the main entry point called every frame from HestiaWavelengthView.
    static func renderToImage(
        size: CGSize,
        scale: CGFloat,
        time: Double,
        params p: WavelengthParams
    ) -> CGImage? {
        let renderer = UIGraphicsImageRenderer(size: size)
        let uiImage = renderer.image { rendererCtx in
            let ctx = rendererCtx.cgContext

            let ox = size.width / 2
            let oy = size.height / 2
            let baseR = Double(min(size.width, size.height)) * 0.36
            let R = baseR * (1 + p.pulse)

            let rot = time * p.spd
            let wobX = 0.025 * sin(time * 0.09)
            let wobY = 0.018 * cos(time * 0.07)

            // Generate band paths
            let bandData = WavelengthBand.bands.map { band in
                let pts = greatCircle(band: band, radius: R, rotation: rot, wobbleX: wobX, wobbleY: wobY, params: p, time: time)
                let (front, back) = splitByDepth(pts)
                return (band, front, back)
            }

            // Layer 1: Background ambient glow
            drawBackgroundGlow(in: ctx, cx: ox, cy: oy, radius: R, params: p)

            // Layer 2: Back arcs (10% brightness)
            ctx.saveGState()
            ctx.setBlendMode(.plusLighter)
            for (band, _, back) in bandData {
                for arc in back {
                    drawArc(in: ctx, centerX: ox, centerY: oy, points: arc,
                            baseWidth: 10 * band.w, brightness: band.b * 0.10, params: p)
                }
            }
            ctx.restoreGState()

            // Layer 3: Sphere fill (dark interior)
            drawSphereFill(in: ctx, cx: ox, cy: oy, radius: R, params: p)

            // Layer 4: Rim highlight
            drawRimHighlight(in: ctx, cx: ox, cy: oy, radius: R, params: p)

            // Layer 5: Front arcs (95% brightness) with depth mask
            ctx.saveGState()
            ctx.beginTransparencyLayer(auxiliaryInfo: nil)
            ctx.setBlendMode(.plusLighter)
            for (band, front, _) in bandData {
                for arc in front {
                    drawArc(in: ctx, centerX: ox, centerY: oy, points: arc,
                            baseWidth: 10 * band.w, brightness: band.b * 0.95, params: p)
                }
            }
            // Depth mask via destinationIn
            ctx.setBlendMode(.destinationIn)
            drawDepthMask(in: ctx, cx: ox, cy: oy, radius: R)
            ctx.endTransparencyLayer()
            ctx.restoreGState()

            // Layer 6: Specular highlight
            drawSpecular(in: ctx, cx: ox, cy: oy, radius: R, params: p)

            // Layer 7: Atmosphere halo
            drawAtmosphere(in: ctx, cx: ox, cy: oy, radius: R, params: p)
        }
        return uiImage.cgImage
    }

    // MARK: - CGContext Compositing Helpers

    private static func drawBackgroundGlow(in ctx: CGContext, cx: Double, cy: Double, radius R: Double, params p: WavelengthParams) {
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let colors = [
            CGColor(colorSpace: colorSpace, components: [1, 159/255, 10/255, 0.07 * p.bg])!,
            CGColor(colorSpace: colorSpace, components: [200/255, 100/255, 0, 0.10 * p.bg])!,
            CGColor(colorSpace: colorSpace, components: [80/255, 40/255, 0, 0.04 * p.bg])!,
            CGColor(colorSpace: colorSpace, components: [0, 0, 0, 0])!,
        ] as CFArray
        let locations: [CGFloat] = [0, 0.15, 0.45, 1]
        guard let gradient = CGGradient(colorsSpace: colorSpace, colors: colors, locations: locations) else { return }
        ctx.drawRadialGradient(gradient, startCenter: CGPoint(x: cx, y: cy), startRadius: 0,
                               endCenter: CGPoint(x: cx, y: cy), endRadius: R * 2.5, options: [])
    }

    private static func drawSphereFill(in ctx: CGContext, cx: Double, cy: Double, radius R: Double, params p: WavelengthParams) {
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let colors = [
            CGColor(colorSpace: colorSpace, components: [28/255, 16/255, 5/255, 0.32 * p.sph])!,
            CGColor(colorSpace: colorSpace, components: [12/255, 7/255, 2/255, 0.58 * p.sph])!,
            CGColor(colorSpace: colorSpace, components: [5/255, 3/255, 1/255, 0.78 * p.sph])!,
            CGColor(colorSpace: colorSpace, components: [2/255, 1/255, 0, 0.88 * p.sph])!,
        ] as CFArray
        let locations: [CGFloat] = [0, 0.25, 0.6, 1]
        guard let gradient = CGGradient(colorsSpace: colorSpace, colors: colors, locations: locations) else { return }
        // Clip to circle
        ctx.saveGState()
        ctx.addEllipse(in: CGRect(x: cx - R, y: cy - R, width: R * 2, height: R * 2))
        ctx.clip()
        ctx.drawRadialGradient(gradient, startCenter: CGPoint(x: cx - R * 0.1, y: cy - R * 0.16), startRadius: R * 0.02,
                               endCenter: CGPoint(x: cx, y: cy), endRadius: R * 1.04, options: [])
        ctx.restoreGState()
    }

    private static func drawRimHighlight(in ctx: CGContext, cx: Double, cy: Double, radius R: Double, params p: WavelengthParams) {
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let colors = [
            CGColor(colorSpace: colorSpace, components: [80/255, 48/255, 0, 0.05 * p.rim])!,
            CGColor(colorSpace: colorSpace, components: [1, 179/255, 71/255, 0.52 * p.rim])!,
            CGColor(colorSpace: colorSpace, components: [1, 159/255, 10/255, 0.30 * p.rim])!,
            CGColor(colorSpace: colorSpace, components: [140/255, 75/255, 0, 0.10 * p.rim])!,
            CGColor(colorSpace: colorSpace, components: [0, 0, 0, 0.02])!,
        ] as CFArray
        let locations: [CGFloat] = [0, 0.28, 0.55, 0.8, 1]
        guard let gradient = CGGradient(colorsSpace: colorSpace, colors: colors, locations: locations) else { return }
        ctx.setLineWidth(2.0 + p.glow * 0.3)
        ctx.addEllipse(in: CGRect(x: cx - R + 1, y: cy - R + 1, width: (R - 1) * 2, height: (R - 1) * 2))
        ctx.replacePathWithStrokedPath()
        ctx.clip()
        ctx.drawLinearGradient(gradient, start: CGPoint(x: cx - R, y: cy - R), end: CGPoint(x: cx + R, y: cy + R), options: [])
    }

    private static func drawDepthMask(in ctx: CGContext, cx: Double, cy: Double, radius R: Double) {
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let colors = [
            CGColor(colorSpace: colorSpace, components: [1, 1, 1, 1.0])!,
            CGColor(colorSpace: colorSpace, components: [1, 1, 1, 0.97])!,
            CGColor(colorSpace: colorSpace, components: [1, 1, 1, 0.88])!,
            CGColor(colorSpace: colorSpace, components: [1, 1, 1, 0.68])!,
            CGColor(colorSpace: colorSpace, components: [1, 1, 1, 0.42])!,
            CGColor(colorSpace: colorSpace, components: [1, 1, 1, 0.20])!,
            CGColor(colorSpace: colorSpace, components: [1, 1, 1, 0.06])!,
        ] as CFArray
        let locations: [CGFloat] = [0, 0.3, 0.52, 0.68, 0.8, 0.9, 1]
        guard let gradient = CGGradient(colorsSpace: colorSpace, colors: colors, locations: locations) else { return }
        ctx.drawRadialGradient(gradient, startCenter: CGPoint(x: cx, y: cy), startRadius: 0,
                               endCenter: CGPoint(x: cx, y: cy), endRadius: R * 1.4,
                               options: .drawsAfterEndLocation)
    }

    private static func drawSpecular(in ctx: CGContext, cx: Double, cy: Double, radius R: Double, params p: WavelengthParams) {
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let colors = [
            CGColor(colorSpace: colorSpace, components: [1, 1, 1, 0])!,
            CGColor(colorSpace: colorSpace, components: [1, 225/255, 170/255, 0.03 + p.glow * 0.012])!,
            CGColor(colorSpace: colorSpace, components: [1, 245/255, 235/255, 0.045 + p.glow * 0.020])!,
            CGColor(colorSpace: colorSpace, components: [1, 1, 1, 0])!,
        ] as CFArray
        let locations: [CGFloat] = [0, 0.3, 0.5, 0.75]
        guard let gradient = CGGradient(colorsSpace: colorSpace, colors: colors, locations: locations) else { return }
        let specCenter = CGPoint(x: cx + R * 0.08, y: cy - R * 0.46)
        ctx.saveGState()
        ctx.addEllipse(in: CGRect(x: specCenter.x - R * 0.58, y: specCenter.y - R * 0.20, width: R * 1.16, height: R * 0.40))
        ctx.clip()
        ctx.drawRadialGradient(gradient, startCenter: specCenter, startRadius: 0,
                               endCenter: specCenter, endRadius: R * 0.58, options: [])
        ctx.restoreGState()
    }

    private static func drawAtmosphere(in ctx: CGContext, cx: Double, cy: Double, radius R: Double, params p: WavelengthParams) {
        let colorSpace = CGColorSpaceCreateDeviceRGB()
        let colors = [
            CGColor(colorSpace: colorSpace, components: [1, 130/255, 0, 0.04 * p.bg])!,
            CGColor(colorSpace: colorSpace, components: [180/255, 70/255, 0, 0.025 * p.bg])!,
            CGColor(colorSpace: colorSpace, components: [0, 0, 0, 0])!,
        ] as CFArray
        let locations: [CGFloat] = [0, 0.35, 1]
        guard let gradient = CGGradient(colorsSpace: colorSpace, colors: colors, locations: locations) else { return }
        ctx.drawRadialGradient(gradient, startCenter: CGPoint(x: cx, y: cy), startRadius: R * 0.88,
                               endCenter: CGPoint(x: cx, y: cy), endRadius: R * 1.8, options: [])
    }
}
```

- [ ] **Step 6: Verify the file compiles**

Run: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

- [ ] **Step 7: Commit**

```bash
git add HestiaApp/Shared/Views/Common/WavelengthRenderer.swift
git commit -m "feat(ios): add WavelengthRenderer — CGContext-based 3D geometry, 5-pass glow, 7-layer compositing"
```

---

## ~~Task 2B~~ (REMOVED — CGContext is now the primary renderer in Task 2)

Previously this was a "CGContext fallback." After the second opinion audit confirmed that SwiftUI `GraphicsContext` lacks `drawLayer`, `plusLighter`, and per-pass `blur`, CGContext was promoted to the primary and only rendering path. Task 2B no longer exists.

- [ ] **Step 1: Add a CGContext-based render method that produces a UIImage**

```swift
    // MARK: - CGContext Fallback (for shadow support)

    /// Render the wavelength into a UIImage using CGContext (supports setShadow).
    /// Use this if SwiftUI GraphicsContext glow doesn't match the HTML mockup.
    static func renderToImage(
        size: CGSize,
        scale: CGFloat,
        time: Double,
        params p: WavelengthParams
    ) -> CGImage? {
        let w = Int(size.width * scale)
        let h = Int(size.height * scale)

        guard let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
              let ctx = CGContext(
                  data: nil, width: w, height: h,
                  bitsPerComponent: 8, bytesPerRow: 0,
                  space: colorSpace,
                  bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
              ) else { return nil }

        ctx.scaleBy(x: scale, y: scale)

        let ox = size.width / 2
        let oy = size.height / 2
        let baseR = Double(min(size.width, size.height)) * 0.36
        let R = baseR * (1 + p.pulse)

        let rot = time * p.spd
        let wobX = 0.025 * sin(time * 0.09)
        let wobY = 0.018 * cos(time * 0.07)

        let bandData = WavelengthBand.bands.map { band in
            let pts = greatCircle(band: band, radius: R, rotation: rot, wobbleX: wobX, wobbleY: wobY, params: p, time: time)
            let (front, back) = splitByDepth(pts)
            return (band, front, back)
        }

        // Back arcs
        for (band, _, back) in bandData {
            for arc in back {
                drawArc(in: ctx, centerX: ox, centerY: oy, points: arc,
                        baseWidth: 10 * band.w, brightness: band.b * 0.10, params: p)
            }
        }

        // Front arcs
        for (band, front, _) in bandData {
            for arc in front {
                drawArc(in: ctx, centerX: ox, centerY: oy, points: arc,
                        baseWidth: 10 * band.w, brightness: band.b * 0.95, params: p)
            }
        }

        return ctx.makeImage()
    }
```

- [ ] **Step 2: Commit if used**

```bash
git add HestiaApp/Shared/Views/Common/WavelengthRenderer.swift
git commit -m "feat(ios): add CGContext fallback for wavelength glow fidelity"
```

---

## Task 3: HestiaWavelengthView — SwiftUI Wrapper

**Files:**
- Create: `HestiaApp/Shared/Views/Common/HestiaWavelengthView.swift`

- [ ] **Step 1: Create the SwiftUI view with TimelineView + CGImage rendering**

**IMPORTANT:** Do NOT mutate @State from inside Canvas closures. Use a @StateObject ViewModel
that updates on each TimelineView tick. The renderer produces a CGImage displayed via Image().

```swift
// HestiaWavelengthView.swift
import SwiftUI

// MARK: - ViewModel (owns animation state, updates per frame)

@MainActor
final class WavelengthViewModel: ObservableObject {
    @Published var renderedFrame: CGImage?

    private var currentParams: WavelengthParams?
    private var globalTime: Double = 0
    private var lastTimestamp: TimeInterval = 0

    func update(date: Date, mode: WavelengthMode, audioLevel: CGFloat, size: CGSize) {
        let now = date.timeIntervalSinceReferenceDate
        let dt = lastTimestamp == 0 ? 0.016 : min(0.033, now - lastTimestamp)
        lastTimestamp = now
        globalTime += dt

        let level = Double(audioLevel)
        let target = WavelengthParams.target(for: mode, level: level, time: globalTime)
        let alpha = min(max(dt * 4.0, 0), 1)

        if let current = currentParams {
            currentParams = current.lerped(toward: target, alpha: alpha)
        } else {
            currentParams = target
        }

        guard let p = currentParams else { return }
        renderedFrame = WavelengthRenderer.renderToImage(
            size: size, scale: UIScreen.main.scale,
            time: globalTime, params: p
        )
    }
}

// MARK: - View

struct HestiaWavelengthView: View {
    let mode: WavelengthMode
    var size: CGFloat = 320
    var audioLevel: CGFloat = 0.0

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @StateObject private var viewModel = WavelengthViewModel()

    // Adaptive frame rate: 20fps idle, 30fps active
    private var frameInterval: Double {
        mode == .idle ? 1.0 / 20.0 : 1.0 / 30.0
    }

    private var renderSize: CGSize {
        CGSize(width: size * 1.6, height: size * 1.6)
    }

    var body: some View {
        if reduceMotion {
            staticFallback
        } else {
            animatedWavelength
        }
    }

    // MARK: - Animated View

    private var animatedWavelength: some View {
        TimelineView(.animation(minimumInterval: frameInterval)) { timeline in
            // Update ViewModel on each tick (safe — we're on main, outside Canvas)
            let _ = viewModel.update(date: timeline.date, mode: mode, audioLevel: audioLevel, size: renderSize)

            if let cgImage = viewModel.renderedFrame {
                Image(cgImage, scale: UIScreen.main.scale, label: Text("Hestia wavelength"))
                    .frame(width: renderSize.width, height: renderSize.height)
            } else {
                Color.clear
                    .frame(width: renderSize.width, height: renderSize.height)
            }
        }
    }

    // MARK: - Static Fallback (Reduce Motion)

    private var staticFallback: some View {
        Circle()
            .fill(
                RadialGradient(
                    colors: [
                        Color(red: 1, green: 159/255, blue: 10/255).opacity(0.3),
                        Color(red: 80/255, green: 40/255, blue: 0).opacity(0.15),
                        .clear
                    ],
                    center: .center,
                    startRadius: 0,
                    endRadius: size / 2
                )
            )
            .frame(width: size, height: size)
            .overlay(
                Circle()
                    .strokeBorder(
                        LinearGradient(
                            colors: [
                                Color(red: 1, green: 179/255, blue: 71/255).opacity(0.4),
                                Color(red: 1, green: 159/255, blue: 10/255).opacity(0.2)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ),
                        lineWidth: 2
                    )
            )
    }
}

#if DEBUG
#Preview("Wavelength - Idle") {
    ZStack {
        Color.black
        HestiaWavelengthView(mode: .idle, size: 200)
    }
}

#Preview("Wavelength - Speaking") {
    ZStack {
        Color.black
        HestiaWavelengthView(mode: .speaking, size: 200, audioLevel: 0.6)
    }
}
#endif
```

- [ ] **Step 2: Build and visually verify in Xcode preview**

Run: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

Open Xcode → HestiaWavelengthView.swift → Preview canvas. Compare against `docs/superpowers/specs/chat-ui-orb-mockup.html` in browser. The ribbons should rotate, glow, and breathe similarly.

**If the glow doesn't match:** Execute Task 2B (CGContext fallback), then update this view to use `renderToImage()` and display via `Image(uiImage:)`.

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/Shared/Views/Common/HestiaWavelengthView.swift
git commit -m "feat(ios): add HestiaWavelengthView — TimelineView + Canvas wavelength renderer"
```

---

## Task 4: ChatView Idle State — Centered Wavelength + Greeting

**Files:**
- Create: `HestiaApp/Shared/Views/Chat/ChatIdleView.swift`
- Modify: `HestiaApp/Shared/Views/Chat/ChatView.swift`

- [ ] **Step 1: Create ChatIdleView**

```swift
// ChatIdleView.swift
import SwiftUI

struct ChatIdleView: View {
    let wavelengthMode: WavelengthMode
    let audioLevel: CGFloat
    let greeting: String
    let size: CGFloat

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            HestiaWavelengthView(
                mode: wavelengthMode,
                size: size,
                audioLevel: audioLevel
            )
            .padding(.bottom, -20)

            VStack(spacing: 8) {
                Text(greeting)
                    .font(.system(size: 16, weight: .regular))
                    .foregroundColor(Color(red: 184/255, green: 144/255, blue: 96/255))

                Text("How can I help\nyou today?")
                    .font(.system(size: 28, weight: .bold))
                    .foregroundColor(Color(red: 1, green: 245/255, blue: 230/255))
                    .multilineTextAlignment(.center)
                    .lineSpacing(4)
            }

            Spacer()
            Spacer()
        }
    }
}
```

- [ ] **Step 2: Add conversation state tracking to ChatView**

In `ChatView.swift`, add a computed property to determine if we're in idle vs conversation state. Add near the existing `@State` properties:

```swift
    // Add this computed property
    private var isIdleState: Bool {
        viewModel.messages.isEmpty && !viewModel.isLoading
    }
```

- [ ] **Step 3: Replace the ChatView body with idle/conversation layout**

In `ChatView.swift`, replace the main ZStack body content to conditionally show idle view or conversation view:

```swift
    // Replace the existing body content inside the ZStack, AFTER the background gradient
    // Keep the existing background gradient as-is

    // Use matchedGeometryEffect for smooth size/position morph between idle and conversation
    // Both states render the SAME HestiaWavelengthView — SwiftUI interpolates frame & position

    if isIdleState {
        ChatIdleView(
            wavelengthMode: wavelengthModeForState,
            audioLevel: conversationManager.state == .listening ? CGFloat(voiceViewModel.audioLevel) : 0,
            greeting: greetingText,
            size: 280
        )
        // Apply matchedGeometryEffect to the wavelength INSIDE ChatIdleView
        // (see ChatIdleView implementation — the wavelength has .matchedGeometryEffect(id: "wavelength", in: wavelengthNamespace))
    } else {
        VStack(spacing: 0) {
            // Header wavelength (small) — same matchedGeometryEffect ID for smooth morph
            HestiaWavelengthView(
                mode: wavelengthModeForState,
                size: 60,
                audioLevel: conversationManager.state == .listening ? CGFloat(voiceViewModel.audioLevel) : 0
            )
            .matchedGeometryEffect(id: "wavelength", in: wavelengthNamespace)
            .padding(.top, 60)
            .padding(.bottom, 4)

            Text("Hestia")
                .font(.system(size: 12, weight: .semibold))
                .foregroundColor(Color(red: 184/255, green: 144/255, blue: 96/255))
                .tracking(0.5)

            // Conversation status (replaces VoiceConversationOverlay transcript display)
            if conversationManager.isActive {
                ConversationStatusView(manager: conversationManager)
            }

            // Existing message list ScrollView
            // ... (keep existing code)
        }
    }
```

- [ ] **Step 4: Add helper properties for wavelength state mapping**

```swift
    // Add these computed properties to ChatView

    private var wavelengthModeForState: WavelengthMode {
        if conversationManager.isActive {
            switch conversationManager.state {
            case .idle: return .idle
            case .listening: return .listening
            case .processing: return .thinking
            case .speaking: return .speaking
            }
        }
        if viewModel.isLoading { return .thinking }
        return .idle
    }

    private var greetingText: String {
        let hour = Calendar.current.component(.hour, from: Date())
        let timeOfDay: String
        switch hour {
        case 5..<12: timeOfDay = "Good morning"
        case 12..<17: timeOfDay = "Good afternoon"
        case 17..<22: timeOfDay = "Good evening"
        default: timeOfDay = "Hello"
        }
        return "\(timeOfDay), Boss"
    }
```

- [ ] **Step 5: Animate the idle/conversation transition**

Wrap the `if isIdleState` block in an animation modifier:

```swift
    // Add this modifier to the ZStack containing the idle/conversation views
    .animation(.spring(response: 0.6, dampingFraction: 0.8), value: isIdleState)
```

- [ ] **Step 6: Build and verify**

Run: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

- [ ] **Step 7: Commit**

```bash
git add HestiaApp/Shared/Views/Chat/ChatIdleView.swift HestiaApp/Shared/Views/Chat/ChatView.swift
git commit -m "feat(ios): add idle state with centered wavelength + greeting, conversation morph layout"
```

---

## Task 5: Input Bar Redesign — Tap/Hold Mic

**Files:**
- Modify: `HestiaApp/Shared/Views/Chat/ChatInputBar.swift`
- Modify: `HestiaApp/Shared/Models/ChatInputMode.swift`

- [ ] **Step 1: Simplify ChatInputMode — remove journal, rename to transcription**

Replace the contents of `ChatInputMode.swift`:

```swift
import SwiftUI

enum ChatInputMode: String, CaseIterable {
    case chat
    case transcription  // Was "journal" — single tap mic

    var icon: String {
        switch self {
        case .chat: return "text.bubble"
        case .transcription: return "waveform"
        }
    }

    var placeholder: String {
        switch self {
        case .chat: return "Ask anything..."
        case .transcription: return "Listening..."
        }
    }
}
```

- [ ] **Step 2: Redesign ChatInputBar with tap/hold mic**

Replace the action button section of `ChatInputBar.swift`. Remove the mode cycle button entirely. The input bar becomes: text field + send button (when text) + mic button (when no text).

```swift
    // Replace the action button logic in ChatInputBar body

    // Send button (visible when text is present)
    if !messageText.trimmingCharacters(in: .whitespaces).isEmpty {
        Button(action: { onSend(messageText) }) {
            Image(systemName: "arrow.up.circle.fill")
                .font(.system(size: 32))
                .foregroundColor(Color(red: 1, green: 159/255, blue: 10/255))
        }
        .transition(.scale.combined(with: .opacity))
    }

    // Mic button (tap = transcription, hold 2s = conversation)
    MicHoldButton(
        onTap: onStartTranscription,
        onHold: onStartConversation,
        isActive: isRecording
    )
```

- [ ] **Step 3: Create MicHoldButton as a separate component**

Add to `ChatInputBar.swift` (or create a new file if preferred):

```swift
struct MicHoldButton: View {
    let onTap: () -> Void
    let onHold: () -> Void
    var isActive: Bool = false

    @State private var isHolding = false
    @State private var holdProgress: CGFloat = 0
    @State private var holdTimer: Timer?
    @State private var holdStart: Date?

    private let holdDuration: TimeInterval = 2.0

    var body: some View {
        ZStack {
            // Progress ring (visible during hold)
            Circle()
                .trim(from: 0, to: holdProgress)
                .stroke(Color(red: 1, green: 159/255, blue: 10/255), style: StrokeStyle(lineWidth: 2.5, lineCap: .round))
                .rotationEffect(.degrees(-90))
                .frame(width: 52, height: 52)
                .opacity(isHolding ? 1 : 0)
                .animation(.linear(duration: 0.1), value: holdProgress)

            // Mic icon
            Circle()
                .fill(isActive
                    ? Color(red: 1, green: 159/255, blue: 10/255).opacity(0.35)
                    : Color(red: 1, green: 159/255, blue: 10/255).opacity(0.08))
                .frame(width: 44, height: 44)
                .overlay(
                    Image(systemName: "mic.fill")
                        .font(.system(size: 18))
                        .foregroundColor(
                            isActive
                                ? Color(red: 1, green: 159/255, blue: 10/255)
                                : Color(red: 184/255, green: 144/255, blue: 96/255)
                        )
                )
                .overlay(
                    Circle()
                        .strokeBorder(
                            isActive
                                ? Color(red: 1, green: 159/255, blue: 10/255)
                                : Color(red: 1, green: 159/255, blue: 10/255).opacity(0.15),
                            lineWidth: 1
                        )
                )
                .scaleEffect(isActive ? 1.1 : 1.0)
                .animation(.spring(response: 0.3), value: isActive)
        }
        .gesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in
                    guard !isHolding else { return }
                    isHolding = true
                    holdStart = Date()
                    startHoldTimer()
                }
                .onEnded { _ in
                    let elapsed = Date().timeIntervalSince(holdStart ?? Date())
                    cancelHoldTimer()

                    if elapsed < holdDuration {
                        // Short tap → Transcription Mode
                        let impact = UIImpactFeedbackGenerator(style: .light)
                        impact.impactOccurred()
                        onTap()
                    }
                    // If elapsed >= holdDuration, onHold was already called by the timer

                    isHolding = false
                    holdProgress = 0
                }
        )
    }

    private func startHoldTimer() {
        holdTimer?.invalidate()
        let startTime = Date()
        holdTimer = Timer.scheduledTimer(withTimeInterval: 0.016, repeats: true) { [self] timer in
            let elapsed = Date().timeIntervalSince(startTime)
            let progress = min(elapsed / holdDuration, 1.0)

            DispatchQueue.main.async {
                holdProgress = progress

                if progress >= 1.0 {
                    timer.invalidate()
                    let impact = UIImpactFeedbackGenerator(style: .heavy)
                    impact.impactOccurred()
                    onHold()
                }
            }
        }
    }

    private func cancelHoldTimer() {
        holdTimer?.invalidate()
        holdTimer = nil
    }
}
```

- [ ] **Step 4: Update ChatInputBar callbacks**

Replace the existing `onStartVoice` callback with two:

```swift
// In ChatInputBar, replace:
//   let onStartVoice: () -> Void
// With:
    let onStartTranscription: () -> Void
    let onStartConversation: () -> Void
```

- [ ] **Step 5: Update ChatView to pass the new callbacks**

In `ChatView.swift`, update the ChatInputBar initialization to use the new callbacks:

```swift
    ChatInputBar(
        messageText: $messageText,
        inputMode: $inputMode,
        isInputFocused: $isInputFocused,
        isLoading: viewModel.isLoading,
        isRecording: conversationManager.isActive || voiceViewModel.phase == .recording,
        audioLevel: /* existing audio level */,
        forceLocal: viewModel.forceLocal,
        onSend: { text in sendMessage(text) },
        onToggleLocal: { viewModel.forceLocal.toggle() },
        onStartTranscription: {
            // Start transcription mode (was journal mode)
            voiceViewModel.startRecording()
            inputMode = .transcription
        },
        onStartConversation: {
            // Start conversation mode (was voice mode)
            Task {
                await conversationManager.start()
            }
        }
    )
```

- [ ] **Step 6: Build and verify**

Run: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

- [ ] **Step 7: Commit**

```bash
git add HestiaApp/Shared/Views/Chat/ChatInputBar.swift HestiaApp/Shared/Models/ChatInputMode.swift HestiaApp/Shared/Views/Chat/ChatView.swift
git commit -m "feat(ios): tap mic = transcription, hold 2s = conversation mode"
```

---

## Task 6: Hidden Tab Bar with Swipe-Up Gesture

**Files:**
- Modify: `HestiaApp/Shared/App/ContentView.swift`

- [ ] **Step 1: Hide the default tab bar and add swipe-up gesture**

In `ContentView.swift`, modify `MainTabView` to hide the system tab bar and overlay a custom one:

```swift
struct MainTabView: View {
    @State private var selectedTab = 0
    @State private var showTabBar = false

    var body: some View {
        ZStack(alignment: .bottom) {
            // Content
            Group {
                switch selectedTab {
                case 0: ChatView()
                case 1: MobileCommandView()
                case 2: MobileSettingsView()
                default: ChatView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // Swipe hint bar (always visible when tab bar is hidden)
            if !showTabBar {
                VStack {
                    Spacer()
                    RoundedRectangle(cornerRadius: 3)
                        .fill(Color(red: 184/255, green: 144/255, blue: 96/255).opacity(0.3))
                        .frame(width: 36, height: 5)
                        .padding(.bottom, 8)
                }
                .allowsHitTesting(false)
            }

            // Custom tab bar (slides up from bottom)
            if showTabBar {
                CustomTabBar(selectedTab: $selectedTab, showTabBar: $showTabBar)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .background(Color(red: 2/255, green: 1/255, blue: 1/255))
        .gesture(
            DragGesture(minimumDistance: 40)
                .onEnded { value in
                    let verticalDrag = value.translation.height
                    if verticalDrag < -40 && !showTabBar {
                        withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                            showTabBar = true
                        }
                    } else if verticalDrag > 40 && showTabBar {
                        withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                            showTabBar = false
                        }
                    }
                }
        )
        .onTapGesture {
            if showTabBar {
                withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                    showTabBar = false
                }
            }
        }
    }
}
```

- [ ] **Step 2: Create CustomTabBar component**

Add to `ContentView.swift`:

```swift
struct CustomTabBar: View {
    @Binding var selectedTab: Int
    @Binding var showTabBar: Bool

    private let tabs: [(icon: String, label: String)] = [
        ("message", "Chat"),
        ("square.grid.2x2", "Command"),
        ("gearshape", "Settings"),
    ]

    var body: some View {
        HStack {
            ForEach(0..<tabs.count, id: \.self) { index in
                Button {
                    selectedTab = index
                    withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                        showTabBar = false
                    }
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tabs[index].icon)
                            .font(.system(size: 22))
                        Text(tabs[index].label)
                            .font(.system(size: 10, weight: .medium))
                    }
                    .foregroundColor(
                        selectedTab == index
                            ? Color(red: 1, green: 159/255, blue: 10/255)
                            : Color(red: 184/255, green: 144/255, blue: 96/255)
                    )
                    .opacity(selectedTab == index ? 1 : 0.5)
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(.top, 12)
        .padding(.bottom, 28)
        .background(
            Color(red: 10/255, green: 7/255, blue: 4/255).opacity(0.95)
                .background(.ultraThinMaterial)
        )
        .overlay(
            Rectangle()
                .frame(height: 1)
                .foregroundColor(Color(red: 1, green: 159/255, blue: 10/255).opacity(0.1)),
            alignment: .top
        )
    }
}
```

- [ ] **Step 3: Build and verify**

Run: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

- [ ] **Step 4: Commit**

```bash
git add HestiaApp/Shared/App/ContentView.swift
git commit -m "feat(ios): hide tab bar, swipe up to reveal custom tab bar"
```

---

## Task 7: Fix Conversation Mode Crash

**Files:**
- Modify: `HestiaApp/Shared/Services/VoiceConversationManager.swift`

**Root cause:** Race condition — `ttsService.speak("Hmm...")` fires in `transitionToProcessing()` before `speechService.stopTranscription()` has fully completed. The AVAudioEngine input tap is still active when the synthesizer tries to acquire the audio session.

- [ ] **Step 1: Make the silence handler properly await stopTranscription**

In `VoiceConversationManager.swift`, find the `vad.onSilenceDetected` callback (around line 183). The current code calls `stopTranscription()` and immediately proceeds. Fix by ensuring proper sequencing:

```swift
        vad.onSilenceDetected = { [weak self] in
            Task { @MainActor [weak self] in
                guard let self, self.state == .listening else { return }

                // CRITICAL: Fully await speech recognition shutdown before proceeding
                let transcript = await self.speechService?.stopTranscription() ?? ""
                let trimmed = transcript.trimmingCharacters(in: .whitespacesAndNewlines)

                guard !trimmed.isEmpty else {
                    // No speech detected — return to listening
                    if self.isActive {
                        await self.transitionToListening()
                    }
                    return
                }

                self.currentTranscript = trimmed
                await self.transitionToProcessing(transcript: trimmed)
            }
        }
```

- [ ] **Step 2: Add audio session deactivation/reactivation between listen and speak**

In `transitionToProcessing()`, add explicit audio session reconfiguration before TTS:

```swift
    private func transitionToProcessing(transcript: String) async {
        state = .processing
        vad.stopMonitoring()

        // Deactivate audio session before TTS to prevent conflict
        // Use notification-based handoff instead of arbitrary sleep
        do {
            try AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
            // Reactivate for playback — no arbitrary sleep, the deactivation
            // with .notifyOthersOnDeactivation ensures the system settles
            try AVAudioSession.sharedInstance().setCategory(.playAndRecord, mode: .voiceChat, options: [.defaultToSpeaker, .allowBluetooth])
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            #if DEBUG
            print("[VoiceConversation] Audio session reconfiguration error: \(error)")
            #endif
            // If reconfiguration fails, still attempt TTS — it may work
        }

        // NOW safe to speak
        ttsService.speak("Hmm...")

        await processWithLLM(transcript: transcript)
    }
```

- [ ] **Step 3: Guard against re-entrance in silence detection**

Add a flag to prevent the VAD from firing twice during state transition:

```swift
    // Add property
    private var isTransitioning = false

    // Update silence handler guard
    vad.onSilenceDetected = { [weak self] in
        Task { @MainActor [weak self] in
            guard let self,
                  self.state == .listening,
                  !self.isTransitioning else { return }

            self.isTransitioning = true
            defer { self.isTransitioning = false }

            // ... rest of handler
        }
    }
```

- [ ] **Step 4: Add the same audio session handoff when transitioning back to listening**

In `transitionToListening()`, ensure clean audio session state:

```swift
    private func transitionToListening() async {
        // Stop any ongoing TTS
        ttsService.stop()

        // Reconfigure audio session for recording
        do {
            try AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
            try await Task.sleep(nanoseconds: 50_000_000) // 50ms
            try AVAudioSession.sharedInstance().setCategory(.playAndRecord, mode: .voiceChat, options: [.defaultToSpeaker, .allowBluetooth])
            try AVAudioSession.sharedInstance().setActive(true)
        } catch {
            #if DEBUG
            print("[VoiceConversation] Audio session reconfiguration error: \(error)")
            #endif
        }

        state = .listening
        currentTranscript = ""
        currentResponse = ""

        // Restart speech recognition
        guard let speechService else { return }
        setupSpeechCallbacks()
        await speechService.startTranscription()
        vad.startMonitoring(speechService: speechService)
    }
```

- [ ] **Step 5: Build and verify**

Run: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

- [ ] **Step 6: Commit**

```bash
git add HestiaApp/Shared/Services/VoiceConversationManager.swift
git commit -m "fix(ios): conversation mode crash — await stopTranscription before TTS, add audio session handoff"
```

---

## Task 8: Remove VoiceConversationOverlay & Old Orb

**Files:**
- Delete: `HestiaApp/Shared/Views/Chat/VoiceConversationOverlay.swift`
- Modify: `HestiaApp/Shared/Views/Chat/ChatView.swift` (remove overlay references)
- Modify: Any file referencing `HestiaOrbView` → replace with `HestiaWavelengthView`

- [ ] **Step 1: Remove VoiceConversationOverlay from ChatView**

In `ChatView.swift`, remove the `VoiceConversationOverlay` ZStack layer and the `showConversationOverlay` state. Conversation mode now displays inline — the wavelength in the idle/header view reacts to `conversationManager.state`.

```swift
// Remove these:
// @State var showConversationOverlay: Bool = false
// VoiceConversationOverlay(manager: conversationManager, onStop: { ... })
```

- [ ] **Step 2: Delete VoiceConversationOverlay.swift**

```bash
git rm HestiaApp/Shared/Views/Chat/VoiceConversationOverlay.swift
```

- [ ] **Step 3: Search for remaining HestiaOrbView references**

Run: `grep -r "HestiaOrbView" HestiaApp/ --include="*.swift" -l`

For each file found, replace `HestiaOrbView` with `HestiaWavelengthView` and update the state mapping:
- `HestiaOrbState.idle` → `WavelengthMode.idle`
- `HestiaOrbState.thinking` → `WavelengthMode.thinking`
- `HestiaOrbState.success` → `WavelengthMode.speaking`
- `HestiaOrbState.listening` → `WavelengthMode.listening`

- [ ] **Step 4: Remove HestiaOrbView.swift (after all references are updated)**

```bash
git rm HestiaApp/Shared/Views/Common/HestiaOrbView.swift
```

- [ ] **Step 5: Build both targets**

Run:
```bash
xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build 2>&1 | tail -5
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5
```
Expected: Both BUILD SUCCEEDED

**Note:** If macOS target also used `HestiaOrbView`, those references need updating too. Check `macOS/Views/` for any orb usage.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(ios): remove VoiceConversationOverlay and HestiaOrbView, replace with wavelength"
```

---

## Task 9: Visual Fidelity Tuning

**Files:**
- Modify: `HestiaApp/Shared/Views/Common/WavelengthRenderer.swift`
- Modify: `HestiaApp/Shared/Views/Common/HestiaWavelengthView.swift`

This task is iterative — run the app, compare against the HTML mockup, and adjust.

- [ ] **Step 1: Side-by-side comparison**

Open `docs/superpowers/specs/chat-ui-orb-mockup.html` in browser and the iOS Simulator side-by-side. Check:
1. Ribbon width and glow radius match
2. Rotation speed feels similar
3. Color temperature (warmth) matches
4. Depth ordering (front/back) is correct
5. Sphere fill darkness matches
6. Idle breathing rhythm matches

- [ ] **Step 2: Adjust constants if needed**

Common tuning areas:
- `baseR` in `render()` — controls overall size relative to frame
- Band `w` values — controls ribbon width
- Glow pass alpha multipliers — controls bloom intensity
- `frameInterval` — if animation feels choppy, reduce to `1.0 / 30.0` for idle too
- Background gradient opacity — if too dim/bright vs mockup

- [ ] **Step 3: Test on physical device**

Run on a real iPhone to verify:
- Frame rate is smooth (no drops below 30fps)
- Battery impact is acceptable (check CPU/GPU usage in Instruments)
- Colors look correct on OLED display (may need slight adjustments vs LCD simulator)

- [ ] **Step 4: Commit any tuning changes**

```bash
git add HestiaApp/Shared/Views/Common/WavelengthRenderer.swift HestiaApp/Shared/Views/Common/HestiaWavelengthView.swift
git commit -m "style(ios): tune wavelength visual fidelity to match HTML mockup"
```

---

## Task 10: Integration Test & Cleanup

- [ ] **Step 1: Full flow test**

Test the complete flow on simulator:
1. App opens → idle state with wavelength + greeting visible
2. Type a message → wavelength morphs to header, messages appear
3. Receive response → wavelength pulses during thinking, settles after
4. Tap mic → transcription mode activates (wavelength shifts to listening)
5. Hold mic 2s → conversation mode activates (wavelength shifts to speaking, no crash)
6. Swipe up → tab bar appears
7. Tap Command tab → switches to Command view, tab bar hides
8. Swipe up → tab bar appears, tap Chat → returns to chat
9. Click header wavelength or wait → returns to idle state when messages empty

- [ ] **Step 2: Remove old voice mode references**

Search for any remaining references to `.voice` or `.journal` input modes:
```bash
grep -r "\.voice\b\|\.journal\b\|ChatInputMode\.voice\|ChatInputMode\.journal\|VoiceConversationOverlay\|HestiaOrbView\|HestiaOrbState" HestiaApp/ --include="*.swift"
```
Fix any remaining references.

- [ ] **Step 3: Update project.yml if needed**

If `project.yml` explicitly lists source files, ensure:
- New files are included: `WavelengthState.swift`, `WavelengthRenderer.swift`, `HestiaWavelengthView.swift`, `ChatIdleView.swift`
- Removed files are excluded: `HestiaOrbView.swift`, `VoiceConversationOverlay.swift`

- [ ] **Step 4: Final build both targets**

```bash
xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build 2>&1 | tail -5
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore(ios): cleanup old orb/voice mode references, verify full integration"
```

---

## Estimated Effort (Revised after second opinion)

| Task | Hours | Risk | Notes |
|------|-------|------|-------|
| 1: WavelengthState | 1h | Low | Math/state — unchanged |
| 2: WavelengthRenderer (CGContext) | 5-7h | **High** | CGContext is primary — `setShadow`, `plusLighter`, `beginTransparencyLayer` |
| 3: HestiaWavelengthView | 2-3h | Medium | @StateObject ViewModel, CGImage display, no @State in Canvas |
| 4: Chat idle/morph + ConversationStatusView | 4-5h | Medium | `matchedGeometryEffect` morph, new ConversationStatusView |
| 5: Tap/hold mic | 2-3h | Medium | SwiftUI animation (not Timer), haptics |
| 6: Hidden tab bar | 2-3h | Medium | Swipe gesture scoped to bottom 60px |
| 7: Crash fix | 2-3h | Medium | Notification-based audio handoff, re-entrance guard |
| 8: Remove old code | 1-2h | Low | HestiaOrbView, VoiceConversationOverlay, macOS refs |
| 9: Visual tuning | 3-4h | Medium | Side-by-side with HTML mockup, device testing |
| 10: Integration test | 2-3h | Low | Full flow verification |
| **Total** | **24-34h** | | |

**Critical path:** Tasks 1 → 2 → 3 → 4 (wavelength must render before it can be placed in the layout). Tasks 5, 6, 7 are independent and can be parallelized.

**Key corrections from second opinion:**
- CGContext is the PRIMARY renderer (SwiftUI GraphicsContext lacks required APIs)
- @State is NEVER mutated from inside Canvas — use @StateObject ViewModel
- `matchedGeometryEffect` for idle→conversation morph (not opacity crossfade)
- `ConversationStatusView` replaces VoiceConversationOverlay transcript display
- Audio session handoff uses notification-based approach (not 50ms sleep)
- Swipe-up gesture scoped to bottom 60px to avoid ScrollView conflicts
