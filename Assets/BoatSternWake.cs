using UnityEngine;
using Suimono.Core;
using Random = UnityEngine.Random;

/// <summary>
/// Physically shaped stern wake for one boat, replacing the legacy fx_boatwake
/// puffs (camera-facing billboards with no material that stood up like a white
/// wall in front of the follower cameras).
///
/// The scene's hulls are small (leader ~4.6 m, followers ~3 m) and run at up
/// to ~18 m/s, i.e. a length Froude number Fr = U/sqrt(gL) ≈ 2.7: hard
/// planing. A planing boat's wake is dominated by:
///
///   1. Turbulent stern wash - opaque white water directly astern, about 1.5
///      beams wide at the transom, spreading and fading over ~10 s; it follows
///      the boat's actual track through turns. Flat on the water.
///
///   2. Kelvin divergent waves - foam along the two arms of the V. A point on
///      an arm moves sideways at U·tan(19.47°) while the boat moves on at U,
///      which is the 19.47° Kelvin half-angle of a deep-water ship wave.
///
///   3. Spray - the rooster tail thrown up behind the transom (vertical speed
///      ~0.2-0.4 U, so its height grows with U²) plus chine spray sheets thrown
///      out to the sides. Spray is volumetric, so it is drawn camera-facing;
///      it is what partially hides a fast small boat's hull from a camera
///      following behind it, which is the detection stress this project tests.
///
/// Everything is emitted per metre travelled (a stationary boat leaves no
/// wake) and scales with speed; spray only develops once the hull planes
/// (Fr > 1). Foam is re-seated onto the SUIMONO surface each frame (small
/// budget) so it rides the waves.
///
/// WaveController adds this to every boat at startup; Python sets strength
/// (WAKE_REALISTIC_STRENGTH) or switches back to the legacy stress-test wake.
/// </summary>
[DisallowMultipleComponent]
public class BoatSternWake : MonoBehaviour
{
    [Header("Hull (auto-detected from the boat's renderers when <= 0)")]
    public float hullLength = 0f;
    public float hullBeam = 0f;

    [Header("Speed response")]
    [Tooltip("Below this planar speed (m/s) no new foam forms.")]
    public float minSpeed = 0.8f;
    [Tooltip("Planar speed (m/s) at which the foam reaches full strength.")]
    public float fullSpeed = 12f;
    [Tooltip("1 = realistic. Scales opacity, spray density and spray size; 2 ≈ rough/heavy spray. (Python: WAKE_REALISTIC_STRENGTH)")]
    public float strength = 1f;
    [Tooltip("Rooster tail + chine spray (the part that can hide the hull from a following camera).")]
    public bool sprayEnabled = true;

    [Header("Turbulent stern wash")]
    public float washLifetime = 11f;
    public float washStartAlpha = 0.8f;
    public float washWidthBeams = 1.5f;       // white-water width at the transom, in beams
    public float washGrowth = 3.5f;           // final size / initial size
    public float washSpreadFraction = 0.05f;  // lateral spread speed as fraction of boat speed
    public float washDrag = 0.5f;             // 1/s

    [Header("Kelvin divergent waves")]
    public float kelvinHalfAngleDeg = 19.47f;
    public float kelvinLifetime = 3.5f;
    public float kelvinStartAlpha = 0.6f;
    public float kelvinWidthBeams = 0.9f;
    public float kelvinGrowth = 2.5f;

    [Header("Spray (rooster tail + chine spray)")]
    public float sprayLifetime = 2.0f;
    public float sprayStartAlpha = 0.55f;
    public float spraySizeBeams = 0.45f;
    public float sprayGrowth = 4f;
    public float roosterUpFraction = 0.42f;   // max vertical launch speed / boat speed
    public float sprayPerMetre = 7f;          // particles per metre travelled at full planing
    public float sprayDrag = 0.6f;            // 1/s air drag on droplets / mist

    [Header("Water surface")]
    public float surfaceOffset = 0.08f;       // metres above the water so foam isn't z-fighting
    public int surfaceSamplesPerFrame = 40;   // per foam particle system

    [Header("Rendering (optional - a procedural foam material is built when empty)")]
    public Material foamMaterial;

    const float Gravity = 9.81f;
    static readonly Color FoamColor = new Color(0.94f, 0.97f, 1f, 1f);
    static readonly Color SprayColor = new Color(0.9f, 0.94f, 0.97f, 1f);
    static Material sharedProceduralMaterial;
    static SuimonoModule suimono;
    static bool suimonoSearched;

