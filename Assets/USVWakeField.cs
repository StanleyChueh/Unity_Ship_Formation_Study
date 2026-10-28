using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// World-space stern-wave (Kelvin wake) height field shared by rendering and
/// physics, so the wake both deforms the visible water and moves the boats.
///
/// Model: linear Kelvin ship-wave pattern by stationary phase. At a point a
/// distance s behind a hull and y abeam (angle φ, tanφ = |y|/s), two wave
/// systems exist whose propagation angle θ satisfies
///     tanφ = tanθ / (1 + 2 tan²θ)          (none beyond the 19.47° cusp)
/// with deep-water wavenumber k = g / (U² cos²θ). Each contributes
///     A0 · F(kL) · sqrt(L / r) · cos(k (s cosθ - |y| sinθ) ± π/4),
/// where F(kL) is a pressure-patch hull filter peaking at kL ≈ 1.5. The filter
/// is what narrows the visible V of small fast hulls (Rabaud & Moisy 2013):
/// leader ~4.6 m at 18 m/s → Fr ≈ 2.7, crests concentrate near 9-15°.
/// The turbulent stern wash is a foam channel ~1 beam wide that widens and
/// fades over ~2 s; steep crests near the hull whitecap.
/// A finite-width crest/trough pair models the near-field transom shoulders;
/// this is a tunable approximation, not a hydrodynamic hull solver.
///
/// Positions are measured along each boat's recorded track, so the wake
/// follows curved paths.
///
/// Consumers:
///   - GPU: renders _usvWakeTex (R = height m, G = foam 0..1) around the
///     formation every frame; SuimonoFunctionLibrary.cginc displaces the
///     water vertices, tilts the shading normals and adds foam from it.
///   - CPU: SampleHeight() is added inside SuimonoModule.CalculateHeights, so
///     fx_buoyancy, HullWaveResponse and particle placement all feel the wake.
///
/// SampleHeight() and Hidden/USV/WakeField implement the same formula; keep
/// them in sync.
/// </summary>
public class USVWakeField : MonoBehaviour
{
    public const int MaxBoats = 4;
    public const int TrackPoints = 96;

    [Tooltip("Metres between recorded track points (TrackPoints of them → wake length).")]
    public float trackSpacing = 2.5f;
    [Tooltip("Wake amplitude per metre of hull length at full speed (0.08 → ~0.35 m wave height for the 4.6 m leader).")]
    public float amplitudePerLength = 0.08f;
    [Tooltip("Global multiplier (Python: WAKE_REALISTIC_STRENGTH).")]
    public float strength = 1f;
    public int textureSize = 640;
    public float textureWorldSize = 320f;

    public static USVWakeField Instance { get; private set; }

    const float Gravity = 9.81f;
    const float CuspTan = 0.35355339f;   // tan(19.47°) = 1/sqrt(8)

    class BoatTrack
    {
        public Transform transform;
        public Rigidbody rb;
        public BoatSternWake hull;
        public readonly List<Vector2> history = new List<Vector2>();
        public readonly Vector2[] points = new Vector2[TrackPoints];
        public readonly float[] along = new float[TrackPoints];
        public int count;
        public float speed;
        public float length = 4f;
        public float beam = 1.5f;
        public float amplitude;
    }

    readonly List<BoatTrack> boats = new List<BoatTrack>();
    readonly Vector4[] trackArray = new Vector4[MaxBoats * TrackPoints];
    readonly Vector4[] boatArray = new Vector4[MaxBoats];
    readonly Vector4[] ampArray = new Vector4[MaxBoats];
    RenderTexture wakeTexture;
    Material fieldMaterial;
    Vector4 rect;

    static readonly int WakeTexId = Shader.PropertyToID("_usvWakeTex");
    static readonly int WakeRectId = Shader.PropertyToID("_usvWakeRect");
    static readonly int WakeOnId = Shader.PropertyToID("_usvWakeOn");
    static readonly int TrackId = Shader.PropertyToID("_usvTrack");
    static readonly int BoatId = Shader.PropertyToID("_usvBoat");
    static readonly int AmpId = Shader.PropertyToID("_usvBoatAmp");
    static readonly int BoatCountId = Shader.PropertyToID("_usvBoatCount");

    void Awake()
    {
        Instance = this;
        Shader shader = Shader.Find("Hidden/USV/WakeField");
        if (shader == null || !shader.isSupported)
        {
            Debug.LogWarning("[USVWakeField] Hidden/USV/WakeField shader unavailable; wake will affect physics only.");
        }
        else
        {
            fieldMaterial = new Material(shader) { hideFlags = HideFlags.HideAndDontSave };
            wakeTexture = new RenderTexture(textureSize, textureSize, 0, RenderTextureFormat.RGHalf, RenderTextureReadWrite.Linear)
            {
                name = "USVWakeField",
                wrapMode = TextureWrapMode.Clamp,
                filterMode = FilterMode.Bilinear,
            };
            wakeTexture.Create();
            Shader.SetGlobalTexture(WakeTexId, wakeTexture);
        }
        Shader.SetGlobalFloat(WakeOnId, 0f);
    }

