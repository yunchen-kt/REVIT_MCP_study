# -*- coding: utf-8 -*-
"""Auto-generate one Legend View per door/window type from a Seed Legend View."""

from Autodesk.Revit import DB
from pyrevit import revit, forms
import sys

doc = revit.doc


def is_valid_legend_component(element):
    if not element:
        return False
    p = element.get_Parameter(DB.BuiltInParameter.LEGEND_COMPONENT)
    return p is not None and p.StorageType == DB.StorageType.ElementId


def get_element_name(element):
    try:
        p = element.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM)
        if p and p.AsString():
            return p.AsString()
        p = element.get_Parameter(DB.BuiltInParameter.ALL_MODEL_TYPE_NAME)
        if p and p.AsString():
            return p.AsString()
        p = element.get_Parameter(DB.BuiltInParameter.VIEW_NAME)
        if p and p.AsString():
            return p.AsString()
        return element.Name
    except Exception:
        return "Unknown"


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


def get_filtered_types(symbols, selected_comments):
    results = []
    for symbol in symbols:
        type_comment_param = symbol.get_Parameter(
            DB.BuiltInParameter.ALL_MODEL_TYPE_COMMENTS)
        tc = type_comment_param.AsString() if type_comment_param else ""
        if not tc:
            tc = "(未填/空白)"

        if tc not in selected_comments:
            continue

        type_mark_param = symbol.get_Parameter(
            DB.BuiltInParameter.ALL_MODEL_TYPE_MARK)
        type_mark = type_mark_param.AsString() if type_mark_param else ""
        if not type_mark or not type_mark.strip():
            type_mark = "(未填)"

        results.append({
            "TypeId": symbol.Id,
            "TypeMark": type_mark.strip(),
            "TypeName": get_element_name(symbol)
        })
    return results


def main():
    active_view = doc.ActiveView
    if active_view.ViewType != DB.ViewType.Legend:
        forms.alert(
            "目前啟用的視圖不是 Legend，\n"
            "請切換到您準備好的 Seed Legend View。",
            title="錯誤", exitscript=True)

    seed_components = DB.FilteredElementCollector(doc, active_view.Id)\
        .WhereElementIsNotElementType()\
        .ToElements()

    legend_component = None
    for c in seed_components:
        if is_valid_legend_component(c):
            legend_component = c
            break

    if not legend_component:
        forms.alert(
            "在目前的 Seed View 中找不到 Legend Component，無法做為種子。",
            title="錯誤", exitscript=True)

    # 1. 詢問要更新門還是窗
    category_options = {"門 (Doors)": DB.BuiltInCategory.OST_Doors, 
                        "窗 (Windows)": DB.BuiltInCategory.OST_Windows}
    
    selected_cat_name = forms.CommandSwitchWindow.show(
        category_options.keys(),
        message="請選擇要建立圖例的類別："
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

    # 取得最終要處理的型號
    target_types = get_filtered_types(used_symbols, selected_comments)
    if not target_types:
        forms.alert("沒有符合條件的型號需要處理。", title="提示", exitscript=True)

    print("=== 開始執行 P 模式：一型一 Legend 自動生成 ===")
    print("已選擇類別: {}".format(selected_cat_name))
    print("符合篩選條件的型號共 {} 種。".format(len(target_types)))

    existing_view_names = set()
    for v in DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements():
        v_name = get_element_name(v)
        if v_name:
            existing_view_names.add(v_name)

    created_count = 0
    skipped_count = 0

    with revit.Transaction("批次生成圖例(P模式)"):
        for t_info in target_types:
            mark = t_info["TypeMark"]
            tid = t_info["TypeId"]

            if mark == "(未填)":
                print("跳過未填 Type Mark 的元件: {}".format(t_info["TypeName"]))
                continue

            if mark in existing_view_names:
                print("跳過: 視圖 [{}] 已存在。".format(mark))
                skipped_count += 1
                continue

            new_view_id = active_view.Duplicate(
                DB.ViewDuplicateOption.WithDetailing)
            new_view = doc.GetElement(new_view_id)

            name_param = new_view.get_Parameter(
                DB.BuiltInParameter.VIEW_NAME)
            if name_param and not name_param.IsReadOnly:
                name_param.Set(mark)
            else:
                try:
                    new_view.Name = mark
                except Exception:
                    pass
            existing_view_names.add(mark)

            new_components = DB.FilteredElementCollector(
                doc, new_view.Id)\
                .WhereElementIsNotElementType()\
                .ToElements()

            for nc in new_components:
                if is_valid_legend_component(nc):
                    orig_bbox = nc.get_BoundingBox(new_view)
                    if orig_bbox:
                        orig_bottom = orig_bbox.Min.Y
                        orig_center_x = (
                            orig_bbox.Min.X + orig_bbox.Max.X) / 2.0
                    else:
                        orig_bbox = None

                    p = nc.get_Parameter(
                        DB.BuiltInParameter.LEGEND_COMPONENT)
                    if p and not p.IsReadOnly:
                        p.Set(tid)

                    doc.Regenerate()

                    if orig_bbox:
                        new_bbox = nc.get_BoundingBox(new_view)
                        if new_bbox:
                            new_bottom = new_bbox.Min.Y
                            new_center_x = (
                                new_bbox.Min.X + new_bbox.Max.X) / 2.0

                            dy = orig_bottom - new_bottom
                            dx = orig_center_x - new_center_x
                            translation = DB.XYZ(dx, dy, 0)

                            if translation.GetLength() > 0.0001:
                                DB.ElementTransformUtils.MoveElement(
                                    doc, nc.Id, translation)
                    break

            print("成功建立視圖 [{}] (對應 Family Type: {})".format(
                mark, t_info["TypeName"]))
            created_count += 1

    print("=== 執行完畢 ===")
    print("成功建立: {} 個圖例".format(created_count))
    print("略過 (已存在): {} 個".format(skipped_count))

    if created_count > 0:
        forms.alert(
            "成功建立 {} 個圖例視圖！\n略過 (已存在): {} 個".format(
                created_count, skipped_count),
            title="執行結果")


if __name__ == '__main__':
    main()
