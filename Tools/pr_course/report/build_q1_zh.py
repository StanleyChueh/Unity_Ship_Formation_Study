"""期中考第 1 題答案（繁體中文版，HTML -> PDF）。Usage: python build_q1_zh.py BUILD_DIR OUT.pdf"""
import json, os, subprocess, sys

ROOT = "/home/stanley/Github/Unity_Ship_Formation_Study"
B, PDF = sys.argv[1], sys.argv[2]
EV = json.load(open(f"{ROOT}/Experiments/PR_Course/rollouts/evidence.json"))
U = json.load(open(f"{ROOT}/Experiments/PR_Course/usv/usv_report.json"))
u = lambda g, a: U[f"{g}|{a}"]["all"]["success50"]
d3 = EV["drone"]["L3|testv4"]; d3b = EV["drone"]["L3|img7888"]; ua = EV["usv"]["all"]

html = f"""<!DOCTYPE html><html lang="zh-Hant-TW"><head><meta charset="utf-8"><title>期中考第 1 題：期末專題提案</title>
<style>
@page {{ size: A4; margin: 15mm 16mm 15mm 16mm; }}
body {{ font-family: 'Noto Sans CJK TC', 'Liberation Sans', sans-serif; font-size: 9.6pt; line-height: 1.55; color: #1a1a19; }}
h1 {{ font-size: 15pt; margin: 0 0 2pt; }} .sub {{ color: #52514e; font-size: 9pt; margin-bottom: 8pt; }}
h2 {{ font-size: 11.2pt; margin: 9pt 0 4pt; padding-bottom: 2pt; border-bottom: 1.4px solid #2a78d6; break-after: avoid; }}
p {{ margin: 0 0 5pt; text-align: justify; }} ol, ul {{ margin: 0 0 5pt; padding-left: 16pt; }} li {{ margin-bottom: 1.5pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 3pt 0 6pt; font-size: 8.7pt; break-inside: avoid; }}
th, td {{ border-bottom: 0.6px solid #d6d5d0; padding: 2.5pt 5pt; text-align: left; vertical-align: top; }} th {{ background: #f3f2ef; }}
.eq {{ font-family: 'Liberation Serif', 'Noto Serif CJK TC', serif; font-size: 10.5pt; text-align: center; margin: 3pt 0 5pt; }}
.box {{ background: #f3f6fb; border-left: 3px solid #2a78d6; padding: 5pt 8pt; margin: 4pt 0 6pt; }}
.small {{ font-size: 8.4pt; color: #3d3c39; font-family: 'Liberation Sans', 'Noto Sans CJK TC', sans-serif; line-height: 1.4; }}
</style></head><body>
<h1>第 1 題　期末專題提案</h1>
<div class="sub">姓名：____________________　　學號：____________________　　組員（無人機平台）：____________________</div>

<h2>一、題目</h2>
<p><b>從資料中學習追蹤器：以最大概似估計與貝氏決策法則，改善無人機與無人水面載具（USV）在影像快速垂直運動下的目標追蹤。</b></p>
<p><b>背景：</b>本組在兩個平台上使用同一套相機追蹤流程：YOLOv8 物件偵測 → Lucas-Kanade 光流 → 卡爾曼濾波器。組員負責追蹤飛行中的無人機；
我負責模擬的 USV 船隊，跟隨船僅靠相機追蹤領航船以維持編隊。兩者都在目標框於影像中快速上下移動時失效：無人機是目標本身快速升降，
USV 則是相機隨海浪俯仰。在我的 USV 資料中，當目標框垂直速度由每步 0–2 像素增加到 20–40 像素時，YOLO 漏偵率由 1.8% 上升到 14.7%。</p>
<p><b>問題：</b>追蹤器的關鍵參數都是針對單一平台手動調整的：過程雜訊 Q、量測雜訊 R = 60·(0.5/信心值)²，以及決定哪個框是目標的經驗式閘門。
手調參數無法跨平台使用：把無人機追蹤器直接用在船上，表現反而比單純 YOLO 差。在平靜海況下，IoU ≥ 0.5 的影格比例為
{u('clear','his'):.0f}%，而單純 YOLO 為 {u('clear','yolo_only'):.0f}%。</p>
<p><b>方法（對應課程內容）：</b></p>
<ol>
<li><b>最大概似估計（第 3-1 章）。</b>R 為偵測誤差的高斯最大概似估計：Σ̂ = (1/n)Σ(e<sub>k</sub> − μ̂)(e<sub>k</sub> − μ̂)<sup>t</sup>。
Q 則選擇使濾波器新息（innovation）概似最大的值：
<div class="eq">Q̂ = arg max<sub>Q</sub> Σ<sub>k</sub> ln N(ν<sub>k</sub>; 0, S<sub>k</sub>(Q))，　S<sub>k</sub> = HP<sub>k|k−1</sub>H<sup>t</sup> + R</div>
若有真值，Q 亦可用課本的封閉解：Q̂ = (1/n)Σ w<sub>k</sub>w<sub>k</sub><sup>t</sup>，其中 w<sub>k</sub> = x<sub>k+1</sub> − Fx<sub>k</sub>。</li>
<li><b>最小風險貝氏決策（第 2 章）</b>：決定是否接受每一個偵測框。特徵為信心值、馬氏距離與尺寸變化。當下式成立時接受：
<div class="eq">p(x|ω<sub>1</sub>)/p(x|ω<sub>2</sub>) &gt; [(λ<sub>12</sub> − λ<sub>22</sub>)/(λ<sub>21</sub> − λ<sub>11</sub>)] · P(ω<sub>2</sub>)/P(ω<sub>1</sub>)</div>
其中「接受錯誤框」的損失大於「拒絕正確框」的損失。</li>
<li><b>主成分分析、費雪線性判別與休斯現象（第 3-2 章、第 1 章）</b>：用來選擇與視覺化特徵，並實際量測準確率隨特徵維度與訓練樣本數變化的曲線。</li></ol>
<div class="box"><b>初步結果</b>（離線重播並與真值比對；Q 僅由訓練資料學得）：在船上，最大概似估計選出的 Q 為手調值的 10 倍。
這與影格率一致：10 Hz 相較於 30 fps，每步移動量約 3 倍，變異數約 9 倍。使用學得的 Q 後，追蹤器在
<b>{ua['better_than_hand']}/{ua['n']} 個 USV 序列</b>上都優於手調版本（中位數 +{ua['median_gain_vs_hand']:.1f} 個百分點，Wilcoxon 檢定
p = {ua['p_vs_hand']:.0e}）；平靜海況下達到 {u('clear','his+learned_Q'):.0f}%，高於單純 YOLO 的 {u('clear','yolo_only'):.0f}%。
在偵測器延遲較大的無人機影片上，分別提升 {d3['learnedQ_minus_his']['diff']:+.0f} 與 {d3b['learnedQ_minus_his']['diff']:+.0f} 個百分點
（95% 信賴區間不包含 0）；在未參與訓練的另一台無人機影片上提升 24 個百分點。在預先登錄的極端海況（海況 4–5、大雨、暗夜暴風雨）中，
仍在 <b>28/30 個新序列</b>上優於手調版本（p = 3.5e-06）；與單純 YOLO 相比，在晴天與大雨的巨浪中持平或接近，但在暗夜暴風雨中落後約
10 個百分點，這正是期末專題要解決的限制。</div>

<h2>二、相關文獻</h2>
<ol class="small">
<li>R. O. Duda, P. E. Hart, D. G. Stork, <i>Pattern Classification</i>, 2nd ed., Wiley, 2001（貝氏決策理論、最大概似估計、PCA、LDA）。</li>
<li>R. E. Kalman, "A new approach to linear filtering and prediction problems," <i>J. Basic Engineering</i>, 1960.</li>
<li>R. K. Mehra, "On the identification of variances and adaptive Kalman filtering," <i>IEEE Trans. Automatic Control</i>, 1970（以最大概似法估計 Q 與 R）。</li>
<li>G. F. Hughes, "On the mean accuracy of statistical pattern recognizers," <i>IEEE Trans. Information Theory</i>, 1968.</li>
<li>R. A. Fisher, "The use of multiple measurements in taxonomic problems," <i>Annals of Eugenics</i>, 1936.</li>
<li>Y. Bar-Shalom, E. Tse, "Tracking in a cluttered environment with probabilistic data association," <i>Automatica</i>, 1975.</li>
<li>B. D. Lucas, T. Kanade, "An iterative image registration technique with an application to stereo vision," IJCAI 1981.</li>
<li>A. Bewley et al., "Simple online and realtime tracking," ICIP 2016.</li></ol>

<h2>三、專題工作項目與時程</h2>
<table><tr><th style="width:16%">週次</th><th>工作項目</th><th style="width:20%">對應課程</th></tr>
<tr><td>11/5 – 11/11</td><td>提案與 3 分鐘簡報。資料已備妥：含模擬器真值的 USV 資料；以 Grounding DINO 標註並經人工檢查的無人機影片。</td><td>第 1 章 設計流程</td></tr>
<tr><td>11/12 – 11/18</td><td>依座標軸與信心值估計 R；以 Q-Q 圖檢驗高斯假設；由真值計算 Q 的封閉解</td><td>第 3-1 章</td></tr>
<tr><td>11/19 – 11/25</td><td>在兩平台上以新息概似估計 Q，並與封閉解比較</td><td>第 3-1 章</td></tr>
<tr><td>11/26 – 12/2</td><td>最小風險貝氏閘門；掃描損失比 λ<sub>12</sub>/λ<sub>21</sub>；ROC 曲線</td><td>第 2 章、第 1 章（ROC）</td></tr>
<tr><td>12/3 – 12/9</td><td>候選框特徵的 PCA 與費雪 LDA 投影；休斯曲線</td><td>第 3-2 章、維度問題</td></tr>
<tr><td>12/10 – 12/16</td><td>兩平台完整評估；顯著性檢定；並排比較影片</td><td>第 1 章</td></tr>
<tr><td>12/17 → 期末</td><td>撰寫報告、製作投影片、預演（依公布的期末日期調整）</td><td></td></tr></table>

<h2>四、最終成果</h2>
<ol><li>兩平台共用的 Python 模組，取代手調常數：最大概似雜訊模型（R、Q）、貝氏閘門與特徵分析。</li>
<li>標註評估資料：含模擬器精確真值的 USV 相機序列，以及經檢查的無人機虛擬真值影片。</li>
<li>可重現的離線重播評估：將每個追蹤器版本與真值比對，並附統計檢定。</li>
<li>兩平台的並排偵測影片（單純 YOLO｜手調版本｜學習版本）。</li></ol>

<h2>五、專題報告架構與項目</h2>
<p>摘要 · 緒論（兩平台的影像快速垂直運動問題）· 相關文獻 · 問題定義（狀態模型、類別、損失矩陣、最小風險法則）·
方法（R 與 Q 的最大概似推導、貝氏閘門、PCA/LDA）· 資料與真值 · 實驗（追蹤準確率、快速運動影格、各元件消融實驗、休斯曲線）·
統計檢定 · 討論與限制（USV 僅為模擬、無人機為虛擬真值、失敗案例如暗夜暴風雨）· 結論 · 參考文獻 · 附錄（程式碼）。</p>

<h2>六、專題簡報</h2>
<p>約 15 分鐘，兩位組員共同報告：(1) 無人機與船的失效影片，2 分鐘；(2) 共用流程與手調參數，2 分鐘；(3) 課程方法：最大概似推導、
最小風險法則、LDA，3 分鐘；(4) USV 結果：概似在 10 倍處達到峰值、準確率表格與 64/64 檢定，3 分鐘；(5) 無人機結果與並排影片，
3 分鐘；(6) 跨平台可移轉的部分、限制與問答，2 分鐘。</p>
</body></html>"""
os.makedirs(B, exist_ok=True)
open(f"{B}/q1_zh.html", "w").write(html)
subprocess.run(["google-chrome", "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={PDF}",
                f"file://{os.path.abspath(B)}/q1_zh.html"], check=True, capture_output=True)
print("wrote", PDF)
