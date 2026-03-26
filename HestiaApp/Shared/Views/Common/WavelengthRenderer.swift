// WavelengthRenderer.swift
// HestiaApp
//
// Pure CGContext rendering engine for Wavelength orb visualization.
// Produces a CGImage per frame using UIGraphicsImageRenderer (iOS only).

#if os(iOS)
import UIKit
#else
import AppKit
#endif

// MARK: - Wavelength Renderer

struct WavelengthRenderer {

    // MARK: - Great Circle Generation

    /// Generate 101 points along a great circle on a sphere with multi-frequency waviness.
    static func greatCircle(
        band: WavelengthBand,
        radius: Double,
        rotation: Double,
        wobbleX: Double,
        wobbleY: Double,
        params: WavelengthParams,
        time: Double
    ) -> [WavelengthPoint] {
        let count = 101
        let wAmp = radius * params.wave
        let wSpd = params.wSpd
        let (f1, f2, f3) = band.wv

        var points: [WavelengthPoint] = []
        points.reserveCapacity(count)

        for i in 0..<count {
            let u = Double(i) / Double(count - 1)
            let a = u * .pi * 2.0 + rotation + band.off

            // Start on flat circle
            var x = cos(a) * radius
            var y = sin(a) * radius
            var z = 0.0

            // 3 Z-waves for vertical displacement
            z += sin(u * .pi * 2.0 * f1 + time * wSpd * 1.3) * wAmp * 1.0
            z += sin(u * .pi * 2.0 * f2 + time * wSpd * 0.7) * wAmp * 0.5
            z += sin(u * .pi * 2.0 * f3 + time * wSpd * 1.1) * wAmp * 0.22

            // 2 Y-waves for lateral meander
            y += sin(u * .pi * 2.0 * f1 * 0.8 + time * wSpd * 0.9) * wAmp * 0.6
            y += sin(u * .pi * 2.0 * f2 * 1.2 + time * wSpd * 0.5) * wAmp * 0.25

            // Rotate around X axis (tilt X)
            let tiltX = band.tx + wobbleX
            let cosX = cos(tiltX)
            let sinX = sin(tiltX)
            let y1 = y * cosX - z * sinX
            let z1 = y * sinX + z * cosX
            y = y1
            z = z1

            // Rotate around Y axis (tilt Y)
            let tiltY = band.ty + wobbleY
            let cosY = cos(tiltY)
            let sinY = sin(tiltY)
            let x1 = x * cosY + z * sinY
            let z2 = -x * sinY + z * cosY
            x = x1
            z = z2

            // Normalize back onto sphere surface
            let len = sqrt(x * x + y * y + z * z)
            if len > 0 {
                let scale = radius / len
                x *= scale
                y *= scale
                z *= scale
            }

            // Depth: 0 = far, 1 = near
            let depth = (z / radius + 1.0) * 0.5

            points.append(WavelengthPoint(x: x, y: y, z: z, depth: depth))
        }

        return points
    }

    // MARK: - Depth Splitting

    /// Split path into contiguous arcs where z >= 0 (front) and z < 0 (back).
    static func splitByDepth(
        _ points: [WavelengthPoint]
    ) -> (front: [[WavelengthPoint]], back: [[WavelengthPoint]]) {
        var front: [[WavelengthPoint]] = []
        var back: [[WavelengthPoint]] = []
        var currentArc: [WavelengthPoint] = []
        var currentIsFront = true

        for point in points {
            let isFront = point.z >= 0
            if currentArc.isEmpty {
                currentIsFront = isFront
                currentArc.append(point)
            } else if isFront == currentIsFront {
                currentArc.append(point)
            } else {
                // Transition — close current arc and start new one
                if currentArc.count >= 2 {
                    if currentIsFront {
                        front.append(currentArc)
                    } else {
                        back.append(currentArc)
                    }
                }
                currentArc = [point]
                currentIsFront = isFront
            }
        }

        // Close final arc
        if currentArc.count >= 2 {
            if currentIsFront {
                front.append(currentArc)
            } else {
                back.append(currentArc)
            }
        }

        return (front, back)
    }

    // MARK: - Path Tracing (Catmull-Rom)

