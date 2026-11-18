# Rory 工作台

為旅遊報價與檔案交付準備的可重用工具。程式使用 Python 3.12 以上版本；
報價核心與基礎測試不需另裝套件。此專案不等於已安裝全域技能或外掛。

## 報價與匯率

```powershell
python tools/quote.py examples/quote.json
python tools/quote.py my-quote.json --output quote-result.json
```

- 匯率欄位 `vnd_per_1000_twd`：1000 台幣能換多少越南盾。例如 800000。
- `twd_per_usd`：1 美元換多少台幣。所有示例匯率與價格都是虛構測試資料。
- `single_travelers` 是住單人房的人數；其他旅客採兩人一房。
- `hotel` 是每房每晚成本；`cost_lines.quantity` 是全團數量。
- `margin_percent` 是毛利率，售價 = 成本 ÷ (1 − 毛利率)，並向上取整。
- 結果分列雙人房每人售價、單人房每人售價、單房差、全團成本與毛利。
- 稅費、小費、簽證、保險與其他費用需自行加入成本，不會自動估計。
- 成本採全精度加總，最後顯示到小數點後兩位；逐列顯示值加總可能有分位差。

報價結果含內部成本與毛利，請先轉成客戶版本再對外提供。

## 檔案交付檢查

```powershell
python tools/check_deliverables.py itinerary.pdf costing.xlsx video.mp4 --output checks.json
```

檢查檔案存在、非空、SHA-256、JSON 可讀性、ZIP/Office 檔案結構。
若有安裝 `openpyxl`、`pypdf`、`Pillow`，可增加 Excel 錯誤／公式快取、
PDF 頁數、圖片尺寸與損壞檢查；影片軌道與時長使用可選的 `ffprobe`。
缺少工具會明確標成待檢查，不會假報通過。

`FAIL` 代表檢出問題，結束碼為 1。`REVIEW` 代表仍需指定的人工確認，
結束碼為 0，便於把自動檢查與人工交付確認分開。此程式不重算 Excel、
不判定中文字體是否正常，也不代替影片實際播放。

## 自動測試

```powershell
python -m unittest discover -s tests -v
```

GitHub Actions 對每次修改及 Pull Request 執行測試，權限僅讀取程式。
`AGENTS.md` 說明此專案的工具用法與交付原則，方便後續接續工作。

本公開專案僅存放程式與虛構範例。客戶名單、真實供應商報價與私人資料
請存放在自己的非公開工作位置。
