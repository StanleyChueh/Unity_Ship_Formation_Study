using UnityEngine;

public class SimpleMove : MonoBehaviour
{
    [Header("馬力設定")]
    public float moveForce = 50000.0f;   // 前後推力 (W/S)
    public float turnTorque = 20000.0f;  // 左右轉向力 (A/D) -> 改回這個！

    [Header("尾流特效控制")]
    public ParticleSystem wakeParticle;
    public float maxEmissionRate = 20f; 
    public float minSpeedToSpawn = 0.5f;

    private Rigidbody rb;
    private ParticleSystem.EmissionModule wakeEmission;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
        
        if (wakeParticle != null)
        {
            wakeEmission = wakeParticle.emission;
            wakeEmission.rateOverTime = 0f;
        }
    }

    void FixedUpdate()
    {
        if (rb == null) return;

        // --- 讀取鍵盤 ---
        float move = Input.GetAxis("Vertical");   // W/S
        float turn = Input.GetAxis("Horizontal"); // A/D

        // --- 1. 前後移動 (W/S) ---
        // 因為你的船轉了 -90 度，Y軸 (綠色) 才是前方
        if (move != 0) 
        {
            rb.AddRelativeForce(Vector3.up * move * moveForce);
        }

        // --- 2. 左右轉彎 (A/D) ---
        // 改回使用 Torque (扭力) 來旋轉
        // 因為你的船轉了 -90 度，Z軸 (藍色) 變成了天頂方向
        // 所以我們要繞著 Z 軸轉，船才會左右轉頭
        if (turn != 0) 
        {
            rb.AddRelativeTorque(Vector3.forward * turn * turnTorque);
        }

        // --- 3. 尾流自動控制 ---
        if (wakeParticle != null)
        {
            float currentSpeed = rb.velocity.magnitude;
            if (currentSpeed > minSpeedToSpawn)
            {
                // 根據速度計算噴發量
                float targetRate = (currentSpeed / 10.0f) * maxEmissionRate;
                wakeEmission.rateOverTime = Mathf.Clamp(targetRate, 0f, maxEmissionRate);
            }
            else
            {
                wakeEmission.rateOverTime = 0f;
            }
        }
    }
}