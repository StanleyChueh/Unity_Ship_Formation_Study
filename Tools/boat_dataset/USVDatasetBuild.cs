using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

// Copied into the isolated project's Assets/Editor by generate_dataset.py.
public static class USVDatasetBuild
{
    public static void Build()
    {
        var report=BuildPipeline.BuildPlayer(new BuildPlayerOptions{
            scenes=new[]{"Assets/SUIMONO - WATER SYSTEM 2/_DEMO/Suimono2_Buoyancy_Demo.unity"},
            locationPathName=System.Environment.GetEnvironmentVariable("USV_DATASET_BUILD"),
            target=BuildTarget.StandaloneLinux64,options=BuildOptions.None});
        Debug.Log("[DatasetBuild] "+report.summary.result+" errors="+report.summary.totalErrors);
        EditorApplication.Exit(report.summary.result==BuildResult.Succeeded ? 0 : 1);
    }
}
