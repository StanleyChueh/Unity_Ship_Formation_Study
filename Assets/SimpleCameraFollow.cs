using UnityEngine;
using System;

public class SimpleCameraFollow : MonoBehaviour
{
    [Header("追蹤目標")]
    public Transform target;

    [Header("自動鎖定領航船")]
    public bool autoFindLeaderTarget = true;
    public string leaderTargetName = "leader";

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
        ResolveTarget();

        var underwater = GetComponent("Suimono_UnderwaterFog");
        if (underwater != null)
        {
            (underwater as MonoBehaviour).enabled = false;
        }
    }

    void ResolveTarget()
    {
        if (!autoFindLeaderTarget || target != null)
        {
            return;
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