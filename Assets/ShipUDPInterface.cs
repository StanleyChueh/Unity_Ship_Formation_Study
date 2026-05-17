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

    private UdpClient udpClient;
    private IPEndPoint remoteEndPoint;
    private Thread receiveThread;
    private bool isRunning = true;
    private float targetThrottle = 0f;
    private float targetSteer = 0f;
    private Rigidbody rb;
    private Vector3 spawnPosition;
    private Quaternion spawnRotation;
    private bool startupHoldReleased = false;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
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
                        SimpleMove sm = targetTransform.GetComponent<SimpleMove>();
                        if (sm != null)
                        {
                            if ((cmode.mode ?? "").ToLower() == "keyboard")
                            {
                                sm.controlMode = SimpleMove.ControlMode.Keyboard;
                                Debug.Log($"[ShipUDPInterface] Applied startup control mode Keyboard to {targetTransform.name}");
                            }
                            else
                            {
                                sm.controlMode = SimpleMove.ControlMode.Trajectory;
                                sm.ResetTrajectory();
                                Debug.Log($"[ShipUDPInterface] Applied startup control mode Trajectory to {targetTransform.name}");
                            }
                        }
                    }

                    TrajectoryCommand tcmd = JsonUtility.FromJson<TrajectoryCommand>(text);
                    if (tcmd != null && (tcmd.cmd ?? "") == "set_trajectory")
                    {
                        Transform targetTransform = leaderBoat != null ? leaderBoat : this.transform;
                        SimpleMove sm = targetTransform.GetComponent<SimpleMove>();
                        if (sm != null)
                        {
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
                            sm.loopTrajectory = tcmd.loop;
                            if (tcmd.reset)
                            {
                                sm.ResetTrajectory();
                            }
                            Debug.Log($"[ShipUDPInterface] Applied startup trajectory to {targetTransform.name}: mode={tcmd.mode} speed={tcmd.speed}");
                        }
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
                            SimpleMove sm = targetTransform.GetComponent<SimpleMove>();
                            if (sm != null)
                            {
                                if ((cmode.mode ?? "").ToLower() == "keyboard")
                                {
                                    sm.controlMode = SimpleMove.ControlMode.Keyboard;
                                    Debug.Log($"[ShipUDPInterface] (coroutine) Applied startup control mode Keyboard to {targetTransform.name}");
                                }
                                else
                                {
                                    sm.controlMode = SimpleMove.ControlMode.Trajectory;
                                    sm.ResetTrajectory();
                                    Debug.Log($"[ShipUDPInterface] (coroutine) Applied startup control mode Trajectory to {targetTransform.name}");
                                }
                            }
                        }

                        TrajectoryCommand tcmd = JsonUtility.FromJson<TrajectoryCommand>(text);
                        if (tcmd != null && (tcmd.cmd ?? "") == "set_trajectory")
                        {
                            Transform targetTransform = leaderBoat != null ? leaderBoat : this.transform;
                            SimpleMove sm = targetTransform.GetComponent<SimpleMove>();
                            if (sm != null)
                            {
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
                                sm.loopTrajectory = tcmd.loop;
                                if (tcmd.reset)
                                {
                                    sm.ResetTrajectory();
                                }
                                Debug.Log($"[ShipUDPInterface] (coroutine) Applied startup trajectory to {targetTransform.name}: mode={tcmd.mode} speed={tcmd.speed}");
                            }
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
                            if (sm != null)
                            {
                                if ((cmode.mode ?? "").ToLower() == "keyboard")
                                {
                                    sm.controlMode = SimpleMove.ControlMode.Keyboard;
                                    Debug.Log($"[ShipUDPInterface] Applied control mode Keyboard to {targetTransform.name}");
                                }
                                else
                                {
                                    sm.controlMode = SimpleMove.ControlMode.Trajectory;
                                    sm.ResetTrajectory();
                                    Debug.Log($"[ShipUDPInterface] Applied control mode Trajectory to {targetTransform.name}");
                                }
                            }
                            else
                            {
                                Debug.LogWarning($"[ShipUDPInterface] Received set_control_mode but SimpleMove not found on {targetTransform.name}");
                            }
                        }

                        // Then try trajectory params
                        TrajectoryCommand tcmd = JsonUtility.FromJson<TrajectoryCommand>(text);
                        if (tcmd != null && tcmd.cmd == "set_trajectory")
                        {
                            SimpleMove sm = targetTransform.GetComponent<SimpleMove>();
                            if (sm != null)
                            {
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
                                sm.loopTrajectory = tcmd.loop;
                                if (tcmd.reset)
                                {
                                    sm.ResetTrajectory();
                                }
                            }
                        }
                        // If we handled a command, skip control parsing below
                        if (text.Contains("set_trajectory") || text.Contains("set_control_mode")) continue;
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

        rb.AddRelativeForce(Vector3.up * targetThrottle * moveForce);
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

    void OnApplicationQuit()
    {
        isRunning = false;
        if (udpClient != null) udpClient.Close();
        if (receiveThread != null) receiveThread.Abort();
    }
}
