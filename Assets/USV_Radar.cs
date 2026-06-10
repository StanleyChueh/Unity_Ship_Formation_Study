using UnityEngine;

public class USV_Radar : MonoBehaviour
{
    [Header("📡 雷達感測設定")]
    public float rayDistance = 15f; // 射線最遠偵測距離
    public float sideAngle = 30f;   // 左右射線的夾角 (度)

    void Update()
    {
        // 1. 定義三條射線的方向 (正前、左前 30 度、右前 30 度)
        Vector3 forwardDir = transform.forward;
        Vector3 leftDir = Quaternion.Euler(0, -sideAngle, 0) * transform.forward;
        Vector3 rightDir = Quaternion.Euler(0, sideAngle, 0) * transform.forward;

        // 2. 發射射線並偵測
        // 稍微把發射點提高一點 (加上 Vector3.up)，避免射線直接掃到海平面
        Vector3 origin = transform.position + Vector3.up * 1.0f; 

        CheckRay(origin, forwardDir, Color.green, "正前方");
        CheckRay(origin, leftDir, Color.blue, "左前方");
        CheckRay(origin, rightDir, Color.red, "右前方");
    }

    // 負責發射射線與畫線的函數
    void CheckRay(Vector3 origin, Vector3 direction, Color safeColor, string dirName)
    {
        RaycastHit hit;
        
        // 發射物理射線 (起點, 方向, 裝載碰撞資訊, 最遠距離)
        if (Physics.Raycast(origin, direction, out hit, rayDistance))
        {
            // 🚨 撞到東西了！將射線畫成醒目的黃色，長度縮短到撞擊點
            Debug.DrawRay(origin, direction * hit.distance, Color.yellow);
            
            // 在 Console 印出警告與精準距離
            Debug.Log($"⚠️ {dirName} 偵測到障礙物: {hit.collider.name}, 距離: {hit.distance:F1} 公尺");
        }
        else
        {
            // 🟢 沒撞到東西 (安全)！畫出原本設定的顏色，長度為極限距離
            Debug.DrawRay(origin, direction * rayDistance, safeColor);
        }
    }
}