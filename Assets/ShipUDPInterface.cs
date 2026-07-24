using UnityEngine;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

public class ShipUDPInterface : MonoBehaviour
{
    [Header("船隻身分")]
    public string boatID = "Follower_1";

    [Header("角色設定")]
    public Transform leaderBoat;

    [Header("網路設定")]
    public string pythonIP = "127.0.0.1";
    public int sendPort = 5066;
    // Default receive port changed to match Python's leader RX (5075)
    // so the Python `set_control_mode` startup command is applied
    // to the leader without needing to manually flip the inspector.
    public int receivePort = 5075;

    [Header("動力參數")]
    public float moveForce = 20000.0f;
    public float turnTorque = 20000.0f;
    public bool enableThrottleSpeedRamp = true;
    [Tooltip("Normalized throttle units per second while ramping up toward the latest command.")]
    public float throttleRampUpRate = 0.65f;
    [Tooltip("Normalized throttle units per second while ramping down toward the latest command.")]
    public float throttleRampDownRate = 1.2f;

    [Header("啟動時原地待命")]
    public bool holdSpawnPoseUntilLeaderMoves = true;
    public float leaderMoveReleaseSpeed = 0.35f;

    [Header("動態尾流特效控制")]
    public ParticleSystem wakeParticle;
    public float minSpeedToSpawn = 0.5f;
    public float maxSpeed = 10f;

    [Header("特效動態範圍 (最小 ~ 最大)")]
    public float minEmission = 5f;
    public float maxEmission = 150f;
    public float minSize = 0.5f;
    public float maxSize = 1.5f;

    // --- 定義要傳給 Python 的資料結構 ---
    [System.Serializable]
    public class SimulationState
    {
        public string id; // ★ 新增：船的身分證
        
        // Follower 的狀態
        public float x;
        public float z;
        public float yaw;
        public float speed; 
        
        // Leader 的狀態
        public float leader_x;
        public float leader_z;
        public float leader_yaw;
        public float leader_forward_x;
        public float leader_forward_z;
        public float leader_speed;
    }

    [System.Serializable]
    public class ControlData
    {
        public float throttle;
        public float steer;
    }

    [System.Serializable]
    public class TrajectoryCommand
    {
        public string cmd;
        public string mode;
        public float speed;
        public bool enable_speed_ramp;
        public float trajectory_acceleration;
        public float trajectory_initial_speed;
        public float circle_radius;
        public float triangle_side_length;
        public float rectangle_size_x;
        public float rectangle_size_y;
        public bool loop;
        public bool reset;
    }

    [System.Serializable]
    public class ControlModeCommand
    {
        public string cmd;
        public string mode;
    }

    [System.Serializable]
    public class DriveTuningCommand
    {
        public string cmd;
        public bool enable_throttle_ramp;
        public float throttle_ramp_up_rate;
        public float throttle_ramp_down_rate;
    }

    private UdpClient udpClient;
    private IPEndPoint remoteEndPoint;
    private Thread receiveThread;
    private bool isRunning = true;
    private float targetThrottle = 0f;
    private float targetSteer = 0f;
    private float appliedThrottle = 0f;
    private Rigidbody rb;
    private Vector3 spawnPosition;
    private Quaternion spawnRotation;
    private bool startupHoldReleased = false;

    Vector3 GetPlanarBoatForward(Transform boatTransform)
    {
        if (boatTransform == null)
        {
            return Vector3.forward;
        }

        Vector3 planarForward = boatTransform.TransformDirection(Vector3.up);
        planarForward.y = 0f;

        if (planarForward.sqrMagnitude < 1e-4f)
        {
            planarForward = boatTransform.forward;
            planarForward.y = 0f;
        }

        if (planarForward.sqrMagnitude < 1e-4f)
        {
            planarForward = Vector3.forward;
        }

        return planarForward.normalized;
    }

