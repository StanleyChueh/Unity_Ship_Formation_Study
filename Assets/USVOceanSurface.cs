using UnityEngine;
using Suimono.Core;

/// <summary>
/// Shared world-space ocean swells. The same amplitudes, wave vectors, phase
/// time and analytic slopes drive water geometry, shading and buoyancy.
/// Suimono's texture ripples remain fine visual detail, not hull-sized waves.
/// </summary>
[DefaultExecutionOrder(-200)]
[DisallowMultipleComponent]
public sealed class USVOceanSurface : MonoBehaviour
{
    public static USVOceanSurface Instance { get; private set; }
    public static bool Active => Instance != null && Instance.isActiveAndEnabled;
    public const int WaveCount = 4;
    readonly Vector4[] waves = new Vector4[WaveCount];
    static readonly float[] Wavelengths = { 8f, 13f, 23f, 41f };
    static readonly float[] Weights = { 0.45f, 0.28f, 0.18f, 0.09f };
    static readonly float[] Directions = { 0f, 48f, -37f, 105f };
    SuimonoObject water;
    float height;
    bool initialized;

    void Awake() { Instance = this; }
    void OnEnable() { Shader.SetGlobalFloat("_usvOceanOn", 1f); }
    void OnDisable() { Shader.SetGlobalFloat("_usvOceanOn", 0f); }
    void OnDestroy() { if (Instance == this) Instance = null; }

    void Update()
    {
        if (water == null) water = FindObjectOfType<SuimonoObject>();
        if (water == null) { Shader.SetGlobalFloat("_usvOceanOn", 0f); return; }
        // lgWaveHeight is now an explicit height budget in metres: the sum of
        // component peak-to-trough heights, not Suimono's texture height gain.
        float targetHeight = Mathf.Max(0f, water.lgWaveHeight * water.useHeightProjection);
        height = initialized ? Mathf.Lerp(height, targetHeight, 1f - Mathf.Exp(-Time.deltaTime / 1.5f)) : targetHeight;
        initialized = true;
        float lengthScale = Mathf.Clamp(0.04f / Mathf.Max(0.005f, water.lgWaveScale), 0.4f, 4f);
        for (int i = 0; i < WaveCount; i++)
        {
            float angle = (water.flowDirection + Directions[i]) * Mathf.Deg2Rad;
            float k = 2f * Mathf.PI / (Wavelengths[i] * lengthScale);
            waves[i] = new Vector4(k * Mathf.Sin(angle), k * Mathf.Cos(angle),
                0.5f * height * Weights[i], Mathf.Sqrt(9.81f * k));
        }
        Shader.SetGlobalVectorArray("_usvOceanWaves", waves);
        Shader.SetGlobalFloat("_usvOceanTime", Time.time);
        Shader.SetGlobalFloat("_usvOceanDetail", Mathf.Clamp01(height / 0.55f));
        Shader.SetGlobalFloat("_usvOceanOn", 1f);
    }

    public static float SampleHeight(Vector3 p) => Sample(p, Time.time).x;

    // x = displacement (metres), yz = dh/dx, dh/dz. Public time argument also
    // allows direct CPU/GPU agreement checks without physics-frame ambiguity.
    public static Vector3 Sample(Vector3 p, float time)
    {
        if (!Active) return Vector3.zero;
        Vector3 result = Vector3.zero;
        for (int i = 0; i < WaveCount; i++)
        {
            Vector4 w = Instance.waves[i];
            float phase = w.x * p.x + w.y * p.z - w.w * time + i * 1.73f;
            float c = w.z * Mathf.Cos(phase);
            result.x += w.z * Mathf.Sin(phase);
            result.y += w.x * c;
            result.z += w.y * c;
        }
        return result;
    }
}
