using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

// Verification-only build entry point (scratch copy of the project).
public static class USVCaptureBuild
{
    public static void Build()
    {
        string outPath = System.Environment.GetEnvironmentVariable("USV_BUILD_OUT") ?? "Build/usv.x86_64";
        var opts = new BuildPlayerOptions
        {
            scenes = new[] { "Assets/SUIMONO - WATER SYSTEM 2/_DEMO/Suimono2_Buoyancy_Demo.unity" },
            locationPathName = outPath,
            target = BuildTarget.StandaloneLinux64,
            options = BuildOptions.None,
        };
        BuildReport report = BuildPipeline.BuildPlayer(opts);
        Debug.Log($"[USVCaptureBuild] result={report.summary.result} errors={report.summary.totalErrors}");
        EditorApplication.Exit(report.summary.result == BuildResult.Succeeded ? 0 : 1);
    }
}
