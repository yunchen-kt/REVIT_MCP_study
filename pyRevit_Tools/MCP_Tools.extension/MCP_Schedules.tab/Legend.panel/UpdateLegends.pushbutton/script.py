# -*- coding: utf-8 -*-
"""Read door/window data from Excel and batch-update Legend View text notes."""

import os
import tempfile
import subprocess
import json
import codecs

from Autodesk.Revit import DB
from pyrevit import revit, forms

import clr
clr.AddReference('System.Windows.Forms')
from System.Windows.Forms import OpenFileDialog, DialogResult

doc = revit.doc

COORD_MAP = {
    "19.863,12.144,0.000": "門窗編號",
    "19.863,10.504,0.000": "形式材質",
    "19.863,8.863,0.000":  "表面處理",
    "19.863,7.223,0.000":  "尺寸",
    "19.863,5.582,0.000":  "防火阻熱性",
    "19.863,3.942,0.000":  "其他五金",
    "31.346,12.144,0.000": "玻璃",
    "31.346,10.504,0.000": "門鎖",
    "31.346,8.863,0.000":  "鉸鍊",
    "31.346,7.223,0.000":  "把手",
    "31.346,5.582,0.000":  "天地栓/門止",
    "31.346,3.942,0.000":  "備註",
}


def format_coord(coord):
    return "{:.3f},{:.3f},{:.3f}".format(coord.X, coord.Y, coord.Z)


def read_excel_data(filepath):
    temp_ps1 = os.path.join(tempfile.gettempdir(), "read_excel.ps1")
    temp_json = os.path.join(tempfile.gettempdir(), "excel_data.json")

    ps_code = """
$ErrorActionPreference = 'Stop'
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
try {{
    $workbook = $excel.Workbooks.Open('{0}')
    $ws = $workbook.Sheets.Item('門窗資訊')
    $maxCol = $ws.UsedRange.Columns.Count
    $maxRow = $ws.UsedRange.Rows.Count

    $headers = @()
    for ($c = 1; $c -le $maxCol; $c++) {{
        $headers += $ws.Cells.Item(1, $c).Text
    }}

    $data = @{{}}
    for ($r = 2; $r -le $maxRow; $r++) {{
        $id = $ws.Cells.Item($r, 1).Text
        if ([string]::IsNullOrWhiteSpace($id)) {{ continue }}

        $rowData = @{{}}
        for ($c = 1; $c -le $maxCol; $c++) {{
            $val = $ws.Cells.Item($r, $c).Text
            $colName = $headers[$c - 1]
            if ([string]::IsNullOrWhiteSpace($val)) {{ $val = '-' }}
            $rowData[$colName] = $val
        }}
        $data[$id] = $rowData
    }}
    $workbook.Close($false)
    $data | ConvertTo-Json -Depth 5 | Out-File -FilePath '{1}' -Encoding utf8
}} finally {{
    $excel.Quit()
    [System.Runtime.Interopservices.Marshal]::ReleaseComObject($excel) | Out-Null
}}
""".format(filepath, temp_json)

    with codecs.open(temp_ps1, "w", "utf-8-sig") as f:
        f.write(ps_code)

    process = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy",
         "Bypass", "-File", temp_ps1],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise Exception("PowerShell Error: " + stderr)

    with codecs.open(temp_json, "r", "utf-8-sig") as f:
        data = json.load(f)

    return data


def main():
    dialog = OpenFileDialog()
    dialog.Filter = "Excel Files|*.xlsx;*.xls|All Files|*.*"
    dialog.Title = "請選擇門窗資訊 Excel 檔案"

    if dialog.ShowDialog() != DialogResult.OK:
        print("取消操作。")
        return

    excel_path = dialog.FileName

    print(">>> 正在從 Excel 讀取資料: {}".format(excel_path))
    try:
        excel_data = read_excel_data(excel_path)
        print(">>> 成功讀取了 {} 筆門窗型號資料。".format(len(excel_data)))
    except Exception as e:
        forms.alert(
            "讀取 Excel 失敗:\n{}".format(e),
            title="錯誤", exitscript=True)

    all_views = DB.FilteredElementCollector(doc).OfClass(DB.View)
    legend_views = [v for v in all_views
                    if v.ViewType == DB.ViewType.Legend and not v.IsTemplate]

    total_updated = 0
    views_updated = 0

    with revit.Transaction("Batch Update Legend Data"):
        for view in legend_views:
            view_name = view.Name

            if view_name in excel_data:
                target_data = excel_data[view_name]
                text_notes = DB.FilteredElementCollector(
                    doc, view.Id).OfClass(DB.TextNote)

                updated_in_view = 0
                for tn in text_notes:
                    coord_key = format_coord(tn.Coord)

                    if coord_key in COORD_MAP:
                        col_name = COORD_MAP[coord_key]
                        new_value = target_data.get(col_name, "-")

                        if tn.Text != new_value:
                            tn.Text = new_value
                            updated_in_view += 1

                if updated_in_view > 0:
                    print("已更新 View [{}]，變更了 {} 個欄位。".format(
                        view_name, updated_in_view))
                    views_updated += 1
                    total_updated += updated_in_view
                else:
                    print("View [{}] 已是最新狀態 (Idempotent)。".format(
                        view_name))

    print("--- 批次更新完成 ---")
    print("共處理了 {} 個 Legend 視圖，更新了 {} 個欄位。".format(
        views_updated, total_updated))

    forms.alert(
        "批次更新完成！\n處理了 {} 個視圖，更新了 {} 個欄位。".format(
            views_updated, total_updated),
        title="執行結果")


if __name__ == '__main__':
    main()
