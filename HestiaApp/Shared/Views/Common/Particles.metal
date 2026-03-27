// Particles.metal
// HestiaApp
//
// Vertex + fragment shaders for the wavelength particle renderer.
// Uses instanced quads with per-particle data (position, size, alpha, color).
// Additive blending configured on the pipeline, not in the shader.

#include <metal_stdlib>
using namespace metal;

// Must match ParticleGPUData in MetalParticleRenderer.swift
struct ParticleInstance {
    float2 position;   // screen-space position (points)
    float  size;       // draw size (points)
    float  alpha;      // 0-1 final alpha
    uint   texIndex;   // index into texture array (colorIdx * 2 + isHero)
};

struct Uniforms {
    float2 viewportSize;  // width, height in points
};

struct VertexOut {
    float4 position [[position]];
    float2 texCoord;
    float  alpha;
    uint   texIndex;
};

// Unit quad vertices: 6 vertices forming 2 triangles
constant float2 quadPositions[6] = {
    float2(-0.5, -0.5), float2( 0.5, -0.5), float2( 0.5,  0.5),
    float2(-0.5, -0.5), float2( 0.5,  0.5), float2(-0.5,  0.5),
};

constant float2 quadTexCoords[6] = {
    float2(0, 1), float2(1, 1), float2(1, 0),
    float2(0, 1), float2(1, 0), float2(0, 0),
};

vertex VertexOut particleVertex(
    uint vertexID [[vertex_id]],
    uint instanceID [[instance_id]],
    const device ParticleInstance* particles [[buffer(0)]],
    constant Uniforms& uniforms [[buffer(1)]]
) {
    ParticleInstance p = particles[instanceID];

    // Scale unit quad by particle size, offset by position
    float2 pos = quadPositions[vertexID] * p.size + p.position;

    // Convert from screen points to normalized device coordinates (-1 to 1)
    float2 ndc;
    ndc.x = (pos.x / uniforms.viewportSize.x) * 2.0 - 1.0;
    ndc.y = 1.0 - (pos.y / uniforms.viewportSize.y) * 2.0;  // flip Y

    VertexOut out;
    out.position = float4(ndc, 0.0, 1.0);
    out.texCoord = quadTexCoords[vertexID];
    out.alpha = p.alpha;
    out.texIndex = p.texIndex;
    return out;
}

fragment float4 particleFragment(
    VertexOut in [[stage_in]],
    texture2d_array<float> texArray [[texture(0)]]
) {
    constexpr sampler texSampler(mag_filter::linear, min_filter::linear);
    float4 color = texArray.sample(texSampler, in.texCoord, in.texIndex);
    color.a *= in.alpha;
    // RGB premultiplied by alpha for correct additive blending
    color.rgb *= in.alpha;
    return color;
}
