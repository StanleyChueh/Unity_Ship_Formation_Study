using UnityEngine;

public class SimpleMove : MonoBehaviour
{
    public enum ControlMode
    {
        Keyboard = 0,
        Trajectory = 1,
    }

    public enum TrajectoryMode
    {
        Straight = 0,
        Circle = 1,
        Triangle = 2,
        Rectangle = 3,
    }

    [Header("控制模式")]
    public ControlMode controlMode = ControlMode.Keyboard;

    [Header("馬力設定")]
    public float moveForce = 50000.0f;   // 前後推力 (W/S)
    public float turnTorque = 20000.0f;  // 左右轉向力 (A/D) -> 改回這個！

    [Header("自動軌跡測試")]
    public TrajectoryMode trajectoryMode = TrajectoryMode.Circle;
    public float trajectorySpeed = 7.0f;
    [Tooltip("Enable gradual speed ramping for trajectory mode. Disable this for fixed-speed leader experiments.")]
    public bool enableTrajectorySpeedRamp = true;
    [Tooltip("Acceleration (m/s^2) used to ramp toward trajectorySpeed when speed ramping is enabled.")]
    public float trajectoryAcceleration = 12.0f;
    [Tooltip("Starting speed used when a trajectory begins while ramping is enabled.")]
    public float trajectoryInitialSpeed = 0.0f;
    public float straightLeadInDistance = 25.0f;
    public float circleRadius = 18.0f;
    public float triangleSideLength = 30.0f;
    public Vector2 rectangleSize = new Vector2(36.0f, 22.0f);
    public bool loopTrajectory = true;

    [Header("尾流特效控制")]
    public ParticleSystem wakeParticle;
    public float maxEmissionRate = 20f;
    public float minSpeedToSpawn = 0.5f;

    private Rigidbody rb;
    private ParticleSystem.EmissionModule wakeEmission;
    private Vector3 spawnPosition;
    private Quaternion spawnRotation;
    private Vector3 spawnForwardPlanar;
    private Vector3 spawnRightPlanar;
    private float travelledDistance = 0.0f;
    private float currentTrajectorySpeed = 0.0f;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
        CacheSpawnFrame();

