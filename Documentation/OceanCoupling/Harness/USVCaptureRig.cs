using System.Collections;
using System.IO;
using System.Text;
using UnityEngine;

// Verification-only (scratch copy of the project): renders views of the wake
// and logs hull motion, then quits. Activated by the -usvcapture <dir> argument.
public class USVCaptureRig : MonoBehaviour
{
    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    static void Boot()
    {
        if (!System.Environment.CommandLine.Contains("-usvcapture")) return;
        // Isolate from any real controller / editor session: private ports, no camera streams.
        int port = 46100;
        foreach (ShipUDPInterface s in FindObjectsOfType<ShipUDPInterface>()) {
            s.receivePort = s.name == "Leader" ? 46102 : (s.name == "Follower_Left" ? 46100 : 46101);
            s.sendPort = s.name == "Follower_Left" ? 46110 : (s.name == "Follower_Right" ? 46111 : 9);
        }
        port = 46103;
        foreach (WaveController w in FindObjectsOfType<WaveController>()) w.listenPort = port++;
        foreach (MainCameraStreamSender m in FindObjectsOfType<MainCameraStreamSender>()) {
            if (System.Environment.CommandLine.Contains("-usvvision")) m.serverPort += 35000;
            else { m.StopAllCoroutines(); m.enabled = false; }
        }
        new GameObject("USVCaptureRig").AddComponent<USVCaptureRig>();
    }