    void Start()
    {
        rb = GetComponent<Rigidbody>();
        appliedThrottle = 0f;
        spawnPosition = transform.position;
        spawnRotation = transform.rotation;
        remoteEndPoint = new IPEndPoint(IPAddress.Parse(pythonIP), sendPort);
        udpClient = new UdpClient(receivePort);
        Debug.Log($"[ShipUDPInterface] Bound UDP receive port: {receivePort}");
        // Try file-based startup command as a fallback (written by Python)
        try
        {
            string startupPath = Path.Combine(Application.dataPath, "..", "leader_startup.json");
            if (File.Exists(startupPath))
            {
                string text = File.ReadAllText(startupPath);
                Debug.Log("[ShipUDPInterface] Found startup file: " + startupPath + " -> " + text);
                try
                {
                    ControlModeCommand cmode = JsonUtility.FromJson<ControlModeCommand>(text);
                    if (cmode != null && (cmode.cmd ?? "") == "set_control_mode")
                    {
                        Transform targetTransform = leaderBoat != null ? leaderBoat : this.transform;
                        ApplyControlModeCommand(targetTransform, cmode, "[ShipUDPInterface]");
                    }

                    TrajectoryCommand tcmd = JsonUtility.FromJson<TrajectoryCommand>(text);
                    if (tcmd != null && (tcmd.cmd ?? "") == "set_trajectory")
                    {
                        Transform targetTransform = leaderBoat != null ? leaderBoat : this.transform;
                        ApplyTrajectoryCommand(targetTransform, tcmd, text, "[ShipUDPInterface]");
                    }

                    DriveTuningCommand dcmd = JsonUtility.FromJson<DriveTuningCommand>(text);
                    if (dcmd != null && (dcmd.cmd ?? "") == "set_drive_tuning")
                    {
                        ApplyDriveTuningCommand(dcmd, text, "[ShipUDPInterface]");
                    }

                    // Optionally remove the startup file after applying
                    try { File.Delete(startupPath); }
                    catch {}
                }
                catch (System.Exception ex)
                {
                    Debug.LogWarning("[ShipUDPInterface] Failed to apply startup file: " + ex.Message);
                }
            }
        }
        catch {}
        // Also watch for the startup file for a short while in case Python writes it after Start()
        StartCoroutine(CheckStartupFileCoroutine());
        receiveThread = new Thread(new ThreadStart(ReceiveData));
        receiveThread.IsBackground = true;
        receiveThread.Start();
    }

    void FixedUpdate()
    {
        SendState();

        if (ShouldHoldSpawnPose())
        {
            HoldSpawnPose();
            return;
        }

        ApplyControl();
    }

    System.Collections.IEnumerator CheckStartupFileCoroutine()
    {
        string startupPath = Path.Combine(Application.dataPath, "..", "leader_startup.json");
        float timeout = 5.0f;
        float waited = 0f;
        float interval = 0.5f;
        while (waited < timeout)
        {
            try
            {
                if (File.Exists(startupPath))
                {
                    string text = File.ReadAllText(startupPath);
                    Debug.Log("[ShipUDPInterface] Found startup file (coroutine): " + startupPath + " -> " + text);
                    try
                    {
                        ControlModeCommand cmode = JsonUtility.FromJson<ControlModeCommand>(text);
                        if (cmode != null && (cmode.cmd ?? "") == "set_control_mode")
                        {
                            Transform targetTransform = leaderBoat != null ? leaderBoat : this.transform;
                            ApplyControlModeCommand(targetTransform, cmode, "[ShipUDPInterface] (coroutine)");
                        }

                        TrajectoryCommand tcmd = JsonUtility.FromJson<TrajectoryCommand>(text);
                        if (tcmd != null && (tcmd.cmd ?? "") == "set_trajectory")
                        {
                            Transform targetTransform = leaderBoat != null ? leaderBoat : this.transform;
                            ApplyTrajectoryCommand(targetTransform, tcmd, text, "[ShipUDPInterface] (coroutine)");
                        }

                        DriveTuningCommand dcmd = JsonUtility.FromJson<DriveTuningCommand>(text);
                        if (dcmd != null && (dcmd.cmd ?? "") == "set_drive_tuning")
                        {
                            ApplyDriveTuningCommand(dcmd, text, "[ShipUDPInterface] (coroutine)");
                        }

                        try { File.Delete(startupPath); } catch {}
                        yield break;
                    }
                    catch (System.Exception ex)
                    {
                        Debug.LogWarning("[ShipUDPInterface] (coroutine) Failed to apply startup file: " + ex.Message);
                    }
                }
            }
            catch {}

            yield return new WaitForSeconds(interval);
            waited += interval;
        }
    }

