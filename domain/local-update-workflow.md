# Local Update Workflow (Environment Specific)

這份文件記錄了本機環境，每次從 GitHub 同步更新 (pull) 之後，AI 以及開發者應該執行的標準更新與部署流程。請未來的 AI 執行更新相關任務時，嚴格遵守以下路徑與步驟。

## 環境背景與限制

- **使用者系統**：Windows
- **Revit 目標版本**：2025 (`Release.R25`)
- **.NET SDK 環境**：本機目前只有安裝 `.NET SDK 8.0.x`。
- **已知問題**：如果上游更新時將 `Nice3point.Revit.Sdk` 更新至 `6.1.0` 或以上，在使用 `dotnet build` 時會因為載入 MSBuild 任務失敗（報錯 `System.Runtime, Version=10.0.0.0`）而中斷。
- **核心路徑**：`c:\WIP\REVIT_MCP`

---

## 每次同步/更新後的標準操作步驟

如果使用者要求「更新」、「部署」或「重新編譯整個專案」，請照順序執行以下三個步驟：

### 1. 重新編譯 MCP Server
MCP Server 是 Node.js 專案，需要重新安裝套件與編譯 TypeScript。
- **路徑**：`c:\WIP\REVIT_MCP\MCP-Server`
- **指令**（請在 PowerShell 依序執行，或分開下達指令避免 `&&` 語法相容問題）：
  ```powershell
  npm install
  npm run build
  ```

### 2. 解決 C# 專案版本衝突與重新編譯
- **路徑**：`c:\WIP\REVIT_MCP\MCP\RevitMCP.csproj`
- **降級 Sdk（如果需要）**：
  在執行編譯前，先檢驗 `RevitMCP.csproj` 檔案第一行的 `Sdk` 屬性。如果是 `Nice3point.Revit.Sdk/6.1.0`，必須將它改回 `6.0.0`：
  ```xml
  <Project Sdk="Nice3point.Revit.Sdk/6.0.0">
  ```
  這樣才能相容本機的 .NET 8.0 SDK。
- **執行編譯指令**：
  ```powershell
  # 工作目錄需在 c:\WIP\REVIT_MCP\MCP
  dotnet build -c Release.R25 RevitMCP.csproj
  ```

### 3. 將編譯好的 DLL 部署到 Revit 2025 目錄
由於本專案在 `.csproj` 中預設將 `<DeployAddin>` 設為 `false`，編譯後並不會自動部署，需經由以下指令手動複製：
- **操作目錄**：`c:\WIP\REVIT_MCP\MCP`
- **PowerShell 指令**：
  ```powershell
  mkdir "$env:APPDATA\Autodesk\Revit\Addins\2025\RevitMCP" -Force
  Copy-Item ".\bin\Release.R25\RevitMCP.dll" "$env:APPDATA\Autodesk\Revit\Addins\2025\RevitMCP\" -Force
  ```
> **注意**：只有 `RevitMCP.dll` 需要被覆蓋與複製，而 `.addin` 檔應該已經存在於正確的位置，不要去覆寫或產生出錯版本的 manifest 檔案。
