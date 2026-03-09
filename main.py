# backend/main.py
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware

import urllib3
import time
import json
from datetime import date, datetime
from dotenv import load_dotenv
import os
import pytz

import geopandas as gpd
from geopandas import GeoDataFrame
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.neighbors import KernelDensity

from arcgis.features import FeatureLayer, FeatureSet

from openai import OpenAI

app = FastAPI()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later if you want
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
#client = OpenAI()
client = OpenAI(api_key = os.getenv("OPENAI_API_KEY"))

# --- CONFIG: set these to your layers ---
SALESFORCE_311_URL = os.getenv(
    "SF311_URL",
    "https://services5.arcgis.com/54falWtcpty3V47Z/arcgis/rest/services/SalesForce311_View/FeatureServer/0",
)
SCHOOLS_URL = os.getenv(
    "SCHOOLS_URL",
    "https://services5.arcgis.com/54falWtcpty3V47Z/arcgis/rest/services/Schools/FeatureServer/0",
)

DEFAULT_BUFFER_FT = float(os.getenv("DEFAULT_BUFFER_FT", "500"))
_cached_school_buffers = {}

# CRS your services are actually in (you said 2226 for both now)
WKID_NATIVE = int(os.getenv("NATIVE_WKID", "2226"))


def _to_timestamp_where(start_datetime: str | None, end_datetime: str | None) -> str:
    # ArcGIS REST SQL often wants TIMESTAMP
    if start_datetime and end_datetime:
        return (
            f"(DateCreated >= TIMESTAMP '{start_datetime}' "
            f"AND DateCreated <= TIMESTAMP '{end_datetime}')"
        )
    return "1=1"

def _safe_lower(s: str) -> str:
    return (s or "").strip().lower()

def get_school_buffers(buffer_distance_ft: float, school_type):
    global _cached_school_buffers

    cache_key = float(buffer_distance_ft)
    if cache_key in _cached_school_buffers:
        return _cached_school_buffers[cache_key]

    schools_layer = FeatureLayer(SCHOOLS_URL)

    t2 = time.time()
    if school_type == None:
        schools_features = schools_layer.query(
            where=f"GRADE_LEVEL not like 'College%' and GRADE_LEVEL not like 'Ad%' and SCHOOL_GROUND_ID is not null and SCHOOL_GROUND_ID <> 0",
            out_fields="SCHOOL_GROUND_ID,SCHOOL_NAME,GRADE_LEVEL, SCHOOL_TYPE",
            return_geometry=True,
        )
    else:
        schools_features = schools_layer.query(
            where=f"GRADE_LEVEL not like 'College%' and GRADE_LEVEL not like 'Ad%' and SCHOOL_GROUND_ID is not null and SCHOOL_GROUND_ID <> 0 and SCHOOL_TYPE = '{school_type}'",
            out_fields="SCHOOL_GROUND_ID,SCHOOL_NAME,GRADE_LEVEL, SCHOOL_TYPE",
            return_geometry=True,
        )
    print(f"Schools query took {time.time() - t2:.2f}s, returned {len(schools_features.features)} features")

    schools_sdf = schools_features.sdf
    print("schools_sdf columns:", list(schools_sdf.columns))

    geom_candidates = ["SHAPE", "shape", "geometry", "Geometry"]
    geom_col = next((c for c in geom_candidates if c in schools_sdf.columns), None)
    if geom_col is None:
        raise ValueError(f"No geometry column found in schools_sdf. Columns were: {list(schools_sdf.columns)}")

    schools_sdf = schools_sdf[schools_sdf[geom_col].notnull()].copy()

    school_gdf = gpd.GeoDataFrame(schools_sdf, geometry=geom_col)
    school_gdf = school_gdf.set_crs(epsg='2226', allow_override=True)

    print("Selected school geometry column:", geom_col)
    print("school_gdf geometry name:", school_gdf.geometry.name)

    school_buffers = school_gdf.buffer(buffer_distance_ft)

    buffer_gdf = gpd.GeoDataFrame(
        {
            "school_ground_id": school_gdf.get("SCHOOL_GROUND_ID", None),
            "school_name": school_gdf.get("SCHOOL_NAME", None),
        },
        geometry=school_buffers,
        crs=school_gdf.crs,
    )

    _cached_school_buffers[cache_key] = buffer_gdf
    return buffer_gdf

