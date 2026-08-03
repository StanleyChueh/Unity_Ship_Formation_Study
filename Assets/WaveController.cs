using UnityEngine;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using Suimono.Core;

/// <summary>
/// Receives SUIMONO wave settings and boat stern-wake settings from Python via
/// UDP and applies them at runtime. Add this script to any GameObject in the
/// scene. Set listenPort to match WAVE_CONTROL_PORT in config.py (default: 5070).
///
/// Python sends: {"cmd":"set_wave","wave_height":X,"turbulence":X,
///                "large_wave_height":X,"large_wave_scale":X,
///                "wave_scale":X,"flow_speed":X,"camera_tilt_strength":X}
///
/// and:          {"cmd":"set_wake","enable":1,"target":"leader",
///                "rate_over_time":X,"rate_over_distance":X,"lifetime":X,
///                "start_size_min":X,"start_size_max":X,"size_growth":X,
///                "alpha":X,"lift":X,"width":X,"max_particles":N}
/// </summary>
public class WaveController : MonoBehaviour
{
    [Header("UDP 接收埠 (需與 config.py WAVE_CONTROL_PORT 一致)")]
    public int listenPort = 5070;

    private SuimonoModule suimonoModule;
    private CameraWaveTilt[] cameraWaveTilts;
    private UdpClient udpClient;
    private Thread receiveThread;
    private volatile bool isRunning = false;

    [System.Serializable]
    private class WaveCmd
    {
        public string cmd;
        public float wave_height;
        public float turbulence;
        public float large_wave_height;
        public float large_wave_scale;
        public float wave_scale;
        public float flow_speed;
        public float camera_tilt_strength;
    }

    [System.Serializable]
    private class WakeCmd
    {
        public string cmd;
        public int enable;              // 0 = stop wake emission entirely
        public string target;           // "leader" (default) or "all"
        public float rate_over_time;    // particles per second
        public float rate_over_distance;// particles per metre travelled
        public float lifetime;          // seconds each foam puff survives
        public float start_size_min;
        public float start_size_max;
        public float size_growth;       // size-over-lifetime multiplier
        public float alpha;             // 0..1 opacity of each puff
        public float lift;              // world-space upward velocity (m/s)
        public float width;             // emitter box width across the stern
        public int max_particles;
    }

    private WaveCmd pendingCmd = null;
    private WakeCmd pendingWakeCmd = null;
    private readonly object pendingLock = new object();

    // Resolved once on first set_wake, then reused.
    private List<ParticleSystem> leaderWakes;
    private List<ParticleSystem> allWakes;

    void Start()
    {
        suimonoModule = FindObjectOfType<SuimonoModule>();
        cameraWaveTilts = FindObjectsOfType<CameraWaveTilt>();

        if (suimonoModule == null)
            Debug.LogWarning("[WaveController] SuimonoModule not found in scene — wave settings will not apply.");
        if (suimonoModule != null && suimonoModule.suimonoObject == null)
            Debug.LogWarning("[WaveController] SuimonoModule.suimonoObject is null — assign the water object in the inspector.");

        try
        {
            udpClient = new UdpClient(listenPort);
            isRunning = true;
            receiveThread = new Thread(ReceiveLoop) { IsBackground = true, Name = "WaveControllerUDP" };
            receiveThread.Start();
            Debug.Log($"[WaveController] Listening for wave settings on UDP port {listenPort}");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[WaveController] Failed to bind UDP port {listenPort}: {e.Message}");
        }
    }

    void Update()
    {
        WaveCmd cmd;
        WakeCmd wakeCmd;
        lock (pendingLock)
        {
            cmd = pendingCmd;
            pendingCmd = null;
            wakeCmd = pendingWakeCmd;
            pendingWakeCmd = null;
        }
        if (cmd != null)
            ApplyWaveCmd(cmd);
        if (wakeCmd != null)
            ApplyWakeCmd(wakeCmd);
    }

    void ReceiveLoop()
    {
        IPEndPoint ep = new IPEndPoint(IPAddress.Any, 0);
        while (isRunning)
        {
            try
            {
                byte[] data = udpClient.Receive(ref ep);
                string json = Encoding.UTF8.GetString(data);
                if (json.Contains("set_wave"))
                {
                    WaveCmd cmd = JsonUtility.FromJson<WaveCmd>(json);
                    if (cmd != null && cmd.cmd == "set_wave")
                        lock (pendingLock) { pendingCmd = cmd; }
                }
                else if (json.Contains("set_wake"))
                {
                    WakeCmd cmd = JsonUtility.FromJson<WakeCmd>(json);
                    if (cmd != null && cmd.cmd == "set_wake")
                        lock (pendingLock) { pendingWakeCmd = cmd; }
                }
            }
            catch (System.Exception) { }
        }
    }

