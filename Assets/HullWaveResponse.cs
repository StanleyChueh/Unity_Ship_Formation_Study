using UnityEngine;
using Suimono.Core;

/// <summary>
/// Pitches and rolls a hull with the local water surface (ambient SUIMONO
/// waves + USVWakeField stern waves), like a small hull's waterplane
/// stiffness would. fx_buoyancy only samples one point, so on its own it can
/// heave a boat but never tilt it, which left the boat-mounted cameras rock
/// steady even when crossing a wake.
///
/// The surface is sampled at bow/stern/port/starboard; the hull is driven
/// toward that plane by a damped spring with natural periods typical of a
/// 3-5 m planing hull, plus a small bow-up running trim when planing.
///   - Physics-driven hulls (followers): torques on the Rigidbody.
///   - Scripted hulls (SimpleMove in Trajectory mode, i.e. the leader): the
///     same oscillator is integrated here and handed to SimpleMove as
///     waveAttitude, which it composes with its scripted yaw.
/// </summary>
[DisallowMultipleComponent]
public class HullWaveResponse : MonoBehaviour
{
    [Tooltip("Natural roll period (s) of the hull.")]
    public float rollPeriod = 2.0f;
    [Tooltip("Natural pitch period (s) of the hull.")]
    public float pitchPeriod = 1.4f;
    public float dampingRatio = 0.8f;
    [Tooltip("Bow-up trim (deg) when fully planing.")]
    public float planingTrimDeg = 3f;
    public float maxTiltDeg = 25f;

    Rigidbody rb;
    SimpleMove scripted;
    BoatSternWake hull;
    Vector3 localUp;        // hull axis that points up at spawn
    Vector3 localForward;   // bow axis (boats are authored with local +Y as bow)
    static SuimonoModule suimono;

    // Oscillator state for scripted hulls (radians, rad/s).
    float pitch, roll, pitchRate, rollRate;

    void Awake()
    {
        rb = GetComponent<Rigidbody>();
        scripted = GetComponent<SimpleMove>();
        hull = GetComponent<BoatSternWake>();
        localForward = Vector3.up;
        localUp = ClosestLocalAxis(Vector3.up);
    }

    Vector3 ClosestLocalAxis(Vector3 world)
    {
        Vector3[] axes = { Vector3.right, Vector3.left, Vector3.up, Vector3.down, Vector3.forward, Vector3.back };
        Vector3 best = Vector3.forward;
        float bestDot = -2f;
        foreach (Vector3 a in axes)
        {
            float d = Vector3.Dot(transform.TransformDirection(a), world);
            if (d > bestDot) { bestDot = d; best = a; }
        }
        return best;
    }

    void FixedUpdate()
    {
        if (suimono == null) suimono = FindObjectOfType<SuimonoModule>();
        if (suimono == null) return;

        Vector3 fwd = transform.TransformDirection(localForward);
        fwd.y = 0f;
        if (fwd.sqrMagnitude < 1e-4f) return;
        fwd.Normalize();
        Vector3 right = Vector3.Cross(Vector3.up, fwd);

        float L = hull != null && hull.hullLength > 0f ? hull.hullLength : 4f;
        float B = hull != null && hull.hullBeam > 0f ? hull.hullBeam : 1.6f;
        Vector3 c = transform.position;
        float hBow = Height(c + fwd * (0.4f * L));
        float hStern = Height(c - fwd * (0.4f * L));
        float hPort = Height(c - right * (0.5f * B));
        float hStbd = Height(c + right * (0.5f * B));

        float speed = rb != null ? new Vector2(rb.velocity.x, rb.velocity.z).magnitude : 0f;
        float planing = Mathf.Clamp01((speed / Mathf.Sqrt(9.81f * L) - 1f) / 1.5f);
        float maxTilt = maxTiltDeg * Mathf.Deg2Rad;
        // Targets: bow-up pitch positive, port-side-up roll positive.
        float pitchTarget = Mathf.Clamp(Mathf.Atan2(hBow - hStern, 0.8f * L) + planing * planingTrimDeg * Mathf.Deg2Rad, -maxTilt, maxTilt);
        float rollTarget = Mathf.Clamp(Mathf.Atan2(hPort - hStbd, B), -maxTilt, maxTilt);

        float wPitch = 2f * Mathf.PI / Mathf.Max(0.2f, pitchPeriod);
        float wRoll = 2f * Mathf.PI / Mathf.Max(0.2f, rollPeriod);

        if (scripted != null && scripted.controlMode == SimpleMove.ControlMode.Trajectory)
        {
            float dt = Time.fixedDeltaTime;
            pitchRate += (wPitch * wPitch * (pitchTarget - pitch) - 2f * dampingRatio * wPitch * pitchRate) * dt;
            rollRate += (wRoll * wRoll * (rollTarget - roll) - 2f * dampingRatio * wRoll * rollRate) * dt;
            pitch += pitchRate * dt;
            roll += rollRate * dt;
            // Unity rotations are left-handed: a positive angle about the starboard
            // axis lowers the bow, a positive angle about the bow axis raises starboard.
            scripted.waveAttitude = Quaternion.AngleAxis(-pitch * Mathf.Rad2Deg, right)
                                  * Quaternion.AngleAxis(-roll * Mathf.Rad2Deg, fwd);
            return;
        }

        if (rb == null || rb.isKinematic) return;

        // Current attitude of the hull relative to its planar heading.
        Vector3 up = transform.TransformDirection(localUp);
        float pitchNow = Mathf.Asin(Mathf.Clamp(Vector3.Dot(up, -fwd), -1f, 1f));
        float rollNow = Mathf.Asin(Mathf.Clamp(Vector3.Dot(up, right), -1f, 1f));
        float pitchRateNow = -Vector3.Dot(rb.angularVelocity, right);
        float rollRateNow = -Vector3.Dot(rb.angularVelocity, fwd);

        float pitchAcc = wPitch * wPitch * (pitchTarget - pitchNow) - 2f * dampingRatio * wPitch * pitchRateNow;
        float rollAcc = wRoll * wRoll * (rollTarget - rollNow) - 2f * dampingRatio * wRoll * rollRateNow;
        rb.AddTorque(-right * pitchAcc - fwd * rollAcc, ForceMode.Acceleration);
    }

    static float Height(Vector3 p)
    {
        return suimono.SuimonoGetHeight(p, "height");
    }
}
