using UnityEngine;
using System;

[DisallowMultipleComponent]
public class FollowerCameraLookAt : MonoBehaviour
{
    [Header("模式")]
    [Tooltip("啟動時只對準一次，不持續追蹤")]
    public bool alignOnlyAtStart = true;

    [Header("目標")]
    public Transform leader;
    public bool autoFindLeader = true;
    public string leaderName = "Leader";
    public bool findCaseInsensitive = true;

    [Header("取景")]
    [Tooltip("抬高視線，讓船身不會壓在畫面正中央")]
    public float lookAtHeight = 1.2f;

    [Tooltip("0=硬鎖定，數值越大越平滑")]
    public float rotationSmooth = 8f;

    private void Start()
    {
        ResolveLeader();
        AlignNow();
    }

    private void ResolveLeader()
    {
        if (!autoFindLeader || leader != null)
        {
            return;
        }

        GameObject byName = GameObject.Find(leaderName);
        if (byName != null)
        {
            leader = byName.transform;
            Debug.Log($"[FollowerCameraLookAt] Leader found by name: {leader.name}");
            return;
        }

        if (!findCaseInsensitive)
        {
            return;
        }

        Transform[] allTransforms = FindObjectsOfType<Transform>(true);
        foreach (Transform t in allTransforms)
        {
            if (t == null)
            {
                continue;
            }

            if (string.Equals(t.name, leaderName, StringComparison.OrdinalIgnoreCase))
            {
                leader = t;
                Debug.Log($"[FollowerCameraLookAt] Leader found (ignore case): {leader.name}");
                return;
            }
        }
    }

    [ContextMenu("Align Camera To Leader Now")]
    public void AlignNow()
    {
        if (leader == null)
        {
            ResolveLeader();
            if (leader == null)
            {
                return;
            }
        }

        Vector3 lookPoint = leader.position + Vector3.up * lookAtHeight;
        Vector3 dir = lookPoint - transform.position;

        if (dir.sqrMagnitude < 0.0001f)
        {
            return;
        }

        Quaternion desired = Quaternion.LookRotation(dir.normalized, Vector3.up);

        if (rotationSmooth <= 0f)
        {
            transform.rotation = desired;
            return;
        }

        transform.rotation = Quaternion.Slerp(
            transform.rotation,
            desired,
            Time.deltaTime * rotationSmooth
        );
    }

    private void LateUpdate()
    {
        if (alignOnlyAtStart)
        {
            return;
        }

        AlignNow();
    }
}