        if (wakeParticle != null)
        {
            wakeEmission = wakeParticle.emission;
            wakeEmission.rateOverTime = 0f;
        }
    }

    void OnEnable()
    {
        travelledDistance = 0.0f;
        ResetTrajectorySpeed();
    }

    // Allow external scripts to reset/re-anchor the trajectory origin
    public void ResetTrajectory()
    {
        travelledDistance = 0.0f;
        CacheSpawnFrame();
        ResetTrajectorySpeed();
    }

    public void RefreshTrajectorySpeedState()
    {
        float targetSpeed = Mathf.Max(0f, trajectorySpeed);
        if (!enableTrajectorySpeedRamp)
        {
            currentTrajectorySpeed = targetSpeed;
            return;
        }

        float startSpeed = Mathf.Clamp(trajectoryInitialSpeed, 0f, targetSpeed);
        currentTrajectorySpeed = Mathf.Clamp(currentTrajectorySpeed, startSpeed, targetSpeed);
    }

    void FixedUpdate()
    {
        if (rb == null) return;

        if (controlMode == ControlMode.Trajectory)
        {
            RunTrajectoryControl();
        }
        else
        {
            RunKeyboardControl();
        }

        UpdateWakeEffect();
    }

    void CacheSpawnFrame()
    {
        spawnPosition = transform.position;
        spawnRotation = transform.rotation;

        spawnForwardPlanar = transform.TransformDirection(Vector3.up);
        spawnForwardPlanar.y = 0f;

        if (spawnForwardPlanar.sqrMagnitude < 1e-4f)
        {
            spawnForwardPlanar = transform.forward;
            spawnForwardPlanar.y = 0f;
        }

        if (spawnForwardPlanar.sqrMagnitude < 1e-4f)
        {
            spawnForwardPlanar = Vector3.forward;
        }

        spawnForwardPlanar.Normalize();
        spawnRightPlanar = Vector3.Cross(Vector3.up, spawnForwardPlanar).normalized;
    }

    void RunKeyboardControl()
    {
        float move = Input.GetAxis("Vertical");   // W/S
        float turn = Input.GetAxis("Horizontal"); // A/D

        if (move != 0)
        {
            rb.AddRelativeForce(Vector3.up * move * moveForce);
        }

        if (turn != 0)
        {
            rb.AddRelativeTorque(Vector3.forward * turn * turnTorque);
        }
    }

    void RunTrajectoryControl()
    {
        float targetSpeed = Mathf.Max(0f, trajectorySpeed);
        if (enableTrajectorySpeedRamp)
        {
            currentTrajectorySpeed = Mathf.MoveTowards(
                currentTrajectorySpeed,
                targetSpeed,
                Mathf.Max(0f, trajectoryAcceleration) * Time.fixedDeltaTime
            );
        }
        else
        {
            currentTrajectorySpeed = targetSpeed;
        }

        travelledDistance += currentTrajectorySpeed * Time.fixedDeltaTime;

        Vector2 localPoint;
        Vector2 localTangent;
        EvaluateTrajectory(travelledDistance, out localPoint, out localTangent);

        Vector3 planarPosition = spawnPosition
            + (spawnRightPlanar * localPoint.x)
            + (spawnForwardPlanar * localPoint.y);

        Vector3 desiredPosition = rb.position;
        desiredPosition.x = planarPosition.x;
        desiredPosition.z = planarPosition.z;
        rb.MovePosition(desiredPosition);

        Vector3 desiredPlanarForward = (spawnRightPlanar * localTangent.x) + (spawnForwardPlanar * localTangent.y);
        desiredPlanarForward.y = 0f;
        if (desiredPlanarForward.sqrMagnitude > 1e-4f)
        {
            desiredPlanarForward.Normalize();
            Quaternion yawDelta = Quaternion.FromToRotation(spawnForwardPlanar, desiredPlanarForward);
            rb.MoveRotation(yawDelta * spawnRotation);

                Vector3 planarVelocity = desiredPlanarForward * currentTrajectorySpeed;
            rb.velocity = new Vector3(planarVelocity.x, rb.velocity.y, planarVelocity.z);
        }
        else
        {
            rb.velocity = new Vector3(0f, rb.velocity.y, 0f);
        }

        rb.angularVelocity = Vector3.zero;
    }

    void EvaluateTrajectory(float distance, out Vector2 point, out Vector2 tangent)
    {
        float leadDistance = Mathf.Max(0f, straightLeadInDistance);

        if (trajectoryMode == TrajectoryMode.Straight || distance <= leadDistance)
        {
            point = new Vector2(0f, distance);
            tangent = Vector2.up;
            return;
        }

        float shapeDistance = distance - leadDistance;
        Vector2 leadOffset = new Vector2(0f, leadDistance);

        switch (trajectoryMode)
        {
            case TrajectoryMode.Circle:
                EvaluateCircle(shapeDistance, leadOffset, out point, out tangent);
                break;
            case TrajectoryMode.Triangle:
                EvaluatePolygon(
                    shapeDistance,
                    leadOffset,
                    BuildTrianglePoints(),
                    out point,
                    out tangent
                );
                break;
            case TrajectoryMode.Rectangle:
                EvaluatePolygon(
                    shapeDistance,
                    leadOffset,
                    BuildRectanglePoints(),
                    out point,
                    out tangent
                );
                break;
            default:
                point = new Vector2(0f, distance);
                tangent = Vector2.up;
                break;
        }
    }

    void EvaluateCircle(float shapeDistance, Vector2 leadOffset, out Vector2 point, out Vector2 tangent)
    {
        float radius = Mathf.Max(0.1f, circleRadius);
        float circumference = 2.0f * Mathf.PI * radius;
        float wrappedDistance = WrapDistance(shapeDistance, circumference);
        float angle = wrappedDistance / radius;

        Vector2 loopPoint = new Vector2(
            radius * (1.0f - Mathf.Cos(angle)),
            radius * Mathf.Sin(angle)
        );
        Vector2 loopTangent = new Vector2(Mathf.Sin(angle), Mathf.Cos(angle)).normalized;

        point = leadOffset + loopPoint;
        tangent = loopTangent;
    }

    void EvaluatePolygon(float shapeDistance, Vector2 leadOffset, Vector2[] points, out Vector2 point, out Vector2 tangent)
    {
        if (points == null || points.Length < 2)
        {
            point = leadOffset;
            tangent = Vector2.up;
            return;
        }

        float perimeter = 0f;
        for (int i = 0; i < points.Length - 1; i++)
        {
            perimeter += Vector2.Distance(points[i], points[i + 1]);
        }

        if (perimeter <= 1e-4f)
        {
            point = leadOffset + points[0];
            tangent = Vector2.up;
            return;
        }

        float remaining = WrapDistance(shapeDistance, perimeter);
        tangent = (points[1] - points[0]).normalized;

        for (int i = 0; i < points.Length - 1; i++)
        {
            Vector2 a = points[i];
            Vector2 b = points[i + 1];
            Vector2 segment = b - a;
            float length = segment.magnitude;
            if (length <= 1e-4f)
            {
                continue;
            }

            if (remaining <= length || i == points.Length - 2)
            {
                float t = Mathf.Clamp01(remaining / length);
                point = leadOffset + Vector2.Lerp(a, b, t);
                tangent = segment / length;
                return;
            }

            remaining -= length;
        }

        point = leadOffset + points[points.Length - 1];
    }

    Vector2[] BuildTrianglePoints()
    {
        float side = Mathf.Max(1f, triangleSideLength);
        float halfSide = side * 0.5f;
        float triangleWidth = Mathf.Sqrt(3f) * halfSide;

        return new Vector2[]
        {
            new Vector2(0f, 0f),
            new Vector2(0f, side),
            new Vector2(triangleWidth, halfSide),
            new Vector2(0f, 0f),
        };
    }

    Vector2[] BuildRectanglePoints()
    {
        float width = Mathf.Max(1f, rectangleSize.x);
        float height = Mathf.Max(1f, rectangleSize.y);

        return new Vector2[]
        {
            new Vector2(0f, 0f),
            new Vector2(0f, height),
            new Vector2(width, height),
            new Vector2(width, 0f),
            new Vector2(0f, 0f),
        };
    }

    float WrapDistance(float distance, float length)
    {
        if (length <= 1e-4f)
        {
            return 0f;
        }

        if (!loopTrajectory)
        {
            return Mathf.Clamp(distance, 0f, length);
        }

        return Mathf.Repeat(distance, length);
    }

    void ResetTrajectorySpeed()
    {
        float targetSpeed = Mathf.Max(0f, trajectorySpeed);
        if (!enableTrajectorySpeedRamp)
        {
            currentTrajectorySpeed = targetSpeed;
            return;
        }

        currentTrajectorySpeed = Mathf.Clamp(trajectoryInitialSpeed, 0f, targetSpeed);
    }

    void UpdateWakeEffect()
    {
        if (wakeParticle != null)
        {
            float currentSpeed = rb.velocity.magnitude;
            if (currentSpeed > minSpeedToSpawn)
            {
                // 根據速度計算噴發量
                float targetRate = (currentSpeed / 10.0f) * maxEmissionRate;
                wakeEmission.rateOverTime = Mathf.Clamp(targetRate, 0f, maxEmissionRate);
            }
            else
            {
                wakeEmission.rateOverTime = 0f;
            }
        }
    }
}
