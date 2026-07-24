using System;
using UnityEngine;
using System.Net.Sockets;
using System.Text;

[DisallowMultipleComponent]
public class Formation_Camera_Rotate : MonoBehaviour
{
    [Serializable]
    public class FormationRotationSetting
    {
        public string label = "Formation";
        public KeyCode triggerKey = KeyCode.None;
        [Tooltip("Camera local rotation X in degrees.")]
        public float rx = 20f;
    }

    [Header("Formation Rx Settings")]
    public FormationRotationSetting vFormation = new FormationRotationSetting
    {
        label = "V Formation",
        triggerKey = KeyCode.Alpha1,
        rx = 20f,
    };

    public FormationRotationSetting lineFormation = new FormationRotationSetting
    {
        label = "Line Formation",
        triggerKey = KeyCode.Alpha2,
        rx = 35f,
    };

    [Header("Rotation")]
    public bool useLocalRotation = true;
    public bool smoothRotation = true;
    [Tooltip("Rotation speed in degrees per second.")]
    public float rotationDegreesPerSecond = 8f;

    private float targetRx;
    private float lockedRy;
    private float lockedRz;
    private bool initialized;

    [Serializable]
    public class FormationModeCommand
    {
        public string cmd;
        public string mode;
    }

    [Header("Python Formation Mode")]
    public string pythonIP = "127.0.0.1";
    public int formationModePort = 5072;

    private UdpClient formationModeClient;

    private void Start()
    {
        formationModeClient = new UdpClient();
        CacheLockedAxes();
        targetRx = GetCurrentRx();
        initialized = true;
    }

    private void SendFormationMode(string mode)
    {
        if (string.IsNullOrEmpty(mode))
        {
            return;
        }

        FormationModeCommand cmd = new FormationModeCommand
        {
            cmd = "set_formation_mode",
            mode = mode
        };

        string json = JsonUtility.ToJson(cmd);
        byte[] data = Encoding.UTF8.GetBytes(json);

        try
        {
            formationModeClient.Send(data, data.Length, pythonIP, formationModePort);
            Debug.Log($"[Formation_Camera_Rotate] Sent formation mode: {mode}");
        }
        catch (Exception ex)
        {
            Debug.LogWarning($"[Formation_Camera_Rotate] Failed to send formation mode: {ex.Message}");
        }
    }

    private void Update()
    {
        HandleFormationHotkeys();
        ApplyRotation();
    }

    private void HandleFormationHotkeys()
    {
        ApplySettingIfTriggered(vFormation);
        ApplySettingIfTriggered(lineFormation);
    }

    private void ApplySettingIfTriggered(FormationRotationSetting setting)
    {
                if (setting == null || setting.triggerKey == KeyCode.None)
        {
            return;
        }

        if (!Input.GetKeyDown(setting.triggerKey))
        {
            return;
        }

        targetRx = setting.rx;

        if (!smoothRotation)
        {
            SetCurrentRx(targetRx);
        }

        string mode = null;
        if (setting == vFormation)
        {
            mode = "v";
        }
        else if (setting == lineFormation)
        {
            mode = "line";
        }

        SendFormationMode(mode);

        Debug.Log($"[Formation_Camera_Rotate] {setting.label} selected, Camera Rx -> {targetRx:F1}, mode={mode}");
    }

    private void ApplyRotation()
    {
        if (!initialized)
        {
            return;
        }

        if (!smoothRotation)
        {
            return;
        }

        float currentRx = GetCurrentRx();
        float maxStep = Mathf.Max(0f, rotationDegreesPerSecond) * Time.deltaTime;
        float nextRx = Mathf.MoveTowardsAngle(currentRx, targetRx, maxStep);
        SetCurrentRx(nextRx);
    }

    private float GetCurrentRx()
    {
        Vector3 euler = useLocalRotation ? transform.localEulerAngles : transform.eulerAngles;
        return NormalizeAngle(euler.x);
    }

    private void SetCurrentRx(float rx)
    {
        Quaternion rotation = Quaternion.Euler(rx, lockedRy, lockedRz);

        if (useLocalRotation)
        {
            transform.localRotation = rotation;
            return;
        }

        transform.rotation = rotation;
    }

    private void CacheLockedAxes()
    {
        Vector3 euler = useLocalRotation ? transform.localEulerAngles : transform.eulerAngles;
        lockedRy = NormalizeAngle(euler.y);
        lockedRz = NormalizeAngle(euler.z);
    }


    private float NormalizeAngle(float angle)
    {
        angle %= 360f;
        if (angle > 180f)
        {
            angle -= 360f;
        }

        return angle;
    }
        private void OnDestroy()
    {
        if (formationModeClient != null)
        {
            formationModeClient.Close();
            formationModeClient = null;
        }
    }
}