    void OnDisable()
    {
        Shader.SetGlobalFloat(WakeOnId, 0f);
    }

    void OnDestroy()
    {
        if (Instance == this) Instance = null;
        Shader.SetGlobalFloat(WakeOnId, 0f);
        if (wakeTexture != null) wakeTexture.Release();
        if (fieldMaterial != null) Destroy(fieldMaterial);
    }

    public void ClearBoats()
    {
        boats.Clear();
    }

    public void RemoveInactiveBoats()
    {
        boats.RemoveAll(b => b.transform == null || b.hull == null || !b.hull.enabled);
    }

    public void Register(Transform boat)
    {
        if (boat == null || boats.Count >= MaxBoats) return;
        foreach (BoatTrack b in boats) if (b.transform == boat) return;
        boats.Add(new BoatTrack
        {
            transform = boat,
            rb = boat.GetComponent<Rigidbody>(),
            hull = boat.GetComponent<BoatSternWake>(),
        });
    }

    // Boats move in FixedUpdate; build the field after that.
    void LateUpdate()
    {
        foreach (BoatTrack b in boats) UpdateTrack(b);
        RenderField();
    }

    void UpdateTrack(BoatTrack b)
    {
        if (b.transform == null) { b.count = 0; return; }
        if (b.hull != null && b.hull.hullLength > 0f)
        {
            b.length = b.hull.hullLength;
            b.beam = b.hull.hullBeam;
        }

        Vector3 pos3 = b.transform.position;
        Vector2 pos = new Vector2(pos3.x, pos3.z);
        float rawSpeed = 0f;
        if (b.rb != null)
        {
            Vector3 v = b.rb.velocity;
            rawSpeed = new Vector2(v.x, v.z).magnitude;
        }
        b.speed = Mathf.Lerp(b.speed, rawSpeed, 1f - Mathf.Exp(-Time.deltaTime / 0.3f));

        List<Vector2> h = b.history;
        if (h.Count > 0 && (pos - h[h.Count - 1]).sqrMagnitude > 25f * 25f) h.Clear();   // teleport / reset
        if (h.Count == 0 || (pos - h[h.Count - 1]).sqrMagnitude >= trackSpacing * trackSpacing)
        {
            h.Add(pos);
            if (h.Count > TrackPoints - 1) h.RemoveAt(0);
        }

        // Polyline from the hull back along the recorded track.
        b.points[0] = pos;
        b.along[0] = 0f;
        int n = 1;
        for (int i = h.Count - 1; i >= 0 && n < TrackPoints; i--)
        {
            float seg = (h[i] - b.points[n - 1]).magnitude;
            if (seg < 1e-3f) continue;
            b.points[n] = h[i];
            b.along[n] = b.along[n - 1] + seg;
            n++;
        }
        b.count = n;

        // Waves grow from displacement speed up to planing.
        float speedFactor = Mathf.Clamp01((b.speed - 1f) / 8f);
        b.amplitude = amplitudePerLength * b.length * speedFactor * Mathf.Max(0f, strength);
    }

    void RenderField()
    {
        if (fieldMaterial == null || wakeTexture == null) return;

        // Centre on the formation, snapped to the texel grid so the field
        // does not shimmer as it follows the boats.
        Vector2 centre = Vector2.zero;
        int live = 0;
        foreach (BoatTrack b in boats)
        {
            if (b.transform == null) continue;
            centre += new Vector2(b.transform.position.x, b.transform.position.z);
            live++;
        }
        if (live == 0) { Shader.SetGlobalFloat(WakeOnId, 0f); return; }
        centre /= live;
        float texel = textureWorldSize / textureSize;
        centre.x = Mathf.Round(centre.x / texel) * texel;
        centre.y = Mathf.Round(centre.y / texel) * texel;
        rect = new Vector4(centre.x - textureWorldSize * 0.5f, centre.y - textureWorldSize * 0.5f, textureWorldSize, 1f / textureWorldSize);

        for (int i = 0; i < MaxBoats; i++)
        {
            BoatTrack b = i < boats.Count ? boats[i] : null;
            int n = b != null ? b.count : 0;
            boatArray[i] = b != null ? new Vector4(n, b.speed, b.length, b.beam) : Vector4.zero;
            ampArray[i] = b != null ? new Vector4(b.amplitude, 0f, 0f, 0f) : Vector4.zero;
            for (int k = 0; k < TrackPoints; k++)
            {
                trackArray[i * TrackPoints + k] = k < n
                    ? new Vector4(b.points[k].x, b.points[k].y, b.along[k], 0f)
                    : Vector4.zero;
            }
        }

        fieldMaterial.SetVectorArray(TrackId, trackArray);
        fieldMaterial.SetVectorArray(BoatId, boatArray);
        fieldMaterial.SetVectorArray(AmpId, ampArray);
        fieldMaterial.SetInt(BoatCountId, Mathf.Min(boats.Count, MaxBoats));
        fieldMaterial.SetVector(WakeRectId, rect);
        Graphics.Blit(null, wakeTexture, fieldMaterial);

        Shader.SetGlobalTexture(WakeTexId, wakeTexture);
        Shader.SetGlobalVector(WakeRectId, rect);
        Shader.SetGlobalFloat(WakeOnId, 1f);
    }

