using UnityEngine;
using Suimono.Core;
using Random = UnityEngine.Random;

/// <summary>
/// Hull measurement + spray for one boat. The stern wave itself (Kelvin wave
/// crests, turbulent wash foam, hull motion) lives in the water surface via
/// USVWakeField; this component adds what a surface cannot show: water
/// thrown into the air by a planing hull.
///
/// The scene's hulls are small (leader ~4.6 m, followers ~3 m) and run at up
/// to ~18 m/s, a length Froude number Fr = U/sqrt(gL) ≈ 2.7 (hard planing):
///   - rooster tail: a jet off the transom, launched upward at ~0.16-0.32 U
///     (height ∝ U², roughly 1-1.7 m at cruise) that barely keeps pace with the hull,
///     so it trails astern while rising and falling back;
///   - chine spray: sheets peeling off the hull sides near amidships.
/// Droplets are drawn as velocity-stretched streaks with a droplet-cluster
/// texture and die when they fall back to the surface, so the spray reads as
/// water rather than smoke. Spray only develops once the hull planes (Fr > 1).
///
/// WaveController adds this to every boat at startup; Python sets strength
/// (WAKE_REALISTIC_STRENGTH) and can turn spray off (WAKE_REALISTIC_SPRAY).
/// </summary>
[DisallowMultipleComponent]
public class BoatSternWake : MonoBehaviour
{
    [Header("Hull (auto-detected from the boat's renderers when <= 0)")]
    public float hullLength = 0f;
    public float hullBeam = 0f;

    [Header("Spray")]
    [Tooltip("1 = baseline. Scales spray density, size and opacity; 2 = heavier. (Python: WAKE_REALISTIC_STRENGTH)")]
    public float strength = 1f;
    [Tooltip("Rooster tail + chine spray (Python: WAKE_REALISTIC_SPRAY).")]
    public bool sprayEnabled = true;
    public float sprayStartAlpha = 0.85f;
    public float dropletSizeBeams = 0.28f;    // streak width, in beams
    public float roosterUpFraction = 0.32f;    // max vertical launch speed / boat speed
    public float sprayPerMetre = 140f;         // droplets per metre travelled at full planing
    public float sprayDrag = 0.4f;            // 1/s air drag on droplets
    public float maxLifetime = 1.6f;

    [Header("Rendering (optional - a procedural droplet material is built when empty)")]
    public Material sprayMaterial;

    const float Gravity = 9.81f;
    static readonly Color SprayColor = new Color(0.92f, 0.95f, 0.98f, 1f);
    static Material sharedProceduralMaterial;
    static SuimonoModule suimono;
    static bool suimonoSearched;

    Rigidbody rb;
    ParticleSystem spraySystem;
    float sternAlong;      // transom position along the hull axis, relative to the pivot
    float sternLateral;    // hull centreline offset, relative to the pivot
    Vector3 lastStern;
    bool hasLastStern;
    float sprayAccum;
    float lastWaterHeight;
    bool hasWaterHeight;

    void Awake()
    {
        rb = GetComponent<Rigidbody>();
        MeasureHull();
        spraySystem = CreateSpraySystem("BoatSpray_" + name, sprayMaterial != null ? sprayMaterial : GetProceduralMaterial());
    }

    void OnEnable()
    {
        hasLastStern = false;
        sprayAccum = 0f;
    }

    void OnDestroy()
    {
        if (spraySystem != null) Destroy(spraySystem.gameObject);
    }