    System.Reflection.FieldInfo thrField = typeof(ShipUDPInterface).GetField("targetThrottle", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
    System.Reflection.FieldInfo steerField = typeof(ShipUDPInterface).GetField("targetSteer", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
    Vector2 offL, offR;   // follower offsets in the leader frame (along, lateral)
    bool started;

    void StartRun()
    {
        started = true;
        var sm = leader.GetComponent<SimpleMove>();
        sm.trajectoryMode = SimpleMove.TrajectoryMode.Circle;
        sm.circleRadius = 360f; sm.trajectorySpeed = 18f; sm.enableTrajectorySpeedRamp = true;
        sm.trajectoryAcceleration = 3f; sm.trajectoryInitialSpeed = 0f; sm.loopTrajectory = true;
        sm.controlMode = SimpleMove.ControlMode.Trajectory;
        sm.ResetTrajectory();
        offL = Offset(fl); offR = Offset(fr);
        string[] args = System.Environment.GetCommandLineArgs();
        for (int k = 0; k < args.Length - 1; k++)
            if (args[k] == "-usvwakegain" && USVWakeField.Instance != null)
                USVWakeField.Instance.amplitudePerLength *= float.Parse(args[k + 1], System.Globalization.CultureInfo.InvariantCulture);
        float sea = 0.55f;
        for (int k = 0; k < args.Length-1; k++) if (args[k]=="-usvsea") sea=float.Parse(args[k+1],System.Globalization.CultureInfo.InvariantCulture);
        if (System.Environment.CommandLine.Contains("-usvnowake"))
            typeof(WaveController).GetMethod("SetRealisticWake",System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .Invoke(FindObjectOfType<WaveController>(), new object[]{false,false,1f,true});
        // Shared geometric sea
        var so = FindObjectOfType<Suimono.Core.SuimonoObject>();
        if (so != null)
        {
            so.customWaves = true; so.waveHeight = 0.50f; so.turbulenceFactor = 0.12f; so.lgWaveHeight = sea;
            so.lgWaveScale = 0.040f; so.waveScale = 0.45f; so.flowSpeed = 0.010f;
        }
        Debug.Log($"[Capture] run started; offsets L={offL} R={offR} sea={(so != null)}");
    }

    Vector2 Offset(Transform b)
    {
        Vector3 f = Fwd(leader), r = Vector3.Cross(Vector3.up, f), d = b.position - leader.position;
        return new Vector2(Vector3.Dot(d, f), Vector3.Dot(d, r));
    }

    void Drive(Transform b, Vector2 off)
    {
        var iface = b.GetComponent<ShipUDPInterface>();
        var rb = b.GetComponent<Rigidbody>();
        var lrb = leader.GetComponent<Rigidbody>();
        Vector3 f = Fwd(leader), r = Vector3.Cross(Vector3.up, f);
        Vector3 target = leader.position + f * off.x + r * off.y;
        Vector3 bf = Fwd(b);
        float alongErr = Vector3.Dot(target - b.position, f);
        float vL = new Vector2(lrb.velocity.x, lrb.velocity.z).magnitude;
        float thr = Mathf.Clamp((vL + 0.6f * alongErr) / 23.4f, 0f, 0.95f);
        Vector3 aim = target + f * 15f - b.position; aim.y = 0f;
        float ang = Vector3.SignedAngle(bf, aim, Vector3.up);
        float yawRate = Vector3.Dot(rb.angularVelocity, Vector3.up) * Mathf.Rad2Deg;
        thrField.SetValue(iface, thr);
        steerField.SetValue(iface, Mathf.Clamp(ang / 15f - yawRate / 60f, -1f, 1f));
    }

    void FixedUpdate()
    {
        if (leader == null || System.Environment.CommandLine.Contains("-usvvision")) return;
        if (!started && Time.time > 3f) StartRun();
        if (started) {
            if (System.Environment.CommandLine.Contains("-usvcrosswake") && Time.time > 14f)
                offR.y = 5f * Mathf.Sin((Time.time - 14f) * 0.35f);
            Drive(fl, offL); Drive(fr, offR);
        }
    }

    string outDir = "capture";
    Transform leader, fl, fr;
    Camera frontCam, rig;
    float moveTime = -1f, lastLog;
    readonly float[] shots = { 5f, 9f, 13f, 18f, 24f, 32f };
    int next;
    readonly StringBuilder motion = new StringBuilder("t,boat,speed,pitch_deg,roll_deg,heave_m,wake_at_boat_m,surface_m,surface_pitch_deg,surface_roll_deg,camera_roll_deg\n");
    readonly StringBuilder wake = new StringBuilder("t,s_behind,y_abeam,eta_m\n");
    bool busy;
    float lastVideo;
    int videoFrame;

    void Start()
    {
        string[] a = System.Environment.GetCommandLineArgs();
        for (int i = 0; i < a.Length - 1; i++) if (a[i] == "-usvcapture") outDir = a[i + 1];
        Directory.CreateDirectory(outDir);
        leader = GameObject.Find("Leader")?.transform;
        fl = GameObject.Find("Follower_Left")?.transform;
        fr = GameObject.Find("Follower_Right")?.transform;
        if (fr != null)
            foreach (Camera c in fr.GetComponentsInChildren<Camera>(true))
                if (c.name == "Camera") frontCam = c;
        var go = new GameObject("CaptureCam");
        rig = go.AddComponent<Camera>();
        if (frontCam != null) rig.CopyFrom(frontCam);
        rig.enabled = false;
        rig.fieldOfView = 55f;
        rig.farClipPlane = 3000f;
        Debug.Log($"[Capture] out={outDir} leader={leader != null} front={frontCam != null}");
    }

    static Vector3 Fwd(Transform t) { Vector3 f = t.TransformDirection(Vector3.up); f.y = 0; return f.normalized; }

    void Log(Transform b, float t)
    {
        if (b == null) return;
        Vector3 f = Fwd(b), r = Vector3.Cross(Vector3.up, f), up = b.TransformDirection(Vector3.forward);
        var rb = b.GetComponent<Rigidbody>();
        float sp = rb ? new Vector2(rb.velocity.x, rb.velocity.z).magnitude : 0f;
        motion.AppendFormat(System.Globalization.CultureInfo.InvariantCulture, "{0:F2},{1},{2:F2},{3:F2},{4:F2},{5:F3},{6:F3},{7:F3},{8:F3},{9:F3},{10:F3}\n", t, b.name, sp,
            Mathf.Asin(Vector3.Dot(up, -f)) * Mathf.Rad2Deg, Mathf.Asin(Vector3.Dot(up, r)) * Mathf.Rad2Deg, b.position.y,
            USVWakeField.SampleHeight(b.position), USVOceanSurface.SampleHeight(b.position),
            Mathf.Atan(USVOceanSurface.Sample(b.position,Time.time).y*f.x + USVOceanSurface.Sample(b.position,Time.time).z*f.z)*Mathf.Rad2Deg,
            -Mathf.Atan(USVOceanSurface.Sample(b.position,Time.time).y*r.x + USVOceanSurface.Sample(b.position,Time.time).z*r.z)*Mathf.Rad2Deg,
            frontCam != null && b == fr ? Vector3.SignedAngle(Vector3.up,frontCam.transform.up,frontCam.transform.forward) : 0f);
    }

    void LateUpdate()
    {
        float t = Time.time;
        if (t >= 12f && t < 22f && t-lastVideo >= 0.1f && frontCam != null && System.Environment.CommandLine.Contains("-usvvideo"))
        {
            lastVideo = t;
            Save(frontCam, $"video_boat_{videoFrame:D4}");
            Vector3 f = Fwd(leader), L = leader.position;
            Shoot($"video_chase_{videoFrame:D4}", L - f*24f + Vector3.up*7f, L-f*6f,55f,false);
            videoFrame++;
        }
        if (leader != null && moveTime < 0f)
        {
            var rb = leader.GetComponent<Rigidbody>();
            if (rb != null && new Vector2(rb.velocity.x, rb.velocity.z).magnitude > 1f) moveTime = t;
        }
        if (t - lastLog > 0.05f) { lastLog = t; Log(leader, t); Log(fl, t); Log(fr, t); }
        if (moveTime > 0f && next < shots.Length && !busy && t - moveTime >= shots[next])
        {
            StartCoroutine(Capture(next, t - moveTime));
            next++;
        }
        if ((moveTime > 0f && next >= shots.Length && !busy && t - moveTime > shots[shots.Length - 1] + 1f) || t > 240f)
        {
            File.WriteAllText(Path.Combine(outDir, "motion.csv"), motion.ToString());
            File.WriteAllText(Path.Combine(outDir, "wake_profile.csv"), wake.ToString());
            Debug.Log("[Capture] done");
            Application.Quit();
        }
    }

    IEnumerator Capture(int i, float since)
    {
        busy = true;
        yield return new WaitForEndOfFrame();
        Vector3 f = Fwd(leader), r = Vector3.Cross(Vector3.up, f), L = leader.position;
        float wl = L.y;
        // Cross-section of the CPU wake field 20 m astern of the leader.
        for (float y = -15f; y <= 15.01f; y += 0.5f)
            wake.AppendFormat(System.Globalization.CultureInfo.InvariantCulture, "{0:F1},20,{1:F1},{2:F3}\n", since, y, USVWakeField.SampleHeight(L - f * 20f + r * y));

        Shoot($"{i}_chase_t{since:F0}", L - f * 28f + Vector3.up * 11f, L - f * 4f, 55f, false);
        Shoot($"{i}_low_t{since:F0}", L - f * 30f + r * 14f + Vector3.up * 2.2f, L - f * 2f, 50f, false);
        Shoot($"{i}_side_t{since:F0}", L + r * 22f + f * 6f + Vector3.up * 5f, L - f * 22f, 55f, false);
        Shoot($"{i}_high_t{since:F0}", L - f * 70f + r * 25f + Vector3.up * 45f, L - f * 30f, 55f, false);
        if (!System.Environment.CommandLine.Contains("-usvvision")) DumpField($"{i}_field_t{since:F0}");
        if (frontCam != null)
        {
            Save(frontCam, $"{i}_followerR_cam_t{since:F0}");
            var fog = frontCam.GetComponent("Suimono_UnderwaterFog") as Behaviour;
            if (fog != null && fog.enabled)
            {
                fog.enabled = false;
                Save(frontCam, $"{i}_followerR_cam_nofog_t{since:F0}");
                fog.enabled = true;
            }
        }
        busy = false;
    }

    void Shoot(string name, Vector3 pos, Vector3 look, float fov, bool ortho)
    {
        rig.transform.position = pos;
        rig.transform.rotation = ortho ? Quaternion.LookRotation(Vector3.down, Fwd(leader)) : Quaternion.LookRotation(look - pos, Vector3.up);
        rig.orthographic = ortho;
        rig.orthographicSize = 70f;
        if (!ortho) rig.fieldOfView = fov;
        Save(rig, name);
    }

    // GPU wake field (R = height, G = foam) as an image: grey = flat, brighter = crest, red = foam.
    void DumpField(string name)
    {
        var rt = Shader.GetGlobalTexture("_usvWakeTex") as RenderTexture;
        if (rt == null) { Debug.Log("[Capture] no wake texture"); return; }
        var tmp = new Texture2D(rt.width, rt.height, TextureFormat.RGBAFloat, false);
        RenderTexture.active = rt;
        tmp.ReadPixels(new Rect(0, 0, rt.width, rt.height), 0, 0);
        tmp.Apply();
        RenderTexture.active = null;
        Color[] px = tmp.GetPixels();
        Vector4 rect = Shader.GetGlobalVector("_usvWakeRect");
        float maxDifference = 0f; float sumDifference = 0f; int samples = 0;
        for (int y = rt.height/20; y < rt.height*19/20; y += 7)
        for (int x = rt.width/20; x < rt.width*19/20; x += 7)
        {
            Vector3 pos = new Vector3(rect.x + (x + 0.5f) / rt.width * rect.z, 0,
                                      rect.y + (y + 0.5f) / rt.height * rect.z);
            float difference = Mathf.Abs(px[y * rt.width + x].r - USVWakeField.SampleHeight(pos));
            maxDifference = Mathf.Max(maxDifference, difference); sumDifference += difference; samples++;
        }
        Debug.Log($"[Validation] CPU/GPU {name}: samples={samples} max_error_m={maxDifference:F6} mean_error_m={sumDifference/samples:F6}");
        if (maxDifference > 0.005f) Debug.LogError("[Validation] CPU/GPU wake height disagreement");
        ValidateOcean(name);
        // Repeated controller commands must preserve the existing wave history.
        var controller = FindObjectOfType<WaveController>();
        Vector3 probe = leader.position - Fwd(leader)*20f + Vector3.Cross(Vector3.up,Fwd(leader))*3f;
        float before = USVWakeField.SampleHeight(probe);
        if (!System.Environment.CommandLine.Contains("-usvnowake"))
            typeof(WaveController).GetMethod("SetRealisticWake", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance)
                .Invoke(controller, new object[] {true,false,1f,true});
        float after = USVWakeField.SampleHeight(probe);
        if (Mathf.Abs(before-after)>0.0001f) Debug.LogError("[Validation] Wake command cleared history");
        var outPx = new Color32[px.Length];
        float maxH = 0f, maxF = 0f;
        for (int k = 0; k < px.Length; k++)
        {
            float h = px[k].r, fo = px[k].g;
            maxH = Mathf.Max(maxH, Mathf.Abs(h)); maxF = Mathf.Max(maxF, fo);
            byte g = (byte)Mathf.Clamp(128 + h * 600f, 0, 255);
            outPx[k] = new Color32((byte)Mathf.Clamp(g + fo * 200f, 0, 255), g, g, 255);
        }
        var img = new Texture2D(rt.width, rt.height, TextureFormat.RGBA32, false);
        img.SetPixels32(outPx); img.Apply();
        File.WriteAllBytes(Path.Combine(outDir, name + ".png"), img.EncodeToPNG());
        Debug.Log($"[Capture] field {name}: max|h|={maxH:F3} m maxFoam={maxF:F2}");
        Destroy(tmp); Destroy(img);
    }

    void ValidateOcean(string name)
    {
        var mat=new Material(Shader.Find("Hidden/USV/OceanProbe"));
        var rect=new Vector4(leader.position.x-30f,leader.position.z-30f,60f,0);
        mat.SetVector("_ProbeRect",rect);
        var rt=RenderTexture.GetTemporary(64,64,0,RenderTextureFormat.ARGBFloat,RenderTextureReadWrite.Linear);
        Graphics.Blit(null,rt,mat);
        var tex=new Texture2D(64,64,TextureFormat.RGBAFloat,false,true);
        RenderTexture.active=rt;tex.ReadPixels(new Rect(0,0,64,64),0,0);tex.Apply();RenderTexture.active=null;
        Color[] pixels=tex.GetPixels();float maxError=0f;
        for(int y=0;y<64;y++)for(int x=0;x<64;x++){
            Vector3 w=new Vector3(rect.x+(x+0.5f)/64f*60f,0,rect.y+(y+0.5f)/64f*60f);
            Vector3 cpu=USVOceanSurface.Sample(w,Shader.GetGlobalFloat("_usvOceanTime"));
            Color gpu=pixels[y*64+x];
            maxError=Mathf.Max(maxError,Mathf.Abs(cpu.x-gpu.r),Mathf.Abs(cpu.y-gpu.g),Mathf.Abs(cpu.z-gpu.b));
        }
        Debug.Log($"[OceanValidation] {name} height_and_slope_max_error={maxError:F7}");
        if(maxError>0.001f)Debug.LogError("Ocean CPU/GPU mismatch");
        RenderTexture.ReleaseTemporary(rt);Destroy(tex);Destroy(mat);
    }

    void Save(Camera cam, string name)
    {
        var rt = RenderTexture.GetTemporary(1280, 720, 24, RenderTextureFormat.ARGB32);
        RenderTexture prev = cam.targetTexture;
        cam.targetTexture = rt;
        cam.Render();
        cam.targetTexture = prev;
        RenderTexture.active = rt;
        var tex = new Texture2D(1280, 720, TextureFormat.RGB24, false);
        tex.ReadPixels(new Rect(0, 0, 1280, 720), 0, 0);
        tex.Apply();
        RenderTexture.active = null;
        File.WriteAllBytes(Path.Combine(outDir, name + ".png"), tex.EncodeToPNG());
        Destroy(tex);
        RenderTexture.ReleaseTemporary(rt);
    }
}
