// Renders the world-space stern-wave field for USVWakeField.cs:
//   R = water surface height from all boat wakes (m)
//   G = wake foam coverage 0..1 (turbulent stern wash + whitecapping crests)
// The Kelvin height formula must stay identical to USVWakeField.KelvinHeight().
Shader "Hidden/USV/WakeField"
{
    SubShader
    {
        Cull Off ZWrite Off ZTest Always

        Pass
        {
            CGPROGRAM
            #pragma vertex vert_img
            #pragma fragment frag
            #pragma target 3.5
            #include "UnityCG.cginc"

            #define MAX_BOATS 4
            #define TRACK_POINTS 96
            #define GRAVITY 9.81
            #define CUSP_TAN 0.35355339

            float4 _usvTrack[MAX_BOATS * TRACK_POINTS]; // xy = world xz, z = distance along track from hull
            float4 _usvBoat[MAX_BOATS];                 // x = point count, y = speed U, z = hull length L, w = beam B
            float4 _usvBoatAmp[MAX_BOATS];              // x = amplitude A0
            int _usvBoatCount;
            float4 _usvWakeRect;                        // x0, z0, size, 1/size

            float HullFilter(float kL)
            {
                kL = min(kL, 20.0);
                return (kL / 1.5) * exp(0.5 - kL * kL / 4.5);
            }

            float KelvinHeight(float s, float y, float U, float L, float B, float A0, float trackLength)
            {
                if (s <= 0.0 || U < 0.5) return 0.0;
                float ay = abs(y);
                float k0 = GRAVITY / (U * U);
                float r = sqrt(s * s + ay * ay);
                float t = ay / s;
                float tc = min(t, CUSP_TAN);
                float D = sqrt(saturate(1.0 - 8.0 * tc * tc));
                float tq = max(t, 1e-4);
                float eta = 0.0;
                [unroll]
                for (int br = -1; br <= 1; br += 2)
                {
                    float tanTh = (1.0 + br * D) / (4.0 * tq);
                    if (br < 0 && t < 1e-4) tanTh = t;
                    float cos2 = 1.0 / (1.0 + tanTh * tanTh);
                    float k = k0 / cos2;
                    float cosTh = sqrt(cos2);
                    float sinTh = tanTh * cosTh;
                    float phase = k * (s * cosTh - ay * sinTh);
                    float amp = HullFilter(k * L) * sqrt(L / max(r, 0.5 * L)) / sqrt(max(D, 0.25));
                    eta += amp * cos(phase + br * 0.7853982);
                }
                float edge = saturate((CUSP_TAN * 1.08 - t) / (CUSP_TAN * 0.16));
                float ramp = saturate(s / (1.5 * L));
                ramp *= ramp;
                float fade = exp(-s / (U * 25.0));
                float tail = saturate((trackLength - s) / 20.0);
                // Finite-hull transom shoulder crest and adjacent trough.
                float d = max(s - 0.35 * L, 0.0);
                float froude = U / sqrt(GRAVITY * L);
                float arm = 0.45 * B + d * clamp(0.65 / froude, 0.16, CUSP_TAN);
                float width = 0.4 * B + 0.018 * d;
                float q = (ay - arm) / max(width, 0.4);
                float onset = saturate(d / (0.4 * L));
                onset = onset * onset * (3.0 - 2.0 * onset);
                float shoulder = 0.9 * (1.0 - q*q) * exp(-0.5*q*q - d / (6.0*L)) * onset;
                return A0 * (eta * edge * ramp * fade + shoulder) * tail;
            }

            float WashFoam(float s, float y, float U, float L, float B, float eta, float A0)
            {
                if (s < -0.3 * L || U < 0.8) return 0.0;
                // Turbulent white water starts at the transom about one beam wide,
                // widens slowly and decays over ~2.5 s of travel (~45 m at cruise).
                float sp = max(s - 0.5 * L, 0.0);
                float w = B * 0.45 + 0.025 * sp;
                float wash = exp(-(y * y) / (w * w)) * exp(-sp / (U * 1.8));
                // Whitecaps on the steep near-field divergent crests: thin lines along the V arms.
                float caps = saturate((eta / max(A0, 1e-3) - 0.45) * 2.5) * exp(-max(s, 0.0) / (U * 1.8));
                return saturate(max(wash, 0.8 * caps) * saturate((U - 0.8) / 4.0));
            }

            float4 frag(v2f_img i) : SV_Target
            {
                float2 p = _usvWakeRect.xy + i.uv * _usvWakeRect.z;
                float eta = 0.0;
                float foam = 0.0;

                [loop]
                for (int b = 0; b < _usvBoatCount; b++)
                {
                    int n = (int)_usvBoat[b].x;
                    float U = _usvBoat[b].y;
                    float L = _usvBoat[b].z;
                    float B = _usvBoat[b].w;
                    float A0 = _usvBoatAmp[b].x;
                    if (n < 2) continue;
                    int base = b * TRACK_POINTS;
                    float trackLength = _usvTrack[base + n - 1].z;

                    float2 hull = _usvTrack[base].xy;
                    float reach = trackLength + 30.0;
                    if (dot(p - hull, p - hull) > reach * reach) continue;

                    // Nearest point on the recorded track → (s along, y abeam).
                    float best = 1e20;
                    float s = 0.0;
                    [loop]
                    for (int k = 0; k < n - 1; k++)
                    {
                        float2 a = _usvTrack[base + k].xy;
                        float2 d = _usvTrack[base + k + 1].xy - a;
                        float t = saturate(dot(p - a, d) / max(dot(d, d), 1e-4));
                        float2 q = a + d * t;
                        float dist2 = dot(p - q, p - q);
                        if (dist2 < best)
                        {
                            best = dist2;
                            s = lerp(_usvTrack[base + k].z, _usvTrack[base + k + 1].z, t);
                        }
                    }
                    float y = sqrt(best);

                    // Ahead of the transom the nearest point is the hull itself.
                    if (s <= 0.0)
                    {
                        float2 ahead = p - hull;
                        s = -length(ahead);
                        y = 0.0;
                    }

                    float h = KelvinHeight(s, y, U, L, B, A0, trackLength);
                    eta += h;
                    foam = max(foam, WashFoam(s, y, U, L, B, h, A0) * saturate((trackLength - s) / 20.0));
                }
                return float4(eta, foam, 0, 0);
            }
            ENDCG
        }
    }
}
