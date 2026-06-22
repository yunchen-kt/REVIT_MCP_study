# -*- coding: utf-8 -*-
"""Auto-place Legend Views onto a Sheet using Flow Layout algorithm."""

import clr
import sys
clr.AddReference('Microsoft.VisualBasic')
from Microsoft.VisualBasic import Interaction

from Autodesk.Revit import DB
from pyrevit import revit, forms

doc = revit.doc


def get_element_name(element):
    try:
        p = element.get_Parameter(DB.BuiltInParameter.VIEW_NAME)
        if p and p.AsString():
            return p.AsString()
        return element.Name
    except Exception:
        return ""


def get_used_symbols(category_enum):
    instances = DB.FilteredElementCollector(doc)\
        .OfCategory(category_enum)\
        .WhereElementIsNotElementType()\
        .ToElements()

    type_ids = set()
    for inst in instances:
        tid = inst.GetTypeId()
        if tid != DB.ElementId.InvalidElementId:
            type_ids.add(tid)

    symbols = []
    for tid in type_ids:
        symbol = doc.GetElement(tid)
        if symbol:
            symbols.append(symbol)
    return symbols


def get_unique_type_comments(symbols):
    comments = set()
    for symbol in symbols:
        type_comment_param = symbol.get_Parameter(
            DB.BuiltInParameter.ALL_MODEL_TYPE_COMMENTS)
        tc = type_comment_param.AsString() if type_comment_param else ""
        if not tc:
            tc = "(未填/空白)"
        comments.add(tc)
    return sorted(list(comments))


def get_filtered_marks(symbols, selected_comments):
    used_marks = set()
    for symbol in symbols:
        type_comment_param = symbol.get_Parameter(
            DB.BuiltInParameter.ALL_MODEL_TYPE_COMMENTS)
        tc = type_comment_param.AsString() if type_comment_param else ""
        if not tc:
            tc = "(未填/空白)"

        if tc not in selected_comments:
            continue

        tm_param = symbol.get_Parameter(
            DB.BuiltInParameter.ALL_MODEL_TYPE_MARK)
        tm = tm_param.AsString() if tm_param else ""
        if tm and tm.strip():
            used_marks.add(tm.strip())
            
    return sorted(list(used_marks))


def main():
    active_sheet = doc.ActiveView
    if active_sheet.ViewType != DB.ViewType.DrawingSheet:
        forms.alert(
            "目前啟用的視圖不是圖紙 (Sheet)！\n"
            "請切換到您要排版的圖紙視圖。",
            title="錯誤", exitscript=True)

    default_width = "73"
    user_input = Interaction.InputBox(
        "請輸入圖紙的「可放置範圍總寬度 (cm)」\n\n"
        "(超過此寬度時，大圖例會自動折行):",
        "圖紙排版設定",
        default_width
    )

    if not user_input or not user_input.strip():
        print("使用者取消操作。")
        return

    try:
        AVAILABLE_WIDTH_CM = float(user_input.strip())
    except Exception:
        forms.alert("輸入的值無效，請輸入數字。",
                     title="錯誤", exitscript=True)

    # 1. 詢問要排版門還是窗
    category_options = {"門 (Doors)": DB.BuiltInCategory.OST_Doors, 
                        "窗 (Windows)": DB.BuiltInCategory.OST_Windows}
    
    selected_cat_name = forms.CommandSwitchWindow.show(
        category_options.keys(),
        message="請選擇要排版的類別："
    )

    if not selected_cat_name:
        print("已取消操作。")
        sys.exit()

    selected_category = category_options[selected_cat_name]

    # 取得有被使用的 Symbols
    used_symbols = get_used_symbols(selected_category)
    if not used_symbols:
        forms.alert("專案中沒有找到被使用的該類別元件。", title="提示", exitscript=True)

    # 2. 篩選 Type Comments
    unique_comments = get_unique_type_comments(used_symbols)
    
    selected_comments = forms.SelectFromList.show(
        unique_comments,
        multiselect=True,
        title="請選擇要包含的 Type Comments",
        button_name="確認選擇"
    )

    if not selected_comments:
        print("未選擇任何 Type Comment，已取消操作。")
        sys.exit()

    # 取得最終要處理的 Type Mark 清單
    sorted_marks = get_filtered_marks(used_symbols, selected_comments)

    ROW_HEIGHT_CM = 18.0
    X_SPACING_CM = 0.0
    CM_TO_FEET = 0.0328083989501312
    START_X_CM = 10.0
    START_Y_CM = 80.0

    all_legend_views = DB.FilteredElementCollector(doc)\
        .OfClass(DB.View).ToElements()
    legend_dict = {}
    for v in all_legend_views:
        if v.ViewType == DB.ViewType.Legend and not v.IsTemplate:
            name = get_element_name(v)
            if name:
                legend_dict[name] = v

    views_to_place = []
    for mark in sorted_marks:
        if mark in legend_dict:
            views_to_place.append(legend_dict[mark])

    print("=== 開始執行圖紙排版 ===")
    print("已選擇類別: {}".format(selected_cat_name))
    print("準備放置 {} 個圖例視圖到圖紙 [{}] 上。".format(
        len(views_to_place), get_element_name(active_sheet)))

    if not views_to_place:
        forms.alert("沒有找到對應的圖例視圖可供放置（請確認圖例是否已產生且名稱相符）。",
                     title="提示", exitscript=True)

    existing_viewports = DB.FilteredElementCollector(
        doc, active_sheet.Id).OfClass(DB.Viewport).ToElements()
    placed_view_ids = set([vp.ViewId for vp in existing_viewports])

    placed_count = 0
    skipped_count = 0

    current_x_cm = START_X_CM
    current_y_cm = START_Y_CM

    with revit.Transaction("批次圖紙排版(Flow Layout)"):
        for v in views_to_place:
            if v.Id in placed_view_ids:
                print("略過: 視圖 [{}] 已經在圖紙上了。".format(
                    get_element_name(v)))
                skipped_count += 1
                continue

            outline = v.Outline
            width_ft = outline.Max.U - outline.Min.U
            height_ft = outline.Max.V - outline.Min.V

            width_cm = width_ft / CM_TO_FEET
            height_cm = height_ft / CM_TO_FEET

            if (current_x_cm + width_cm >
                    START_X_CM + AVAILABLE_WIDTH_CM
                    and current_x_cm > START_X_CM):
                current_x_cm = START_X_CM
                current_y_cm -= ROW_HEIGHT_CM

            center_x_cm = current_x_cm + (width_cm / 2.0)
            center_y_cm = current_y_cm - (height_cm / 2.0)

            point = DB.XYZ(
                center_x_cm * CM_TO_FEET,
                center_y_cm * CM_TO_FEET, 0)

            try:
                DB.Viewport.Create(doc, active_sheet.Id, v.Id, point)
                placed_count += 1
                current_x_cm += (width_cm + X_SPACING_CM)
            except Exception as e:
                print("放置視圖 [{}] 時發生錯誤: {}".format(
                    get_element_name(v), e))

    print("=== 執行完畢 ===")
    print("設定總寬度: {} cm".format(AVAILABLE_WIDTH_CM))
    print("成功放置: {} 個圖例".format(placed_count))
    print("略過 (已在圖紙上): {} 個".format(skipped_count))

    if placed_count > 0:
        forms.alert(
            "排版完成！\n成功放置 {} 個圖例。\n略過 (已在圖紙上): {} 個".format(
                placed_count, skipped_count),
            title="執行結果")


if __name__ == '__main__':
    main()