    Rigidbody rb;
    ParticleSystem washSystem;
    ParticleSystem kelvinSystem;
    ParticleSystem spraySystem;
    ParticleSystem.Particle[] particleBuffer;
    float sternAlong;      // transom position along the hull axis, relative to the pivot
    float sternLateral;    // hull centreline offset, relative to the pivot
    Vector3 lastStern;
    Vector3 lastPosition;
    bool hasLastStern;
    float washAccum;
    float kelvinAccum;
    float sprayAccum;
    float lastWaterHeight;
    bool hasWaterHeight;
    int washCursor;
    int kelvinCursor;

    void Awake()
    {
        rb = GetComponent<Rigidbody>();
        MeasureHull();

        Material mat = foamMaterial != null ? foamMaterial : GetProceduralMaterial();
        washSystem = CreateSystem("BoatFoam_Wash_" + name, mat, 4000, washGrowth, washDrag, 0f,
            ParticleSystemRenderMode.HorizontalBillboard,
            new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0.85f, 0.15f),
            new GradientAlphaKey(0.4f, 0.55f), new GradientAlphaKey(0f, 1f));
        kelvinSystem = CreateSystem("BoatFoam_Kelvin_" + name, mat, 3000, kelvinGrowth, 0f, 0f,
            ParticleSystemRenderMode.HorizontalBillboard,
            new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0.6f, 0.3f),
            new GradientAlphaKey(0.2f, 0.7f), new GradientAlphaKey(0f, 1f));
        spraySystem = CreateSystem("BoatFoam_Spray_" + name, mat, 4000, sprayGrowth, sprayDrag, 1f,
            ParticleSystemRenderMode.Billboard,
            new GradientAlphaKey(0.9f, 0f), new GradientAlphaKey(1f, 0.15f),
            new GradientAlphaKey(0.45f, 0.6f), new GradientAlphaKey(0f, 1f));
        particleBuffer = new ParticleSystem.Particle[4000];
    }

    void OnEnable()
    {
        hasLastStern = false;
        washAccum = kelvinAccum = sprayAccum = 0f;
    }

    void OnDestroy()
    {
        if (washSystem != null) Destroy(washSystem.gameObject);
        if (kelvinSystem != null) Destroy(kelvinSystem.gameObject);
        if (spraySystem != null) Destroy(spraySystem.gameObject);
    }

    // Boats move in FixedUpdate; emitting after that keeps the stern point exact.
    void LateUpdate()
    {
        float dt = Time.deltaTime;
        if (dt <= 0f) return;

        Vector3 forward = PlanarForward();
        Vector3 right = Vector3.Cross(Vector3.up, forward);
        Vector3 pivot = transform.position;
        Vector3 stern = pivot + forward * sternAlong + right * sternLateral;

        float speed;
        if (rb != null)
        {
            Vector3 v = rb.velocity;
            speed = new Vector2(v.x, v.z).magnitude;
        }
        else
        {
            Vector3 d = pivot - lastPosition;
            speed = hasLastStern ? new Vector2(d.x, d.z).magnitude / dt : 0f;
        }
        lastPosition = pivot;

        if (!hasLastStern)
        {
            lastStern = stern;
            hasLastStern = true;
        }

        Vector3 step = stern - lastStern;
        step.y = 0f;
        float travelled = step.magnitude;
        // A teleport (scene reset) must not paint a foam line across the map.
        if (travelled > Mathf.Max(5f, speed * dt * 4f))
        {
            lastStern = stern;
            travelled = 0f;
        }

        if (speed > minSpeed && travelled > 0f && strength > 0f)
        {
            float sf = Mathf.Clamp01((speed - minSpeed) / Mathf.Max(0.01f, fullSpeed - minSpeed));
            // Spray needs a planing hull: none below Fr 1, full by Fr 2.5.
            float froude = speed / Mathf.Sqrt(Gravity * Mathf.Max(0.5f, hullLength));
            float planing = Mathf.Clamp01((froude - 1f) / 1.5f);

            EmitWash(lastStern, step, travelled, forward, right, speed, sf);
            EmitKelvin(lastStern, step, travelled, forward, right, speed, sf);
            if (sprayEnabled && planing > 0f)
                EmitSpray(lastStern, step, travelled, forward, right, speed, planing);
        }
        else
        {
            washAccum = kelvinAccum = sprayAccum = 0f;
        }

        lastStern = stern;

        FollowSurface(washSystem, ref washCursor);
        FollowSurface(kelvinSystem, ref kelvinCursor);
    }

    void EmitWash(Vector3 from, Vector3 step, float travelled, Vector3 forward, Vector3 right, float speed, float sf)
    {
        float size = Mathf.Max(0.8f, hullBeam * washWidthBeams) * Mathf.Lerp(0.5f, 1f, sf);
        float spacing = Mathf.Max(0.1f, size * 0.22f);   // overlapping puffs → continuous white water
        float alpha = Mathf.Clamp01(washStartAlpha * strength * Mathf.Lerp(0.3f, 1f, sf));
        washAccum += travelled;

        var ep = new ParticleSystem.EmitParams();
        while (washAccum >= spacing)
        {
            washAccum -= spacing;
            Vector3 p = from + step * Mathf.Clamp01(1f - washAccum / travelled);
            p += right * (Random.Range(-0.25f, 0.25f) * size) - forward * Random.Range(0f, 0.5f);
            p.y = WaterHeight(p) + surfaceOffset;

            // Wash water is thrown slightly aft and outward, then drag settles it.
            ep.position = p;
            ep.velocity = right * (Random.Range(-1f, 1f) * washSpreadFraction * speed)
                          - forward * (Random.Range(0f, 0.06f) * speed);
            ep.startSize = size * Random.Range(0.8f, 1.2f);
            ep.startLifetime = washLifetime * Random.Range(0.8f, 1.1f);
            ep.rotation = Random.Range(0f, 360f);
            ep.startColor = WithAlpha(FoamColor, alpha * Random.Range(0.75f, 1f));
            washSystem.Emit(ep, 1);
        }
    }

    void EmitKelvin(Vector3 from, Vector3 step, float travelled, Vector3 forward, Vector3 right, float speed, float sf)
    {
        // Divergent waves only break into visible foam at speed.
        float alpha = Mathf.Clamp01(kelvinStartAlpha * strength * sf);
        if (alpha <= 0.01f)
        {
            kelvinAccum = 0f;
            return;
        }
        float size = Mathf.Max(0.5f, hullBeam * kelvinWidthBeams) * Mathf.Lerp(0.6f, 1f, sf);
        float spacing = Mathf.Max(0.1f, size * 0.3f);
        // Lateral crest speed that traces the Kelvin half-angle behind the boat.
        float spread = speed * Mathf.Tan(kelvinHalfAngleDeg * Mathf.Deg2Rad);
        kelvinAccum += travelled;

        var ep = new ParticleSystem.EmitParams();
        while (kelvinAccum >= spacing)
        {
            kelvinAccum -= spacing;
            Vector3 c = from + step * Mathf.Clamp01(1f - kelvinAccum / travelled) + forward * (0.2f * hullLength);

            for (int s = -1; s <= 1; s += 2)
            {
                Vector3 p = c + right * (s * 0.5f * hullBeam);
                p.y = WaterHeight(p) + surfaceOffset;
                ep.position = p;
                ep.velocity = right * (s * spread * Random.Range(0.92f, 1.05f));
                ep.startSize = size * Random.Range(0.8f, 1.25f);
                ep.startLifetime = kelvinLifetime * Random.Range(0.85f, 1.1f);
                ep.rotation = Random.Range(0f, 360f);
                ep.startColor = WithAlpha(FoamColor, alpha * Random.Range(0.7f, 1f));
                kelvinSystem.Emit(ep, 1);
            }
        }
    }

    void EmitSpray(Vector3 from, Vector3 step, float travelled, Vector3 forward, Vector3 right, float speed, float planing)
    {
        float heavy = Mathf.Max(0f, strength);
        float spacing = 1f / Mathf.Max(0.5f, sprayPerMetre * planing * Mathf.Max(0.25f, heavy));
        float size = Mathf.Max(0.3f, hullBeam * spraySizeBeams) * Mathf.Sqrt(Mathf.Max(0.25f, heavy));
        float alpha = Mathf.Clamp01(sprayStartAlpha * Mathf.Min(1.5f, heavy) * planing);
        sprayAccum += travelled;

        var ep = new ParticleSystem.EmitParams();
        while (sprayAccum >= spacing)
        {
            sprayAccum -= spacing;
            Vector3 c = from + step * Mathf.Clamp01(1f - sprayAccum / travelled);
            float water = WaterHeight(c);

            // 3 of 4 particles feed the rooster tail, the rest the chine sheets.
            if (Random.value < 0.75f)
            {
                // Jet off the transom: in the world frame it barely keeps up with
                // the boat, so the plume trails astern while it rises and falls.
                Vector3 p = c + right * (Random.Range(-0.2f, 0.2f) * hullBeam);
                p.y = water + 0.15f;
                float up = speed * roosterUpFraction * planing * Random.Range(0.45f, 1f);
                ep.position = p;
                ep.velocity = Vector3.up * up
                              + forward * (speed * Random.Range(0.05f, 0.3f))
                              + right * (speed * Random.Range(-0.06f, 0.06f));
                ep.startSize = size * Random.Range(0.6f, 1.2f);
                ep.startLifetime = FlightTime(up, sprayLifetime);
            }
            else
            {
                // Spray sheet peeling off a chine near amidships, thrown outward.
                int s = Random.value < 0.5f ? -1 : 1;
                Vector3 p = c + forward * (0.45f * hullLength) + right * (s * 0.5f * hullBeam);
                p.y = water + 0.1f;
                float up = speed * Random.Range(0.06f, 0.14f) * planing;
                ep.position = p;
                ep.velocity = right * (s * speed * Random.Range(0.15f, 0.3f))
                              + Vector3.up * up
                              + forward * (speed * Random.Range(0.3f, 0.6f));
                ep.startSize = size * Random.Range(0.4f, 0.8f);
                ep.startLifetime = FlightTime(up, sprayLifetime * 0.6f);
            }
            ep.rotation = Random.Range(0f, 360f);
            ep.startColor = WithAlpha(SprayColor, alpha * Random.Range(0.6f, 1f));
            spraySystem.Emit(ep, 1);
        }
    }

    // Ballistic time until a droplet launched upward at `up` falls back to the
    // water, plus a short mist tail, so spray dies at the surface instead of
    // sinking visibly below it.
    static float FlightTime(float up, float maxLifetime)
    {
        return Mathf.Clamp(2f * up / Gravity + 0.3f, 0.3f, Mathf.Max(0.3f, maxLifetime));
    }

    // Re-seat a rolling slice of live foam particles onto the wave surface.
    void FollowSurface(ParticleSystem ps, ref int cursor)
    {
        if (ps == null || GetSuimono() == null || surfaceSamplesPerFrame <= 0) return;
        int count = ps.GetParticles(particleBuffer);
        if (count == 0) return;

        int budget = Mathf.Min(surfaceSamplesPerFrame, count);
        for (int k = 0; k < budget; k++)
        {
            cursor = (cursor + 1) % count;
            Vector3 p = particleBuffer[cursor].position;
            p.y = WaterHeight(p) + surfaceOffset;
            particleBuffer[cursor].position = p;
        }
        ps.SetParticles(particleBuffer, count);
    }

    float WaterHeight(Vector3 p)
    {
        SuimonoModule module = GetSuimono();
        if (module != null)
        {
            float h = module.SuimonoGetHeight(p, "height");
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
        // Fallback: the last good sample, else the hull pivot.
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

    ParticleSystem CreateSystem(string systemName, Material mat, int maxParticles, float growth, float drag,
        float gravity, ParticleSystemRenderMode renderMode, params GradientAlphaKey[] alphaKeys)
    {
        // A root object with identity transform: particles live in world space and
        // their sizes must not inherit the boat's scale.
        var go = new GameObject(systemName);
        var ps = go.AddComponent<ParticleSystem>();
        ps.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

        var main = ps.main;
        main.loop = true;
        main.playOnAwake = false;
        main.simulationSpace = ParticleSystemSimulationSpace.World;
        main.scalingMode = ParticleSystemScalingMode.Local;
        main.maxParticles = maxParticles;
        main.startSpeed = 0f;
        main.gravityModifier = gravity;

        var emission = ps.emission;
        emission.enabled = false;   // emitted explicitly per metre travelled
        var shape = ps.shape;
        shape.enabled = false;

        var sizeOverLifetime = ps.sizeOverLifetime;
        sizeOverLifetime.enabled = true;
        // Fast initial spread that slows down, like real wash and spray mist.
        sizeOverLifetime.size = new ParticleSystem.MinMaxCurve(growth,
            new AnimationCurve(new Keyframe(0f, 1f / growth, 0f, 2.5f), new Keyframe(1f, 1f, 0.3f, 0f)));

        var colorOverLifetime = ps.colorOverLifetime;
        colorOverLifetime.enabled = true;
        var gradient = new Gradient();
        gradient.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) }, alphaKeys);
        colorOverLifetime.color = new ParticleSystem.MinMaxGradient(gradient);

        if (drag > 0f)
        {
            var limit = ps.limitVelocityOverLifetime;
            limit.enabled = true;
            limit.limit = 1000f;
            limit.dampen = 0f;
            limit.drag = drag;
        }

        var renderer = go.GetComponent<ParticleSystemRenderer>();
        renderer.renderMode = renderMode;
        renderer.sharedMaterial = mat;
        renderer.sortMode = renderMode == ParticleSystemRenderMode.Billboard
            ? ParticleSystemSortMode.Distance
            : ParticleSystemSortMode.YoungestInFront;
        renderer.maxParticleSize = 4f;
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

    static SuimonoModule GetSuimono()
    {
        if (!suimonoSearched)
        {
            suimono = FindObjectOfType<SuimonoModule>();
            suimonoSearched = true;
        }
        return suimono;
    }

    static Material GetProceduralMaterial()
    {
        if (sharedProceduralMaterial != null) return sharedProceduralMaterial;

        Shader shader = Shader.Find("Legacy Shaders/Particles/Alpha Blended");
        bool legacy = shader != null;
        if (shader == null) shader = Shader.Find("Particles/Standard Unlit");
        if (shader == null) shader = Shader.Find("Sprites/Default");

        var mat = new Material(shader) { name = "BoatFoam (procedural)" };
        mat.mainTexture = BuildFoamTexture(128);
        if (legacy)
        {
            mat.SetColor("_TintColor", new Color(0.5f, 0.5f, 0.5f, 0.5f));
        }
        else if (shader.name == "Particles/Standard Unlit")
        {
            // Fade blend mode
            mat.SetFloat("_Mode", 2f);
            mat.SetInt("_SrcBlend", (int)UnityEngine.Rendering.BlendMode.SrcAlpha);
            mat.SetInt("_DstBlend", (int)UnityEngine.Rendering.BlendMode.OneMinusSrcAlpha);
            mat.SetInt("_ZWrite", 0);
            mat.EnableKeyword("_ALPHABLEND_ON");
        }
        // Draw after the SUIMONO water surface (Geometry+50).
        mat.renderQueue = 3100;
        sharedProceduralMaterial = mat;
        return mat;
    }

    // Soft-edged, broken-up foam patch: radial falloff times fractal noise.
    static Texture2D BuildFoamTexture(int size)
    {
        var tex = new Texture2D(size, size, TextureFormat.RGBA32, true)
        {
            name = "BoatFoamTex",
            wrapMode = TextureWrapMode.Clamp,
            filterMode = FilterMode.Trilinear,
        };
        var pixels = new Color32[size * size];
        for (int y = 0; y < size; y++)
        {
            for (int x = 0; x < size; x++)
            {
                float u = (x + 0.5f) / size * 2f - 1f;
                float v = (y + 0.5f) / size * 2f - 1f;
                float r = Mathf.Sqrt(u * u + v * v);
                float falloff = 1f - Mathf.SmoothStep(0.2f, 1f, r);

                float n = 0f, amp = 0.5f, freq = 6f;
                for (int o = 0; o < 4; o++)
                {
                    n += amp * ValueNoise((x / (float)size) * freq, (y / (float)size) * freq, o);
                    amp *= 0.5f;
                    freq *= 2.1f;
                }
                float foam = 0.35f + 0.65f * Mathf.SmoothStep(0.3f, 0.7f, n);
                byte a = (byte)Mathf.RoundToInt(255f * Mathf.Clamp01(falloff * foam));
                pixels[y * size + x] = new Color32(255, 255, 255, a);
            }
        }
        tex.SetPixels32(pixels);
        tex.Apply(true, true);
        return tex;
    }

    static float ValueNoise(float x, float y, int seed)
    {
        int x0 = Mathf.FloorToInt(x), y0 = Mathf.FloorToInt(y);
        float fx = x - x0, fy = y - y0;
        fx = fx * fx * (3f - 2f * fx);
        fy = fy * fy * (3f - 2f * fy);
        float a = Hash(x0, y0, seed), b = Hash(x0 + 1, y0, seed);
        float c = Hash(x0, y0 + 1, seed), d = Hash(x0 + 1, y0 + 1, seed);
        return Mathf.Lerp(Mathf.Lerp(a, b, fx), Mathf.Lerp(c, d, fx), fy);
    }

    static float Hash(int x, int y, int seed)
    {
        unchecked
        {
            int h = x * 374761393 + y * 668265263 + seed * 1442695041;
            h = (h ^ (h >> 13)) * 1274126177;
            return ((h ^ (h >> 16)) & 0x7fffffff) / (float)int.MaxValue;
        }
    }
}