    // Boats move in FixedUpdate; emitting after that keeps the stern point exact.
    void LateUpdate()
    {
        float dt = Time.deltaTime;
        if (dt <= 0f) return;

        Vector3 forward = PlanarForward();
        Vector3 right = Vector3.Cross(Vector3.up, forward);
        Vector3 stern = transform.position + forward * sternAlong + right * sternLateral;
        float speed = 0f;
        if (rb != null) speed = new Vector2(rb.velocity.x, rb.velocity.z).magnitude;

        if (!hasLastStern)
        {
            lastStern = stern;
            hasLastStern = true;
        }
        Vector3 step = stern - lastStern;
        step.y = 0f;
        float travelled = step.magnitude;
        // A teleport (scene reset) must not paint spray across the map.
        if (travelled > Mathf.Max(5f, speed * dt * 4f)) travelled = 0f;

        float froude = speed / Mathf.Sqrt(Gravity * Mathf.Max(0.5f, hullLength));
        float planing = Mathf.Clamp01((froude - 1f) / 1.5f);
        if (sprayEnabled && strength > 0f && planing > 0f && travelled > 0f)
            EmitSpray(lastStern, step, travelled, forward, right, speed, planing);
        else
            sprayAccum = 0f;

        lastStern = stern;
    }

    void EmitSpray(Vector3 from, Vector3 step, float travelled, Vector3 forward, Vector3 right, float speed, float planing)
    {
        float heavy = Mathf.Max(0f, strength);
        float spacing = 1f / Mathf.Max(0.5f, sprayPerMetre * planing * Mathf.Max(0.25f, heavy));
        float size = Mathf.Max(0.12f, hullBeam * dropletSizeBeams) * Mathf.Sqrt(Mathf.Max(0.25f, heavy));
        float alpha = Mathf.Clamp01(sprayStartAlpha * Mathf.Min(1.4f, heavy) * Mathf.Lerp(0.5f, 1f, planing));
        sprayAccum += travelled;

        var ep = new ParticleSystem.EmitParams();
        while (sprayAccum >= spacing)
        {
            sprayAccum -= spacing;
            Vector3 c = from + step * Mathf.Clamp01(1f - sprayAccum / travelled);
            float water = WaterHeight(c);
            float up;

            // Broad, low chine sheets supply most of the aerated spray collar.
            if (Random.value < 0.35f)
            {
                // Jet off the transom: in the world frame it barely keeps up with the
                // hull, so the plume trails astern while it rises and falls.
                Vector3 p = c + right * (Random.Range(-0.35f, 0.35f) * hullBeam);
                p.y = water + 0.1f;
                up = speed * roosterUpFraction * planing * Random.Range(0.5f, 1f);
                ep.position = p;
                ep.velocity = Vector3.up * up
                              + forward * (speed * Random.Range(0.5f, 0.75f))
                              + right * (speed * Random.Range(-0.05f, 0.05f));
                ep.startSize = size * Random.Range(0.7f, 1.3f);
            }
            else
            {
                // Spray sheet peeling off a chine near amidships, thrown outward.
                int s = Random.value < 0.5f ? -1 : 1;
                Vector3 p = c + forward * (0.45f * hullLength) + right * (s * 0.5f * hullBeam);
                p.y = water + 0.05f;
                up = speed * Random.Range(0.06f, 0.14f) * planing;
                ep.position = p;
                ep.velocity = right * (s * speed * Random.Range(0.12f, 0.25f))
                              + Vector3.up * up
                              + forward * (speed * Random.Range(0.4f, 0.7f));
                ep.startSize = size * Random.Range(0.5f, 0.9f);
            }
            // Ballistic flight back to the water plus a brief mist tail.
            ep.startLifetime = Mathf.Clamp(2f * up / Gravity + 0.15f, 0.2f, maxLifetime);
            ep.startColor = WithAlpha(SprayColor, alpha * Random.Range(0.6f, 1f));
            spraySystem.Emit(ep, 1);
        }
    }

    float WaterHeight(Vector3 p)
    {
        if (!suimonoSearched)
        {
            suimono = FindObjectOfType<SuimonoModule>();
            suimonoSearched = true;
        }
        if (suimono != null)
        {
            float h = suimono.SuimonoGetHeight(p, "height");
            // Off the water surface Suimono returns -1; keep the last good value.
            bool notSentinel = h > -0.99f || h < -1.01f;
            bool plausible = !hasWaterHeight || Mathf.Abs(h - lastWaterHeight) < 8f;
            if (notSentinel && plausible)
            {
                lastWaterHeight = h;
                hasWaterHeight = true;
                return h;
            }
        }
        return hasWaterHeight ? lastWaterHeight : transform.position.y;
    }

