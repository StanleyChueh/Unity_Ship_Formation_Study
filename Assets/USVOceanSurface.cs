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
    public const int WaveCount = 16;
    readonly Vector4[] waves = new Vector4[WaveCount];
    static readonly float[] Wavelengths = {5.6f,6.9f,8.3f,9.7f,11.5f,13.4f,15.9f,18.8f,22.3f,26.5f,31.7f,38.1f,45.3f,54.2f,65.1f,79.3f};
    static readonly float[] Weights = {0.02f,0.035f,0.06f,0.085f,0.105f,0.12f,0.115f,0.105f,0.09f,0.075f,0.06f,0.045f,0.035f,0.025f,0.015f,0.01f};
    static readonly float[] Directions = {-31f,18f,-9f,42f,-24f,8f,31f,-42f,17f,-5f,55f,-29f,4f,38f,-15f,68f};
    static readonly float[] Phases = {0.29f,4.15f,1.77f,5.82f,0.93f,3.21f,5.04f,2.48f,6.02f,1.39f,3.87f,0.47f,4.69f,2.91f,5.61f,1.08f};
    readonly Vector4[] ripples = new Vector4[6];
    SuimonoObject water;
    float height;
    bool initialized;

    void Awake() {
        Instance = this;
        Texture2D photo=Resources.Load<Texture2D>("USVPhotographicSpray");
        Shader.SetGlobalTexture("_usvFoamPhoto",photo);
        Shader.SetGlobalFloat("_usvFoamPhotoOn",photo!=null ? 1f : 0f);
    }
    void OnEnable() { Shader.SetGlobalFloat("_usvOceanOn", 1f); }
    void OnDisable() { Shader.SetGlobalFloat("_usvOceanOn", 0f); }
    void OnDestroy() { if (Instance == this) Instance = null; }

    void Update()
    {
        if (water == null) water = FindObjectOfType<SuimonoObject>();
        if (water == null) { Shader.SetGlobalFloat("_usvOceanOn", 0f); return; }
        // Nominal swell-height scale, energy normalized across a directional
        // spectrum. No single component dominates the surface as a sine band.
        float targetHeight = Mathf.Max(0f, water.lgWaveHeight * water.useHeightProjection);
        height = initialized ? Mathf.Lerp(height, targetHeight, 1f - Mathf.Exp(-Time.deltaTime / 1.5f)) : targetHeight;
        initialized = true;
        float lengthScale = Mathf.Clamp(0.04f / Mathf.Max(0.005f, water.lgWaveScale), 0.4f, 4f);
        float energy=0f;
        foreach(float weight in Weights) energy+=weight*weight;
        float amplitudeNorm=Mathf.Sqrt(0.3214f/energy);
        for (int i = 0; i < WaveCount; i++)
        {
            float angle = (water.flowDirection + Directions[i]) * Mathf.Deg2Rad;
            float k = 2f * Mathf.PI / (Wavelengths[i] * lengthScale);
            waves[i] = new Vector4(k * Mathf.Sin(angle), k * Mathf.Cos(angle),
                0.5f * height * Weights[i] * amplitudeNorm, Mathf.Sqrt(9.81f * k));
        }
        for(int i=0;i<ripples.Length;i++){
            float angle=(water.flowDirection+Directions[i])*Mathf.Deg2Rad;
            float k=2f*Mathf.PI/(0.22f*Mathf.Pow(1.65f,i));
            ripples[i]=new Vector4(k*Mathf.Sin(angle),k*Mathf.Cos(angle),0.035f/Mathf.Pow(1.2f,i),Mathf.Sqrt(9.81f*k));
        }
        Transform surface=water.transform.Find("Suimono_Object");
        Shader.SetGlobalFloat("_usvOceanBaseHeight",surface!=null ? surface.position.y : water.transform.position.y);
        Shader.SetGlobalVectorArray("_usvOceanRipples",ripples);
        Shader.SetGlobalFloatArray("_usvOceanPhases",Phases);
        // A new property name avoids old four-entry array bindings retained in the editor.
        Shader.SetGlobalVectorArray("_usvOceanSpectrum16", waves);
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
            float phase = w.x * p.x + w.y * p.z - w.w * time + Phases[i];
            float c = w.z * Mathf.Cos(phase);
            result.x += w.z * Mathf.Sin(phase);
            result.y += w.x * c;
            result.z += w.y * c;
        }
        return result;
    }
}