    /// Catmull-Rom to cubic bezier smooth path.
    static func tracePath(
        points: [WavelengthPoint],
        centerX cx: CGFloat,
        centerY cy: CGFloat
    ) -> CGPath {
        let path = CGMutablePath()
        guard points.count >= 2 else { return path }

        path.move(to: CGPoint(x: cx + points[0].x, y: cy + points[0].y))

        for i in 0..<(points.count - 1) {
            let p0 = i > 0 ? points[i - 1] : points[i]
            let p1 = points[i]
            let p2 = points[i + 1]
            let p3 = (i + 2 < points.count) ? points[i + 2] : points[i + 1]

            // Control points at 1/6 of segment
            let cp1x = CGFloat(p1.x) + CGFloat(p2.x - p0.x) / 6.0
            let cp1y = CGFloat(p1.y) + CGFloat(p2.y - p0.y) / 6.0
            let cp2x = CGFloat(p2.x) - CGFloat(p3.x - p1.x) / 6.0
            let cp2y = CGFloat(p2.y) - CGFloat(p3.y - p1.y) / 6.0

            path.addCurve(
                to: CGPoint(x: cx + p2.x, y: cy + p2.y),
                control1: CGPoint(x: cx + cp1x, y: cy + cp1y),
                control2: CGPoint(x: cx + cp2x, y: cy + cp2y)
            )
        }

        return path
    }

    // MARK: - Arc Drawing (5-pass glow)

    /// Draw a single arc with 5 glow passes, darkest/widest to brightest/thinnest.
    static func drawArc(
        in ctx: CGContext,
        centerX cx: CGFloat,
        centerY cy: CGFloat,
        points: [WavelengthPoint],
        baseWidth: CGFloat,
        brightness: CGFloat,
        params: WavelengthParams
    ) {
        let path = tracePath(points: points, centerX: cx, centerY: cy)
        let w = baseWidth * CGFloat(params.bw)
        let b = min(max(brightness * CGFloat(params.glow), 0), 6)

        // Pass 1: outermost glow with shadow
        ctx.saveGState()
        ctx.setShadow(
            offset: .zero,
            blur: w * 12,
            color: UIColor(red: 255/255, green: 90/255, blue: 0, alpha: 0.09 * b).cgColor
        )
        ctx.setStrokeColor(UIColor(red: 155/255, green: 50/255, blue: 0, alpha: 0.055 * b).cgColor)
        ctx.setLineWidth(w * 7)
        ctx.setLineCap(.round)
        ctx.setLineJoin(.round)
        ctx.addPath(path)
        ctx.strokePath()
        ctx.restoreGState()

        // Pass 2: mid glow with shadow
        ctx.saveGState()
        ctx.setShadow(
            offset: .zero,
            blur: w * 6,
            color: UIColor(red: 255/255, green: 105/255, blue: 0, alpha: 0.10 * b).cgColor
        )
        ctx.setStrokeColor(UIColor(red: 255/255, green: 115/255, blue: 5/255, alpha: 0.13 * b).cgColor)
        ctx.setLineWidth(w * 3.5)
        ctx.setLineCap(.round)
        ctx.setLineJoin(.round)
        ctx.addPath(path)
        ctx.strokePath()
        ctx.restoreGState()

        // Pass 3: core warm
        ctx.setStrokeColor(UIColor(red: 255/255, green: 168/255, blue: 38/255, alpha: 0.32 * b).cgColor)
        ctx.setLineWidth(w * 1.7)
        ctx.setLineCap(.round)
        ctx.setLineJoin(.round)
        ctx.addPath(path)
        ctx.strokePath()

        // Pass 4: bright center
        ctx.setStrokeColor(UIColor(red: 255/255, green: 212/255, blue: 125/255, alpha: 0.52 * b).cgColor)
        ctx.setLineWidth(w * 0.7)
        ctx.setLineCap(.round)
        ctx.setLineJoin(.round)
        ctx.addPath(path)
        ctx.strokePath()

        // Pass 5: white-hot core
        ctx.setStrokeColor(UIColor(red: 255/255, green: 248/255, blue: 228/255, alpha: 0.40 * b).cgColor)
        ctx.setLineWidth(w * 0.22)
        ctx.setLineCap(.round)
        ctx.setLineJoin(.round)
        ctx.addPath(path)
        ctx.strokePath()
    }

    // MARK: - 7-Layer Compositing