    Vector3 PlanarForward()
    {
        // The boat models are authored with local +Y as the bow (see ShipUDPInterface).
        Vector3 f = transform.TransformDirection(Vector3.up);
        f.y = 0f;
        if (f.sqrMagnitude < 1e-4f)
        {
            f = transform.forward;
            f.y = 0f;
        }
        return f.sqrMagnitude < 1e-4f ? Vector3.forward : f.normalized;
    }

    void MeasureHull()
    {
        Vector3 forward = PlanarForward();
        Vector3 right = Vector3.Cross(Vector3.up, forward);
        Vector3 pivot = transform.position;
        float minF = float.MaxValue, maxF = float.MinValue;
        float minR = float.MaxValue, maxR = float.MinValue;

        foreach (Renderer r in GetComponentsInChildren<Renderer>())
        {
            if (r is ParticleSystemRenderer || r is TrailRenderer || r is LineRenderer) continue;
            Bounds b = r.bounds;
            if (b.size.magnitude > 120f) continue;
            for (int i = 0; i < 8; i++)
            {
                Vector3 corner = b.center + Vector3.Scale(b.extents,
                    new Vector3((i & 1) == 0 ? -1f : 1f, (i & 2) == 0 ? -1f : 1f, (i & 4) == 0 ? -1f : 1f));
                Vector3 d = corner - pivot;
                float along = Vector3.Dot(d, forward);
                float lat = Vector3.Dot(d, right);
                minF = Mathf.Min(minF, along); maxF = Mathf.Max(maxF, along);
                minR = Mathf.Min(minR, lat); maxR = Mathf.Max(maxR, lat);
            }
        }

        float measuredLength = maxF - minF;
        float measuredBeam = maxR - minR;
        bool valid = measuredLength > 1f && measuredLength < 100f && measuredBeam > 0.3f && measuredBeam < 40f;

        if (hullLength <= 0f) hullLength = valid ? measuredLength : 5f;
        if (hullBeam <= 0f) hullBeam = valid ? Mathf.Min(measuredBeam, hullLength * 0.6f) : 2f;
        sternAlong = valid ? minF : -0.5f * hullLength;
        sternLateral = valid ? 0.5f * (minR + maxR) : 0f;

        Debug.Log($"[BoatSternWake] {name}: hull length={hullLength:F1}m beam={hullBeam:F1}m stern={sternAlong:F1}m");
    }

