using UnityEngine;
using UnityEngine.Rendering;
using Suimono.Core;

// Reversible runtime daylight preset for the multi-camera water scene.
[DefaultExecutionOrder(10000)]
public sealed class USVDaylightPresentation : MonoBehaviour
{
    [Range(10f,75f)] public float sunElevation=38f;
    public float sunAzimuth=145f;
    [Range(0.2f,2f)] public float sunIntensity=1.15f;
    Light previousSun;
    Light sun; SuimonoObject water; Material previousSky, sky;
    RenderTexture reflection;
    bool initialized;
    Quaternion previousRotation;Color previousSunColor;float previousIntensity;LightShadows previousShadows;
    AmbientMode previousAmbientMode;Color previousSkyAmbient,previousEquator,previousGround;
    bool previousFog;FogMode previousFogMode;float previousFogDensity;Color previousFogColor;
    Texture previousCube;int previousFallback;bool previousDynamic;
    float previousRoughness,previousRoughness2,previousSpecular,previousReflectTerm;Color previousReflectionColor;

    void LateUpdate()
    {
        if(!initialized)Initialize();
        if(!initialized)return;
        // The demo's time-of-day slider updates in LateUpdate too. Applying
        // this preset afterwards keeps a consistent light while enabled.
        sun.transform.rotation=Quaternion.Euler(sunElevation,sunAzimuth,0);
        sun.color=new Color(1f,0.975f,0.94f);sun.intensity=sunIntensity;sun.shadows=LightShadows.Soft;
        if(reflection==null)CaptureSky();
    }

    void Initialize()
    {
        previousSun=RenderSettings.sun;
        sun=RenderSettings.sun;
        if(sun==null)foreach(var candidate in FindObjectsOfType<Light>())
            if(candidate.type==LightType.Directional && candidate.enabled){sun=candidate;break;}
        if(sun==null)return;
        water=FindObjectOfType<SuimonoObject>();
        previousRotation=sun.transform.rotation;previousSunColor=sun.color;previousIntensity=sun.intensity;previousShadows=sun.shadows;
        previousSky=RenderSettings.skybox;
        previousAmbientMode=RenderSettings.ambientMode;previousSkyAmbient=RenderSettings.ambientSkyColor;
        previousEquator=RenderSettings.ambientEquatorColor;previousGround=RenderSettings.ambientGroundColor;
        previousFog=RenderSettings.fog;previousFogMode=RenderSettings.fogMode;previousFogDensity=RenderSettings.fogDensity;previousFogColor=RenderSettings.fogColor;
        Shader shader=Shader.Find("Skybox/Procedural");
        if(shader!=null){
            sky=new Material(shader){name="USV neutral daylight"};
            sky.SetFloat("_AtmosphereThickness",0.85f);sky.SetFloat("_Exposure",1.05f);
            sky.SetFloat("_SunSize",0.018f);sky.SetColor("_SkyTint",new Color(0.5f,0.53f,0.57f));
            sky.SetColor("_GroundColor",new Color(0.32f,0.36f,0.40f));
            RenderSettings.skybox=sky;
        }
        RenderSettings.sun=sun;
        RenderSettings.ambientMode=AmbientMode.Trilight;
        RenderSettings.ambientSkyColor=new Color(0.62f,0.72f,0.84f);
        RenderSettings.ambientEquatorColor=new Color(0.40f,0.47f,0.54f);
        RenderSettings.ambientGroundColor=new Color(0.18f,0.21f,0.24f);
        RenderSettings.fog=true;RenderSettings.fogMode=FogMode.ExponentialSquared;
        RenderSettings.fogDensity=0.00018f;RenderSettings.fogColor=new Color(0.62f,0.70f,0.76f);
        if(water!=null){
            previousCube=water.customRefCubemap;previousFallback=water.reflectFallback;previousDynamic=water.enableDynamicReflections;
            previousRoughness=water.roughness;previousRoughness2=water.roughness2;previousSpecular=water.specularPower;
            previousReflectTerm=water.reflectTerm;previousReflectionColor=water.reflectionColor;
            water.roughness=0.22f;water.roughness2=0.40f;water.specularPower=0.40f;water.reflectTerm=0.022f;
            water.reflectionColor=new Color(0.92f,0.97f,1f,0.9f);
        }
        initialized=true;
        Debug.Log("[USVDaylight] Neutral daylight and softer water reflections enabled.");
    }

    void CaptureSky()
    {
        reflection=new RenderTexture(256,256,16,RenderTextureFormat.ARGBHalf){name="USV daylight sky reflection",dimension=TextureDimension.Cube,useMipMap=true,autoGenerateMips=false};
        reflection.Create();
        var go=new GameObject("USV sky capture"){hideFlags=HideFlags.HideAndDontSave};
        var camera=go.AddComponent<Camera>();camera.enabled=false;camera.cullingMask=0;camera.clearFlags=CameraClearFlags.Skybox;
        camera.nearClipPlane=0.1f;camera.farClipPlane=1000f;camera.RenderToCubemap(reflection);reflection.GenerateMips();
        Destroy(go);
        if(water!=null){
            // A sky cubemap is view-independent. Reusing a planar reflection
            // rendered for another camera caused inconsistent multi-view glare.
            water.customRefCubemap=reflection;water.reflectFallback=2;water.enableDynamicReflections=false;
        }
        DynamicGI.UpdateEnvironment();
    }

    void OnDisable()
    {
        if(!initialized)return;
        RenderSettings.sun=previousSun;
        RenderSettings.skybox=previousSky;RenderSettings.ambientMode=previousAmbientMode;
        RenderSettings.ambientSkyColor=previousSkyAmbient;RenderSettings.ambientEquatorColor=previousEquator;RenderSettings.ambientGroundColor=previousGround;
        RenderSettings.fog=previousFog;RenderSettings.fogMode=previousFogMode;RenderSettings.fogDensity=previousFogDensity;RenderSettings.fogColor=previousFogColor;
        if(sun!=null){sun.transform.rotation=previousRotation;sun.color=previousSunColor;sun.intensity=previousIntensity;sun.shadows=previousShadows;}
        if(water!=null){water.customRefCubemap=previousCube;water.reflectFallback=previousFallback;water.enableDynamicReflections=previousDynamic;
            water.roughness=previousRoughness;water.roughness2=previousRoughness2;water.specularPower=previousSpecular;water.reflectTerm=previousReflectTerm;water.reflectionColor=previousReflectionColor;}
        if(reflection!=null){reflection.Release();Destroy(reflection);reflection=null;}
        if(sky!=null)Destroy(sky);
        initialized=false;
    }
}