@app.post("/api/interpret-execute")
async def interpret_execute(user_input: str = Form(...)):
    """
    Returns features with geometry + attributes including referencenumber, categoryname, etc.
    All analysis types pull from the 311 REST endpoint first.
    """
    local_now = datetime.now(pytz.timezone("America/Los_Angeles"))
    today_str = local_now.strftime("%Y-%m-%d")
    current_local_dt_str = local_now.strftime("%Y-%m-%d %H:%M:%S")

    # --- Ask OpenAI what to run + any params ---
    prompt = f"""
    Current local datetime is {current_local_dt_str} in the user's local timezone (America/Los_Angeles).
    Analyze this user request: {user_input}

    Return ONLY valid JSON with:
    - "analysis_type": one of "clustering", "proximity", or "hotspot"
    - "buffer_distance": number (feet) or null
    - "start_datetime": "YYYY-MM-DD HH:MM:SS AM/PM" or null
    - "end_datetime": "YYYY-MM-DD HH:MM:SS AM/PM" or null
    - "school_type": one of "Private", "Public", or "Charter" or null

    Interpret relative time phrases like:
    - "today"
    - "yesterday"
    - "last 24 hours"
    - "last 36 hours"
    - "last week"

    relative to this local datetime: {current_local_dt_str}.

    Example:
    {{"analysis_type":"proximity","buffer_distance":500,"start_datetime":"2026-03-05 08:15:00","end_datetime":"2026-03-06 20:15:00","school_type":"Public"}}
    """
    _cached_school_buffers = {}
    t0 = time.time()
    print("=== interpret_execute start ===")
    print("user_input:", user_input)

    analysis_type = "proximity"
    school_type = None
    buffer_distance_ft = DEFAULT_BUFFER_FT
    start_datetime = None
    end_datetime = None

    try:
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5"),
            messages=[{"role": "user", "content": prompt}],
        )
        msg = resp.choices[0].message.content or "{}"
        content = json.loads(msg)
        print("OpenAI response content:", content)
        print(f"OpenAI step took {time.time() - t0:.2f}s")

        if isinstance(content, dict):
            analysis_type = _safe_lower(content.get("analysis_type")) or analysis_type
            start_datetime = content.get("start_datetime")
            end_datetime = content.get("end_datetime")
            bd = content.get("buffer_distance")
            school_type = content.get("school_type")
            if isinstance(bd, (int, float)) and bd > 0:
                buffer_distance_ft = float(bd)
    except Exception as e:
        print("OpenAI parse error; using defaults:", e)
        print("analysis_type:", analysis_type)
        print("buffer_distance_ft:", buffer_distance_ft)
        print("start_date:", start_datetime)
        print("end_date:", end_datetime)

    if analysis_type not in ("clustering", "hotspot", "proximity"):
        analysis_type = "proximity"

    # --- 1) Query 311 from REST ---
    salesforce_layer = FeatureLayer(SALESFORCE_311_URL)

    where_311 = _to_timestamp_where(start_datetime, end_datetime)
    t1 = time.time()
    features_311 = salesforce_layer.query(
        where=where_311,
        out_fields="ReferenceNumber,CategoryName,DateCreated,DateUpdated,DateClosed,PublicStatus,StatusType",
        return_geometry=True,
    )
    print(f"311 query took {time.time() - t1:.2f}s, returned {len(features_311.features)} features")
    # keep only valid geometries
    valid_features = [f for f in features_311.features if isinstance(getattr(f, "geometry", None), dict)]
    valid_fset = FeatureSet(valid_features)

    sdf = valid_fset.sdf  # often a Spatially Enabled DataFrame
    print("311 sdf columns:", list(sdf.columns))
    geom_candidates = ["SHAPE", "shape", "geometry", "Geometry"]
    geom_col_311 = next((c for c in geom_candidates if c in sdf.columns), None)
    if geom_col_311 is None:
        raise ValueError(f"No geometry column found in 311 sdf. Columns were: {list(sdf.columns)}")

    sdf = sdf[sdf[geom_col_311].notnull()].copy()
    gdf = GeoDataFrame(sdf, geometry=geom_col_311)

    # IMPORTANT: your geometry coords look like 2226/3857 numbers — set to your native WKID.
    # Use allow_override since incoming CRS may be None.
    gdf = gdf.set_crs(epsg=3857, allow_override=True)
    gdf = gdf.to_crs(epsg=WKID_NATIVE)

    # normalize some common fields to lowercase access later
    # (keeps original columns; we’ll use row.get with lowercase keys too)
    gdf.columns = [c.lower() for c in gdf.columns]
    gdf = gdf.set_geometry("shape")

    # --- 2) Run analysis ---
    result_gdf = gdf  # default fall-through

    if analysis_type == "clustering":
        coords = np.array([[geom.x, geom.y] for geom in gdf.geometry])
        db = DBSCAN(eps=100, min_samples=3).fit(coords)
        result_gdf = gdf.copy()
        result_gdf["cluster"] = db.labels_

    elif analysis_type == "hotspot":
        coords = np.array([[geom.x, geom.y] for geom in gdf.geometry])
        kde = KernelDensity(bandwidth=300).fit(coords)
        scores = kde.score_samples(coords)
        result_gdf = gdf.copy()
        result_gdf["hotspot_score"] = scores
        # label by percentile
        thresh = np.percentile(scores, 75)
        result_gdf["hotspot_label"] = np.where(result_gdf["hotspot_score"] > thresh, "Hotspot", "Coldspot")

    elif analysis_type == "proximity":
        buffer_gdf = get_school_buffers(buffer_distance_ft,school_type)

        # Ensure 311 gdf has CRS + matches school buffers CRS
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=WKID_NATIVE, allow_override=True)
        if buffer_gdf.crs != gdf.crs:
            buffer_gdf = buffer_gdf.to_crs(gdf.crs)

        t3 = time.time()
        joined = gpd.sjoin(gdf, buffer_gdf, how="inner", predicate="within")
        print(f"Spatial join took {time.time() - t3:.2f}s, rows={len(joined)}")
        print(f"Total request took {time.time() - t0:.2f}s")

        # Remove duplicates by referencenumber (your business key)
        if "referencenumber" in joined.columns:
            before = len(joined)
            joined = joined.drop_duplicates(subset=["referencenumber"])
            after = len(joined)
            print(f"Proximity join count: {before} -> deduped: {after}")
        else:
            print(f"Proximity join count: {len(joined)} (no referencenumber column to dedupe)")

        result_gdf = joined

    # --- 3) Emit response ---
    # Always return UNIQUE business IDs in output attributes so the widget filters correctly.
    out = []
    geom_col = result_gdf.geometry.name
    for i, row in result_gdf.iterrows():
        geom = row[geom_col]
        if geom is None or geom.is_empty:
            continue
        attrs = dict(row)

        # normalize / ensure referencenumber string
        ref = attrs.get("referencenumber")
        if ref is not None:
            ref = str(ref)

        label = "Result"
        if analysis_type == "clustering":
            label = f"Cluster {attrs.get('cluster', '')}"
        elif analysis_type == "hotspot":
            label = str(attrs.get("hotspot_label", "Hotspot/Coldspot"))
        elif analysis_type == "proximity":
            label = f"Within {buffer_distance_ft} ft of School"

        out.append(
            {
                "geometry": {
                    "x": float(geom.x),
                    "y": float(geom.y),
                    "spatialReference": {"wkid": WKID_NATIVE},
                },
                "attributes": {
                    "id": int(i) if str(i).isdigit() else str(i),
                    "label": label,
                    # "start_date": start_datetime,
                    # "end_date": end_datetime,
                    # "buffer_distance": buffer_distance_ft,
                    # 311 fields
                    "referencenumber": ref,
                    "categoryname": attrs.get("categoryname"),
                    "datecreated": attrs.get("datecreated"),
                    "dateupdated": attrs.get("dateupdated"),
                    "dateclosed": attrs.get("dateclosed"),
                    "publicstatus": attrs.get("publicstatus") or attrs.get("statustype"),
                    # proximity fields (may be null for non-proximity)
                    "school_ground_id": attrs.get("school_ground_id"),
                    "school_name": attrs.get("school_name"),
                },
            }
        )

    print(f"API returning features: {len(out)}")
    return {
        "geometryType": "esriGeometryPoint",
        "fields": [
            {"name": "id", "type": "esriFieldTypeOID", "alias": "ID"},
            {"name": "label", "type": "esriFieldTypeString", "alias": "Label"},
            {"name": "referencenumber", "type": "esriFieldTypeString", "alias": "ReferenceNumber"},
        ],
        "objectIdField": "id",
        "features": out,
        "analysis": {
            "analysis_type": analysis_type,
            "start_date": start_datetime,
            "end_date": end_datetime,
            "buffer_distance": buffer_distance_ft
        }
    }

if __name__ == "__main__":
    # bind to localhost only for safety
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)