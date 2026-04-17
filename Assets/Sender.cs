using UnityEngine;
using System;
using System.Net.Sockets;
using System.IO;
using System.Collections;
using System.Threading.Tasks;

[RequireComponent(typeof(Camera))]
public class MainCameraStreamSender : MonoBehaviour
{
    [Header("TCP 設定")]
    public string serverIP = "127.0.0.1";
    public int serverPort = 9999;

    [Header("串流設定")]
    [Range(1, 60)]
    public int sendFPS = 15;

    [Range(0.1f, 1.0f)]
    public float resizeScale = 0.5f;   // 1.0=原解析度, 0.5=半解析度

    [Range(30, 100)]
    public int jpgQuality = 70;

    [Header("除錯")]
    public bool autoReconnect = true;
    public float reconnectInterval = 2.0f;
    public bool showDebugLog = false;

    private Camera cam;
    private TcpClient client;
    private NetworkStream netStream;
    private BinaryWriter writer;

    private RenderTexture renderTexture;
    private Texture2D captureTexture;

    private bool isConnected = false;
    private bool isSending = false;
    private bool isConnecting = false;

    private int targetWidth;
    private int targetHeight;

    private float nextRetryTime = 0f;
    private Coroutine sendCoroutine;

    void Start()
    {
        cam = GetComponent<Camera>();

        targetWidth = Mathf.Max(64, Mathf.RoundToInt(Screen.width * resizeScale));
        targetHeight = Mathf.Max(64, Mathf.RoundToInt(Screen.height * resizeScale));

        renderTexture = new RenderTexture(targetWidth, targetHeight, 24, RenderTextureFormat.ARGB32);
        renderTexture.Create();

        captureTexture = new Texture2D(targetWidth, targetHeight, TextureFormat.RGB24, false);

        ConnectToServer();
        sendCoroutine = StartCoroutine(SendFramesCoroutine());
    }

    async void ConnectToServer()
    {
        if (isConnected || isConnecting)
            return;

        isConnecting = true;
        CloseConnection();

        TcpClient newClient = null;

        try
        {
            newClient = new TcpClient();
            newClient.NoDelay = true;

            Task connectTask = newClient.ConnectAsync(serverIP, serverPort);
            Task timeoutTask = Task.Delay(300);   // 最多等 300ms，避免卡主執行緒

            Task finishedTask = await Task.WhenAny(connectTask, timeoutTask);

            if (finishedTask != connectTask || !newClient.Connected)
            {
                try { newClient.Close(); } catch { }
                isConnected = false;
                nextRetryTime = Time.time + reconnectInterval;

                if (showDebugLog)
                {
                    Debug.Log("[Unity] Python server not ready, will retry later.");
                }

                return;
            }

            client = newClient;
            netStream = client.GetStream();
            writer = new BinaryWriter(netStream);

            isConnected = true;

            if (showDebugLog)
            {
                Debug.Log($"[Unity] Connected to Python server: {serverIP}:{serverPort}");
            }
        }
        catch (Exception e)
        {
            try { newClient?.Close(); } catch { }

            isConnected = false;
            nextRetryTime = Time.time + reconnectInterval;

            if (showDebugLog)
            {
                Debug.Log($"[Unity] Connect failed: {e.Message}");
            }
        }
        finally
        {
            isConnecting = false;
        }
    }

    IEnumerator SendFramesCoroutine()
    {
        isSending = true;
        WaitForEndOfFrame wait = new WaitForEndOfFrame();

        while (isSending)
        {
            float interval = 1.0f / Mathf.Max(1, sendFPS);

            yield return wait;

            if (!isConnected)
            {
                if (autoReconnect && !isConnecting && Time.time >= nextRetryTime)
                {
                    ConnectToServer();
                    nextRetryTime = Time.time + reconnectInterval;
                }

                yield return new WaitForSeconds(interval);
                continue;
            }

            try
            {
                CaptureAndSendFrame();
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[Unity] Send frame failed: {e.Message}");
                isConnected = false;
                CloseConnection();
                nextRetryTime = Time.time + reconnectInterval;
            }

            yield return new WaitForSeconds(interval);
        }
    }

    void CaptureAndSendFrame()
    {
        if (cam == null || writer == null || !isConnected)
            return;

        RenderTexture prevCamTarget = cam.targetTexture;
        RenderTexture prevActive = RenderTexture.active;

        try
        {
            cam.targetTexture = renderTexture;
            cam.Render();

            RenderTexture.active = renderTexture;
            captureTexture.ReadPixels(new Rect(0, 0, targetWidth, targetHeight), 0, 0, false);
            captureTexture.Apply(false);

            byte[] jpgBytes = captureTexture.EncodeToJPG(jpgQuality);
            if (jpgBytes == null || jpgBytes.Length == 0)
                return;

            // 傳送格式：
            // 4 bytes: width
            // 4 bytes: height
            // 4 bytes: jpg length
            // N bytes: jpg data
            writer.Write(targetWidth);
            writer.Write(targetHeight);
            writer.Write(jpgBytes.Length);
            writer.Write(jpgBytes);
            writer.Flush();

            if (showDebugLog)
            {
                Debug.Log($"[Unity] Sent frame: {targetWidth}x{targetHeight}, {jpgBytes.Length} bytes");
            }
        }
        finally
        {
            cam.targetTexture = prevCamTarget;
            RenderTexture.active = prevActive;
        }
    }

    void CloseConnection()
    {
        try { writer?.Close(); } catch { }
        try { netStream?.Close(); } catch { }
        try { client?.Close(); } catch { }

        writer = null;
        netStream = null;
        client = null;
        isConnected = false;
    }

    void OnDestroy()
    {
        isSending = false;

        if (sendCoroutine != null)
        {
            StopCoroutine(sendCoroutine);
            sendCoroutine = null;
        }

        CloseConnection();

        if (renderTexture != null)
        {
            renderTexture.Release();
            Destroy(renderTexture);
            renderTexture = null;
        }

        if (captureTexture != null)
        {
            Destroy(captureTexture);
            captureTexture = null;
        }
    }

    void OnApplicationQuit()
    {
        isSending = false;
        CloseConnection();
    }
}
