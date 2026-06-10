using UnityEngine;

[RequireComponent(typeof(Rigidbody))]
public class ShipStabilizer : MonoBehaviour
{
    [Header("重心上下 (Y軸：越低越抗側翻)")]
    public float centerOfMassY = -1.5f; // 稍微收斂一點
    
    [Header("重心前後 (Z軸：正值往前，負值往後)")]
    public float centerOfMassZ = 0.0f;  // 🌟 先改回 0，我們慢慢調！

    private Rigidbody rb;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
    }

    void FixedUpdate()
    {
        // 為了讓你可以在執行時動態拉動 Inspector 的滑桿測試，
        // 我們把重心的設定放在 Update 裡即時更新
        rb.centerOfMass = new Vector3(0, centerOfMassY, centerOfMassZ);
    }

    // 🌟 透視魔法：在 Scene 視窗畫出重心的位置！
    void OnDrawGizmos()
    {
        if (Application.isPlaying)
        {
            // 算出重心的世界座標
            Vector3 worldCoM = transform.TransformPoint(new Vector3(0, centerOfMassY, centerOfMassZ));
            
            // 畫一顆紅色的球
            Gizmos.color = Color.red;
            Gizmos.DrawSphere(worldCoM, 0.4f); 
        }
    }
}