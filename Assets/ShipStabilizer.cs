using UnityEngine;

[RequireComponent(typeof(Rigidbody))]
public class ShipStabilizer : MonoBehaviour
{
    [Header("重心上下 (Y軸：越低越抗側翻)")]
    public float centerOfMassY = -1.5f;

    [Header("重心前後 (Z軸：正值往前，負值往後)")]
    public float centerOfMassZ = 0.0f;

    [Header("主動扶正力 (Active uprighting torque)")]
    [Tooltip("Torque applied each FixedUpdate to push the boat back upright. " +
             "Raise this if the boat capsizes in heavy waves (Storm / Typhoon). " +
             "15000 is tuned for near-Typhoon (lgWaveHeight=2.5); use 18000 for lgWaveHeight=3.0.")]
    public float uprightTorque = 15000f;

    [Tooltip("Maximum tilt angle (degrees) before uprighting torque is applied.")]
    public float tiltDeadzone = 5f;

    private Rigidbody rb;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
    }

    void FixedUpdate()
    {
        rb.centerOfMass = new Vector3(0f, centerOfMassY, centerOfMassZ);
        ApplyUprightingTorque();
    }

    void ApplyUprightingTorque()
    {
        // Compute the angle between the boat's local up and world up
        Vector3 localUp   = transform.up;
        Vector3 worldUp   = Vector3.up;
        float   tiltAngle = Vector3.Angle(localUp, worldUp);

        if (tiltAngle <= tiltDeadzone) return;

        // Rotation axis that would bring local-up back to world-up
        Vector3 axis      = Vector3.Cross(localUp, worldUp).normalized;
        float   strength  = Mathf.InverseLerp(tiltDeadzone, 90f, tiltAngle);
        rb.AddTorque(axis * uprightTorque * strength, ForceMode.Force);
    }

    void OnDrawGizmos()
    {
        if (Application.isPlaying)
        {
            Vector3 worldCoM = transform.TransformPoint(new Vector3(0f, centerOfMassY, centerOfMassZ));
            Gizmos.color = Color.red;
            Gizmos.DrawSphere(worldCoM, 0.4f);
        }
    }
}