    /// <summary>Wake surface height (m) at a world position; 0 when no field.</summary>
    public static float SampleHeight(Vector3 world)
    {
        USVWakeField f = Instance;
        if (f == null || !f.isActiveAndEnabled) return 0f;
        Vector2 p = new Vector2(world.x, world.z);
        float eta = 0f;
        foreach (BoatTrack b in f.boats)
        {
            if (b.count < 2 || b.amplitude <= 0f) continue;
            // Cheap reject: farther than the whole track from the hull.
            if ((p - b.points[0]).sqrMagnitude > (b.along[b.count - 1] + 30f) * (b.along[b.count - 1] + 30f)) continue;
            NearestOnTrack(b, p, out float s, out float y);
            eta += KelvinHeight(s, y, b.speed, b.length, b.beam, b.amplitude, b.along[b.count - 1]);
        }
        return eta;
    }

    static void NearestOnTrack(BoatTrack b, Vector2 p, out float s, out float y)
    {
        float best = float.MaxValue;
        s = 0f;
        for (int k = 0; k < b.count - 1; k++)
        {
            Vector2 a = b.points[k];
            Vector2 d = b.points[k + 1] - a;
            float t = Mathf.Clamp01(Vector2.Dot(p - a, d) / Mathf.Max(d.sqrMagnitude, 1e-4f));
            Vector2 q = a + d * t;
            float dist2 = (p - q).sqrMagnitude;
            if (dist2 < best)
            {
                best = dist2;
                s = Mathf.Lerp(b.along[k], b.along[k + 1], t);
            }
        }
        y = Mathf.Sqrt(best);
    }

    static float HullFilter(float kL)
    {
        kL = Mathf.Min(kL, 20f);
        return (kL / 1.5f) * Mathf.Exp(0.5f - kL * kL / 4.5f);
    }

    // Same formula as KelvinWake() in Hidden/USV/WakeField.
    static float KelvinHeight(float s, float y, float U, float L, float B, float A0, float trackLength)
    {
        if (s <= 0f || U < 0.5f) return 0f;
        float ay = Mathf.Abs(y);
        float k0 = Gravity / (U * U);
        float r = Mathf.Sqrt(s * s + ay * ay);
        float t = ay / s;
        float tc = Mathf.Min(t, CuspTan);
        float D = Mathf.Sqrt(Mathf.Clamp01(1f - 8f * tc * tc));
        float tq = Mathf.Max(t, 1e-4f);
        float eta = 0f;
        for (int br = -1; br <= 1; br += 2)
        {
            float tanTh = (1f + br * D) / (4f * tq);
            if (br < 0 && t < 1e-4f) tanTh = t;
            float cos2 = 1f / (1f + tanTh * tanTh);
            float k = k0 / cos2;
            float cosTh = Mathf.Sqrt(cos2);
            float sinTh = tanTh * cosTh;
            float phase = k * (s * cosTh - ay * sinTh);
            float amp = HullFilter(k * L) * Mathf.Sqrt(L / Mathf.Max(r, 0.5f * L)) / Mathf.Sqrt(Mathf.Max(D, 0.25f));
            eta += amp * Mathf.Cos(phase + br * 0.7853982f);
        }
        float edge = Mathf.Clamp01((CuspTan * 1.08f - t) / (CuspTan * 0.16f));
        float ramp = Mathf.Clamp01(s / (1.5f * L));
        ramp *= ramp;
        float fade = Mathf.Exp(-s / (U * 25f));
        float tail = Mathf.Clamp01((trackLength - s) / 20f);
        // Finite-hull shoulder waves dominate close to a planing transom;
        // the stationary-phase Kelvin solution describes the far field only.
        float d = Mathf.Max(s - 0.35f * L, 0f);
        float froude = U / Mathf.Sqrt(Gravity * L);
        float arm = 0.45f * B + d * Mathf.Clamp(0.65f / froude, 0.16f, CuspTan);
        float width = 0.4f * B + 0.018f * d;
        float q = (ay - arm) / Mathf.Max(width, 0.4f);
        float onset = Mathf.Clamp01(d / (0.4f * L));
        onset = onset * onset * (3f - 2f * onset);
        float shoulder = 0.9f * (1f - q*q) * Mathf.Exp(-0.5f*q*q - d / (6f*L)) * onset;
        return A0 * (eta * edge * ramp * fade + shoulder) * tail;
    }
}