    void Update()
    {
        // --- 尾流特效動態控制邏輯 ---
        if (wakeParticle != null && rb != null) {
            var emission = wakeParticle.emission; 
            var main = wakeParticle.main; 
            
            // 抓取真實平面速度
            float currentSpeed = new Vector3(rb.velocity.x, 0, rb.velocity.z).magnitude;
            
            if (currentSpeed > minSpeedToSpawn) {
                float speedFactor = Mathf.InverseLerp(minSpeedToSpawn, maxSpeed, currentSpeed);
                emission.rateOverTime = Mathf.Lerp(minEmission, maxEmission, speedFactor);
                main.startSize = Mathf.Lerp(minSize, maxSize, speedFactor);
            } else {
                emission.rateOverTime = 0f; // 船停了，把噴水關掉
            }
        }
    }

    void SendState()
    {
        SimulationState state = new SimulationState();
        
        state.id = boatID;
        
        // 1. 填寫 Follower (自己) 的資料
        state.x = transform.position.x;
        state.z = transform.position.z;
        state.yaw = transform.eulerAngles.y;
        
        // 抓取 Rigidbody 的物理速度 (m/s)
        if (rb != null) {
            state.speed = rb.velocity.magnitude; 
        }

        // 2. 填寫 Leader (老大) 的資料
        if (leaderBoat != null)
        {
            state.leader_x = leaderBoat.position.x;
            state.leader_z = leaderBoat.position.z;
            state.leader_yaw = leaderBoat.eulerAngles.y;
            Vector3 leaderForwardPlanar = GetPlanarBoatForward(leaderBoat);
            state.leader_forward_x = leaderForwardPlanar.x;
            state.leader_forward_z = leaderForwardPlanar.z;

            // Startup hold logic in Python needs to know when the leader has
            // actually begun moving, not just where it is.
            Rigidbody leaderRb = leaderBoat.GetComponent<Rigidbody>();
            if (leaderRb != null)
            {
                state.leader_speed = leaderRb.velocity.magnitude;
            }
        }

        string json = JsonUtility.ToJson(state);
        byte[] data = Encoding.UTF8.GetBytes(json);
        try { udpClient.Send(data, data.Length, remoteEndPoint); }
        catch {}
    }

    void ReceiveData()
    {
        while (isRunning)
        {
            try
            {
                IPEndPoint anyIP = new IPEndPoint(IPAddress.Any, 0);
                byte[] data = udpClient.Receive(ref anyIP);
                string text = Encoding.UTF8.GetString(data);
                // Check for high-level commands (e.g. set_trajectory or set_control_mode)
                if (text.Contains("\"cmd\""))
                {
                    Debug.Log("[ShipUDPInterface] Received: " + text);
                    try
                    {
                        // Determine which GameObject should receive the command:
                        // prefer explicit `leaderBoat` if assigned, otherwise apply to this GameObject.
                        Transform targetTransform = leaderBoat != null ? leaderBoat : this.transform;

                        // Try control-mode first
                        ControlModeCommand cmode = JsonUtility.FromJson<ControlModeCommand>(text);
                        if (cmode != null && cmode.cmd == "set_control_mode")
                        {
                            SimpleMove sm = targetTransform.GetComponent<SimpleMove>();
                            if (sm == null)
                            {
                                Debug.LogWarning($"[ShipUDPInterface] Received set_control_mode but SimpleMove not found on {targetTransform.name}");
                            }
                            else
                            {
                                ApplyControlModeCommand(targetTransform, cmode, "[ShipUDPInterface]");
                            }
                        }

                        // Then try trajectory params
                        TrajectoryCommand tcmd = JsonUtility.FromJson<TrajectoryCommand>(text);
                        if (tcmd != null && tcmd.cmd == "set_trajectory")
                        {
                            ApplyTrajectoryCommand(targetTransform, tcmd, text, "[ShipUDPInterface]");
                        }

                        DriveTuningCommand dcmd = JsonUtility.FromJson<DriveTuningCommand>(text);
                        if (dcmd != null && dcmd.cmd == "set_drive_tuning")
                        {
                            ApplyDriveTuningCommand(dcmd, text, "[ShipUDPInterface]");
                        }
                        // If we handled a command, skip control parsing below
                        if (text.Contains("set_trajectory") || text.Contains("set_control_mode") || text.Contains("set_drive_tuning")) continue;
                    }
                    catch {}
                }

                ControlData cmd = JsonUtility.FromJson<ControlData>(text);
                targetThrottle = cmd.throttle;
                targetSteer = cmd.steer;
            }
            catch {}
        }
    }

