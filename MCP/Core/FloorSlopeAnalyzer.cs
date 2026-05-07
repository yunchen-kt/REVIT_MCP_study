using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.Revit.DB;
using Newtonsoft.Json.Linq;

// Revit 2025+ ElementId: int -> long
#if REVIT2025_OR_GREATER
using IdType = System.Int64;
#else
using IdType = System.Int32;
#endif

namespace RevitMCP.Core
{
    public class FloorSlopeAnalyzer
    {
        public static object AnalyzeAndWriteSlopes(Document doc, JObject parameters)
        {
            string minSlopeParamName = parameters["minSlopeParam"]?.Value<string>() ?? "Comments";
            string maxSlopeParamName = parameters["maxSlopeParam"]?.Value<string>() ?? "Comments";

            var elementIdsToken = parameters["elementIds"] as JArray;
            List<Floor> targetFloors = new List<Floor>();

            if (elementIdsToken != null && elementIdsToken.Count > 0)
            {
                foreach (var token in elementIdsToken)
                {
                    IdType id = token.Value<IdType>();
                    Element elem = doc.GetElement(new ElementId(id));
                    if (elem is Floor floor)
                    {
                        targetFloors.Add(floor);
                    }
                }
            }
            else
            {
                // default to all exterior floors
                var allFloors = new FilteredElementCollector(doc)
                    .OfClass(typeof(Floor))
                    .Cast<Floor>();
                    
                foreach (var floor in allFloors)
                {
                    Parameter functionParam = floor.get_Parameter(BuiltInParameter.FUNCTION_PARAM);
                    if (functionParam != null && functionParam.AsInteger() == (int)WallFunction.Exterior)
                    {
                        targetFloors.Add(floor);
                    }
                }
            }

            Options geomOptions = new Options { DetailLevel = ViewDetailLevel.Fine };
            var results = new List<object>();

            using (Transaction trans = new Transaction(doc, "Analyze and Write Floor Slopes"))
            {
                trans.Start();

                foreach (Floor floor in targetFloors)
                {
                    GeometryElement geomElem = floor.get_Geometry(geomOptions);
                    double minSlope = double.MaxValue;
                    double maxSlope = double.MinValue;
                    bool foundUpwardFace = false;

                    if (geomElem != null)
                    {
                        foreach (GeometryObject geomObj in geomElem)
                        {
                            if (geomObj is Solid solid && solid.Volume > 0)
                            {
                                foreach (Face face in solid.Faces)
                                {
                                    if (face is PlanarFace planarFace)
                                    {
                                        XYZ normal = planarFace.FaceNormal;
                                        // 僅檢查朝上的頂部表面 (Z > 0.001)
                                        if (normal.Z > 0.001)
                                        {
                                            double angleWithVertical = normal.AngleTo(XYZ.BasisZ);
                                            double slopePercent = Math.Tan(angleWithVertical) * 100.0;

                                            if (slopePercent < minSlope) minSlope = slopePercent;
                                            if (slopePercent > maxSlope) maxSlope = slopePercent;
                                            foundUpwardFace = true;
                                        }
                                    }
                                }
                            }
                        }
                    }

                    if (foundUpwardFace)
                    {
                        Parameter minParam = floor.LookupParameter(minSlopeParamName);
                        Parameter maxParam = floor.LookupParameter(maxSlopeParamName);

                        string minStr = minSlope.ToString("F2") + "%";
                        string maxStr = maxSlope.ToString("F2") + "%";

                        bool written = false;

                        if (minSlopeParamName == maxSlopeParamName)
                        {
                            if (minParam != null && !minParam.IsReadOnly)
                            {
                                minParam.Set($"Slope: {minStr} ~ {maxStr}");
                                written = true;
                            }
                        }
                        else
                        {
                            if (minParam != null && !minParam.IsReadOnly)
                            {
                                minParam.Set(minStr);
                                written = true;
                            }
                            if (maxParam != null && !maxParam.IsReadOnly)
                            {
                                maxParam.Set(maxStr);
                                written = true;
                            }
                        }

                        results.Add(new
                        {
                            ElementId = floor.Id.GetIdValue(),
                            Name = floor.Name,
                            MinSlope = minSlope,
                            MaxSlope = maxSlope,
                            Written = written
                        });
                    }
                }

                trans.Commit();
            }

            return new
            {
                ProcessedCount = results.Count,
                Results = results
            };
        }
    }
}
