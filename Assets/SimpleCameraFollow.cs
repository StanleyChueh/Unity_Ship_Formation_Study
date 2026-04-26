using UnityEngine;
using System;

public class SimpleCameraFollow : MonoBehaviour
{
    [Header("追蹤目標")]
    public Transform target;

    [Header("自動鎖定領航船")]
    public bool autoFindLeaderTarget = true;
    public string leaderTargetName = "leader";
    public bool tryFindByTagFirst = true;
    public string leaderTargetTag = "Leader";

    [Header("輸出顯示")]
    public bool forceCameraTargetDisplay = true;
    [Tooltip("0=Display1, 1=Display2, 2=Display3")]
    public int cameraTargetDisplay = 2;
    public bool autoActivateDisplayOnStart = true;

    [Header("多船追蹤 (可選)")]
    public Transform[] targets;

    [Header("模式")]
    public bool topDownMode = true;

    [Header("Top View 設定")]
    public float topDownHeight = 40f;
    public float topDownOffsetX = 0f;
    public float topDownOffsetZ = 0f;

    [Header("跟隨模式設定")]
    public float followHeight = 6f;
    public float distanceBehind = 12f;

    [Header("平滑")]
    public float positionSmoothSpeed = 4f;

    void Start()
    {
        SetupDisplay();
        ResolveTarget();

        var underwater = GetComponent("Suimono_UnderwaterFog");
        if (underwater != null)
        {
            (underwater as MonoBehaviour).enabled = false;
        }
    }

    void SetupDisplay()
    {
        Camera cam = GetComponent<Camera>();
        if (cam != null && forceCameraTargetDisplay)
        {
            cam.targetDisplay = Mathf.Max(0, cameraTargetDisplay);
            Debug.Log($"[SimpleCameraFollow] Camera target display set to {cam.targetDisplay + 1}");
        }

        if (!autoActivateDisplayOnStart)
        {
            return;
        }

        int displayIndex = Mathf.Max(0, cameraTargetDisplay);
        if (displayIndex == 0)
        {
            return;
        }

        if (Display.displays == null || displayIndex >= Display.displays.Length)
        {
            Debug.LogWarning($"[SimpleCameraFollow] Display {displayIndex + 1} is unavailable. Connected displays: {(Display.displays == null ? 0 : Display.displays.Length)}");
            return;
        }

        Display.displays[displayIndex].Activate();
        Debug.Log($"[SimpleCameraFollow] Activated Display {displayIndex + 1}");
    }

    void ResolveTarget()
    {
        if (!autoFindLeaderTarget || target != null)
        {
            return;
        }

        if (tryFindByTagFirst && !string.IsNullOrEmpty(leaderTargetTag))
        {
            try
            {
                GameObject taggedLeader = GameObject.FindGameObjectWithTag(leaderTargetTag);
                if (taggedLeader != null)
                {
                    target = taggedLeader.transform;
                    Debug.Log($"[SimpleCameraFollow] Tracking leader target by tag '{leaderTargetTag}': {target.name}");
                    return;
                }
            }
            catch (UnityException)
            {
                // Tag not defined in project settings. Fall back to name search.
            }
        }

        GameObject leaderObject = GameObject.Find(leaderTargetName);
        if (leaderObject == null)
        {
            Transform[] allTransforms = FindObjectsOfType<Transform>(true);
            foreach (Transform candidate in allTransforms)
            {
                if (candidate == null)
                {
                    continue;
                }

                if (string.Equals(candidate.name, leaderTargetName, StringComparison.OrdinalIgnoreCase))
                {
                    leaderObject = candidate.gameObject;
                    break;
                }
            }
        }

        if (leaderObject != null)
        {
            target = leaderObject.transform;
            Debug.Log($"[SimpleCameraFollow] Tracking leader target: {target.name}");
        }
    }

    private Vector3 GetFocusPoint()
    {
        ResolveTarget();

        if (targets != null && targets.Length > 0)
        {
            Vector3 sum = Vector3.zero;
            int count = 0;

            foreach (Transform candidate in targets)
            {
                if (candidate == null)
                {
                    continue;
                }

                sum += candidate.position;
                count++;
            }

            if (count > 0)
            {
                return sum / count;
            }
        }

        if (target != null)
        {
            return target.position;
        }

        return transform.position;
    }

    void LateUpdate()
    {
        if (autoFindLeaderTarget && target == null)
        {
            ResolveTarget();
        }

        Vector3 focusPoint = GetFocusPoint();

        if (topDownMode)
        {
            Vector3 desiredPosition = new Vector3(
                focusPoint.x + topDownOffsetX,
                topDownHeight,
                focusPoint.z + topDownOffsetZ
            );

            transform.position = Vector3.Lerp(transform.position, desiredPosition, Time.deltaTime * positionSmoothSpeed);
            transform.rotation = Quaternion.Euler(90f, 0f, 0f);
            return;
        }

        if (target == null)
        {
            return;
        }

        Vector3 desiredFollowPosition = focusPoint - (target.forward * distanceBehind);
        desiredFollowPosition.y = followHeight;
        transform.position = Vector3.Lerp(transform.position, desiredFollowPosition, Time.deltaTime * positionSmoothSpeed);
        transform.LookAt(focusPoint + Vector3.up * 1.5f);
    }
}