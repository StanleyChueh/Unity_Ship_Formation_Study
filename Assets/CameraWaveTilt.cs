using UnityEngine;
using Suimono.Core;

public class CameraWaveTilt : MonoBehaviour
{
    [Header("🚢 目標船隻 (用來偵測哪裡的海浪)")]
    public Transform targetBoat;

    [Header("🌊 鏡頭晃動強度 (0 = 不晃, 1 = 完全貼合海浪)")]
    [Range(0f, 2f)]
    public float tiltStrength = 1.0f;
    
    [Header("🎥 鏡頭平滑度 (越大越靈敏，越小越遲鈍)")]
    public float smoothSpeed = 5.0f;

    private SuimonoModule suimonoModule;
    private Quaternion defaultRotation;

    void Start()
    {
        suimonoModule = FindObjectOfType<SuimonoModule>();
        defaultRotation = transform.localRotation;
    }

    void LateUpdate()
    {
        if (suimonoModule == null || targetBoat == null) return;

        // 1. 取得船目前的座標
        Vector3 centerPos = targetBoat.position;
        float offset = 0.5f; // 在船的周圍 0.5 公尺處採樣

        // 2. 利用舊版支援的 SuimonoGetHeightAll 取得 3 個點的真實海面高度 [0]
        float hCenter = suimonoModule.SuimonoGetHeightAll(centerPos)[0];
        float hRight = suimonoModule.SuimonoGetHeightAll(centerPos + Vector3.right * offset)[0];
        float hForward = suimonoModule.SuimonoGetHeightAll(centerPos + Vector3.forward * offset)[0];

        // 3. 在 3D 空間中建立這 3 個點的座標
        Vector3 pCenter = new Vector3(centerPos.x, hCenter, centerPos.z);
        Vector3 pRight = new Vector3(centerPos.x + offset, hRight, centerPos.z);
        Vector3 pForward = new Vector3(centerPos.x, hForward, centerPos.z + offset);

        // 4. 算出兩個貼著海面的向量
        Vector3 vRight = pRight - pCenter;
        Vector3 vForward = pForward - pCenter;

        // 5. 🌟 數學魔法：利用外積 (Cross) 算出垂直於這個海面的「法線 (Normal)」
        Vector3 waveNormal = Vector3.Cross(vForward, vRight).normalized;

        // 6. 把算出來的法線拿來轉攝影機
        Quaternion waveRotation = Quaternion.FromToRotation(Vector3.up, Vector3.Lerp(Vector3.up, waveNormal, tiltStrength));
        Quaternion targetRotation = waveRotation * defaultRotation;

        transform.localRotation = Quaternion.Slerp(transform.localRotation, targetRotation, Time.deltaTime * smoothSpeed);
    }
}