    #if os(iOS)
    /// Render a complete Wavelength frame to CGImage.
    static func renderToImage(
        size: CGSize,
        scale: CGFloat,
        time: Double,
        params: WavelengthParams
    ) -> CGImage? {
        let width = size.width
        let height = size.height
        let cx = width * 0.5
        let cy = height * 0.5
        let baseR = min(width, height) * 0.36
        let R = baseR * (1.0 + CGFloat(params.pulse))
        let rotation = time * params.spd
        let wobX = 0.025 * sin(time * 0.09)
        let wobY = 0.018 * cos(time * 0.07)

        // Generate geometry for all bands
        var allFront: [([WavelengthPoint], WavelengthBand)] = []
        var allBack: [([WavelengthPoint], WavelengthBand)] = []

        for band in WavelengthBand.bands {
            let pts = greatCircle(
                band: band,
                radius: Double(R),
                rotation: rotation,
                wobbleX: wobX,
                wobbleY: wobY,
                params: params,
                time: time
            )
            let split = splitByDepth(pts)
            for arc in split.front {
                allFront.append((arc, band))
            }
            for arc in split.back {
                allBack.append((arc, band))
            }
        }

        let format = UIGraphicsImageRendererFormat()
        format.scale = scale
        format.opaque = false

        let renderer = UIGraphicsImageRenderer(size: size, format: format)

        let image = renderer.image { rendererCtx in
            let ctx = rendererCtx.cgContext

            // ── Layer 1: Background radial glow ──
            let bgAlpha = CGFloat(params.bg)
            let colorSpace = CGColorSpaceCreateDeviceRGB()

            let bgColors: [CGFloat] = [
                255/255, 159/255, 10/255, 0.07 * bgAlpha,
                139/255, 69/255, 19/255, 0.03 * bgAlpha,
                0, 0, 0, 0
            ]
            let bgLocations: [CGFloat] = [0.0, 0.4, 1.0]
            if let bgGrad = CGGradient(colorSpace: colorSpace, colorComponents: bgColors, locations: bgLocations, count: 3) {
                ctx.drawRadialGradient(
                    bgGrad,
                    startCenter: CGPoint(x: cx, y: cy),
                    startRadius: 0,
                    endCenter: CGPoint(x: cx, y: cy),
                    endRadius: R * 2.5,
                    options: []
                )
            }

            // ── Layer 2: Back arcs (10% brightness) ──
            ctx.saveGState()
            ctx.setBlendMode(.plusLighter)
            for (arc, band) in allBack {
                drawArc(
                    in: ctx,
                    centerX: cx,
                    centerY: cy,
                    points: arc,
                    baseWidth: CGFloat(band.w) * 2.0,
                    brightness: CGFloat(band.b) * 0.10,
                    params: params
                )
            }
            ctx.restoreGState()

            // ── Layer 3: Sphere fill ──
            let sphAlpha = CGFloat(params.sph)
            let sphereColors: [CGFloat] = [
                28/255, 16/255, 5/255, 1.0 * sphAlpha,
                2/255, 1/255, 0, 1.0 * sphAlpha
            ]
            let sphereLocations: [CGFloat] = [0.0, 1.0]
            if let sphereGrad = CGGradient(colorSpace: colorSpace, colorComponents: sphereColors, locations: sphereLocations, count: 2) {
                ctx.saveGState()
                let spherePath = CGPath(
                    ellipseIn: CGRect(x: cx - R, y: cy - R, width: R * 2, height: R * 2),
                    transform: nil
                )
                ctx.addPath(spherePath)
                ctx.clip()
                // Offset center for 3D lighting
                let offsetCX = cx - R * 0.1
                let offsetCY = cy - R * 0.16
                ctx.drawRadialGradient(
                    sphereGrad,
                    startCenter: CGPoint(x: offsetCX, y: offsetCY),
                    startRadius: 0,
                    endCenter: CGPoint(x: cx, y: cy),
                    endRadius: R,
                    options: []
                )
                ctx.restoreGState()
            }

            // ── Layer 4: Rim highlight ──
            let rimWidth: CGFloat = 2.0 + CGFloat(params.glow) * 0.3
            let rimPath = CGPath(
                ellipseIn: CGRect(x: cx - R, y: cy - R, width: R * 2, height: R * 2),
                transform: nil
            )
            ctx.saveGState()
            ctx.addPath(rimPath)
            ctx.setLineWidth(rimWidth)
            ctx.replacePathWithStrokedPath()
            ctx.clip()

            let rimColors: [CGFloat] = [
                255/255, 180/255, 60/255, 0.35 * CGFloat(params.rim),
                255/255, 120/255, 20/255, 0.08 * CGFloat(params.rim),
                255/255, 80/255, 10/255, 0.0
            ]
            let rimLocations: [CGFloat] = [0.0, 0.5, 1.0]
            if let rimGrad = CGGradient(colorSpace: colorSpace, colorComponents: rimColors, locations: rimLocations, count: 3) {
                ctx.drawLinearGradient(
                    rimGrad,
                    start: CGPoint(x: cx - R, y: cy - R),
                    end: CGPoint(x: cx + R, y: cy + R),
                    options: []
                )
            }
            ctx.restoreGState()

            // ── Layer 5: Front arcs (95% brightness) + depth mask ──
            ctx.saveGState()
            ctx.setBlendMode(.plusLighter)
            ctx.beginTransparencyLayer(auxiliaryInfo: nil)

            for (arc, band) in allFront {
                drawArc(
                    in: ctx,
                    centerX: cx,
                    centerY: cy,
                    points: arc,
                    baseWidth: CGFloat(band.w) * 2.0,
                    brightness: CGFloat(band.b) * 0.95,
                    params: params
                )
            }

            // Depth mask via destinationIn blend + radial gradient
            ctx.setBlendMode(.destinationIn)
            let maskColors: [CGFloat] = [
                1, 1, 1, 1.0,
                1, 1, 1, 0.06
            ]
            let maskLocations: [CGFloat] = [0.0, 1.0]
            if let maskGrad = CGGradient(colorSpace: colorSpace, colorComponents: maskColors, locations: maskLocations, count: 2) {
                ctx.drawRadialGradient(
                    maskGrad,
                    startCenter: CGPoint(x: cx, y: cy),
                    startRadius: 0,
                    endCenter: CGPoint(x: cx, y: cy),
                    endRadius: R * 1.4,
                    options: []
                )
            }

            ctx.endTransparencyLayer()
            ctx.restoreGState()

            // ── Layer 6: Specular highlight ──
            let specCX = cx + R * 0.28
            let specCY = cy - R * 0.32
            let specR = R * 0.35
            let specColors: [CGFloat] = [
                1, 1, 1, 0.18 * CGFloat(params.glow),
                1, 1, 0.9, 0.0
            ]
            let specLocations: [CGFloat] = [0.0, 1.0]
            if let specGrad = CGGradient(colorSpace: colorSpace, colorComponents: specColors, locations: specLocations, count: 2) {
                ctx.saveGState()
                // Clip to ellipse for specular shape
                let specRect = CGRect(
                    x: specCX - specR,
                    y: specCY - specR * 0.7,
                    width: specR * 2,
                    height: specR * 1.4
                )
                ctx.addEllipse(in: specRect)
                ctx.clip()
                ctx.drawRadialGradient(
                    specGrad,
                    startCenter: CGPoint(x: specCX, y: specCY),
                    startRadius: 0,
                    endCenter: CGPoint(x: specCX, y: specCY),
                    endRadius: specR,
                    options: []
                )
                ctx.restoreGState()
            }

            // ── Layer 7: Atmosphere halo ──
            let haloColors: [CGFloat] = [
                255/255, 140/255, 20/255, 0.0,
                255/255, 100/255, 10/255, 0.06 * CGFloat(params.bloom),
                255/255, 60/255, 0, 0.0
            ]
            let haloLocations: [CGFloat] = [0.0, 0.45, 1.0]
            if let haloGrad = CGGradient(colorSpace: colorSpace, colorComponents: haloColors, locations: haloLocations, count: 3) {
                ctx.drawRadialGradient(
                    haloGrad,
                    startCenter: CGPoint(x: cx, y: cy),
                    startRadius: R * 0.88,
                    endCenter: CGPoint(x: cx, y: cy),
                    endRadius: R * 1.8,
                    options: []
                )
            }
        }

        return image.cgImage
    }
    #else
    /// macOS stub — wavelength renderer is iOS-only for now.
    static func renderToImage(
        size: CGSize,
        scale: CGFloat,
        time: Double,
        params: WavelengthParams
    ) -> CGImage? {
        return nil
    }
    #endif
}