    void ApplyWaveCmd(WaveCmd cmd)
    {
        if (suimonoModule != null && suimonoModule.suimonoObject != null)
        {
            SuimonoObject obj = suimonoModule.suimonoObject;
            obj.customWaves      = true;   // prevents Beaufort scale from overwriting Python's values
            obj.waveHeight       = cmd.wave_height;
            obj.turbulenceFactor = cmd.turbulence;
            obj.lgWaveHeight     = cmd.large_wave_height;
            obj.lgWaveScale      = cmd.large_wave_scale;
            obj.waveScale        = cmd.wave_scale;
            obj.flowSpeed        = cmd.flow_speed;
            Debug.Log($"[WaveController] Applied: waveHeight={obj.waveHeight:F3} turb={obj.turbulenceFactor:F3} lgH={obj.lgWaveHeight:F3} lgScale={obj.lgWaveScale:F5} scale={obj.waveScale:F3} speed={obj.flowSpeed:F3}");
        }

        foreach (var cwt in cameraWaveTilts)
            cwt.tiltStrength = cmd.camera_tilt_strength;

        if (cameraWaveTilts.Length > 0)
            Debug.Log($"[WaveController] CameraWaveTilt tiltStrength set to {cmd.camera_tilt_strength:F2} on {cameraWaveTilts.Length} camera(s)");
    }

    /// <summary>
    /// Locates the fx_boatwake particle systems. The leader is found through any
    /// ShipUDPInterface that carries a leaderBoat reference (the followers do),
    /// falling back to a GameObject named "Leader".
    /// </summary>
    void ResolveWakeSystems()
    {
        allWakes = new List<ParticleSystem>();
        leaderWakes = new List<ParticleSystem>();

        foreach (ParticleSystem ps in FindObjectsOfType<ParticleSystem>(true))
        {
            if (ps.gameObject.name.ToLowerInvariant().Contains("wake"))
                allWakes.Add(ps);
        }

        Transform leader = null;
        foreach (ShipUDPInterface iface in FindObjectsOfType<ShipUDPInterface>())
        {
            if (iface.leaderBoat != null) { leader = iface.leaderBoat; break; }
        }
        if (leader == null)
        {
            GameObject go = GameObject.Find("Leader");
            if (go != null) leader = go.transform;
        }

        if (leader != null)
        {
            foreach (ParticleSystem ps in allWakes)
                if (ps.transform.IsChildOf(leader)) leaderWakes.Add(ps);
        }

        if (allWakes.Count == 0)
            Debug.LogWarning("[WaveController] No fx_boatwake particle systems found — wake settings will not apply.");
        else if (leaderWakes.Count == 0)
            Debug.LogWarning("[WaveController] Leader boat not found — 'leader' target falls back to no-op; use target='all'.");
    }

    void ApplyWakeCmd(WakeCmd cmd)
    {
        // A wake tweak is a cosmetic stress-test knob — it must never be able to
        // throw into Unity's player loop, because with Console "Error Pause"
        // enabled that halts the whole editor mid-run.
        try
        {
            if (allWakes == null || allWakes.Count == 0) ResolveWakeSystems();

            bool leaderOnly = string.IsNullOrEmpty(cmd.target) || cmd.target.ToLowerInvariant() != "all";
            List<ParticleSystem> targets = leaderOnly ? leaderWakes : allWakes;
            if (targets == null || targets.Count == 0)
            {
                Debug.LogWarning("[WaveController] No wake particle systems resolved — wake command ignored.");
                return;
            }

            int applied = 0;
            foreach (ParticleSystem ps in targets)
            {
                if (ps == null) continue;
                try
                {
                    ApplyWakeToSystem(ps, cmd);
                    applied++;
                }
                catch (System.Exception e)
                {
                    Debug.LogWarning($"[WaveController] Wake apply skipped on '{ps.name}': {e.Message}");
                }
            }

            Debug.Log(
                $"[WaveController] Wake applied to {applied} system(s) [{(leaderOnly ? "leader" : "all")}]: " +
                $"enable={cmd.enable} rate={cmd.rate_over_time:F0}/s +{cmd.rate_over_distance:F0}/m " +
                $"life={cmd.lifetime:F1}s size={cmd.start_size_min:F2}-{cmd.start_size_max:F2}x{cmd.size_growth:F1} " +
                $"alpha={cmd.alpha:F3} lift={cmd.lift:F2} width={cmd.width:F1} max={cmd.max_particles}");
        }
        catch (System.Exception e)
        {
            Debug.LogWarning($"[WaveController] Wake command failed, run continues unaffected: {e}");
        }
    }

