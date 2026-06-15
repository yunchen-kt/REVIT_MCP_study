# -*- coding: utf-8 -*-
import math
import System
from System.Collections.Generic import List
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Analysis import *
from pyrevit import revit, DB, UI, forms, script

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

def main():
    if not (isinstance(view, DB.View3D) or isinstance(view, DB.ViewPlan)):
        forms.alert("Tool must be run in 3D or Plan view.", exitscript=True)

    selection = revit.get_selection()
    floors = [el for el in selection.elements if isinstance(el, DB.Floor)]

    if not floors:
        last_uids = script.load_data("DrainageHeatmap_LastFloors")
        if last_uids:
            for uid in last_uids:
                try:
                    el = doc.GetElement(uid)
                    if el and isinstance(el, DB.Floor):
                        floors.append(el)
                except Exception:
                    pass

    if not floors:
        try:
            sel_refs = uidoc.Selection.PickObjects(UI.Selection.ObjectType.Element, "Select floors to analyze")
            floors = [doc.GetElement(ref) for ref in sel_refs if isinstance(doc.GetElement(ref), DB.Floor)]
        except Exception:
            pass

    if not floors:
        forms.alert("No floor selected.", exitscript=True)
    else:
        script.store_data("DrainageHeatmap_LastFloors", [f.UniqueId for f in floors])

    sfm = SpatialFieldManager.GetSpatialFieldManager(view)
    if sfm:
        sfm.Clear()
    else:
        sfm = SpatialFieldManager.CreateSpatialFieldManager(view, 1)

    schema = AnalysisResultSchema("Floor Slope Heatmap", "Shows slope of floor faces in percentage")
    schemaIndex = -1
    
    results = sfm.GetRegisteredResults()
    for r in results:
        s = sfm.GetResultSchema(r)
        if s.Name == "Floor Slope Heatmap":
            schemaIndex = r
            break

    if schemaIndex == -1:
        schemaIndex = sfm.RegisterResult(schema)

    opt = DB.Options()
    opt.ComputeReferences = True

    processed_faces = 0

    with revit.Transaction("Analyze Floor Slope Heatmap"):
        for floor in floors:
            geom_elem = floor.get_Geometry(opt)
            if not geom_elem:
                continue

            for geom_obj in geom_elem:
                if isinstance(geom_obj, DB.Solid) and geom_obj.Faces.Size > 0:
                    for face in geom_obj.Faces:
                        bbox = face.GetBoundingBox()
                        uv_center = (bbox.Min + bbox.Max) / 2.0
                        try:
                            derivatives = face.ComputeDerivatives(uv_center)
                            normal = derivatives.BasisZ.Normalize()
                        except Exception:
                            continue

                        if normal.Z > 0.1:
                            xy_len = math.sqrt(normal.X**2 + normal.Y**2)
                            slope_percent = (xy_len / normal.Z) * 100.0 if normal.Z != 0 else 0.0

                            if face.Reference:
                                try:
                                    idx = sfm.AddSpatialFieldPrimitive(face.Reference)
                                    
                                    mesh = face.Triangulate()
                                    if mesh:
                                        uv_pts_list = List[DB.UV]()
                                        vals_list = List[ValueAtPoint]()
                                        
                                        for pt in mesh.Vertices:
                                            inter_res = face.Project(pt)
                                            if inter_res:
                                                uv_pts_list.Add(inter_res.UVPoint)
                                                
                                                val_list = List[System.Double]()
                                                val_list.Add(slope_percent)
                                                vals_list.Add(ValueAtPoint(val_list))
                                            
                                        if uv_pts_list.Count > 0:
                                            pnts = FieldDomainPointsByUV(uv_pts_list)
                                            values = FieldValues(vals_list)
                                            sfm.UpdateSpatialFieldPrimitive(idx, pnts, values, schemaIndex)
                                            processed_faces += 1
                                except Exception as e:
                                    print("Error processing face: {}".format(e))
                                    
        if processed_faces > 0:
            forms.alert("Analysis complete! Processed {} faces. Please select the correct Analysis Display Style in View Properties.".format(processed_faces), title="Success")
        else:
            forms.alert("Could not find any top faces to analyze. Check if Floor shape is valid.", title="Warning")

if __name__ == '__main__':
    main()
