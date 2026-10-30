# 五組策略與已完成消融分析

本文件及圖表由既有完成資料重新計算，沒有重跑Unity、沒有改動原實驗。新分析僅寫入本資料夾。

## 先釐清名稱

`raw_nogate`不等於「原始相機像素／完全沒有任何篩選」：YOLO推論的信心門檻、NMS，以及最小框面積、影像區域與基本類別選擇仍存在。它關閉的是三個追蹤選擇功能：TRACK_GATE_ENABLE、TRACK_GATE_CLASS_AGNOSTIC_ENABLE、TRACK_REACQUIRE_BIAS。

因此簡報建議改稱「無時序bbox gate／無追蹤濾波」。`raw`則是「保留bbox選擇策略，無追蹤平滑與外推」。

## 元件矩陣

|功能|raw_nogate|raw|EMA off_rs|KF on_rs|原OFF off_short|
|---|---|---|---|---|---|
|YOLO信心/NMS、最小框/ROI/基本類別|保留|保留|保留|保留|保留|
|位置/面積時序gate|關|開|開|開|開|
|重捕獲位置偏好|關|開|開|開|開|
|緊位置限制的類別無關重捕獲fallback|關|開|開|開|開|
|觀測平滑|無|無|EMA|Kalman posterior|EMA/有限差分追蹤|
|估測變化率|0|0|平滑有限差分|模型估測|有限差分預測|
|bbox缺失hold上限|0s|0s|3s|3s|0.6s|
|估測器融合自身/Leader速度|否|否|否|是|否|
|協方差、adaptive R、Huber|無|無|無|有|無KF機制|
|額外4σ innovation gate|無|無|無|有|無|
|縱向控制器|新版距離/速度|新版距離/速度|新版距離/速度|新版距離/速度|原面積控制|
|控制器使用Leader速度|是|是|是|是|是|
|命令平滑、slew/ramp及lost fallback|共用相關控制/plant設定；並未由raw_nogate一併關閉|||||

「raw」只移除追蹤估測，不代表整個控制系統沒有平滑、保護或速度資訊。原OFF在研究harness仍共用已記錄的控制修正與plant，不是普通非同步GUI app完全原樣執行。

主模型：視覺距離z=c/√A；距離狀態[r,b]，r_dot=κ(vL−vF)+b；水平[o,o_dot]通道。融合KF是模型、速度融合、adaptive/robust量測策略及coast的組合，不能歸因為只有Kalman增益公式。

## 我實際完成的分析

- e02主要96回合＋e02x補充raw_nogate 24回合，組成同case/seed的五組描述性對照（120回合）。
- e03_laps：同批次10天候/波浪條件×5方法×2seeds＝100回合，完整135s圓周。
- e04_wlaps：4條非固定天候路徑×3方法×2seeds＝24回合；只有KF、原OFF、raw_nogate，不能假裝有五組。
- 以上隊列分開報告，不混合不同路徑、回合長度或樣本數。
- 檢查completed/planned、source freeze、seed配對及重複鍵；主推論三個效果數字重新計算與存檔結果一致至1e-9。
- e02與e02x使用相同Unity binary，26項source hash中只有run_d04.py不同；唯讀diff顯示runner新增raw_nogate分支，原組別patch邏輯保留。這仍是事後擴充，不升格為新的確認性假設。

## 主要情境的增量比較

效果＝每個seed內等權平均C8/C10/W1的log RMSE ratio，再對8個seed blocks平均並轉成百分比。正值表示降低誤差，不是把逐步百分比直接相加。

|比較|這個比較真正改變的項目|幾何RMSE降低|失隊時間降低(pp)|證據層級|
|---|---|---:|---:|---|
|raw vs raw_nogate|基本時序gate＋重捕獲偏好＋類別無關fallback的組合|7.2%|2.16|事後跨批次描述性|
|EMA vs raw|EMA平滑＋變化率＋3s coast|53.3%|30.94|描述性，非單獨EMA效果|
|KF vs EMA|KF模型＋速度融合＋robust/adaptive量測＋innovation gate|33.2%|13.58|e02預定H3；p=.0781，未確認|
|KF vs raw|完整融合追蹤策略，控制器共用|68.8%|44.52|e02預定H1；p=.0078|
|KF vs 原OFF|估測＋hold＋縱向控制器更換|48.9%|31.13|e02預定H2；p=.0078|

pp是百分點，不是相對百分比。gate組在此8個seed blocks皆有較低平均log ratio，但效果分析為事後，沒有另做新顯著性宣稱。

## 長回合反例不能省略

e03_L03大浪、固定圓周、135s，2個seed的平均RMSE：raw_nogate 26.71m，raw 286.19m，EMA189.82m，KF3.27m，原OFF117.33m。

所以基本bbox選擇策略不是所有情境都幫忙。這個差異顯示整體gate/重捕獲政策有潛在代價；不能只憑RMSE判定一定是gate拒絕真框，需要時間點、選擇及身份診斷。此分析未新增逐幀機制審計，也不宣稱已證明因果機制。

L04–L10長回合雨/夜間即使有相對改善，常仍有數百至上千公尺RMSE，代表持隊失敗。e04非固定天候路徑三組皆失敗。不可把短回合e02正面結果外推成長時間所有天候可靠。

## 還不能分離的單項貢獻

目前沒有同條件下只關閉以下單一元件的已完成配對資料，因此不捏造數字：

- 只關閉KF的4σ gate、保留基本bbox gate和所有其他功能。
- 只關閉Huber、或只固定R、或只關閉水平adaptive Q。
- 只移除估測器速度融合，保持控制器速度前饋。
- KF hold 0/0.6/3秒且所有其餘元件相同。
- 只換控制器而其餘估測、輸入、hold完全相同。

既有raw/EMA/KF比較是策略級消融，不是以上元件各自的效益。詳細後續設計見COMPONENT_ABLATION_PLAN.md；未執行的新回合一律不列結果。

## 歷史方法，不混入最新五組

- legacy：Assets/usv/kalman.py的raw offset/area KF，另有外部平滑及KF-only控制差異。
- d02 on：robust offset/log-area KF＋共同coast控制；e01主要檢定未支持優勢。
- d03 on_ego：自身速度已知輸入的range KF；不融合Leader速度到估測器；e01只作探索。
- d04 on_rs：新增Leader速度融合、4σ gate與range/speed控制，e02以新seeds評估。

不得用各歷史批次均值差宣稱單個程式改動的因果效應。

## 圖與檔案

- primary_ablation.png/.svg：五組主要情境算術平均RMSE，包含災難性回合，非只有中位數。
- lap_ablation.png/.svg：10個長回合條件，2seed描述性均值。
- RESULT_TABLES.md：均值、中位數、失隊比例、catastrophe與配對效果完整表。
- per_arm_summary.csv、paired_contrasts.csv、primary_aggregate.csv：可重用數值。
- ablation_results.json：來源hash、證據層級與現有預定推論。
- analyze_existing.py：可重現的唯讀分析，完全不啟動Unity/runner。

來源：Experiments/KalmanStudy/robust_evaluation/{e02,e02x,e03_laps,e04_wlaps}的results/manifest/source-freeze-check；Tools/kalman_study/{run_d04,raw_tracker,rs_hooks,fusion_tracker,robust_tracker,range_speed_policy}.py；Assets/usv/{vision,control,helpers,config}.py；凍結source_snapshot。原資料未改動。