    void ApplyControl()
    {
        if (rb == null) return;

        float throttleToApply = targetThrottle;
        if (enableThrottleSpeedRamp)
        {
            float rampRate = targetThrottle > appliedThrottle ? throttleRampUpRate : throttleRampDownRate;
            appliedThrottle = Mathf.MoveTowards(
                appliedThrottle,
                targetThrottle,
                Mathf.Max(0f, rampRate) * Time.fixedDeltaTime
            );
            throttleToApply = appliedThrottle;
        }
        else
        {
            appliedThrottle = targetThrottle;
        }

        rb.AddRelativeForce(Vector3.up * throttleToApply * moveForce);
        rb.AddRelativeTorque(Vector3.forward * targetSteer * turnTorque);

        float currentSpeed = rb.velocity.magnitude;
        if (currentSpeed > maxSpeed)
        {
            rb.velocity = rb.velocity.normalized * maxSpeed;
        }
    }

    bool ShouldHoldSpawnPose()
    {
        if (!holdSpawnPoseUntilLeaderMoves || startupHoldReleased || leaderBoat == null)
        {
            return false;
        }

        Rigidbody leaderRb = leaderBoat.GetComponent<Rigidbody>();
        if (leaderRb != null && leaderRb.velocity.magnitude >= leaderMoveReleaseSpeed)
        {
            startupHoldReleased = true;
            return false;
        }

        return true;
    }

    void HoldSpawnPose()
    {
        if (rb == null) return;

        targetThrottle = 0f;
        targetSteer = 0f;
        appliedThrottle = 0f;

        Vector3 heldPosition = rb.position;
        heldPosition.x = spawnPosition.x;
        heldPosition.z = spawnPosition.z;
        rb.position = heldPosition;

        rb.rotation = spawnRotation;

        Vector3 heldVelocity = rb.velocity;
        heldVelocity.x = 0f;
        heldVelocity.z = 0f;
        rb.velocity = heldVelocity;
        rb.angularVelocity = Vector3.zero;
    }

    void ApplyControlModeCommand(Transform targetTransform, ControlModeCommand cmode, string logPrefix)
    {
        if (targetTransform == null || cmode == null)
        {
            return;
        }

        SimpleMove sm = targetTransform.GetComponent<SimpleMove>();
        if (sm == null)
        {
            return;
        }

        if ((cmode.mode ?? "").ToLower() == "keyboard")
        {
            sm.controlMode = SimpleMove.ControlMode.Keyboard;
            Debug.Log($"{logPrefix} Applied control mode Keyboard to {targetTransform.name}");
        }
        else
        {
            sm.controlMode = SimpleMove.ControlMode.Trajectory;
            sm.ResetTrajectory();
            Debug.Log($"{logPrefix} Applied control mode Trajectory to {targetTransform.name}");
        }
    }

