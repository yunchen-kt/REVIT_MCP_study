# pyRevit 開發踩坑與除錯指南 (Development Gotchas)

在開發 pyRevit 擴充功能（特別是 Python 腳本轉 Revit Add-in）時，常常會遇到看似毫無道理的錯誤（例如 `Failed to initialize the add-in... class cannot be found in the add-in assembly`）。這通常是因為底層的 IronPython 2 引擎在編譯腳本時發生崩潰，而 pyRevit 把錯誤細節吞掉了。

以下是我們開發過程中遇到並確認的幾個重大地雷與解法：

## 1. 檔案編碼與字串前綴 (Encoding & Strings)

**症狀**：出現 `Wrong Full Class Name` 錯誤。
**原因**：如果 Python 腳本存成 **UTF-8 (無 BOM)**，且程式碼中混用了 `u"中文字串"` 這種 Unicode 前綴宣告，IronPython 的 parser 在遇到非 ASCII 字元時會直接引發 `SyntaxError`，導致類別無法生成。
**解法**：
1. 檔案開頭務必加上 `# -*- coding: utf-8 -*-`。
2. **不要**使用 `u"中文字"`，直接使用一般字串 `"中文字"` 即可（在 Revit 彈出視窗與字串格式化中運作正常）。
3. 如果編輯器允許，將檔案存為 **UTF-8 with BOM** 可以最大程度避免 IronPython 解析問題。

## 2. 換行符號 (CRLF vs LF)

**症狀**：出現 `Wrong Full Class Name` 錯誤。
**原因**：Unix 風格的 `LF` (\n) 換行符號會讓 pyRevit 的解析器拋出 `unexpected EOF while parsing` 的底層錯誤，導致編譯中斷。
**解法**：永遠確保你的 `script.py` 使用 Windows 風格的 **`CRLF` (\r\n)** 換行符號。如果透過 Node.js 或跨平台腳本自動生成檔案，特別容易踩到這個坑。

> **⚠ 2026-06-22 更正**：實測發現能正常運作的 Landscape 工具（Altitude.pushbutton）實際上是 LF 換行。LF **可能**在某些 pyRevit/IronPython 版本組合下造成問題，但並非必然。統一使用 CRLF 是安全的做法，但若遇到 `Wrong Full Class Name`，**不要只往 LF 的方向排查**，優先檢查下方第 5 點（DLL 快取）。

## 3. pyRevit 的死當快取 (Aggressive Caching)

**症狀**：你已經把程式碼修復了（甚至把程式碼砍到只剩 `print` 兩行），但點擊 `Reload` 後，還是跳出一模一樣的錯誤。
**原因**：pyRevit 有一套強硬的快取機制，當它判定某個按鈕資料夾「編譯失敗」後，有時候普通 Reload 無法清除這個壞掉的狀態，它會拒絕重新編譯。
**解法**：
- **第一招（首選）**：在 Revit 面板中，按住鍵盤的 **`Shift` 鍵不放**，然後點擊 **Reload** 按鈕。這會觸發「強制硬重載 (Hard Reload)」，清空所有記憶體快取。
- **第二招**：直接將該 `.pushbutton` 資料夾重新命名（例如加上 `_v2`），強迫 pyRevit 把它當作一個全新的擴充功能來編譯。

> **⚠ 2026-06-22 更正**：以上兩招只處理 **記憶體內的快取**。如果 DLL 檔案本身就不包含新按鈕的 class（見第 5 點），這兩招都無效。甚至完全關閉 Revit 再重開也可能無效（因為 hash 沒變，pyRevit 不會重新編譯）。**必須手動刪除 DLL 才能解決。**

## 4. 資料夾命名規範與底線

**症狀**：編譯出的類別名稱異常，或無法對應。
**原因**：pyRevit 會根據資料夾路徑自動生成 C# 類別名稱（例如 `mcp_tools_mcp_views_curtainwall_cwelevation_script`）。如果資料夾名稱中包含不必要的底線（例如 `CW_Elevation.pushbutton`），有時會導致 pyRevit 解析規則錯亂或與內建規則衝突。
**解法**：
- 資料夾命名盡量使用 **PascalCase**（大駝峰），例如 `CreateElevation.pushbutton`，避免在按鈕資料夾名稱中使用底線 `_`。
- 嚴格遵守 `.extension` -> `.tab` -> `.panel` -> `.pushbutton` 的四層結構。

## 5. 新增按鈕後 DLL 未重新編譯（最致命的坑）🔴

**症狀**：在已有的 `.extension` 中新增 `.panel` 或 `.pushbutton` 後，新按鈕全部出現 `Wrong Full Class Name`，但同 extension 內的**舊按鈕完全正常**。即使把新腳本砍到只剩一行 `print`，錯誤依舊。Shift+Reload、重新命名、關閉重開 Revit 全部無效。
**原因**：pyRevit 在 `%AppData%\pyRevit\<Year>\` 下為每個 extension 編譯一個 DLL（例如 `pyRevit_2025_4b12b427e0bbe238_MCP_Tools.dll`）。pyRevit 使用 **extension 路徑的 hash** 判斷是否需要重新編譯——如果根路徑沒變，hash 就不變，pyRevit 就直接沿用舊 DLL，**即使你新增了一整個 panel 也不會觸發重新編譯**。結果就是新按鈕的 class 從未被編進 DLL。
**解法**：
1. **完全關閉 Revit**（Task Manager 確認沒有 `Revit.exe`，否則 DLL 被鎖住無法刪除）。
2. 前往 `%AppData%\pyRevit\<Year>\`，找到並**刪除**對應 extension 的 `.dll` 檔案（例如 `pyRevit_2025_*_MCP_Tools.dll`）。
3. 重新啟動 Revit。pyRevit 偵測到 DLL 不存在，會從頭完整重新編譯，新按鈕就會被正確包含。

> **這是 2026-06-22 花了約 2 小時排除所有假設後確認的真正根因。詳細除錯記錄見 Wiki `raw/2026-06-22-pyrevit-wrong-full-class-name-dll-cache.md`。**
