# 尚未執行：單元件消融設計

目的：分離融合KF各元件的貢獻。這是後續實驗方案，不是已完成的結果，也不是重新解讀既有e02為新確認性資料。

## 實驗組（共同新版控制器、detector、基本bbox選擇、calibration、plant）

|組別|相對完整on_rs的唯一介入|
|---|---|
|A0 full|凍結完整實作，作共同參考|
|A1 no innovation gate|跳過4σ拒絕與拒絕計數重建分支；保留Huber、adaptive R、基本bbox gate|
|A2 no Huber|水平與距離通道Huber weight固定1；保留hard innovation gate|
|A3 fixed measurement-noise rule|關閉殘差噪聲學習與confidence inflation；預定offset/log-area基準及距離相對噪聲規則。Huber仍獨立保留，因此它會再調有效R，必須如此標註，不稱最終R完全固定|
|A4 no adaptive offset Q|水平通道Q boost固定1；距離Q原本已無同樣adaptive boost|
|A5 no speed fusion in estimator|距離改成已凍結的constant-velocity [r,rdot] KF，不讀vL/vF；相同視覺觀測R/gate/Huber；控制器仍讀vL。這是過程模型消融，狀態初始化與Q需開發後先凍結，不可看held-out才調|
|A6 short coast|KF hold 0.6s，其他模型/噪聲/gate/控制不變|
|A7 no coast|KF hold 0s；有量測幀仍正常KF預測/更新，丟框才立即lost|

A0與A1～A7的回合應在同一次新批次內全部重新跑，不能混入其他批次full成績。

## 配對與預先限制

- C8、C10、W1，8個真正未使用的新seed blocks，8arms，共192回合×60s。新seed的「未使用」必須在啟動前掃描所有開發/評估manifest確認；本文不擅自指定可能撞號的seed。
- 分離開發檢查與held-out：先用已有開發seed檢查patch及機制，之後再凍結所有wrapper、baseline、噪聲初始化和protocol。
- 在私有project/port啟動，避開Claude工作目錄及現有runner；不得改Assets或現有Tools來源。保存snapshot和hash。
- 檢查每組與A0只差預定介入；單元件極限測試要能觀察該元件真的被停用。特別驗證coast expiry、重新初始化與last_seen不因拒絕而刷新。

## 指標與推論

- RMSE、失隊比例、IoU、P95/peak、最小船距、正確量測率、錯誤重捕獲、控制variation；每組失敗都保留。
- 額外記錄：候選框、基本gate拒絕原因、KF innovation值、innovation gate接受/拒絕、有效R/Q、估測器last_seen及實際控制輸入。不能僅以target_detected flag聲稱KF已接受新量測。
- 每seed對3case等權平均log RMSE比；7個對full的預定比較使用Holm校正，預先凍結alpha與實務門檻。8seed檢定解析度有限，可能無法確認多重比較的個別效應；不事後換單尾或刪比較來找顯著。
- 以整seed block bootstrap描述區間；case-wise結果描述性。沒有新結果前不得填效益百分比。
- 這是one-factor-at-a-time的局部消融，只估完整系統附近的移除效果；若要gate×coast等交互作用，需另外預定factorial批次。

目前只完成既有五組消融資料的唯讀再分析，未建立或啟動這192回合的新runner。完整執行需先完成私有patch、機制驗證、來源凍結及新seed登記。