    void ApplyTrajectoryCommand(Transform targetTransform, TrajectoryCommand tcmd, string rawText, string logPrefix)
    {
        if (targetTransform == null || tcmd == null)
        {
            return;
        }

        SimpleMove sm = targetTransform.GetComponent<SimpleMove>();
        if (sm == null)
        {
            return;
        }

        sm.controlMode = SimpleMove.ControlMode.Trajectory;
        switch ((tcmd.mode ?? "").ToLower())
        {
            case "circle":
                sm.trajectoryMode = SimpleMove.TrajectoryMode.Circle;
                break;
            case "triangle":
                sm.trajectoryMode = SimpleMove.TrajectoryMode.Triangle;
                break;
            case "rectangle":
                sm.trajectoryMode = SimpleMove.TrajectoryMode.Rectangle;
                break;
            default:
                sm.trajectoryMode = SimpleMove.TrajectoryMode.Straight;
                break;
        }

        if (tcmd.speed > 0f) sm.trajectorySpeed = tcmd.speed;
        if (tcmd.circle_radius > 0f) sm.circleRadius = tcmd.circle_radius;
        if (tcmd.triangle_side_length > 0f) sm.triangleSideLength = tcmd.triangle_side_length;
        if (tcmd.rectangle_size_x > 0f && tcmd.rectangle_size_y > 0f) sm.rectangleSize = new Vector2(tcmd.rectangle_size_x, tcmd.rectangle_size_y);
        if (!string.IsNullOrEmpty(rawText))
        {
            if (rawText.Contains("\"enable_speed_ramp\""))
            {
                sm.enableTrajectorySpeedRamp = tcmd.enable_speed_ramp;
            }
            if (rawText.Contains("\"trajectory_acceleration\"") && tcmd.trajectory_acceleration >= 0f)
            {
                sm.trajectoryAcceleration = tcmd.trajectory_acceleration;
            }
            if (rawText.Contains("\"trajectory_initial_speed\"") && tcmd.trajectory_initial_speed >= 0f)
            {
                sm.trajectoryInitialSpeed = tcmd.trajectory_initial_speed;
            }
        }
        sm.loopTrajectory = tcmd.loop;
        if (tcmd.reset)
        {
            sm.ResetTrajectory();
        }
        else
        {
            sm.RefreshTrajectorySpeedState();
        }

        Debug.Log(
            $"{logPrefix} Applied trajectory to {targetTransform.name}: mode={tcmd.mode} speed={tcmd.speed} ramp={(sm.enableTrajectorySpeedRamp ? "on" : "off")}"
        );
    }

    void ApplyDriveTuningCommand(DriveTuningCommand dcmd, string rawText, string logPrefix)
    {
        if (dcmd == null)
        {
            return;
        }

        if (!string.IsNullOrEmpty(rawText) && rawText.Contains("\"enable_throttle_ramp\""))
        {
            enableThrottleSpeedRamp = dcmd.enable_throttle_ramp;
        }
        if (!string.IsNullOrEmpty(rawText) && rawText.Contains("\"throttle_ramp_up_rate\"") && dcmd.throttle_ramp_up_rate >= 0f)
        {
            throttleRampUpRate = dcmd.throttle_ramp_up_rate;
        }
        if (!string.IsNullOrEmpty(rawText) && rawText.Contains("\"throttle_ramp_down_rate\"") && dcmd.throttle_ramp_down_rate >= 0f)
        {
            throttleRampDownRate = dcmd.throttle_ramp_down_rate;
        }
        if (!enableThrottleSpeedRamp)
        {
            appliedThrottle = targetThrottle;
        }

        Debug.Log(
            $"{logPrefix} Applied drive tuning to {boatID}: throttle ramp={(enableThrottleSpeedRamp ? "on" : "off")} up={throttleRampUpRate} down={throttleRampDownRate}"
        );
    }

    void OnApplicationQuit()
    {
        isRunning = false;
        if (udpClient != null) udpClient.Close();
        if (receiveThread != null) receiveThread.Abort();
    }
}
