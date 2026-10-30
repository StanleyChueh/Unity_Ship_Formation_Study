# 10/30 簡報講稿與來源

## 1｜無人水面載具視覺編隊控制

開場：研究重點是視覺估測在閉迴路控制中的效果。

## 2｜研究問題與目前系統輸入

Leader speed 每步由模擬器提供；不可稱為只靠視覺。真值位置與 ID 只作離線評估。

## 3｜環境設定

來源：ProjectVersion、SuimonoModule、WaveController。實驗 harness 則為同步 bridge。

## 4｜控制方法 - 編隊控制

相機朝向設定對應各船 slot；相同框面積不代表所有姿態都能量得相同距離。

## 5｜系統架構

原架構圖保留；補充：持續的速度資訊進控制器，GT 僅供離線計分。

## 6｜海浪與船體運動

USVOceanSurface、HullWaveResponse、CameraWaveTilt。非 CFD；海況參數不是經校準的顯著波高。

## 7｜尾流與噴濺

USVWakeField、BoatSternWake；解析近似加近場修正，並非完整流體求解。

## 8｜控制方法 - 船隻辨識模型

原 YOLO 訓練流程圖保留；新資料採 episode 分組，不將相鄰影格跨訓練／測試。

## 9｜船隻辨識模型 - 資料與離線評估

detection-summary.json。新 train 3178、val/test 各384；26 capture episodes 按18/4/4分組。離線偵測表現不是 KF 增益。

## 10｜控制方法 - 視覺相對幾何

實作有飽和、平滑、追趕補償與失聯策略；不是只有兩個比例增益。

## 11｜第一輪驗證 - 只平滑影像狀態仍不夠

e01 為 d04 的開發資訊，不能再次稱為 d04 held-out；第二輪 e02 使用全新 seeds。

## 12｜控制方法 - 距離與速度融合 Kalman

FusionRangeTracker；κ為隊形幾何近似。速度是持續提供的模擬資訊。5次連續拒絕可重新初始化，並非完美身份識別。

## 13｜控制方法 - 距離／速度控制

range_speed_policy.py。距離單位m，速度m/s。式中 r_dot 是估測量。這是d04實驗版本，尚不可宣稱已部署一般app。

## 14｜實驗設計 - 四個比較組

e02 protocol。KF vs EMA包含速度融合與gating策略差異；不是僅替換Kalman增益公式。原OFF比較包含控制器改動。

## 15｜實驗設計 - 情境與配對

同 binary、detector、plant、10Hz同步步進；每回合運動60s，分析15–60s。各組軌跡分歧後影像不同。26檔案source check passed。

## 16｜評估指標與統計方法

每seed平均3情境log ratio；exact雙尾sign-flip共256種；bootstrap重抽seed block。H1→H2→H3固定順序。

## 17｜實驗結果 - 第二輪主要驗證

來源e02/inference_primary.json。H1/H2各8/8 seed blocks較佳；H3為6/8。CI：H1 62.6–72.4%；H2 39.0–59.7%；H3 5.5–53.3%。bootstrap與exact test方法不同。

## 18｜實驗結果 - 各情境位置誤差

每情境8seeds；表為中位數，不是主推論的幾何平均配對效果。C10 catastrophic回合仍在所有計算中。

## 19｜實驗結果 - 失隊時間比例

每情境8 seeds的時間比例算術平均。這個指標不同於RMSE；兩者一起判斷持隊品質。

## 20｜實驗結果 - 輕雨漏檢時的追蹤差異

W1 seed4409預先指定中間seed，t=35s；從既有keyframe原樣裁切，並非最佳case。單一時刻不代表群體平均。

## 21｜實驗結果 - 大浪仍有錯誤重捕獲

FINAL_REPORT e02 caveat，不可只展示median掩蓋catastrophe。4σ gate在長coast後協方差變大，仍可能接受錯誤身份。

## 22｜實驗結果 - 緊轉彎與長失聯

Secondary descriptive，4seeds/case。C4 EMA優於KF；C7所有方法失敗，KF最小船距約4m。

## 23｜實機延伸 - 無人機驗證規劃

原slide30–33含未完成架構與示意，本頁只描述規劃；無已核對的無人機閉迴路成效數字。

## 24｜限制與後續工作

e01b heavy rain/night limits；e02沒有重跑這些盲視覺case。不要稱為已證明暴雨／夜間可用。

## 25｜結論

可口述：相對raw降低68.8%，相對原OFF降低48.9%，皆p=.0078；不可省略速度融合與控制器改動。

## 26｜附錄 - Kalman 預測與更新

原始通用KF公式示意；e02的狀態定義見前述距離模型，不再用raw area版本解釋e02結果。

## 27｜附錄 - 編隊模式切換

此頁為原簡報的隊形切換機制示意；切換過程未納入本次holding統計。

## 28｜附錄 - 實機通訊架構

保留使用者原始架構圖片，狀態為規劃，未宣稱有成效驗證。

## 29｜附錄 - 結果與方法來源

所有主張依e02 frozen protocol與FINAL_REPORT核對。Kalman1960參考與Rabaud2013僅提供理論背景，不是本研究成效證據。

## 字型與製作說明

以原PDF頁面直接修訂，原圖與保留頁字型不變。新增文字優先重用原嵌入MS PMincho / MS PGothic字形；原檔未包含的新字以Noto Serif / Sans CJK補字，英文用Liberation Serif。此環境沒有原完整字型，故新增文字並非全字元完全相同字型。無可用PowerPoint artifact執行環境，交付為PDF。

來源：Documentation/KalmanStudy/FINAL_REPORT.md；EVALUATION_PROTOCOL_E02.md；e02/results.json；inference_primary.json；source-freeze-check.json；Assets/USVOceanSurface.cs；USVWakeField.cs；HullWaveResponse.cs；BoatSternWake.cs；fusion_tracker.py；range_speed_policy.py。

## 結果頁口述補充

第17頁：H1比較未追蹤濾波組，但同時包含速度融合、異常框gating及coast策略；不能說只隔離Kalman方程式。H2還包含控制器更換。H3共用控制器，但EMA不把速度融合到估測器，所以也不是僅替換矩陣更新。三組比較的因果範圍不同。

H3 bootstrap區間未包含零，exact sign-flip p=.0781仍未通過預定檢定，兩種方法不可互換或挑有利者。

第18頁：中位數是描述每情境典型回合；主推論是配對log RMSE後的幾何降低量。不可用中位數相除重建68.8%或48.9%。

第20頁：指定seed4409、t35s圖是機制示例，不代表所有seed平均；圖中白框是離線評分真值，不送入控制。

第21頁：C10失敗seed仍納入所有統計。請同時講median與mean，避免用median掩蓋長尾。

第23頁：無人機部分只有使用者既有架構，沒有核對到可支持成效的閉迴路實機數據。以規劃報告，不稱完成驗證。

## [Sources]

使用者原檔：/home/stanley/Downloads/10月30日-國科會討論 (2).pdf。
專案根目錄：/home/stanley/Github/Unity_Ship_Formation_Study/。
實驗結果：Documentation/KalmanStudy/FINAL_REPORT.md；Experiments/KalmanStudy/robust_evaluation/e02/results.json、inference_primary.json、source-freeze-check.json。
方法：Documentation/KalmanStudy/EVALUATION_PROTOCOL_E02.md、ROBUST_D04.md。
理論背景：Kalman 1960 https://people.math.harvard.edu/archive/116_fall_03/handouts/Kalman1960.pdf；Rabaud & Moisy 2013 https://arxiv.org/abs/1304.2653。
