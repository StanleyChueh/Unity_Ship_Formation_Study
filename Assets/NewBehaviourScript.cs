using UnityEngine;

public class SimpleCameraFollow : MonoBehaviour
{
    [Header("追蹤目標 (把你的 Follower 船拖進來)")]
    public Transform target;

    [Header("固定高度 (相對於海平面 Y=0)")]
    public float cameraHeight = 6f;

    [Header("後退距離 (水平距離)")]
    public float distanceBehind = 12f;

    void LateUpdate()
    {
        if (target != null)
        {
            // 1. 取得船的平面位置 (忽略 Y 軸起伏)
            Vector3 targetPos = target.position;
            
            // 2. 計算攝影機位置：
            // 我們直接在世界座標的 Y 軸加高，並讓攝影機「往後退」
            // 注意：如果船是倒著開，把 -distanceBehind 改成 +distanceBehind
            Vector3 desiredPosition = targetPos - (target.forward * distanceBehind);
            desiredPosition.y = cameraHeight; // 強制鎖定在海面上方，絕對不進水

            transform.position = desiredPosition;

            // 3. 永遠盯著船身位置看
            transform.LookAt(targetPos + Vector3.up * 1.5f);
        }
    }
    

    void Start()
    {
        // 強制關掉可能存在的 Suimono 自動特效，避免它把畫面塗藍
        var underwater = GetComponent("Suimono_UnderwaterFog");
        if (underwater != null) {
            (underwater as MonoBehaviour).enabled = false;
        }
    }
}