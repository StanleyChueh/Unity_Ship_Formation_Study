using UnityEngine;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using Suimono.Core;

/// <summary>
/// Receives SUIMONO wave settings from Python via UDP and applies them to the
/// SuimonoObject at runtime. Add this script to any GameObject in the scene.
/// Set listenPort to match WAVE_CONTROL_PORT in config.py (default: 5070).
///
/// Python sends: {"cmd":"set_wave","wave_height":X,"turbulence":X,
///                "large_wave_height":X,"large_wave_scale":X,
///                "wave_scale":X,"flow_speed":X,"camera_tilt_strength":X}
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

    private WaveCmd pendingCmd = null;
    private readonly object pendingLock = new object();

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
        lock (pendingLock)
        {
            cmd = pendingCmd;
            pendingCmd = null;
        }
        if (cmd != null)
            ApplyWaveCmd(cmd);
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
                if (!json.Contains("set_wave")) continue;
                WaveCmd cmd = JsonUtility.FromJson<WaveCmd>(json);
                if (cmd != null && cmd.cmd == "set_wave")
                    lock (pendingLock) { pendingCmd = cmd; }
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
