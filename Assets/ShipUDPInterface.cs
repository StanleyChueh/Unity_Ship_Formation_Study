using UnityEngine;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

public class ShipUDPInterface : MonoBehaviour
{
    [Header("船隻身分 (多船控制必備)")]
    public string boatID = "Follower_1"; // ★ 新增：讓 Python 知道這是哪艘船

    [Header("角色設定")]
    public Transform leaderBoat; // ★ 請在這裡拖入 Leader 船的物件

    [Header("網路設定 (每艘小弟的 Port 必須不同!)")]
    public string pythonIP = "127.0.0.1";
    public int sendPort = 5066;    // 傳給 Python 的通道
    public int receivePort = 5065; // 接收 Python 指令的通道

    [Header("動力參數")]
    public float moveForce = 20000.0f;
    public float turnTorque = 20000.0f;

    [Header("啟動時原地待命")]
    public bool holdSpawnPoseUntilLeaderMoves = true;
    public float leaderMoveReleaseSpeed = 0.35f;

    [Header("動態尾流特效控制")]
    public ParticleSystem wakeParticle;
    public float minSpeedToSpawn = 0.5f;
    public float maxSpeed = 10f; // 記得設定成這艘船的最高 m/s

    [Header("特效動態範圍 (最小 ~ 最大)")]
    public float minEmission = 5f;    // ★ 慢速時一秒只噴 5 顆
    public float maxEmission = 150f;  // ★ 極速時一秒噴 150 顆
    public float minSize = 0.5f;      // 慢速時水花比較小
    public float maxSize = 1.5f;      // 極速時水花稍微變大
    
    [Header("UI 顯示設定")]
    public Transform targetLeader;
    public int uiPositionY = 20; // ★ 新增這行：用來控制文字的上下位置

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

    private UdpClient udpClient;
    private IPEndPoint remoteEndPoint;
    private Thread receiveThread;
    private bool isRunning = true;
    private float targetThrottle = 0f;
    private float targetSteer = 0f;
    private Rigidbody rb;
    private float speedKnots = 0f; 
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
        
        state.id = boatID; // ★ 填入這艘船的身分證
        
        // 1. 填寫 Follower (自己) 的資料
        state.x = transform.position.x;
        state.z = transform.position.z;
        state.yaw = transform.eulerAngles.y;
        
        // 抓取 Rigidbody 的物理速度 (m/s)
        if (rb != null) {
            state.speed = rb.velocity.magnitude; 
            speedKnots = state.speed * 1.94384f; 
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
        
        // ★ 換回 Vector3.up！對你這艘歪掉的船來說，Up 才是往前！
        rb.AddRelativeForce(Vector3.up * targetThrottle * moveForce); 
        
        // ★ 換回 Vector3.forward！這才是這艘船正確的轉向軸！
        rb.AddRelativeTorque(Vector3.forward * targetSteer * turnTorque);
        
        // ★ Enforce maxSpeed by clamping velocity magnitude (independent speed limit per boat)
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

    void OnGUI()
    {
        GUIStyle style = new GUIStyle();
        style.fontSize = 35;
        style.normal.textColor = Color.white;
        style.fontStyle = FontStyle.Bold;

        float distance = 0f;
        if (targetLeader != null) {
            distance = Vector3.Distance(transform.position, targetLeader.position);
        }

        // 為了避免兩艘船的 UI 疊在一起，我們把 Boat ID 也印出來
        // 把原本的 20 換成 uiPositionY
        // GUI.Label(new Rect(20, uiPositionY, 800, 50), $"[{boatID}] 船速: {speedKnots:F2} 節 | 距離leader: {distance:F1} m", style);
    }
}