    void ApplyWakeToSystem(ParticleSystem ps, WakeCmd cmd)
    {
        ParticleSystem.MainModule main = ps.main;
        ParticleSystem.EmissionModule emission = ps.emission;

        if (cmd.enable == 0)
        {
            emission.rateOverTime = new ParticleSystem.MinMaxCurve(0f);
            emission.rateOverDistance = new ParticleSystem.MinMaxCurve(0f);
            emission.enabled = false;
            return;
        }

        float sizeMin = Mathf.Min(cmd.start_size_min, cmd.start_size_max);
        float sizeMax = Mathf.Max(cmd.start_size_min, cmd.start_size_max);

        main.startLifetime = new ParticleSystem.MinMaxCurve(Mathf.Max(0.01f, cmd.lifetime));
        main.startSize = new ParticleSystem.MinMaxCurve(sizeMin, sizeMax);
        main.startColor = new ParticleSystem.MinMaxGradient(
            new Color(1f, 1f, 1f, Mathf.Clamp01(cmd.alpha)));
        main.maxParticles = Mathf.Max(1, cmd.max_particles);

        emission.enabled = true;
        emission.rateOverTime = new ParticleSystem.MinMaxCurve(Mathf.Max(0f, cmd.rate_over_time));
        emission.rateOverDistance = new ParticleSystem.MinMaxCurve(Mathf.Max(0f, cmd.rate_over_distance));

        if (cmd.width > 0f)
        {
            ParticleSystem.ShapeModule shape = ps.shape;
            if (shape.enabled)
            {
                Vector3 scale = shape.scale;
                scale.x = cmd.width;
                shape.scale = scale;
            }
        }

        // sizeMultiplier is only meaningful while the module is in Curve mode;
        // touching it otherwise logs an error, which trips Error Pause.
        ParticleSystem.SizeOverLifetimeModule sizeOverLifetime = ps.sizeOverLifetime;
        if (cmd.size_growth > 0f && sizeOverLifetime.enabled)
        {
            ParticleSystemCurveMode mode = sizeOverLifetime.size.mode;
            if (mode == ParticleSystemCurveMode.Curve || mode == ParticleSystemCurveMode.TwoCurves)
                sizeOverLifetime.sizeMultiplier = cmd.size_growth;
        }

        // World-space lift so spray rises into the follower camera's line of
        // sight regardless of how the boat model is rotated.
        //
        // All three velocity axes MUST be written in the same curve mode.  The
        // scene authors x/y/z as TwoConstants; assigning a single-argument
        // MinMaxCurve (Constant mode) to only y makes Unity log "Particle
        // Velocity curves must all be in the same mode" every frame, which halts
        // the editor outright when Console > Error Pause is enabled.  Hence the
        // two-argument constructor on every axis.
        //
        // A deadband keeps the module completely untouched at low lift, so the
        // normal intensity sweep never goes near this code path.
        if (Mathf.Abs(cmd.lift) > 0.01f)
        {
            ParticleSystem.VelocityOverLifetimeModule velocity = ps.velocityOverLifetime;
            velocity.space = ParticleSystemSimulationSpace.World;
            velocity.x = new ParticleSystem.MinMaxCurve(0f, 0f);
            velocity.y = new ParticleSystem.MinMaxCurve(cmd.lift, cmd.lift);
            velocity.z = new ParticleSystem.MinMaxCurve(0f, 0f);
            velocity.enabled = true;
        }

        // Deliberately NOT calling Clear()/Play() here — restarting an emitter
        // that SUIMONO's FX pool also drives can stall it.  New particles pick
        // up the new settings on their own; existing ones just age out.
    }

    void OnApplicationQuit()
    {
        isRunning = false;
        try { udpClient?.Close(); } catch { }
    }

    void OnDestroy()
    {
        isRunning = false;
        try { udpClient?.Close(); } catch { }
    }
}