    ParticleSystem CreateSpraySystem(string systemName, Material mat)
    {
        // A root object with identity transform: particles live in world space and
        // their sizes must not inherit the boat's scale.
        var go = new GameObject(systemName);
        go.layer = gameObject.layer;
        var ps = go.AddComponent<ParticleSystem>();
        ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

        var main = ps.main;
        main.loop = true;
        main.playOnAwake = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.scalingMode = ParticleSystemScalingMode.Local;
        main.maxParticles = 8000;
        main.startSpeed = 0f;
        main.gravityModifier = 1f;

        var emission = ps.emission;
        emission.enabled = false;   // emitted explicitly per metre travelled
        var shape = ps.shape;
        shape.enabled = false;

        // Droplets break up into finer mist as they fly: slight growth only.
        var sizeOverLifetime = ps.sizeOverLifetime;
        sizeOverLifetime.enabled = true;
        sizeOverLifetime.size = new ParticleSystem.MinMaxCurve(1.6f,
            new AnimationCurve(new Keyframe(0f, 1f / 1.6f), new Keyframe(1f, 1f)));

        var colorOverLifetime = ps.colorOverLifetime;
        colorOverLifetime.enabled = true;
        var gradient = new Gradient();
        gradient.SetKeys(
            new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
            new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0.8f, 0.6f), new GradientAlphaKey(0f, 1f) });
        colorOverLifetime.color = new ParticleSystem.MinMaxGradient(gradient);

        var limit = ps.limitVelocityOverLifetime;
        limit.enabled = true;
        limit.limit = 1000f;
        limit.dampen = 0f;
        limit.drag = sprayDrag;

        var renderer = go.GetComponent<ParticleSystemRenderer>();
        // Streaks along the droplet velocity read as flying water, not smoke.
        renderer.renderMode = ParticleSystemRenderMode.Stretch;
        renderer.velocityScale = 0.025f;
        renderer.lengthScale = 1.0f;
        renderer.sharedMaterial = mat;
        renderer.sortMode = ParticleSystemSortMode.Distance;
        renderer.maxParticleSize = 2f;
        renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        renderer.receiveShadows = false;

        ps.Play();
        return ps;
    }

    static Color WithAlpha(Color c, float a)
    {
        c.a = Mathf.Clamp01(a);
        return c;
    }

    static Material GetProceduralMaterial()
    {
        if (sharedProceduralMaterial != null) return sharedProceduralMaterial;

        Shader shader = Shader.Find("Hidden/USV/FoamParticle");
        if (shader == null) shader = Shader.Find("Sprites/Default");
        sharedProceduralMaterial = new Material(shader) { name = "BoatSpray (procedural)" };
        Texture2D photographic=Resources.Load<Texture2D>("USVPhotographicSpray");
        sharedProceduralMaterial.mainTexture = photographic!=null ? photographic : BuildDropletTexture(128);
        return sharedProceduralMaterial;
    }

    // A loose cluster of small soft droplets inside a round falloff.
    static Texture2D BuildDropletTexture(int size)
    {
        var tex = new Texture2D(size, size, TextureFormat.RGBA32, true)
        {
            name = "BoatSprayTex",
            wrapMode = TextureWrapMode.Clamp,
            filterMode = FilterMode.Trilinear,
        };
        var alpha = new float[size * size];
        var rng = new System.Random(7);
        for (int d = 0; d < 70; d++)
        {
            // Denser toward the centre of the streak.
            double ang = rng.NextDouble() * 2.0 * System.Math.PI;
            double rad = System.Math.Sqrt(rng.NextDouble()) * 0.8;
            float cx = (float)(0.5 + 0.5 * rad * System.Math.Cos(ang)) * size;
            float cy = (float)(0.5 + 0.5 * rad * System.Math.Sin(ang)) * size;
            float dr = size * (0.015f + 0.035f * (float)rng.NextDouble());
            float a = 0.55f + 0.45f * (float)rng.NextDouble();
            int x0 = Mathf.Max(0, (int)(cx - dr * 2)), x1 = Mathf.Min(size - 1, (int)(cx + dr * 2));
            int y0 = Mathf.Max(0, (int)(cy - dr * 2)), y1 = Mathf.Min(size - 1, (int)(cy + dr * 2));
            for (int y = y0; y <= y1; y++)
            {
                for (int x = x0; x <= x1; x++)
                {
                    float dist = Mathf.Sqrt((x - cx) * (x - cx) + (y - cy) * (y - cy)) / dr;
                    float v = a * (1f - Mathf.SmoothStep(0.6f, 1.2f, dist));
                    alpha[y * size + x] = Mathf.Max(alpha[y * size + x], v);
                }
            }
        }
        var pixels = new Color32[size * size];
        for (int y = 0; y < size; y++)
        {
            for (int x = 0; x < size; x++)
            {
                float u = (x + 0.5f) / size * 2f - 1f;
                float v = (y + 0.5f) / size * 2f - 1f;
                float fall = 1f - Mathf.SmoothStep(0.5f, 1f, Mathf.Sqrt(u * u + v * v));
                // Faint mist between droplets.
                float a = Mathf.Max(alpha[y * size + x], 0.38f * fall) * fall;
                pixels[y * size + x] = new Color32(255, 255, 255, (byte)Mathf.RoundToInt(255f * Mathf.Clamp01(a)));
            }
        }
        tex.SetPixels32(pixels);
        tex.Apply(true, true);
        return tex;
    }
}
