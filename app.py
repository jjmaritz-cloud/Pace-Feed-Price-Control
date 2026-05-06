import re
import json

import io
from datetime import datetime, date, timedelta
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from st_aggrid import AgGrid, GridOptionsBuilder, JsCode
    from st_aggrid.shared import GridUpdateMode
    HAS_AGGRID = True
except Exception:
    HAS_AGGRID = False
    AgGrid = None
    GridOptionsBuilder = None
    JsCode = None
    GridUpdateMode = None

from pathlib import Path

# ============================================================
# Pace Feed Price Control
# Standalone prototype
# Purpose:
#   Monitor on-farm feed price, feedmill delivery price,
#   recon quality, and farms needing support before pricing review.
# ============================================================

APP_TITLE = "Pace Feed Price Control"

LOCAL_UPLOAD_DIR = Path(r"C:\Pace Feed Price Control\Files to Upload")
LOCAL_TECH_ADVISOR_FILE = LOCAL_UPLOAD_DIR / "Tech Advisor Name List.csv"

# Farms to exclude from Pace feed-price dashboard reporting.
# These are excluded from calculations, support queue, service manager summaries,
# and farm mismatch checks.
EXCLUDED_FARM_NUMBERS = {"2806", "3850", "3851", "3852"}
EXCLUDED_FARM_NAMES = {
    "GW & SL Brown",
    "Bridgewater Estate Eggs Pty Ltd",
    "Egg Farm Business Pty Ltd t/a Beauchamp",
    "Kinross Farm Pty Ltd",
}

PROGRESS_STATUS_COLOURS = {
    "Support Opportunity": "#DC2626",   # red
    "Review Suggested": "#F59E0B",      # orange
    "Improving": "#84CC16",             # lime green
    "Holding Steady": "#16A34A",        # green
    "No issues": "#16A34A",             # green
    "Ready to Finalise": "#16A34A",     # green
    "Not Enough Data": "#94A3B8",       # neutral grey
}

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ------------------------------------------------------------
# Styling
# ------------------------------------------------------------
st.markdown(
    """
    <style>
    .main .block-container {
        max-width: 1680px;
        padding-top: 1rem;
        padding-bottom: 2rem;
    }

    .pf-hero {
        background: linear-gradient(135deg, #254B63 0%, #3F7086 58%, #E8A24A 100%);
        border-radius: 22px;
        padding: 1.35rem 1.55rem;
        color: white;
        margin-bottom: 1rem;
        box-shadow: 0 14px 34px rgba(15, 23, 42, 0.16);
    }

    .pf-hero h1 {
        margin: 0;
        color: white !important;
        font-size: 2.05rem;
        letter-spacing: -0.03em;
    }

    .pf-hero p {
        color: rgba(255,255,255,0.92) !important;
        margin: 0.45rem 0 0 0;
        font-size: 0.98rem;
    }

    .pf-card {
        background: #ffffff;
        border: 1px solid #E2E8F0;
        border-radius: 18px;
        padding: 1rem 1.05rem;
        box-shadow: 0 7px 22px rgba(15, 23, 42, 0.06);
        min-height: 118px;
    }

    .pf-card-label {
        font-size: 0.78rem;
        font-weight: 800;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        margin-bottom: 0.38rem;
    }

    .pf-card-value {
        font-size: 1.55rem;
        font-weight: 850;
        color: #0F172A;
        line-height: 1.05;
        margin-bottom: 0.35rem;
    }

    .pf-card-sub {
        font-size: 0.82rem;
        color: #64748B;
        line-height: 1.3;
    }

    .pf-section-title {
        font-size: 1.18rem;
        font-weight: 850;
        color: #0F172A;
        margin: 0.7rem 0 0.45rem 0;
        letter-spacing: -0.02em;
    }

    .pf-note {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 15px;
        padding: 0.9rem 1rem;
        color: #334155;
        font-size: 0.92rem;
        line-height: 1.45;
    }

    .support-good {
        background: #ECFDF3;
        color: #15803D;
        border: 1px solid #BBF7D0;
        border-radius: 999px;
        padding: 0.25rem 0.55rem;
        font-weight: 800;
        font-size: 0.78rem;
    }

    .support-review {
        background: #EFF6FF;
        color: #1D4ED8;
        border: 1px solid #BFDBFE;
        border-radius: 999px;
        padding: 0.25rem 0.55rem;
        font-weight: 800;
        font-size: 0.78rem;
    }

    .support-needed {
        background: #FFFBEB;
        color: #B45309;
        border: 1px solid #FDE68A;
        border-radius: 999px;
        padding: 0.25rem 0.55rem;
        font-weight: 800;
        font-size: 0.78rem;
    }

    .support-not-ready {
        background: #FEF2F2;
        color: #B91C1C;
        border: 1px solid #FECACA;
        border-radius: 999px;
        padding: 0.25rem 0.55rem;
        font-weight: 800;
        font-size: 0.78rem;
    }

    div[data-testid="stMetricValue"] {
        font-weight: 850;
    }

    .stDataFrame {
        border-radius: 16px;
        overflow: hidden;
    }
    
    /* More pronounced top menu tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.45rem;
        border-bottom: 2px solid #CBD5E1;
        padding-bottom: 0.15rem;
        margin-bottom: 0.85rem;
    }

    .stTabs [data-baseweb="tab"] {
        height: auto;
        white-space: nowrap;
        background: #F8FAFC;
        border: 1px solid #CBD5E1;
        border-bottom: none;
        border-radius: 12px 12px 0 0;
        padding: 0.72rem 1.05rem 0.8rem 1.05rem;
        color: #334155;
        font-weight: 800;
        font-size: 0.98rem;
        box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: #E2E8F0;
        color: #0F172A;
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #254B63 0%, #3F7086 100%) !important;
        color: #FFFFFF !important;
        border-color: #254B63 !important;
        box-shadow: 0 8px 18px rgba(37, 75, 99, 0.22);
    }

    .stTabs [aria-selected="true"] p,
    .stTabs [aria-selected="true"] span {
        color: #FFFFFF !important;
        font-weight: 900 !important;
    }

    
    /* Refined top menu tabs: clearer, but not bulky */
    .stTabs {
        margin-top: 0.85rem;
    }

    .stTabs [data-baseweb="tab-list"] {
        gap: 0.3rem;
        border-bottom: 1px solid #CBD5E1;
        padding-bottom: 0;
        margin-top: 0.45rem;
        margin-bottom: 0.7rem;
    }

    .stTabs [data-baseweb="tab"] {
        height: auto;
        white-space: nowrap;
        background: #F8FAFC;
        border: 1px solid #D7E0EA;
        border-bottom: none;
        border-radius: 9px 9px 0 0;
        padding: 0.45rem 0.78rem 0.48rem 0.78rem;
        color: #334155;
        font-weight: 700;
        font-size: 0.86rem;
        box-shadow: none;
    }

    .stTabs [data-baseweb="tab"]:hover {
        background: #EEF3F8;
        color: #0F172A;
    }

    .stTabs [aria-selected="true"] {
        background: #254B63 !important;
        color: #FFFFFF !important;
        border-color: #254B63 !important;
        box-shadow: none;
    }

    .stTabs [aria-selected="true"] p,
    .stTabs [aria-selected="true"] span {
        color: #FFFFFF !important;
        font-weight: 800 !important;
    }

    
    .pf-menu-spacer {
        height: 0.35rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------



# ------------------------------------------------------------
# Persistent Upload Store
# ------------------------------------------------------------
APP_BASE_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
UPLOAD_STORE_DIR = APP_BASE_DIR / "saved_uploads"
UPLOAD_VERSION_DIR = UPLOAD_STORE_DIR / "versions"
UPLOAD_META_PATH = UPLOAD_STORE_DIR / "upload_manifest.json"

UPLOAD_STORE_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_VERSION_DIR.mkdir(parents=True, exist_ok=True)

UPLOAD_FILE_SLOTS = {
    "feedmill": {
        "label": "Amino feedmill report",
        "saved_stem": "amino_feedmill_report",
        "extensions": ["xlsx", "xls", "csv"],
    },
    "farm": {
        "label": "Amino farm report",
        "saved_stem": "amino_farm_report",
        "extensions": ["xlsx", "xls", "csv"],
    },
    "advisor": {
        "label": "Service Manager / Tech Advisor mapping",
        "saved_stem": "tech_advisor_mapping",
        "extensions": ["csv", "xlsx", "xls"],
    },
}



@st.cache_resource
def get_runtime_upload_store():
    """
    Process-level upload store.

    Streamlit file_uploader state clears on browser refresh. Disk writes can
    also be unreliable on hosted Streamlit environments. This store keeps the
    latest uploaded bytes alive for the running app process, so refresh/rerun
    can still reload the Service Manager mapping.
    """
    return {}


def save_uploaded_file_to_runtime_store(slot_key, uploaded_file):
    if uploaded_file is None:
        return None

    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    try:
        data = uploaded_file.getvalue()
    except Exception:
        data = uploaded_file.read()

    name = getattr(uploaded_file, "name", f"{slot_key}.xlsx")
    ext = Path(name).suffix.lower().replace(".", "") or ("csv" if slot_key == "advisor" else "xlsx")

    store = get_runtime_upload_store()
    store[slot_key] = {
        "name": name,
        "ext": ext,
        "bytes": data,
        "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "size_bytes": len(data),
    }
    return store[slot_key]


def get_runtime_upload_as_file(slot_key):
    store = get_runtime_upload_store()
    item = store.get(slot_key)
    if not item or not item.get("bytes"):
        return None

    bio = io.BytesIO(item["bytes"])
    bio.name = item.get("name", f"{slot_key}.xlsx")
    return bio



def load_upload_manifest():
    try:
        if UPLOAD_META_PATH.exists():
            return json.loads(UPLOAD_META_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_upload_manifest(manifest):
    try:
        UPLOAD_STORE_DIR.mkdir(parents=True, exist_ok=True)
        UPLOAD_META_PATH.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    except Exception as e:
        st.warning(f"Could not save upload manifest: {e}")


def _upload_ext(uploaded_file, fallback="xlsx"):
    name = getattr(uploaded_file, "name", "") or ""
    ext = Path(name).suffix.lower().replace(".", "")
    return ext or fallback


def save_uploaded_file_slot(slot_key, uploaded_file):
    if uploaded_file is None:
        return None

    # Always save to process memory first. This survives browser refresh while
    # the Streamlit app process remains alive.
    runtime_info = save_uploaded_file_to_runtime_store(slot_key, uploaded_file)

    slot = UPLOAD_FILE_SLOTS[slot_key]
    ext = _upload_ext(uploaded_file, "csv" if slot_key == "advisor" else "xlsx")

    stable_path = UPLOAD_STORE_DIR / f"{slot['saved_stem']}.{ext}"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version_path = UPLOAD_VERSION_DIR / f"{slot['saved_stem']}_{stamp}.{ext}"

    try:
        uploaded_file.seek(0)
    except Exception:
        pass

    try:
        data = uploaded_file.getvalue()
    except Exception:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass
        data = uploaded_file.read()

    try:
        stable_path.write_bytes(data)
        version_path.write_bytes(data)

        manifest = load_upload_manifest()
        manifest[slot_key] = {
            "label": slot["label"],
            "original_name": getattr(uploaded_file, "name", stable_path.name),
            "stable_path": str(stable_path),
            "version_path": str(version_path),
            "saved_name": stable_path.name,
            "version_name": version_path.name,
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "size_bytes": len(data),
        }
        save_upload_manifest(manifest)
        return manifest[slot_key]

    except Exception as e:
        # Hosted Streamlit environments may not persist writes. Keep running
        # from the runtime cache instead of losing the upload.
        st.caption(f"Upload kept in app memory; disk save was not available: {e}")
        return {
            "label": slot["label"],
            "original_name": getattr(uploaded_file, "name", runtime_info.get("name", slot_key) if runtime_info else slot_key),
            "stable_path": "",
            "version_path": "",
            "saved_name": runtime_info.get("name", "") if runtime_info else "",
            "version_name": "",
            "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "size_bytes": len(data),
        }


def get_saved_upload_path(slot_key):
    manifest = load_upload_manifest()
    info = manifest.get(slot_key, {})
    if info.get("stable_path") and Path(info["stable_path"]).exists():
        return Path(info["stable_path"])

    slot = UPLOAD_FILE_SLOTS.get(slot_key)
    if not slot:
        return None

    matches = sorted(UPLOAD_STORE_DIR.glob(f"{slot['saved_stem']}.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0] if matches else None


def list_upload_versions(slot_key):
    slot = UPLOAD_FILE_SLOTS.get(slot_key)
    if not slot:
        return []
    return sorted(
        UPLOAD_VERSION_DIR.glob(f"{slot['saved_stem']}_*.*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def read_saved_upload(slot_key):
    path = get_saved_upload_path(slot_key)
    if path:
        return read_excel_uploaded(path)

    runtime_file = get_runtime_upload_as_file(slot_key)
    if runtime_file is not None:
        return read_excel_uploaded(runtime_file)

    return pd.DataFrame()

def read_upload_or_saved(slot_key, uploaded_file=None):
    """
    Read the current Streamlit upload if present, saving it first for persistence.
    If no uploaded file is present, read the last saved file from disk.
    """
    if uploaded_file is not None:
        try:
            save_uploaded_file_slot(slot_key, uploaded_file)
        except Exception as e:
            st.warning(f"Could not save uploaded {slot_key} file: {e}")

        return read_excel_uploaded(uploaded_file)

    return read_saved_upload(slot_key)


def sidebar_upload_status_note():
    """
    Small sidebar status showing whether saved files exist.
    """
    manifest = load_upload_manifest()
    saved_count = 0
    for slot_key in ["feedmill", "farm", "advisor"]:
        if get_saved_upload_path(slot_key):
            saved_count += 1

    if saved_count:
        st.sidebar.success(f"{saved_count} saved upload file(s) available")
    else:
        st.sidebar.info("No saved upload files yet")


def render_upload_page():
    st.markdown('<div class="pf-section-title">Upload</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="pf-note">
        Upload the files used by the dashboard. Files are saved locally, so the dashboard can reload them after refresh or restart.
        Each upload also creates a timestamped version copy.
        </div>
        """,
        unsafe_allow_html=True,
    )

    manifest = load_upload_manifest()

    cols = st.columns(3)
    for i, slot_key in enumerate(["feedmill", "farm", "advisor"]):
        slot = UPLOAD_FILE_SLOTS[slot_key]
        with cols[i]:
            st.markdown(f"#### {slot['label']}")
            current = manifest.get(slot_key)

            if current:
                st.success(f"Current: {current.get('original_name', current.get('saved_name', 'Saved file'))}")
                st.caption(f"Saved: {current.get('uploaded_at', 'Unknown')} · {current.get('size_bytes', 0):,} bytes")
            else:
                st.warning("No saved file yet.")

            uploaded = st.file_uploader(
                f"Upload {slot['label']}",
                type=slot["extensions"],
                key=f"upload_page_{slot_key}",
            )

            if uploaded is not None:
                info = save_uploaded_file_slot(slot_key, uploaded)
                st.success(f"Saved current file: {info['original_name']}")
                st.caption(f"Version copy: {info['version_name']}")

    st.markdown("### Current saved files")
    status_rows = []
    for slot_key, slot in UPLOAD_FILE_SLOTS.items():
        path = get_saved_upload_path(slot_key)
        status_rows.append(
            {
                "File type": slot["label"],
                "Status": "Saved" if path else "Missing",
                "Current file": path.name if path else "",
                "Folder": str(path.parent) if path else "",
            }
        )
    st.dataframe(pd.DataFrame(status_rows), use_container_width=True, hide_index=True, height=160)

    st.markdown("### Version history")
    version_rows = []
    for slot_key, slot in UPLOAD_FILE_SLOTS.items():
        for p in list_upload_versions(slot_key):
            version_rows.append(
                {
                    "File type": slot["label"],
                    "Version": p.name,
                    "Saved at": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                    "Size KB": round(p.stat().st_size / 1024, 1),
                }
            )

    if version_rows:
        st.dataframe(pd.DataFrame(version_rows), use_container_width=True, hide_index=True, height=300)
    else:
        st.info("No version history yet.")


def read_excel_uploaded(uploaded_file):
    """
    Read an uploaded Excel file fresh from bytes every run.

    Important:
    Excel workbooks can contain pivots, summary sheets, and raw source sheets.
    The app needs the raw Amino data sheet, not necessarily the first visible
    worksheet. This reader scans all sheets and chooses the sheet that most
    closely matches Amino raw report columns.
    """
    if uploaded_file is None:
        return pd.DataFrame()

    import io

    if isinstance(uploaded_file, (str, Path)):
        path = Path(uploaded_file)
        if not path.exists():
            return pd.DataFrame()

        if path.suffix.lower() == ".csv":
            try:
                return pd.read_csv(path)
            except UnicodeDecodeError:
                return pd.read_csv(path, encoding="latin1")

        file_bytes = path.read_bytes()
    else:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

        file_bytes = uploaded_file.getvalue()

    if not file_bytes:
        return pd.DataFrame()

    excel_obj = pd.ExcelFile(io.BytesIO(file_bytes), engine="openpyxl")

    best_df = pd.DataFrame()
    best_sheet = None
    best_score = -1
    sheet_summaries = []

    expected_raw_cols = [
        "complex flock no",
        "farm name",
        "begin date",
        "end date",
        "week ending",
        "weekending",
        "feed delivered",
        "feed consumed",
        "feed inventory beg",
        "feed inventory end",
        "bird inv end",
        "transdate",
        "entity trans name",
        "feed mill no",
        "refno",
    ]

    def norm_col(x):
        return (
            str(x)
            .replace("\xa0", " ")
            .replace("_", " ")
            .replace("-", " ")
            .replace("(", " ")
            .replace(")", " ")
            .strip()
            .lower()
            .replace(" ", "")
        )

    expected_norm = [norm_col(c) for c in expected_raw_cols]

    for sheet_name in excel_obj.sheet_names:
        try:
            df = pd.read_excel(
                io.BytesIO(file_bytes),
                sheet_name=sheet_name,
                engine="openpyxl",
            )
        except Exception:
            continue

        if df is None or df.empty:
            sheet_summaries.append(f"{sheet_name}: empty")
            continue

        col_norms = [norm_col(c) for c in df.columns]
        matched = sum(1 for c in expected_norm if c in col_norms)

        # Prefer sheets with many rows and strong raw-column matches.
        row_score = min(len(df), 5000) / 5000
        score = matched * 10 + row_score

        sheet_summaries.append(
            f"{sheet_name}: rows={len(df):,}, matched raw columns={matched}"
        )

        if score > best_score:
            best_score = score
            best_df = df.copy()
            best_sheet = sheet_name

    if best_df is None or best_df.empty:
        return pd.DataFrame()

    best_df.attrs["source_sheet"] = best_sheet
    best_df.attrs["sheet_summaries"] = sheet_summaries

    return best_df



def to_datetime_safe(series):
    """
    Handles Amino dates safely.

    Amino Excel exports may already load as datetime64. Do NOT convert
    datetime64 values to numeric first, because pandas turns them into
    nanoseconds and they become invalid Excel serial dates.
    """
    if series is None:
        return pd.Series(dtype="datetime64[ns]")

    s = series.copy()

    # If pandas already recognised it as a date, keep it as a date.
    if pd.api.types.is_datetime64_any_dtype(s):
        return pd.to_datetime(s, errors="coerce")

    # Try normal date parsing first. This handles most Excel text dates.
    parsed = pd.to_datetime(s, errors="coerce", dayfirst=False)
    parsed_share = parsed.notna().mean() if len(s) else 0
    if parsed_share > 0.6:
        return parsed

    # Excel serial date fallback.
    numeric = pd.to_numeric(s, errors="coerce")
    numeric_share = numeric.notna().mean() if len(s) else 0

    # Only treat as Excel serial dates if values are in a sensible Excel-date range.
    if numeric_share > 0.6:
        median_value = numeric.dropna().median()
        if 20000 <= median_value <= 70000:
            return pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce")

    return parsed



def find_col_case_insensitive(df, candidates):
    """
    Finds a column using case-insensitive and whitespace-insensitive matching.

    Example:
    "Week Ending", "Week ending", " week ending ", "Week_Ending",
    and "WeekEnding" can all be matched from the same candidate list.
    """
    if df is None or df.empty:
        return None

    def normalise_name(x):
        return (
            str(x)
            .replace("\xa0", " ")
            .replace("_", " ")
            .replace("-", " ")
            .strip()
            .lower()
            .replace(" ", "")
        )

    lookup = {normalise_name(c): c for c in df.columns}

    for candidate in candidates:
        key = normalise_name(candidate)
        if key in lookup:
            return lookup[key]

    return None


def first_existing_col(df, possible_cols):
    if df is None or df.empty:
        return None
    clean = {str(c).strip().lower(): c for c in df.columns}
    for col in possible_cols:
        key = str(col).strip().lower()
        if key in clean:
            return clean[key]
    return None


def clean_match_text(value):
    """
    Cleans text used for matching farm names between Amino and support mapping files.
    Handles non-breaking spaces from exported CSV files.
    """
    if value is None:
        return ""
    return (
        str(value)
        .replace("\xa0", " ")
        .strip()
        .lower()
        .replace("  ", " ")
    )


def normalize_farm_no(value):
    """
    Normalises Amino farm numbers.

    Excel often loads farm numbers as 2710.0 instead of 2710.
    This function keeps farm numbers stable across the feedmill and farm reports.
    """
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    text = str(value).replace("\xa0", " ").strip()

    if text.lower() in ["nan", "none", ""]:
        return ""

    # Handle values like 2710.0
    try:
        numeric = float(text)
        if numeric.is_integer():
            return str(int(numeric))
    except Exception:
        pass

    if text.endswith(".0"):
        return text[:-2]

    return text


def apply_farm_exclusions(df):
    """
    Removes farms that should not be included in this dashboard.
    Also removes blank/nan farm numbers.
    """
    if df is None or df.empty:
        return df

    out = df.copy()

    if "Farm No" in out.columns:
        out["Farm No"] = out["Farm No"].apply(normalize_farm_no)
        out = out[
            out["Farm No"].fillna("").astype(str).str.strip().ne("")
            & ~out["Farm No"].fillna("").astype(str).isin(EXCLUDED_FARM_NUMBERS)
        ].copy()

    if "Farm Name" in out.columns:
        clean_excluded_names = {clean_match_text(x) for x in EXCLUDED_FARM_NAMES}
        out = out[
            ~out["Farm Name"].fillna("").astype(str).apply(clean_match_text).isin(clean_excluded_names)
        ].copy()

    return out


def num(df, col, default=0.0):
    if col is None or col not in df.columns:
        return pd.Series(default, index=df.index, dtype="float64")
    return pd.to_numeric(df[col], errors="coerce").fillna(default)





def parse_amino_date(values):
    """
    Strict Amino date parser for Australian dd/mm/yy or dd/mm/yyyy dates.

    This avoids Pandas guessing 03/05/26 as 5 March when Amino means
    3 May. It manually parses slash dates first, then falls back to
    Excel serial dates and existing datetime values.
    """
    if values is None:
        return pd.Series(dtype="datetime64[ns]")

    s = values.copy() if isinstance(values, pd.Series) else pd.Series(values)

    def parse_one(v):
        if pd.isna(v):
            return pd.NaT

        # Already a pandas/python datetime.
        if isinstance(v, (pd.Timestamp, datetime, date)):
            return pd.to_datetime(v, errors="coerce")

        # Excel serial date.
        if isinstance(v, (int, float, np.integer, np.floating)):
            try:
                if 20000 <= float(v) <= 70000:
                    return pd.to_datetime(float(v), unit="D", origin="1899-12-30", errors="coerce")
            except Exception:
                pass

        text = str(v).replace("\\xa0", " ").strip()

        if text == "" or text.lower() in ["nan", "none", "nat"]:
            return pd.NaT

        # Strip any time section from a text date.
        text = text.split(" ")[0]

        # Strict dd/mm/yy or dd/mm/yyyy parser.
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})$", text)
        if m:
            d = int(m.group(1))
            mth = int(m.group(2))
            yr = int(m.group(3))

            if yr < 100:
                yr += 2000 if yr <= 79 else 1900

            try:
                return pd.Timestamp(year=yr, month=mth, day=d)
            except Exception:
                return pd.NaT

        # Strict yyyy-mm-dd parser.
        m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", text)
        if m:
            try:
                return pd.Timestamp(year=int(m.group(1)), month=int(m.group(2)), day=int(m.group(3)))
            except Exception:
                return pd.NaT

        # Final fallback only after strict parsing fails.
        return pd.to_datetime(text, errors="coerce", dayfirst=True)

    parsed = s.apply(parse_one)
    return pd.to_datetime(parsed, errors="coerce")



def week_ending_from_date(dt_series, week_ending_day="Monday"):
    """
    Week ending day defaults to Monday because the recon cutoff is Monday 12pm.
    Monday = 0, Sunday = 6.
    """
    day_lookup = {
        "Monday": 0,
        "Tuesday": 1,
        "Wednesday": 2,
        "Thursday": 3,
        "Friday": 4,
        "Saturday": 5,
        "Sunday": 6,
    }
    target = day_lookup.get(week_ending_day, 0)
    dates = pd.to_datetime(dt_series, errors="coerce")
    days_to_add = (target - dates.dt.weekday) % 7
    return (dates + pd.to_timedelta(days_to_add, unit="D")).dt.normalize()


def fmt_currency(v, decimals=0):
    try:
        if pd.isna(v):
            return "—"
        return f"${float(v):,.{decimals}f}"
    except Exception:
        return "—"


def fmt_num(v, decimals=1):
    try:
        if pd.isna(v):
            return "—"
        return f"{float(v):,.{decimals}f}"
    except Exception:
        return "—"


def status_from_confidence(score):
    if score >= 90:
        return "Ready to Finalise"
    if score >= 70:
        return "Review Suggested"
    if score >= 40:
        return "Support Needed"
    return "Price Not Ready"


def status_badge(status):
    cls = {
        "Ready to Finalise": "support-good",
        "Review Suggested": "support-review",
        "Support Needed": "support-needed",
        "Price Not Ready": "support-not-ready",
    }.get(status, "support-review")
    return f'<span class="{cls}">{status}</span>'


def kpi_card(label, value, sub=""):
    st.markdown(
        f"""
        <div class="pf-card">
            <div class="pf-card-label">{label}</div>
            <div class="pf-card-value">{value}</div>
            <div class="pf-card-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )



def progress_svg_icon(status, size=18):
    """
    Small inline SVG icon for progression/support status.
    """
    status = str(status or "").strip()
    colour = PROGRESS_STATUS_COLOURS.get(status, "#64748B")

    if status == "Support Opportunity":
        return f"""
        <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none">
            <path d="M12 4L21 20H3L12 4Z" stroke="{colour}" stroke-width="2" stroke-linejoin="round"/>
            <path d="M12 9V14" stroke="{colour}" stroke-width="2" stroke-linecap="round"/>
            <circle cx="12" cy="17" r="1.2" fill="{colour}"/>
        </svg>
        """

    if status == "Review Suggested":
        return f"""
        <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none">
            <circle cx="11" cy="11" r="6" stroke="{colour}" stroke-width="2"/>
            <path d="M16 16L20 20" stroke="{colour}" stroke-width="2" stroke-linecap="round"/>
            <path d="M8.5 11H13.5" stroke="{colour}" stroke-width="2" stroke-linecap="round"/>
        </svg>
        """

    if status == "Improving":
        return f"""
        <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none">
            <path d="M4 16.5L9 11.5L13 14.5L20 7.5" stroke="{colour}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M15.5 7.5H20V12" stroke="{colour}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """

    if status in ["Holding Steady", "No issues", "Ready to Finalise"]:
        return f"""
        <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="8" stroke="{colour}" stroke-width="2"/>
            <path d="M8.2 12.2L10.7 14.7L16.2 9.3" stroke="{colour}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        """

    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="12" r="8" stroke="{colour}" stroke-width="2"/>
        <path d="M8 12H16" stroke="{colour}" stroke-width="2" stroke-linecap="round"/>
    </svg>
    """


def progress_status_badge(status):
    """
    HTML badge with SVG icon using progression colours.
    """
    status = str(status or "Not Enough Data").strip()
    colour = PROGRESS_STATUS_COLOURS.get(status, "#64748B")

    bg_map = {
        "Support Opportunity": "#FEF2F2",
        "Review Suggested": "#FFFBEB",
        "Improving": "#F7FEE7",
        "Holding Steady": "#ECFDF3",
        "No issues": "#ECFDF3",
        "Ready to Finalise": "#ECFDF3",
        "Not Enough Data": "#F1F5F9",
    }

    border_map = {
        "Support Opportunity": "#FECACA",
        "Review Suggested": "#FDE68A",
        "Improving": "#D9F99D",
        "Holding Steady": "#BBF7D0",
        "No issues": "#BBF7D0",
        "Ready to Finalise": "#BBF7D0",
        "Not Enough Data": "#CBD5E1",
    }

    bg = bg_map.get(status, "#F1F5F9")
    border = border_map.get(status, "#CBD5E1")
    icon = progress_svg_icon(status, size=16)

    return f"""
    <span class="pf-status-badge" style="background:{bg}; border-color:{border}; color:{colour};">
        {icon}
        <span>{status}</span>
    </span>
    """


def inject_progress_table_styles():
    st.markdown(
        """
        <style>
        .pf-progress-table-wrap {
            border: 1px solid #E2E8F0;
            border-radius: 18px;
            overflow: hidden;
            background: #FFFFFF;
            box-shadow: 0 7px 22px rgba(15, 23, 42, 0.06);
            margin-top: 0.6rem;
            margin-bottom: 1rem;
        }

        .pf-progress-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 0.86rem;
            color: #0F172A;
        }

        .pf-progress-table thead th {
            background: #F8FAFC;
            border-bottom: 1px solid #DBE3EF;
            border-right: 1px solid #E8EEF7;
            padding: 0.72rem 0.65rem;
            text-align: left;
            font-weight: 850;
            color: #334155;
            white-space: nowrap;
        }

        .pf-progress-table tbody td {
            border-bottom: 1px solid #EDF2F7;
            border-right: 1px solid #F1F5F9;
            padding: 0.66rem 0.65rem;
            vertical-align: middle;
            white-space: nowrap;
        }

        .pf-progress-table tbody tr:last-child td {
            border-bottom: none;
        }

        .pf-progress-table tbody tr:hover {
            background: #F8FBFF;
        }

        .pf-progress-table .num {
            text-align: right;
            font-variant-numeric: tabular-nums;
        }

        .pf-status-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border: 1px solid;
            border-radius: 999px;
            padding: 0.28rem 0.58rem;
            font-size: 0.78rem;
            font-weight: 850;
            line-height: 1;
            white-space: nowrap;
        }

        .pf-status-badge svg {
            display: block;
            flex: 0 0 auto;
        }

        .pf-row-support-opportunity td:first-child { box-shadow: inset 5px 0 0 #DC2626; }
        .pf-row-review-suggested td:first-child { box-shadow: inset 5px 0 0 #F59E0B; }
        .pf-row-improving td:first-child { box-shadow: inset 5px 0 0 #84CC16; }
        .pf-row-holding-steady td:first-child,
        .pf-row-no-issues td:first-child,
        .pf-row-ready-to-finalise td:first-child { box-shadow: inset 5px 0 0 #16A34A; }
        .pf-row-not-enough-data td:first-child { box-shadow: inset 5px 0 0 #94A3B8; }

        .pf-delta-pill {
            display: inline-flex;
            align-items: center;
            justify-content: flex-end;
            min-width: 82px;
            border-radius: 999px;
            padding: 0.25rem 0.50rem;
            font-weight: 850;
            font-size: 0.78rem;
            border: 1px solid;
        }

        .pf-delta-good {
            color: #16A34A;
            background: #ECFDF3;
            border-color: #BBF7D0;
        }

        .pf-delta-lime {
            color: #65A30D;
            background: #F7FEE7;
            border-color: #D9F99D;
        }

        .pf-delta-watch {
            color: #D97706;
            background: #FFFBEB;
            border-color: #FDE68A;
        }

        .pf-delta-bad {
            color: #DC2626;
            background: #FEF2F2;
            border-color: #FECACA;
        }

        .pf-delta-neutral {
            color: #475569;
            background: #F1F5F9;
            border-color: #CBD5E1;
        }

        @media (max-width: 1200px) {
            .pf-progress-table-wrap { overflow-x: auto; }
            .pf-progress-table { min-width: 1280px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_to_row_class(status):
    return "pf-row-" + str(status or "not-enough-data").strip().lower().replace(" ", "-").replace("/", "-")


def format_currency_cell(value):
    try:
        if pd.isna(value):
            return "—"
        return f"${float(value):,.2f}"
    except Exception:
        return "—"


def format_delta_pill(value, lower_is_better=True):
    try:
        if pd.isna(value):
            return '<span class="pf-delta-pill pf-delta-neutral">—</span>'
        v = float(value)
    except Exception:
        return '<span class="pf-delta-pill pf-delta-neutral">—</span>'

    if abs(v) <= 0.01:
        return f'<span class="pf-delta-pill pf-delta-neutral">→ ${v:,.2f}</span>'

    good = v < 0 if lower_is_better else v > 0

    if good:
        cls = "pf-delta-lime" if abs(v) >= 10 else "pf-delta-good"
        arrow = "↓" if v < 0 else "↑"
    else:
        cls = "pf-delta-bad" if abs(v) >= 25 else "pf-delta-watch"
        arrow = "↑" if v > 0 else "↓"

    return f'<span class="pf-delta-pill {cls}">{arrow} ${v:,.2f}</span>'


def render_progress_html_table(df, week_cols=None, max_rows=80):
    """
    Custom HTML progression table with SVG icons and status-based row formatting.
    Used for farm/area progression views where visual scanning matters.
    """
    if df is None or df.empty:
        st.info("No progression data available.")
        return

    inject_progress_table_styles()

    show = df.copy().head(max_rows)

    if week_cols is None:
        week_cols = [
            c for c in show.columns
            if str(c).startswith("Week ") or str(c).startswith("Wk")
        ]

    cols = []
    for c in ["Farm No", "Farm Name", "Area Manager"]:
        if c in show.columns:
            cols.append(c)

    cols.extend([c for c in week_cols if c in show.columns])

    for c in [
        "Farm Movement $/t",
        "Business Movement $/t",
        "Business-Adjusted Movement $/t",
        "Progress Status",
        "Support Focus",
        "Recommended Support",
    ]:
        if c in show.columns and c not in cols:
            cols.append(c)

    header_html = "".join([f"<th>{c}</th>" for c in cols])
    rows = []

    for _, row in show.iterrows():
        status = row.get("Progress Status", "Not Enough Data")
        row_class = status_to_row_class(status)

        cells = []
        for c in cols:
            value = row.get(c, "")

            if c == "Progress Status":
                cells.append(f"<td>{progress_status_badge(value)}</td>")
            elif c in ["Farm Movement $/t", "Business Movement $/t", "Business-Adjusted Movement $/t"]:
                cells.append(f'<td class="num">{format_delta_pill(value, lower_is_better=True)}</td>')
            elif c in week_cols:
                cells.append(f'<td class="num">{format_currency_cell(value)}</td>')
            else:
                safe = "" if pd.isna(value) else str(value)
                cells.append(f"<td>{safe}</td>")

        rows.append(f'<tr class="{row_class}">' + "".join(cells) + "</tr>")

    table_html = f"""
    <div class="pf-progress-table-wrap">
        <table class="pf-progress-table">
            <thead><tr>{header_html}</tr></thead>
            <tbody>{''.join(rows)}</tbody>
        </table>
    </div>
    """

    st.markdown(table_html, unsafe_allow_html=True)



def interpret_farm(row):
    status = row.get("Pricing Status", "")
    price = row.get("Farm Feed Cost $/t", np.nan)
    delivered_price = row.get("Delivered Price $/t", np.nan)
    variance = row.get("Closing Stock Variance kg", 0)
    missing = row.get("Closing Stock To Complete", 0)

    if status == "Price Not Ready":
        if missing > 0:
            return "Closing bin stock still needs to be completed, so this farm's price is not ready to finalise."
        if abs(variance) > 3000:
            return "The stock variance is large. Support the farm with recon review before finalising pricing."
        return "Feed price result needs review before it is used for ranking."

    if status == "Support Needed":
        return "This farm has enough data to review, but recon or stock movement should be checked before final pricing."

    if pd.notna(price) and pd.notna(delivered_price) and price > delivered_price * 1.08:
        return "Recon is mostly usable, but farm cost is above delivered price. Review stock movement, ration mix, and timing."

    if status == "Ready to Finalise":
        return "Recon looks complete enough for review. Price can be included in normal farm comparisons."

    return "Review suggested. Check feed movement and stock figures before finalising."


# ------------------------------------------------------------
# Data prep
# ------------------------------------------------------------
def prepare_feedmill(feedmill_df, week_ending_day):
    if feedmill_df is None or feedmill_df.empty:
        return pd.DataFrame()

    df = feedmill_df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    date_col = first_existing_col(df, ["TransDate", "Trans Date", "Delivery Date"])
    farm_no_col = first_existing_col(df, ["Farm No", "FarmNo"])
    farm_name_col = first_existing_col(df, ["Entity Trans Name", "Farm Name", "Entity Name"])
    formula_col = first_existing_col(df, ["Formula Name", "External Formula Name", "Formula No"])
    net_col = first_existing_col(df, ["Net", "Net kg", "Net Weight"])
    cpu_col = first_existing_col(df, ["CPU_Total", "CPU Total", "Total CPU"])
    ing_col = first_existing_col(df, ["$ING"])
    del_col = first_existing_col(df, ["$DEL"])
    man_col = first_existing_col(df, ["$MAN"])
    post_col = first_existing_col(df, ["Post Status"])
    void_col = first_existing_col(df, ["Void"])

    df["Delivery Date"] = to_datetime_safe(df[date_col]) if date_col else pd.NaT
    df["Week Ending"] = week_ending_from_date(df["Delivery Date"], week_ending_day)
    df["Farm No"] = df[farm_no_col].apply(normalize_farm_no) if farm_no_col else ""
    df["Farm Name"] = df[farm_name_col].astype(str).str.strip() if farm_name_col else ""
    df["Formula"] = df[formula_col].astype(str).str.strip() if formula_col else ""
    df["Net kg"] = num(df, net_col)
    df["Tonnes Delivered"] = df["Net kg"] / 1000.0
    df["CPU Total"] = num(df, cpu_col)
    df["Ingredient Cost"] = num(df, ing_col)
    df["Delivery Cost"] = num(df, del_col)
    df["Manufacturing Cost"] = num(df, man_col)

    # CPU_Total appears to be per tonne in the Amino feedmill file.
    df["Delivered Cost"] = df["Tonnes Delivered"] * df["CPU Total"]

    if post_col:
        df["Post Status"] = df[post_col].astype(str)
    else:
        df["Post Status"] = ""

    if void_col:
        df["Void"] = df[void_col].astype(str)
    else:
        df["Void"] = "False"

    # Keep normal posted, non-void rows by default; user can still inspect source files outside app.
    df = df[~df["Void"].str.lower().isin(["true", "1", "yes"])].copy()

    df = apply_farm_exclusions(df)

    return df


def prepare_farm_recon(farm_df):
    if farm_df is None or farm_df.empty:
        return pd.DataFrame()

    df = farm_df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    farm_no_col = first_existing_col(df, ["Farm No", "FarmNo"])
    farm_name_col = first_existing_col(df, ["Farm Name", "FarmName"])
    flock_col = first_existing_col(df, ["Flock No", "Complex Flock No"])
    product_col = first_existing_col(df, ["Product No", "Product"])
    status_col = first_existing_col(df, ["Status"])
    begin_col = first_existing_col(df, ["Feed Inventory (Beg)"])
    delivered_col = first_existing_col(df, ["Feed Delivered"])
    transferred_col = first_existing_col(df, ["Feed Transferred"])
    consumed_col = first_existing_col(df, ["Feed Consumed"])
    feed_cost_col = first_existing_col(df, ["$FeedConsumed"])
    delivered_cost_col = first_existing_col(df, ["$FeedInventoryIn", "Delivered Cost", "Delivered_Cost", "Feed Delivered Cost"])
    ending_col = first_existing_col(df, ["Feed Inventory (End)"])
    ending_calc_col = first_existing_col(df, ["Feed Inventory (EndCalc)"])
    ending_var_col = first_existing_col(df, ["Feed Inventory (EndVar)"])
    begin_date_col = first_existing_col(df, ["Begin Date"])
    end_date_col = first_existing_col(df, ["End Date"])
    farm_week_ending_col = get_explicit_week_ending_col(df)

    df["Farm No"] = df[farm_no_col].apply(normalize_farm_no) if farm_no_col else ""
    df["Farm Name"] = df[farm_name_col].astype(str).str.strip() if farm_name_col else ""
    df["Flock"] = df[flock_col].astype(str).str.strip() if flock_col else ""
    df["Product"] = df[product_col].astype(str).str.strip() if product_col else ""
    df["Status"] = df[status_col].astype(str).str.strip() if status_col else ""

    # Preserve the raw exported Amino date text for recon filtering.
    # This is important because some tools may pre-parse 03/05/26 incorrectly.
    df["Amino Raw Begin Date"] = df[begin_date_col].astype(str).str.strip() if begin_date_col else ""
    df["Amino Raw End Date"] = df[end_date_col].astype(str).str.strip() if end_date_col else ""
    df["Amino Raw Week Ending"] = df[farm_week_ending_col].astype(str).str.strip() if ("farm_week_ending_col" in locals() and farm_week_ending_col) else ""

    df["Begin Date"] = parse_amino_date(df["Amino Raw Begin Date"]) if begin_date_col else pd.NaT
    df["End Date"] = parse_amino_date(df["Amino Raw End Date"]) if end_date_col else pd.NaT
    if "farm_week_ending_col" in locals() and farm_week_ending_col:
        df["Week Ending"] = parse_amino_date(df["Amino Raw Week Ending"]).dt.normalize()
    else:
        df["Week Ending"] = week_ending_from_date(df["End Date"], "Sunday")

    df["Beginning Stock kg"] = num(df, begin_col)
    df["Farm Delivered kg"] = num(df, delivered_col)
    df["Transferred kg"] = num(df, transferred_col)
    df["Consumed kg"] = num(df, consumed_col)
    df["Feed Consumed $"] = num(df, feed_cost_col)
    df["Feed Delivered $"] = num(df, delivered_cost_col)
    df["Closing Stock kg"] = num(df, ending_col)
    df["Calculated Closing Stock kg"] = num(df, ending_calc_col)
    df["Closing Stock Variance kg"] = num(df, ending_var_col)

    df["Farm Feed Cost $/t"] = np.where(
        df["Consumed kg"] > 0,
        df["Feed Consumed $"] / (df["Consumed kg"] / 1000.0),
        np.nan,
    )

    active_or_moving = (
        df["Status"].str.lower().eq("active")
        | (df["Beginning Stock kg"].abs() > 0)
        | (df["Farm Delivered kg"].abs() > 0)
        | (df["Consumed kg"].abs() > 0)
        | (df["Calculated Closing Stock kg"].abs() > 0)
    )

    df["Closing Stock To Complete"] = (
        active_or_moving
        & (df["Closing Stock kg"].fillna(0).abs() <= 0.0001)
        & (df["Calculated Closing Stock kg"].fillna(0) > 100)
    ).astype(int)

    df["Large Stock Variance"] = (df["Closing Stock Variance kg"].abs() > 1000).astype(int)
    df["Very Large Stock Variance"] = (df["Closing Stock Variance kg"].abs() > 3000).astype(int)

    df = apply_farm_exclusions(df)

    return df


def build_farm_summary(feedmill, farm, farm_master):
    # Feedmill summary
    if feedmill is not None and not feedmill.empty:
        mill_sum = (
            feedmill.groupby(["Farm No"], dropna=False)
            .agg(
                Farm_Name_Mill=("Farm Name", "first"),
                Delivered_Tonnes=("Tonnes Delivered", "sum"),
                Delivered_Cost=("Delivered Cost", "sum"),
                Avg_CPU=("CPU Total", "mean"),
                Delivery_Cost=("Delivery Cost", "sum"),
                Ingredient_Cost=("Ingredient Cost", "sum"),
                Manufacturing_Cost=("Manufacturing Cost", "sum"),
                Formula_Count=("Formula", "nunique"),
            )
            .reset_index()
        )
        mill_sum["Delivered Price $/t"] = np.where(
            mill_sum["Delivered_Tonnes"] > 0,
            mill_sum["Delivered_Cost"] / mill_sum["Delivered_Tonnes"],
            np.nan,
        )
    else:
        mill_sum = pd.DataFrame(columns=["Farm No", "Farm Name"])

    # Farm recon summary
    if farm is not None and not farm.empty:
        farm_sum = (
            farm.groupby(["Farm No"], dropna=False)
            .agg(
                Farm_Name_Recon=("Farm Name", "first"),
                Farm_Delivered_kg=("Farm Delivered kg", "sum"),
                Consumed_kg=("Consumed kg", "sum"),
                Feed_Consumed_Dollars=("Feed Consumed $", "sum"),
                Closing_Stock_kg=("Closing Stock kg", "sum"),
                Calculated_Closing_Stock_kg=("Calculated Closing Stock kg", "sum"),
                Closing_Stock_Variance_kg=("Closing Stock Variance kg", "sum"),
                Recon_Rows=("Farm No", "size"),
                Closing_Stock_To_Complete=("Closing Stock To Complete", "sum"),
                Large_Stock_Variance_Rows=("Large Stock Variance", "sum"),
                Very_Large_Stock_Variance_Rows=("Very Large Stock Variance", "sum"),
                Product_Count=("Product", "nunique"),
            )
            .reset_index()
        )
        farm_sum["Farm Feed Cost $/t"] = np.where(
            farm_sum["Consumed_kg"] > 0,
            farm_sum["Feed_Consumed_Dollars"] / (farm_sum["Consumed_kg"] / 1000.0),
            np.nan,
        )
    else:
        farm_sum = pd.DataFrame(columns=["Farm No", "Farm Name"])

    # Merge carefully
    summary = pd.merge(
        mill_sum,
        farm_sum,
        on=["Farm No"],
        how="outer",
    )

    # Prefer the feedmill farm name when available, otherwise use the recon name.
    summary["Farm Name"] = (
        summary.get("Farm_Name_Mill", pd.Series("", index=summary.index))
        .replace("", pd.NA)
        .fillna(summary.get("Farm_Name_Recon", pd.Series("", index=summary.index)))
        .fillna("")
        .astype(str)
        .str.replace("\xa0", " ", regex=False)
        .str.strip()
    )

    for col in [
        "Delivered_Tonnes", "Delivered_Cost", "Delivered Price $/t",
        "Farm_Delivered_kg", "Consumed_kg", "Feed_Consumed_Dollars",
        "Closing_Stock_Variance_kg", "Recon_Rows", "Closing_Stock_To_Complete",
        "Large_Stock_Variance_Rows", "Very_Large_Stock_Variance_Rows",
        "Farm Feed Cost $/t",
    ]:
        if col not in summary.columns:
            summary[col] = 0.0
        summary[col] = pd.to_numeric(summary[col], errors="coerce").fillna(0.0)

    summary["Delivered Tonnes"] = summary["Delivered_Tonnes"]
    summary["Consumed Tonnes"] = summary["Consumed_kg"] / 1000.0
    summary["Closing Stock Variance kg"] = summary["Closing_Stock_Variance_kg"]

    # Data confidence score: supportive, not punitive.
    score = pd.Series(100.0, index=summary.index)
    score -= summary["Closing_Stock_To_Complete"].clip(upper=4) * 18
    score -= summary["Large_Stock_Variance_Rows"].clip(upper=4) * 10
    score -= summary["Very_Large_Stock_Variance_Rows"].clip(upper=2) * 15
    score -= np.where(summary["Delivered Tonnes"].gt(0) & summary["Consumed Tonnes"].eq(0), 15, 0)
    score -= np.where(summary["Consumed Tonnes"].gt(0) & summary["Farm Feed Cost $/t"].eq(0), 15, 0)
    summary["Price Confidence Score"] = score.clip(lower=0, upper=100).round(0)
    summary["Pricing Status"] = summary["Price Confidence Score"].apply(status_from_confidence)

    if summary["Farm Feed Cost $/t"].replace(0, np.nan).notna().any():
        avg_farm_price = np.nanmean(summary["Farm Feed Cost $/t"].replace(0, np.nan))
    else:
        avg_farm_price = np.nan

    summary["Variance vs Farm Avg $/t"] = summary["Farm Feed Cost $/t"] - avg_farm_price

    # Add manager mapping if supplied
    if farm_master is not None and not farm_master.empty:
        fm = farm_master.copy()
        fm.columns = [str(c).strip() for c in fm.columns]

        # Prefer Farm No matching when available.
        if "Farm No" in fm.columns and fm["Farm No"].astype(str).str.strip().ne("").any():
            fm["Farm No"] = fm["Farm No"].apply(normalize_farm_no)
            summary["Farm No"] = summary["Farm No"].apply(normalize_farm_no)

            keep_cols = [c for c in ["Farm No", "Area Manager", "Region", "Farm Type"] if c in fm.columns]

            summary = summary.merge(
                fm[keep_cols].drop_duplicates("Farm No"),
                on="Farm No",
                how="left"
            )

        # Your Service Manager file does not include Farm No, so match by Farm Name.
        elif "Farm Name" in fm.columns:
            fm["Farm Name"] = fm["Farm Name"].astype(str).str.replace("\xa0", " ", regex=False).str.strip()
            summary["Farm Name"] = summary["Farm Name"].astype(str).str.replace("\xa0", " ", regex=False).str.strip()

            fm["_FarmNameKey"] = fm["Farm Name"].apply(clean_match_text)
            summary["_FarmNameKey"] = summary["Farm Name"].apply(clean_match_text)

            keep_cols = [c for c in ["_FarmNameKey", "Area Manager", "Region", "Farm Type"] if c in fm.columns]

            summary = summary.merge(
                fm[keep_cols].drop_duplicates("_FarmNameKey"),
                on="_FarmNameKey",
                how="left"
            )

            if "_FarmNameKey" in summary.columns:
                summary = summary.drop(columns=["_FarmNameKey"])

    for col, default in {
        "Area Manager": "Unassigned",
        "Region": "Unassigned",
        "Farm Type": "Unassigned",
    }.items():
        if col not in summary.columns:
            summary[col] = default
        summary[col] = summary[col].fillna(default).replace("", default)

    summary["Recommended Support"] = summary.apply(interpret_farm, axis=1)

    display_order = [
        "Farm No", "Farm Name", "Area Manager", "Region", "Farm Type",
        "Pricing Status", "Price Confidence Score",
        "Delivered Tonnes", "Delivered Price $/t",
        "Consumed Tonnes", "Farm Feed Cost $/t", "Variance vs Farm Avg $/t",
        "Closing Stock To Complete", "Closing Stock Variance kg",
        "Large_Stock_Variance_Rows", "Recommended Support",
    ]

    for col in display_order:
        if col not in summary.columns:
            summary[col] = np.nan

    return summary[display_order].sort_values(
        ["Price Confidence Score", "Variance vs Farm Avg $/t"],
        ascending=[True, False],
    )


def build_weekly_feedmill(feedmill):
    if feedmill is None or feedmill.empty:
        return pd.DataFrame()

    weekly = (
        feedmill.groupby("Week Ending", dropna=False)
        .agg(
            Tonnes=("Tonnes Delivered", "sum"),
            Delivered_Cost=("Delivered Cost", "sum"),
            Ingredient_Cost=("Ingredient Cost", "sum"),
            Delivery_Cost=("Delivery Cost", "sum"),
            Manufacturing_Cost=("Manufacturing Cost", "sum"),
            Farms=("Farm No", "nunique"),
        )
        .reset_index()
        .sort_values("Week Ending")
    )
    weekly["Delivered Price $/t"] = np.where(
        weekly["Tonnes"] > 0,
        weekly["Delivered_Cost"] / weekly["Tonnes"],
        np.nan,
    )
    return weekly


def read_farm_master(uploaded):
    """
    Reads optional farm / area-manager mapping.

    Supports standard mapping:
        Farm No, Farm Name, Service Manager, Region, Farm Type

    Also supports the Pace Service Manager file:
        TechAdvisorName, Farm_Name

    If no mapping file is uploaded in the sidebar, the app automatically
    looks for:
        C:\Pace Feed Price Control\Files to Upload\Tech Advisor Name List.csv
    """
    try:
        source = uploaded

        # Auto-load the Service Manager / Tech Advisor mapping when no manual
        # upload is supplied. Browser refresh clears st.file_uploader, so check
        # runtime cache first, then disk, then local Windows dev fallback.
        if source is None:
            runtime_advisor_file = get_runtime_upload_as_file("advisor")
            if runtime_advisor_file is not None:
                source = runtime_advisor_file
            else:
                saved_advisor_path = get_saved_upload_path("advisor")
                if saved_advisor_path is not None and Path(saved_advisor_path).exists():
                    source = saved_advisor_path
                elif LOCAL_TECH_ADVISOR_FILE.exists():
                    # Local Windows fallback for development only.
                    source = LOCAL_TECH_ADVISOR_FILE
                else:
                    return pd.DataFrame()

        # Work out file name and extension for both UploadedFile and Path.
        source_name = getattr(source, "name", str(source))
        source_name_lower = str(source_name).lower()

        if source_name_lower.endswith(".csv"):
            if hasattr(source, "seek"):
                source.seek(0)
                try:
                    df = pd.read_csv(source)
                except Exception:
                    source.seek(0)
                    try:
                        df = pd.read_csv(source, encoding="latin1")
                    except Exception:
                        source.seek(0)
                        df = pd.read_csv(source, encoding="cp1252")
            else:
                try:
                    df = pd.read_csv(source)
                except Exception:
                    try:
                        df = pd.read_csv(source, encoding="latin1")
                    except Exception:
                        df = pd.read_csv(source, encoding="cp1252")
        else:
            df = pd.read_excel(source)

        df.columns = [
            str(c).strip().replace("\xa0", " ")
            for c in df.columns
        ]

        for col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace("\xa0", " ", regex=False)
                .str.strip()
                .replace("nan", "")
                .replace("None", "")
            )

        # Support the uploaded Service Manager file.
        rename_map = {}

        if "TechAdvisorName" in df.columns:
            rename_map["TechAdvisorName"] = "Area Manager"

        if "Farm_Name" in df.columns:
            rename_map["Farm_Name"] = "Farm Name"

        df = df.rename(columns=rename_map)

        # Service Manager files often list the advisor once, then leave blanks below.
        # Fill advisor names downward.
        if "Area Manager" in df.columns:
            df["Area Manager"] = (
                df["Area Manager"]
                .replace("", pd.NA)
                .ffill()
                .fillna("Unassigned")
            )

        if "Farm Name" in df.columns:
            df["Farm Name"] = df["Farm Name"].replace("", pd.NA)
            df = df.dropna(subset=["Farm Name"])
            df["Farm Name"] = df["Farm Name"].astype(str).str.replace("\xa0", " ", regex=False).str.strip()

        if "Farm No" in df.columns:
            df["Farm No"] = df["Farm No"].apply(normalize_farm_no)

        if "Region" not in df.columns:
            df["Region"] = "Unassigned"

        if "Farm Type" not in df.columns:
            df["Farm Type"] = "Unassigned"

        return df

    except Exception as e:
        st.warning(f"Could not read farm master mapping: {e}")
        return pd.DataFrame()


def build_service_manager_weekly_trend(feedmill_df, farm_summary_df):
    """
    Builds weighted weekly delivered price by Service Manager.

    Important:
    This uses feedmill delivered price by week/farm, then maps each farm to its
    Service Manager. Price is weighted by tonnes, not a simple average.
    """
    if feedmill_df is None or feedmill_df.empty:
        return pd.DataFrame()

    if farm_summary_df is None or farm_summary_df.empty:
        return pd.DataFrame()

    farm_map = (
        farm_summary_df[["Farm No", "Area Manager"]]
        .drop_duplicates("Farm No")
        .copy()
    )

    df = feedmill_df.copy()
    df["Farm No"] = df["Farm No"].apply(normalize_farm_no)

    df = df.merge(farm_map, on="Farm No", how="left")
    df["Area Manager"] = df["Area Manager"].fillna("Unassigned")

    weekly = (
        df.groupby(["Area Manager", "Week Ending"], dropna=False)
        .agg(
            Tonnes=("Tonnes Delivered", "sum"),
            Delivered_Cost=("Delivered Cost", "sum"),
            Farms=("Farm No", "nunique"),
            Formula_Count=("Formula", "nunique"),
        )
        .reset_index()
        .sort_values(["Area Manager", "Week Ending"])
    )

    weekly["Avg Feed Price $/t"] = np.where(
        weekly["Tonnes"] > 0,
        weekly["Delivered_Cost"] / weekly["Tonnes"],
        np.nan,
    )

    return weekly


def build_farm_weekly_price(feedmill_df, farm_summary_df):
    """
    Builds weighted weekly delivered price by farm with Service Manager mapping.
    """
    if feedmill_df is None or feedmill_df.empty:
        return pd.DataFrame()

    farm_map = pd.DataFrame()
    if farm_summary_df is not None and not farm_summary_df.empty:
        farm_map = farm_summary_df[["Farm No", "Area Manager"]].drop_duplicates("Farm No").copy()

    df = feedmill_df.copy()
    df["Farm No"] = df["Farm No"].apply(normalize_farm_no)

    if not farm_map.empty:
        df = df.merge(farm_map, on="Farm No", how="left")

    if "Area Manager" not in df.columns:
        df["Area Manager"] = "Unassigned"

    df["Area Manager"] = df["Area Manager"].fillna("Unassigned")

    weekly = (
        df.groupby(["Area Manager", "Farm No", "Farm Name", "Week Ending"], dropna=False)
        .agg(
            Tonnes=("Tonnes Delivered", "sum"),
            Delivered_Cost=("Delivered Cost", "sum"),
            Formula_Count=("Formula", "nunique"),
            Main_Formula=("Formula", lambda s: s.dropna().astype(str).mode().iloc[0] if not s.dropna().empty else ""),
        )
        .reset_index()
        .sort_values(["Area Manager", "Farm Name", "Week Ending"])
    )

    weekly["Avg Feed Price $/t"] = np.where(
        weekly["Tonnes"] > 0,
        weekly["Delivered_Cost"] / weekly["Tonnes"],
        np.nan,
    )

    return weekly


def service_manager_plain_english_summary(service_manager, manager_weekly, manager_farms, support_queue_count):
    """
    Builds a plain-English interpretation for Service Managers.
    """
    if manager_weekly is None or manager_weekly.empty:
        return "No weekly feed delivery price trend is available for this service manager in the uploaded period."

    clean = manager_weekly.dropna(subset=["Avg Feed Price $/t"]).sort_values("Week Ending")
    if clean.empty or len(clean) < 2:
        return "There is not enough weekly price data yet to judge whether this group is improving or drifting."

    first = float(clean.iloc[0]["Avg Feed Price $/t"])
    last = float(clean.iloc[-1]["Avg Feed Price $/t"])
    movement = last - first

    if movement > 25:
        direction = "has moved higher"
        tone = "Review the farms with the largest increase, but check ration/formula changes before treating it as a farm issue."
    elif movement > 10:
        direction = "is slightly higher"
        tone = "Keep an eye on farms above the group trend and confirm recons are ready before pricing review."
    elif movement < -10:
        direction = "is improving"
        tone = "This is a positive trend. Check whether the improvement is broad across farms or driven by ration mix."
    else:
        direction = "is holding steady"
        tone = "Focus mainly on recon completeness and farms still needing support before pricing review."

    farms_count = manager_farms["Farm No"].nunique() if manager_farms is not None and not manager_farms.empty else 0

    return (
        f"{service_manager}'s average delivered feed price {direction} over the visible weeks "
        f"({fmt_currency(first, 2)}/t to {fmt_currency(last, 2)}/t). "
        f"{support_queue_count} farm(s) still need recon support before pricing is finalised. "
        f"{tone}"
    )


def render_service_manager_focus_page(feedmill, farm_summary):
    """
    Manager-friendly page focused on weekly price progression and cutoff readiness.
    """
    st.markdown('<div class="pf-section-title">Service Manager Focus</div>', unsafe_allow_html=True)

    manager_weekly = build_service_manager_weekly_trend(feedmill, farm_summary)
    farm_weekly = build_farm_weekly_price(feedmill, farm_summary)

    if manager_weekly.empty:
        st.info("No weekly feed price trend is available yet.")
        return

    managers = sorted([x for x in manager_weekly["Area Manager"].dropna().astype(str).unique().tolist() if x != "Unassigned"])
    if "Unassigned" in manager_weekly["Area Manager"].astype(str).unique().tolist():
        managers.append("Unassigned")


    # Service Manager default: All
    if "managers" in locals():
        managers = ["All"] + [m for m in managers if str(m) != "All"]

    # Default this page to All after this version loads; users can still select their own name.
    if not st.session_state.get("service_manager_focus_default_all_v92", False):
        st.session_state["service_manager_focus_selector"] = "All"
        st.session_state["service_manager_focus_default_all_v92"] = True

    selected_manager = st.selectbox(
        "Select Service Manager",
        options=managers,
        index=0,
        key="service_manager_focus_selector",
    )

    render_service_manager_recon_score_block(farm, farm_summary, selected_manager)


    if not selected_manager:
        st.info("No Service Manager selected.")
        return

    if str(selected_manager) == "All":
        selected_weekly = manager_weekly.copy()
        selected_farms = farm_summary.copy()
    else:
        selected_weekly = manager_weekly[manager_weekly["Area Manager"].astype(str).eq(str(selected_manager))].copy()
        selected_farms = farm_summary[farm_summary["Area Manager"].astype(str).eq(str(selected_manager))].copy()

    support_count = selected_farms["Pricing Status"].isin(["Support Needed", "Price Not Ready", "Review Suggested"]).sum() if not selected_farms.empty else 0
    not_ready_count = selected_farms["Pricing Status"].isin(["Price Not Ready"]).sum() if not selected_farms.empty else 0
    ready_count = selected_farms["Pricing Status"].isin(["Ready to Finalise"]).sum() if not selected_farms.empty else 0

    chart_col1, chart_col2 = st.columns([1, 1])

    with chart_col1:
        fig = px.line(
            selected_weekly.sort_values("Week Ending"),
            x="Week Ending",
            y="Avg Feed Price $/t",
            markers=True,
            title=("All Service Managers: average feed price per week" if str(selected_manager) == "All" else f"{selected_manager}: average feed price per week"),
        )
        fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=25))
        fig.update_yaxes(tickprefix="$", title="Average feed price $/t")
        st.plotly_chart(fig, use_container_width=True)

    with chart_col2:
        all_manager_compare = manager_weekly.copy()
        fig = px.line(
            all_manager_compare.sort_values("Week Ending"),
            x="Week Ending",
            y="Avg Feed Price $/t",
            color="Area Manager",
            markers=True,
            title="Service Manager comparison: average feed price per week",
        )
        fig.update_layout(height=390, margin=dict(l=20, r=20, t=55, b=25), legend_title_text="Service Manager")
        fig.update_yaxes(tickprefix="$", title="Average feed price $/t")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Farm trend within selected Service Manager")

    selected_farm_weekly = farm_weekly[farm_weekly["Area Manager"].astype(str).eq(str(selected_manager))].copy()

    if selected_farm_weekly.empty:
        st.info("No farm-level weekly trend found for this Service Manager.")
    else:
        fig = px.line(
            selected_farm_weekly.sort_values("Week Ending"),
            x="Week Ending",
            y="Avg Feed Price $/t",
            color="Farm Name",
            markers=True,
            hover_data=["Farm No", "Tonnes", "Formula_Count", "Main_Formula"],
            title=f"{selected_manager}: farm average feed price per week",
        )
        fig.update_layout(height=480, margin=dict(l=20, r=20, t=55, b=25), legend_title_text="Farm")
        fig.update_yaxes(tickprefix="$", title="Average feed price $/t")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### Ration/formula note")

    st.markdown(
        """
        <div class="pf-note">
        <strong>Important:</strong> a rising feed price does not automatically mean the farm is doing anything wrong. Ration changes, formula mix, feedmill ingredient cost, delivery cost, and bird age/stage can all move the price. Use this page to identify where to look first, then confirm whether the movement is real or ration-driven.
        </div>
        """,
        unsafe_allow_html=True,
    )


def _recon_present(value, allow_zero=True):
    """
    Returns True when a recon field has been entered / is usable.
    allow_zero is True for fields where 0 can be legitimate.
    """
    try:
        if value is None or pd.isna(value):
            return False
    except Exception:
        pass

    try:
        numeric = float(value)
        if allow_zero:
            return True
        return abs(numeric) > 0.0001
    except Exception:
        text = str(value).strip()
        return text not in ["", "nan", "None"]


def _recon_cell_html(value, ok, decimals=0):
    """
    Green = entered / acceptable
    Red = missing / needs attention
    """
    try:
        if value is None or pd.isna(value):
            display = "—"
        else:
            v = float(value)
            display = f"{v:,.{decimals}f}"
    except Exception:
        display = str(value or "—")

    if ok:
        return f'<span class="recon-cell recon-ok">✓ {display}</span>'
    return f'<span class="recon-cell recon-missing">Needs entry</span>'


def _recon_variance_html(value):
    try:
        if value is None or pd.isna(value):
            return '<span class="recon-cell recon-missing">Needs review</span>'

        v = float(value)
        abs_v = abs(v)

        if abs_v <= 250:
            return f'<span class="recon-cell recon-ok">✓ {v:,.0f}</span>'

        if abs_v <= 1000:
            return f'<span class="recon-cell recon-review">Review {v:,.0f}</span>'

        return f'<span class="recon-cell recon-missing">Check {v:,.0f}</span>'
    except Exception:
        return '<span class="recon-cell recon-missing">Needs review</span>'


def _recon_status_badge(status):
    status = str(status or "").strip()

    if status == "Complete":
        return '<span class="recon-status recon-status-complete">✓ Complete</span>'

    if status in ["Variance to Review", "Opening Stock Review", "Deliveries to Review", "Feed Consumed Review", "Bird Inventory Review"]:
        return f'<span class="recon-status recon-status-review">⚠ {status}</span>'

    if status == "Closing Stock to Complete":
        return '<span class="recon-status recon-status-missing">● Closing Stock to Complete</span>'

    if status == "Not Ready":
        return '<span class="recon-status recon-status-missing">● Not Ready</span>'

    return f'<span class="recon-status recon-status-review">⚠ {status or "Review Needed"}</span>'



def inject_current_recon_styles():
    st.markdown(
        """
        <style>
        .recon-board-wrap {
            border: 1px solid #E2E8F0;
            border-radius: 18px;
            overflow: auto;
            background: #FFFFFF;
            box-shadow: 0 7px 22px rgba(15, 23, 42, 0.06);
            margin-top: 0.75rem;
            margin-bottom: 1rem;
        }

        .recon-board-table {
            width: 100%;
            min-width: 1450px;
            border-collapse: separate;
            border-spacing: 0;
            font-size: 0.84rem;
            color: #0F172A;
        }

        .recon-board-table thead th {
            background: #F8FAFC;
            border-bottom: 1px solid #DBE3EF;
            border-right: 1px solid #E8EEF7;
            padding: 0.72rem 0.65rem;
            text-align: left;
            font-weight: 850;
            color: #334155;
            white-space: nowrap;
            position: sticky;
            top: 0;
            z-index: 2;
        }

        .recon-board-table tbody td {
            border-bottom: 1px solid #EDF2F7;
            border-right: 1px solid #F1F5F9;
            padding: 0.58rem 0.60rem;
            vertical-align: middle;
            white-space: nowrap;
        }

        .recon-board-table tbody tr:hover {
            background: #F8FBFF;
        }

        .recon-cell {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 92px;
            border-radius: 999px;
            padding: 0.26rem 0.55rem;
            font-weight: 850;
            font-size: 0.78rem;
            border: 1px solid;
        }

        .recon-ok {
            color: #15803D;
            background: #ECFDF3;
            border-color: #BBF7D0;
        }

        .recon-review {
            color: #D97706;
            background: #FFFBEB;
            border-color: #FDE68A;
        }

        .recon-missing {
            color: #DC2626;
            background: #FEF2F2;
            border-color: #FECACA;
        }

        .recon-status {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            border-radius: 999px;
            padding: 0.32rem 0.65rem;
            font-weight: 850;
            font-size: 0.78rem;
            border: 1px solid;
        }

        .recon-status-complete {
            color: #15803D;
            background: #ECFDF3;
            border-color: #BBF7D0;
        }

        .recon-status-review {
            color: #D97706;
            background: #FFFBEB;
            border-color: #FDE68A;
        }

        .recon-status-missing {
            color: #DC2626;
            background: #FEF2F2;
            border-color: #FECACA;
        }

        .recon-row-missing td:first-child {
            box-shadow: inset 5px 0 0 #DC2626;
        }

        .recon-row-review td:first-child {
            box-shadow: inset 5px 0 0 #F59E0B;
        }

        .recon-row-complete td:first-child {
            box-shadow: inset 5px 0 0 #16A34A;
        }

        .recon-mini-legend {
            display: flex;
            gap: 0.55rem;
            flex-wrap: wrap;
            margin: 0.35rem 0 0.65rem 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def get_current_recon_window(today=None):
    """
    Current Recon operational window.

    Rule:
    - Monday: show previous Monday to Sunday, because that is the recon
      period that must be finalised by Monday 12pm.
    - Tuesday to Sunday: show current Monday to today, so Service Managers
      can see who is keeping current-week data updated.
    """
    if today is None:
        today = date.today()

    if isinstance(today, pd.Timestamp):
        today = today.date()

    weekday = today.weekday()  # Monday = 0

    if weekday == 0:
        start_date = today - timedelta(days=7)
        end_date = today - timedelta(days=1)
        label = "Previous week recon period"
    else:
        start_date = today - timedelta(days=weekday)
        end_date = today
        label = "Current week progress"

    return pd.to_datetime(start_date), pd.to_datetime(end_date), label


















def render_farm_report_date_diagnostic(farm_df):
    """
    Shows what dates and source sheet the app is actually reading from
    the uploaded Farm report.
    """
    if farm_df is None or farm_df.empty:
        return

    week_col = get_explicit_week_ending_col(farm_df)

    begin_values = parse_amino_date(farm_df["Begin Date"]).dt.normalize() if "Begin Date" in farm_df.columns else pd.Series(pd.NaT, index=farm_df.index)
    end_values = parse_amino_date(farm_df["End Date"]).dt.normalize() if "End Date" in farm_df.columns else pd.Series(pd.NaT, index=farm_df.index)
    week_values = get_explicit_week_ending_series(farm_df)

    begin_list = begin_values.dropna().dt.strftime("%d/%m/%Y").drop_duplicates().sort_values().tolist()
    end_list = end_values.dropna().dt.strftime("%d/%m/%Y").drop_duplicates().sort_values().tolist()
    week_list = week_values.dropna().dt.strftime("%d/%m/%Y").drop_duplicates().sort_values().tolist()

    begin_preview = ", ".join(begin_list[:12]) if begin_list else "None found"
    end_preview = ", ".join(end_list[:12]) if end_list else "None found"
    week_preview = ", ".join(week_list[:12]) if week_list else "None found"
    week_col_label = week_col if week_col else "Not found"
    source_sheet = farm_df.attrs.get("source_sheet", "Unknown sheet")

    st.info(
        f"Farm file source sheet read by app: {source_sheet} | "
        f"Week Ending column: {week_col_label} | "
        f"Week Ending value(s): {week_preview} | "
        f"Begin Date(s): {begin_preview} | End Date(s): {end_preview}"
    )

    sheet_summaries = farm_df.attrs.get("sheet_summaries", [])
    if sheet_summaries:
        with st.expander("Workbook sheets detected by app", expanded=False):
            for item in sheet_summaries:
                st.write(item)



def get_explicit_week_ending_series(df):
    """
    Returns parsed Week Ending values using the robust case-insensitive
    Week Ending column finder.
    """
    if df is None or df.empty:
        return pd.Series(dtype="datetime64[ns]")

    week_col = get_explicit_week_ending_col(df)

    if not week_col:
        return pd.Series(pd.NaT, index=df.index)

    return parse_amino_date(df[week_col]).dt.normalize()



def get_explicit_week_ending_col(df):
    """
    Finds the explicit Week Ending column, accepting variations such as:
    Week Ending, Week ending, week ending, WeekEnding, Week_Ending.
    """
    return find_col_case_insensitive(
        df,
        [
            "Week Ending",
            "Week ending",
            "week ending",
            "WeekEnding",
            "Week End",
            "Week end",
            "W/E",
            "WE",
            "Week_Ending",
            "week_ending",
        ],
    )



def filter_farm_recon_to_window(farm_df, start_date, end_date):
    """
    Filters the Amino Farm report for Current Recon.

    New preferred rule:
    If the report has a Week Ending column, use it directly.

    Manual mode:
        selected Sunday week ending -> rows where Week Ending == selected Sunday.

    Automatic mode:
        if today is not Sunday -> rows with Week Ending equal to the current
        operational week ending, or Begin/End period overlaps Monday-to-today
        if Week Ending is unavailable.
    """
    if farm_df is None or farm_df.empty:
        return pd.DataFrame(), "No farm recon rows found."

    df = farm_df.copy()

    start_date = pd.to_datetime(start_date).normalize()
    end_date = pd.to_datetime(end_date).normalize()

    explicit_week = get_explicit_week_ending_series(df)
    explicit_col = get_explicit_week_ending_col(df)

    if explicit_week.notna().any():
        selected_week_ending = week_ending_from_date(pd.Series([end_date]), "Sunday").iloc[0].normalize()
        mask = explicit_week.eq(selected_week_ending)

        filtered = df[mask].copy()

        if not filtered.empty:
            filtered["Recon Week Ending"] = selected_week_ending
            filtered["Recon Match Type"] = "Week Ending column"
            return (
                filtered,
                f"Filtered using explicit Week Ending column. Showing rows where Week Ending = {selected_week_ending.strftime('%d/%m/%Y')}."
            )

        available_weeks = (
            explicit_week
            .dropna()
            .dt.strftime("%d/%m/%Y")
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        week_preview = ", ".join(available_weeks[:20])

        return filtered, (
            f"No rows found where Week Ending = {selected_week_ending.strftime('%d/%m/%Y')}. "
            f"The uploaded Farm report contains Week Ending values: {week_preview}."
        )

    # Fallback only if Week Ending is unavailable.
    begin_values = parse_amino_date(df["Begin Date"]).dt.normalize() if "Begin Date" in df.columns else pd.Series(pd.NaT, index=df.index)
    end_values = parse_amino_date(df["End Date"]).dt.normalize() if "End Date" in df.columns else pd.Series(pd.NaT, index=df.index)

    # Automatic partial-week mode without Week Ending.
    if end_date.weekday() != 6:
        if "Begin Date" in df.columns and "End Date" in df.columns:
            overlap_mask = begin_values.le(end_date) & end_values.ge(start_date)
            filtered = df[overlap_mask].copy()

            if not filtered.empty:
                filtered["Begin Date"] = begin_values[overlap_mask].values
                filtered["End Date"] = end_values[overlap_mask].values
                filtered["Recon Week Ending"] = week_ending_from_date(filtered["End Date"], "Sunday")
                filtered["Recon Match Type"] = "Automatic current period"

                return (
                    filtered,
                    f"Automatic mode: showing rows whose Begin/End period overlaps "
                    f"{start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}."
                )

        return pd.DataFrame(), (
            f"No recon rows found for the automatic window "
            f"{start_date.strftime('%d/%m/%Y')} to {end_date.strftime('%d/%m/%Y')}."
        )

    # Manual without Week Ending: exact Begin/End match.
    if "Begin Date" in df.columns and "End Date" in df.columns:
        exact_period_mask = begin_values.eq(start_date) & end_values.eq(end_date)
        exact = df[exact_period_mask].copy()

        if not exact.empty:
            exact["Begin Date"] = begin_values[exact_period_mask].values
            exact["End Date"] = end_values[exact_period_mask].values
            exact["Recon Week Ending"] = end_date
            exact["Recon Match Type"] = "Exact selected week"

            return (
                exact,
                f"Filtered by exact selected week. Begin Date = {start_date.strftime('%d/%m/%Y')} "
                f"and End Date = {end_date.strftime('%d/%m/%Y')}."
            )

    return pd.DataFrame(), (
        "No Week Ending column was found and no exact Begin/End match was found. "
        "Add or check the Week Ending column in the Farm report."
    )



def build_current_recon_df(farm_df, farm_summary_df):
    """
    One row per farm/flock/shed from the Amino Farm report.
    Adds Tech/Service Manager from the mapped farm summary.
    """
    if farm_df is None or farm_df.empty:
        return pd.DataFrame()

    df = farm_df.copy()

    # Internal farm report fields created during prepare_farm_recon:
    # Farm No, Farm Name, Flock, Bird Inv etc. Some source columns are still present.
    bird_col = first_existing_col(df, ["Bird Inv (End)", "Bird Inventory (End)", "Bird Inv End"])
    beg_col = first_existing_col(df, ["Feed Inventory (Beg)", "Beginning Stock kg"])
    delivered_col = first_existing_col(df, ["Feed Delivered", "Farm Delivered kg"])
    consumed_col = first_existing_col(df, ["Feed Consumed", "Consumed kg"])
    end_col = first_existing_col(df, ["Feed Inventory (End)", "Closing Stock kg"])
    end_calc_col = first_existing_col(df, ["Feed Inventory (EndCalc)", "Calculated Closing Stock kg"])
    end_var_col = first_existing_col(df, ["Feed Inventory (EndVar)", "Closing Stock Variance kg"])
    flock_col = first_existing_col(df, ["Complex Flock No", "Flock No", "Flock"])
    status_col = first_existing_col(df, ["Status", "Flock Status"])
    entity_stage_col = first_existing_col(df, ["Entity Stage", "Stage"])
    age_col = first_existing_col(df, ["Age", "Age Week", "Age Weeks", "Age in weeks"])
    begin_date_col = first_existing_col(df, ["Begin Date"])
    end_date_col = first_existing_col(df, ["End Date"])
    recon_week_col = first_existing_col(df, ["Recon Week Ending"])
    farm_week_ending_col = get_explicit_week_ending_col(df)
    match_type_col = first_existing_col(df, ["Recon Match Type"])
    raw_begin_date_col = first_existing_col(df, ["Amino Raw Begin Date"])
    raw_end_date_col = first_existing_col(df, ["Amino Raw End Date"])

    out = pd.DataFrame()
    out["Farm No"] = df["Farm No"].apply(normalize_farm_no) if "Farm No" in df.columns else ""
    out["Farm Name"] = df["Farm Name"].astype(str).str.replace("\\xa0", " ", regex=False).str.strip() if "Farm Name" in df.columns else ""
    out["Begin Date"] = parse_amino_date(df[begin_date_col]) if begin_date_col else pd.NaT
    out["End Date"] = parse_amino_date(df[end_date_col]) if end_date_col else pd.NaT
    out["Recon Week Ending"] = parse_amino_date(df[recon_week_col]) if recon_week_col else (parse_amino_date(df[farm_week_ending_col]) if farm_week_ending_col else amino_recon_week_ending_from_date(out["End Date"], "End Date"))
    out["Recon Match Type"] = df[match_type_col].astype(str).str.strip() if match_type_col else "Exact selected week"
    out["Raw Begin Date"] = df[raw_begin_date_col].astype(str).str.strip() if raw_begin_date_col else ""
    out["Raw End Date"] = df[raw_end_date_col].astype(str).str.strip() if raw_end_date_col else ""
    out["Shed / Flock"] = df[flock_col].astype(str).str.replace("\\xa0", " ", regex=False).str.strip() if flock_col else ""
    out["Entity Stage"] = df[entity_stage_col].astype(str).str.replace("\\xa0", " ", regex=False).str.strip() if entity_stage_col else ""
    out["Age"] = pd.to_numeric(df[age_col], errors="coerce") if age_col else np.nan
    out["Bird Inv (End)"] = pd.to_numeric(df[bird_col], errors="coerce") if bird_col else np.nan
    out["Feed Inventory (Beg)"] = pd.to_numeric(df[beg_col], errors="coerce") if beg_col else np.nan
    out["Feed Delivered"] = pd.to_numeric(df[delivered_col], errors="coerce") if delivered_col else np.nan
    out["Feed Consumed"] = pd.to_numeric(df[consumed_col], errors="coerce") if consumed_col else np.nan
    out["Feed Inventory (End)"] = pd.to_numeric(df[end_col], errors="coerce") if end_col else np.nan
    out["Feed Inventory (EndCalc)"] = pd.to_numeric(df[end_calc_col], errors="coerce") if end_calc_col else np.nan
    out["Feed Inventory (EndVar)"] = pd.to_numeric(df[end_var_col], errors="coerce") if end_var_col else np.nan

    if farm_summary_df is not None and not farm_summary_df.empty and "Area Manager" in farm_summary_df.columns:
        mgr_map = (
            farm_summary_df[["Farm No", "Area Manager"]]
            .drop_duplicates("Farm No")
            .copy()
        )
        mgr_map["Farm No"] = mgr_map["Farm No"].apply(normalize_farm_no)
        out = out.merge(mgr_map, on="Farm No", how="left")
    else:
        out["Area Manager"] = "Unassigned"

    out["Area Manager"] = out["Area Manager"].fillna("Unassigned")

    # Completion logic.
    # Delivered can be zero legitimately in a week, so it is green if present.
    # Consumed / bird inventory / closing stock should be real values on active rows.
    # ------------------------------------------------------------------
    # Current Recon operational rules
    # ------------------------------------------------------------------
    # These rules are intentionally practical for farm/Service Manager follow-up:
    # - Feed Inventory (Beg) = 0 means previous closing stock may not have carried through
    # - Feed Delivered = 0 means no delivery/receival was captured
    # - Feed Inventory (End) = 0 means closing bin stock was not recorded
    # - Feed Inventory (EndVar) must be 0 to be reconciled
    #
    # Bird inventory is still checked, but the feed recon fields drive the
    # row-level status.
    out["Bird Inv OK"] = out["Bird Inv (End)"].apply(lambda x: _recon_present(x, allow_zero=False))
    out["Beginning Stock OK"] = pd.to_numeric(out["Feed Inventory (Beg)"], errors="coerce").fillna(0).gt(0)
    out["Feed Delivered OK"] = pd.to_numeric(out["Feed Delivered"], errors="coerce").fillna(0).gt(0)
    out["Feed Consumed OK"] = pd.to_numeric(out["Feed Consumed"], errors="coerce").fillna(0).gt(0)
    out["Closing Stock OK"] = pd.to_numeric(out["Feed Inventory (End)"], errors="coerce").fillna(0).gt(0)
    out["EndCalc OK"] = out["Feed Inventory (EndCalc)"].apply(lambda x: _recon_present(x, allow_zero=True))

    end_var_numeric = pd.to_numeric(out["Feed Inventory (EndVar)"], errors="coerce")
    out["Variance OK"] = end_var_numeric.fillna(999999).abs().le(0.0001)
    out["Variance Review"] = ~out["Variance OK"]

    out["Opening Stock Review"] = ~out["Beginning Stock OK"]
    out["Deliveries Review"] = ~out["Feed Delivered OK"]
    out["Closing Stock Review"] = ~out["Closing Stock OK"]


    # Decide which rows belong in normal Current Recon view.
    #
    # This page is a missing-data follow-up tool, so DO NOT hide rows just
    # because bird inventory, delivery, or closing stock is zero. Those zero
    # values are exactly what Service Managers need to see.
    #
    # Default view should show active selected-week flock rows. It should hide
    # only clearly inactive/closed/finished/transferred rows. The checkbox can
    # still show every row for audit.
    if "Amino Status" not in out.columns:
        out["Amino Status"] = ""

    if "Entity Stage" not in out.columns:
        out["Entity Stage"] = ""

    if "Age" not in out.columns:
        out["Age"] = np.nan

    status_for_scope = out["Amino Status"].astype(str).str.lower().str.strip()
    stage_for_scope = out["Entity Stage"].astype(str).str.lower().str.strip()
    age_for_scope = pd.to_numeric(out["Age"], errors="coerce")
    flock_for_scope = out["Shed / Flock"].astype(str).str.strip() if "Shed / Flock" in out.columns else pd.Series("", index=out.index)

    is_inactive_status = status_for_scope.str.contains(
        "inactive|closed|transferred|finished|depleted|sold",
        na=False,
    )

    # Keep normal production/rearing stages. If stage is blank, keep it too,
    # because missing stage should not hide a recon issue.
    known_stage = stage_for_scope.str.contains(
        "brood|rear|rearing|lay|layer|prod|production",
        na=False,
    )
    blank_stage = stage_for_scope.eq("") | stage_for_scope.eq("nan")

    # Age scope remains broad enough to keep practical active flock rows, but
    # zero/blank age rows are not automatically excluded because new/flawed rows
    # may be exactly what needs review.
    practical_age = (
        age_for_scope.isna()
        | age_for_scope.between(0, 90, inclusive="both")
    )

    has_flock_identifier = flock_for_scope.ne("") & ~flock_for_scope.str.lower().isin(["nan", "none"])

    out["Include In Current Recon"] = (
        has_flock_identifier
        & (~is_inactive_status)
        & (known_stage | blank_stage)
        & practical_age
    )

    def row_status(row):
        if not bool(row.get("Closing Stock OK", False)):
            return "Closing Stock to Complete"

        if not bool(row.get("Beginning Stock OK", False)):
            return "Opening Stock Review"

        if not bool(row.get("Feed Delivered OK", False)):
            return "Deliveries to Review"

        if not bool(row.get("Variance OK", False)):
            return "Variance to Review"

        if not bool(row.get("Feed Consumed OK", False)):
            return "Feed Consumed Review"

        if not bool(row.get("Bird Inv OK", False)):
            return "Bird Inventory Review"

        return "Complete"

    out["Current Recon Status"] = out.apply(row_status, axis=1)

    def support_note(row):
        notes = []

        if not bool(row.get("Beginning Stock OK", False)):
            notes.append("Opening stock is zero; check previous week closing stock carried through.")

        if not bool(row.get("Feed Delivered OK", False)):
            notes.append("No feed deliveries captured/received for this flock and week.")

        if not bool(row.get("Closing Stock OK", False)):
            notes.append("Closing stock is zero; physical bin stock reading may need entry.")

        if not bool(row.get("Variance OK", False)):
            try:
                var_value = float(row.get("Feed Inventory (EndVar)", 0))
                notes.append(f"Stock variance is {var_value:,.0f}; review opening stock, deliveries, consumption, and closing stock.")
            except Exception:
                notes.append("Stock variance exists; review opening stock, deliveries, consumption, and closing stock.")

        if not bool(row.get("Feed Consumed OK", False)):
            notes.append("Feed consumed is zero; confirm consumption/feed usage has calculated correctly.")

        if not bool(row.get("Bird Inv OK", False)):
            notes.append("Bird inventory is zero or missing; confirm whether this is an active flock row.")

        if not notes:
            return "Ready for pricing review."

        return " ".join(notes)

    out["Support Note"] = out.apply(support_note, axis=1)

    return out.sort_values(["Area Manager", "Farm Name", "Shed / Flock"]).reset_index(drop=True)




def get_current_and_previous_sundays(today=None):
    """
    Returns the current Sunday week-ending and previous Sunday week-ending.
    Current Sunday means the Sunday at the end of the current Monday-Sunday week.
    """
    if today is None:
        today = date.today()

    if isinstance(today, pd.Timestamp):
        today = today.date()

    weekday = today.weekday()  # Monday = 0, Sunday = 6
    current_sunday = pd.to_datetime(today + timedelta(days=(6 - weekday))).normalize()
    previous_sunday = current_sunday - pd.Timedelta(days=7)

    return current_sunday, previous_sunday




def amino_recon_week_ending_from_date(date_series, date_col_name="End Date"):
    """
    Converts Amino recon dates to Pace Sunday week-ending.

    Pace rule:
    Any date from Monday to Sunday belongs to the coming Sunday week ending.

    Examples:
        Monday 04/05/2026 -> Sunday 10/05/2026
        Sunday 10/05/2026 -> Sunday 10/05/2026
    """
    dates = parse_amino_date(date_series)
    return week_ending_from_date(dates, "Sunday")





def get_available_recon_week_endings(farm_df):
    """
    Returns available Sunday week-ending dates from the Amino Farm report.

    Preferred source is the explicit Week Ending column if present.
    """
    if farm_df is None or farm_df.empty:
        return [], None

    explicit_week = get_explicit_week_ending_series(farm_df)

    if explicit_week.notna().any():
        week_endings = (
            explicit_week
            .dropna()
            .dt.normalize()
            .drop_duplicates()
            .sort_values(ascending=False)
            .tolist()
        )
        return week_endings, get_explicit_week_ending_col(farm_df) or "Week Ending"

    date_col = None
    df = farm_df.copy()

    for possible_col in ["End Date", "Begin Date", "Date"]:
        if possible_col in df.columns:
            parsed = parse_amino_date(df[possible_col])
            if parsed.notna().any():
                df[possible_col] = parsed
                date_col = possible_col
                break

    if date_col is None:
        return [], None

    week_endings = (
        amino_recon_week_ending_from_date(df[date_col], date_col)
        .dropna()
        .dt.normalize()
        .drop_duplicates()
        .sort_values(ascending=False)
        .tolist()
    )

    return week_endings, date_col



def recon_window_from_week_ending(week_ending):
    """
    Given a Sunday week ending, return Monday-to-Sunday window.
    """
    week_ending = pd.to_datetime(week_ending).normalize()
    start_date = week_ending - pd.Timedelta(days=6)
    end_date = week_ending
    return start_date, end_date



def derive_shed_no_from_complex_flock(value):
    """
    Practical shed number helper from Complex Flock No / Flock code.

    The app keeps the full Complex Flock No visible, but also derives a small
    shed number for sorting/follow-up where possible.
    """
    text = str(value or "").strip()

    if not text or text.lower() in ["nan", "none"]:
        return ""

    # Common Amino format: FARM-FLOCKCODE, e.g. 2002-260103.
    # Use the final two digits as a simple shed indicator.
    if "-" in text:
        tail = text.split("-")[-1]
        digits = "".join(ch for ch in tail if ch.isdigit())
        if len(digits) >= 2:
            return digits[-2:]

    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 2:
        return digits[-2:]

    return ""


def build_static_shed_register(farm_df, farm_summary_df=None):
    """
    Builds the static Current Recon row base.

    This is intentionally NOT filtered to the selected week. It gives the page
    a stable list of farm/shed/flock rows so missing selected-week data becomes
    visible as red instead of disappearing.
    """
    if farm_df is None or farm_df.empty:
        return pd.DataFrame()

    df = farm_df.copy()

    farm_no_col = first_existing_col(df, ["Farm No", "FarmNo"])
    farm_name_col = first_existing_col(df, ["Farm Name", "Farm_Name", "Entity Trans Name"])
    flock_col = first_existing_col(df, ["Complex Flock No", "Flock No", "Flock", "Flock No."])
    status_col = first_existing_col(df, ["Status", "Flock Status"])
    stage_col = first_existing_col(df, ["Entity Stage", "Stage"])
    age_col = first_existing_col(df, ["Age", "Age Week", "Age Weeks", "Age in weeks"])

    out = pd.DataFrame()
    out["Farm No"] = df[farm_no_col].apply(normalize_farm_no) if farm_no_col else ""
    out["Farm Name"] = df[farm_name_col].astype(str).str.replace("\xa0", " ", regex=False).str.strip() if farm_name_col else ""
    out["Shed / Flock"] = df[flock_col].astype(str).str.replace("\xa0", " ", regex=False).str.strip() if flock_col else ""
    out["Shed No"] = out["Shed / Flock"].apply(derive_shed_no_from_complex_flock)
    out["Amino Status"] = df[status_col].astype(str).str.replace("\xa0", " ", regex=False).str.strip() if status_col else ""
    out["Entity Stage"] = df[stage_col].astype(str).str.replace("\xa0", " ", regex=False).str.strip() if stage_col else ""
    out["Age"] = pd.to_numeric(df[age_col], errors="coerce") if age_col else np.nan

    # Remove blank rows.
    out = out[
        out["Farm Name"].astype(str).str.strip().ne("")
        & out["Shed / Flock"].astype(str).str.strip().ne("")
        & ~out["Shed / Flock"].astype(str).str.lower().isin(["nan", "none"])
    ].copy()

    if out.empty:
        return out

    # Keep the latest-looking record for each Farm/Shed based on Age where possible.
    out["_age_sort"] = pd.to_numeric(out["Age"], errors="coerce").fillna(-1)
    out = (
        out.sort_values(["Farm Name", "Shed / Flock", "_age_sort"])
        .drop_duplicates(["Farm Name", "Shed / Flock"], keep="last")
        .drop(columns=["_age_sort"])
    )

    # Add Service Manager from farm summary if available.
    out["Area Manager"] = "Unassigned"

    if farm_summary_df is not None and not farm_summary_df.empty:
        summary = farm_summary_df.copy()

        if "Farm No" in summary.columns and "Area Manager" in summary.columns:
            map_by_no = (
                summary[["Farm No", "Area Manager"]]
                .dropna()
                .drop_duplicates("Farm No")
            )
            out = out.merge(map_by_no, on="Farm No", how="left", suffixes=("", "_mapped"))
            out["Area Manager"] = out["Area Manager_mapped"].fillna(out["Area Manager"])
            out = out.drop(columns=[c for c in ["Area Manager_mapped"] if c in out.columns])

        if "Farm Name" in summary.columns and "Area Manager" in summary.columns:
            map_by_name = (
                summary[["Farm Name", "Area Manager"]]
                .dropna()
                .drop_duplicates("Farm Name")
            )
            out = out.merge(map_by_name, on="Farm Name", how="left", suffixes=("", "_name_mapped"))
            out["Area Manager"] = out["Area Manager_name_mapped"].fillna(out["Area Manager"])
            out = out.drop(columns=[c for c in ["Area Manager_name_mapped"] if c in out.columns])

    # Hide only clearly out-of-scope rows by default.
    status_text = out["Amino Status"].astype(str).str.lower()
    out["Include In Current Recon"] = ~status_text.str.contains(
        "inactive|closed|transferred|finished|depleted|sold",
        na=False,
    )

    return out.sort_values(["Area Manager", "Farm Name", "Shed No", "Shed / Flock"]).reset_index(drop=True)



# ------------------------------------------------------------
# Recon readiness / issue scoring
# ------------------------------------------------------------
RECON_ENDVAR_TOLERANCE_KG = 3000


def is_endvar_within_tolerance(value, tolerance=RECON_ENDVAR_TOLERANCE_KG):
    try:
        v = float(pd.to_numeric(value, errors="coerce"))
        if pd.isna(v):
            return False
        return abs(v) <= tolerance
    except Exception:
        return False


def add_recon_readiness_scores(df):
    """
    Adds practical readiness scoring for recon rows.

    A shed starts at 100%. Each failed check reduces the score.
    This keeps the language supportive: the score shows how ready the row is
    for pricing review, not who has failed.
    """
    if df is None or df.empty:
        return df

    out = df.copy()

    check_columns = {
        "Bird Inv (End)": "Bird Inv OK",
        "Feed Inventory (Beg)": "Opening Stock OK",
        "Feed Delivered": "Feed Delivered OK",
        "Feed Consumed": "Feed Consumed OK",
        "Feed Inventory (End)": "Closing Stock OK",
        "Feed Inventory (EndCalc)": "EndCalc OK",
        "Feed Inventory (EndVar)": "Variance OK",
    }

    # Calculate direct checks from visible values so it works even if hidden OK
    # fields are missing.
    out["Bird Inv OK"] = pd.to_numeric(out.get("Bird Inv (End)", 0), errors="coerce").fillna(0).gt(0)
    out["Opening Stock OK"] = pd.to_numeric(out.get("Feed Inventory (Beg)", 0), errors="coerce").fillna(0).gt(0)
    out["Feed Delivered OK"] = pd.to_numeric(out.get("Feed Delivered", 0), errors="coerce").fillna(0).gt(0)
    out["Feed Consumed OK"] = pd.to_numeric(out.get("Feed Consumed", 0), errors="coerce").fillna(0).gt(0)
    out["Closing Stock OK"] = pd.to_numeric(out.get("Feed Inventory (End)", 0), errors="coerce").fillna(0).gt(0)

    if "Feed Inventory (EndCalc)" in out.columns:
        out["EndCalc OK"] = pd.to_numeric(out["Feed Inventory (EndCalc)"], errors="coerce").notna()
    else:
        out["EndCalc OK"] = False

    if "Feed Inventory (EndVar)" in out.columns:
        out["Variance OK"] = pd.to_numeric(out["Feed Inventory (EndVar)"], errors="coerce").apply(is_endvar_within_tolerance)
    else:
        out["Variance OK"] = False

    checks = [
        "Bird Inv OK",
        "Opening Stock OK",
        "Feed Delivered OK",
        "Feed Consumed OK",
        "Closing Stock OK",
        "EndCalc OK",
        "Variance OK",
    ]

    out["Recon Checks Passed"] = out[checks].sum(axis=1)
    out["Recon Checks Total"] = len(checks)
    out["Recon Issue Count"] = out["Recon Checks Total"] - out["Recon Checks Passed"]
    out["Recon Readiness %"] = ((out["Recon Checks Passed"] / out["Recon Checks Total"]) * 100).round(0).astype(int)

    def readiness_status(row):
        score = row.get("Recon Readiness %", 0)
        if score >= 100:
            return "Ready"
        if score >= 85:
            return "Minor Review"
        if score >= 60:
            return "Needs Follow-up"
        return "High Priority"

    out["Recon Readiness Status"] = out.apply(readiness_status, axis=1)

    def issue_summary(row):
        issues = []
        if not bool(row.get("Bird Inv OK", False)):
            issues.append("bird inventory")
        if not bool(row.get("Opening Stock OK", False)):
            issues.append("opening stock")
        if not bool(row.get("Feed Delivered OK", False)):
            issues.append("feed delivery")
        if not bool(row.get("Feed Consumed OK", False)):
            issues.append("feed consumed")
        if not bool(row.get("Closing Stock OK", False)):
            issues.append("closing stock")
        if not bool(row.get("EndCalc OK", False)):
            issues.append("calculated closing stock")
        if not bool(row.get("Variance OK", False)):
            issues.append("stock variance outside ±3t")

        if not issues:
            return "All key recon fields look ready."
        return "Review: " + ", ".join(issues) + "."

    out["Recon Issue Summary"] = out.apply(issue_summary, axis=1)

    return out


def style_recon_readiness_table(row):
    styles = pd.Series("", index=row.index)

    score = pd.to_numeric(row.get("Recon Readiness %", 0), errors="coerce")
    if pd.isna(score):
        score = 0

    green = "background-color:#DCFCE7; color:#166534; font-weight:900;"
    amber = "background-color:#FEF3C7; color:#92400E; font-weight:900;"
    red = "background-color:#FEE2E2; color:#991B1B; font-weight:900;"
    grey = "background-color:#F8FAFC; color:#475569;"

    if "Recon Readiness %" in row.index:
        if score >= 100:
            styles["Recon Readiness %"] = green
        elif score >= 85:
            styles["Recon Readiness %"] = amber
        else:
            styles["Recon Readiness %"] = red

    if "Recon Readiness Status" in row.index:
        status = str(row.get("Recon Readiness Status", ""))
        if status == "Ready":
            styles["Recon Readiness Status"] = green
        elif status == "Minor Review":
            styles["Recon Readiness Status"] = amber
        else:
            styles["Recon Readiness Status"] = red

    if "Feed Inventory (EndVar)" in row.index:
        if is_endvar_within_tolerance(row.get("Feed Inventory (EndVar)", 0)):
            styles["Feed Inventory (EndVar)"] = green
        else:
            styles["Feed Inventory (EndVar)"] = red

    return styles







def get_last_full_week_ending(ref_date=None):
    """
    Most recent completed Sunday week-ending.
    Example: Wed 06/05/2026 -> Sun 03/05/2026.
    If today is Sunday, use the previous Sunday because the current Sunday is not complete yet.
    """
    if ref_date is None:
        ref_date = pd.Timestamp.today().normalize()
    else:
        ref_date = pd.Timestamp(ref_date).normalize()

    days_back = (ref_date.weekday() + 1) % 7
    if days_back == 0:
        days_back = 7

    return (ref_date - pd.Timedelta(days=days_back)).normalize()


def classify_rearing_layer_for_price(df):
    """
    Returns a Series with Rearing / Layer / Other classification.
    Preferred: Entity Stage.
    Fallback: Age <= 18 is Rearing; Age > 18 and <= 90 is Layer.
    """
    if df is None or df.empty:
        return pd.Series(dtype="object")

    out = pd.Series("Other", index=df.index, dtype="object")

    stage_col = None
    for c in ["Entity Stage", "Stage", "Flock Stage"]:
        if c in df.columns:
            stage_col = c
            break

    age_col = None
    for c in ["Age", "Flock Age", "Age Weeks", "Age in weeks"]:
        if c in df.columns:
            age_col = c
            break

    if stage_col:
        stage = df[stage_col].astype(str).str.strip().str.lower()
        out = np.where(
            stage.str.contains("brood|rear|rearing", na=False),
            "Rearing",
            np.where(stage.str.contains("lay|layer", na=False), "Layer", "Other"),
        )
        out = pd.Series(out, index=df.index)

    if age_col:
        ages = pd.to_numeric(df[age_col], errors="coerce")
        out = pd.Series(
            np.where(
                out.eq("Other") & ages.le(18),
                "Rearing",
                np.where(out.eq("Other") & ages.gt(18) & ages.le(90), "Layer", out),
            ),
            index=df.index,
        )

    return out


def calc_avg_delivered_price_by_type_last_full_week(feedmill_df, farm_df=None, ref_date=None):
    """
    Calculates last-completed-week delivered price for Rearing and Layer.

    Uses feedmill rows when stage/age exists there.
    If feedmill lacks stage/age, tries to enrich from farm data via flock number.
    If that still cannot classify, uses farm report values as fallback:
      Feed Delivered tonnes + $FeedInventoryIn cost.
    """
    last_week = get_last_full_week_ending(ref_date)

    def blank_result():
        return {
            "week_ending": last_week,
            "rearing_avg": np.nan,
            "layer_avg": np.nan,
            "rearing_tonnes": 0.0,
            "layer_tonnes": 0.0,
        }

    # Preferred source: feedmill data.
    if feedmill_df is not None and not feedmill_df.empty:
        fm = feedmill_df.copy()

        week_col = None
        for c in ["Week Ending", "Week ending", "Week_Ending", "week_ending"]:
            if c in fm.columns:
                week_col = c
                break

        if week_col:
            fm["__week"] = pd.to_datetime(fm[week_col], errors="coerce").dt.normalize()
            fm = fm[fm["__week"].eq(last_week)].copy()

            if not fm.empty:
                tonnes_col = None
                for c in ["Tonnes Delivered", "Tonnes", "Delivered Tonnes", "Feed Delivered", "Quantity", "Qty", "Delivered Qty"]:
                    if c in fm.columns:
                        tonnes_col = c
                        break

                cost_col = None
                for c in ["Delivered Cost", "Delivered_Cost", "Cost", "Amount", "Total Cost", "DeliveredCost"]:
                    if c in fm.columns:
                        cost_col = c
                        break

                price_col = None
                for c in ["Delivered Price $/t", "Delivered Price", "Delivered_Price", "Price $/t", "$/t", "Rate"]:
                    if c in fm.columns:
                        price_col = c
                        break

                if tonnes_col:
                    fm["__tonnes"] = pd.to_numeric(fm[tonnes_col], errors="coerce").fillna(0)

                    if cost_col:
                        fm["__cost"] = pd.to_numeric(fm[cost_col], errors="coerce").fillna(0)
                    elif price_col:
                        fm["__price"] = pd.to_numeric(fm[price_col], errors="coerce")
                        fm["__cost"] = fm["__price"].fillna(0) * fm["__tonnes"]
                    else:
                        fm["__cost"] = np.nan

                    fm = fm[fm["__tonnes"].gt(0)].copy()

                    if not fm.empty and fm["__cost"].notna().any():
                        fm["__type"] = classify_rearing_layer_for_price(fm)

                        # Enrich with farm report if feedmill is unclassified.
                        if fm["__type"].eq("Other").all() and farm_df is not None and not farm_df.empty:
                            flock_feed_col = None
                            for c in ["Complex Flock No", "Entity No", "Flock No", "Flock", "Entity No"]:
                                if c in fm.columns:
                                    flock_feed_col = c
                                    break

                            flock_farm_col = None
                            for c in ["Complex Flock No", "Flock No", "Flock"]:
                                if c in farm_df.columns:
                                    flock_farm_col = c
                                    break

                            if flock_feed_col and flock_farm_col:
                                farm_cols = [flock_farm_col]
                                for c in ["Entity Stage", "Age"]:
                                    if c in farm_df.columns:
                                        farm_cols.append(c)
                                lookup = farm_df[farm_cols].drop_duplicates(subset=[flock_farm_col]).copy()

                                # Merge keys from Amino can arrive as mixed types
                                # e.g. feedmill Entity No as float64 and farm Complex Flock No as text.
                                # Convert both to clean strings before merging.
                                fm["__merge_flock_key"] = (
                                    fm[flock_feed_col]
                                    .astype(str)
                                    .str.strip()
                                    .str.replace(r"\.0$", "", regex=True)
                                )
                                lookup["__merge_flock_key"] = (
                                    lookup[flock_farm_col]
                                    .astype(str)
                                    .str.strip()
                                    .str.replace(r"\.0$", "", regex=True)
                                )

                                fm = fm.merge(
                                    lookup.drop(columns=[flock_farm_col], errors="ignore"),
                                    on="__merge_flock_key",
                                    how="left",
                                    suffixes=("", "_farm"),
                                )

                                # Use farm-stage/age classification.
                                classify_df = pd.DataFrame(index=fm.index)
                                if "Entity Stage_farm" in fm.columns:
                                    classify_df["Entity Stage"] = fm["Entity Stage_farm"]
                                elif "Entity Stage" in fm.columns:
                                    classify_df["Entity Stage"] = fm["Entity Stage"]
                                if "Age_farm" in fm.columns:
                                    classify_df["Age"] = fm["Age_farm"]
                                elif "Age" in fm.columns:
                                    classify_df["Age"] = fm["Age"]

                                fm["__type"] = classify_rearing_layer_for_price(classify_df)

                        def avg_for(t):
                            sub = fm[fm["__type"].eq(t)]
                            tonnes = sub["__tonnes"].sum()
                            if tonnes <= 0:
                                return np.nan, 0.0
                            return sub["__cost"].sum() / tonnes, float(tonnes)

                        rearing_avg, rearing_tonnes = avg_for("Rearing")
                        layer_avg, layer_tonnes = avg_for("Layer")

                        # If at least one type worked, return it.
                        if pd.notna(rearing_avg) or pd.notna(layer_avg):
                            return {
                                "week_ending": last_week,
                                "rearing_avg": rearing_avg,
                                "layer_avg": layer_avg,
                                "rearing_tonnes": rearing_tonnes,
                                "layer_tonnes": layer_tonnes,
                            }

    # Fallback source: farm report.
    if farm_df is not None and not farm_df.empty:
        fr = farm_df.copy()

        week_col = None
        for c in ["Week Ending", "Week ending", "Week_Ending", "week_ending"]:
            if c in fr.columns:
                week_col = c
                break

        if week_col:
            fr["__week"] = pd.to_datetime(fr[week_col], errors="coerce").dt.normalize()
            fr = fr[fr["__week"].eq(last_week)].copy()

        if fr.empty:
            return blank_result()

        delivered_col = None
        for c in ["Feed Delivered", "Feed Delivered Kg", "Delivered Kg"]:
            if c in fr.columns:
                delivered_col = c
                break

        cost_col = None
        for c in ["$FeedInventoryIn", "Delivered Cost", "Delivered_Cost", "Feed Delivered Cost"]:
            if c in fr.columns:
                cost_col = c
                break

        if delivered_col and cost_col:
            fr["__delivered_kg"] = pd.to_numeric(fr[delivered_col], errors="coerce").fillna(0)
            fr["__tonnes"] = fr["__delivered_kg"] / 1000.0
            fr["__cost"] = pd.to_numeric(fr[cost_col], errors="coerce").fillna(0)
            fr = fr[fr["__tonnes"].gt(0)].copy()
            fr["__type"] = classify_rearing_layer_for_price(fr)

            def avg_for(t):
                sub = fr[fr["__type"].eq(t)]
                tonnes = sub["__tonnes"].sum()
                if tonnes <= 0:
                    return np.nan, 0.0
                return sub["__cost"].sum() / tonnes, float(tonnes)

            rearing_avg, rearing_tonnes = avg_for("Rearing")
            layer_avg, layer_tonnes = avg_for("Layer")
            return {
                "week_ending": last_week,
                "rearing_avg": rearing_avg,
                "layer_avg": layer_avg,
                "rearing_tonnes": rearing_tonnes,
                "layer_tonnes": layer_tonnes,
            }

    return blank_result()




def build_weekly_delivered_price_by_type(feedmill_df, farm_df=None):
    """
    Build weighted delivered feed price by week for Rearing and Layers.

    Farm report is preferred for the split because it has Entity Stage/Age and
    the delivered-feed value. Feedmill is only used as fallback when it can be
    classified.
    """
    # ------------------------------------------------------------
    # Preferred source: prepared farm report
    # ------------------------------------------------------------
    if farm_df is not None and not farm_df.empty:
        fr = farm_df.copy()

        week_col = None
        for c in ["Week Ending", "Week ending", "Week_Ending", "week_ending"]:
            if c in fr.columns:
                week_col = c
                break

        delivered_col = None
        for c in ["Farm Delivered kg", "Feed Delivered", "Feed Delivered Kg", "Delivered Kg"]:
            if c in fr.columns:
                delivered_col = c
                break

        cost_col = None
        for c in ["Feed Delivered $", "$FeedInventoryIn", "Delivered Cost", "Delivered_Cost", "Feed Delivered Cost"]:
            if c in fr.columns:
                cost_col = c
                break

        if week_col and delivered_col and cost_col:
            fr["__week"] = pd.to_datetime(fr[week_col], errors="coerce").dt.normalize()
            fr["__tonnes"] = pd.to_numeric(fr[delivered_col], errors="coerce").fillna(0) / 1000.0
            fr["__cost"] = pd.to_numeric(fr[cost_col], errors="coerce").fillna(0)
            fr["__type"] = classify_rearing_layer_for_price(fr)

            fr = fr[
                fr["__week"].notna()
                & fr["__tonnes"].gt(0)
                & fr["__cost"].gt(0)
                & fr["__type"].isin(["Rearing", "Layer"])
            ].copy()

            if not fr.empty:
                weekly = (
                    fr.groupby(["__week", "__type"], dropna=False)
                    .agg(Tonnes=("__tonnes", "sum"), Cost=("__cost", "sum"))
                    .reset_index()
                )
                weekly = weekly[weekly["Tonnes"].gt(0)].copy()
                weekly["Delivered Price $/t"] = weekly["Cost"] / weekly["Tonnes"]
                weekly["Type"] = weekly["__type"].replace({"Layer": "Layers"})
                weekly = weekly.rename(columns={"__week": "Week Ending"})

                latest_weeks = sorted(pd.to_datetime(weekly["Week Ending"]).dropna().unique())[-5:]
                weekly = weekly[weekly["Week Ending"].isin(latest_weeks)].copy()
                weekly = weekly.sort_values(["Week Ending", "Type"]).reset_index(drop=True)
                return weekly[["Week Ending", "Type", "Tonnes", "Delivered Price $/t"]]

    # ------------------------------------------------------------
    # Fallback source: feedmill, if it already has enough stage/age data
    # ------------------------------------------------------------
    if feedmill_df is None or feedmill_df.empty:
        return pd.DataFrame()

    df = feedmill_df.copy()

    week_col = None
    for c in ["Week Ending", "Week ending", "Week_Ending", "week_ending"]:
        if c in df.columns:
            week_col = c
            break

    if week_col is None:
        for c in ["TransDate", "Trans Date", "Date", "Delivery Date"]:
            if c in df.columns:
                df["__week"] = pd.to_datetime(df[c], errors="coerce")
                week_col = "__week"
                break

    if week_col is None:
        return pd.DataFrame()

    if week_col != "__week":
        df["__week"] = pd.to_datetime(df[week_col], errors="coerce")

    df = df[df["__week"].notna()].copy()
    if df.empty:
        return pd.DataFrame()

    tonnes_col = None
    for c in ["Tonnes Delivered", "Tonnes", "Delivered Tonnes", "Feed Delivered", "Quantity", "Qty", "Delivered Qty"]:
        if c in df.columns:
            tonnes_col = c
            break

    cost_col = None
    for c in ["Delivered Cost", "Delivered_Cost", "Cost", "Amount", "Total Cost", "DeliveredCost"]:
        if c in df.columns:
            cost_col = c
            break

    price_col = None
    for c in ["Delivered Price $/t", "Delivered Price", "Delivered_Price", "Price $/t", "$/t", "Rate"]:
        if c in df.columns:
            price_col = c
            break

    if tonnes_col is None:
        return pd.DataFrame()

    df["__tonnes"] = pd.to_numeric(df[tonnes_col], errors="coerce").fillna(0)

    if cost_col is not None:
        df["__cost"] = pd.to_numeric(df[cost_col], errors="coerce").fillna(0)
    elif price_col is not None:
        df["__price"] = pd.to_numeric(df[price_col], errors="coerce")
        df["__cost"] = df["__price"].fillna(0) * df["__tonnes"]
    else:
        return pd.DataFrame()

    df = df[df["__tonnes"].gt(0)].copy()
    if df.empty:
        return pd.DataFrame()

    df["__type"] = classify_rearing_layer_for_price(df)

    weekly = (
        df[df["__type"].isin(["Rearing", "Layer"])]
        .groupby(["__week", "__type"], dropna=False)
        .agg(Tonnes=("__tonnes", "sum"), Cost=("__cost", "sum"))
        .reset_index()
    )

    if weekly.empty:
        return weekly

    weekly = weekly[weekly["Tonnes"].gt(0)].copy()
    weekly["Delivered Price $/t"] = weekly["Cost"] / weekly["Tonnes"]
    weekly["Type"] = weekly["__type"].replace({"Layer": "Layers"})
    weekly = weekly.rename(columns={"__week": "Week Ending"})

    latest_weeks = sorted(pd.to_datetime(weekly["Week Ending"]).dropna().unique())[-5:]
    weekly = weekly[weekly["Week Ending"].isin(latest_weeks)].copy()
    weekly = weekly.sort_values(["Week Ending", "Type"]).reset_index(drop=True)
    return weekly[["Week Ending", "Type", "Tonnes", "Delivered Price $/t"]]



def render_rearing_layer_trend_chart(feedmill_df, farm_df=None):
    weekly_type = build_weekly_delivered_price_by_type(feedmill_df, farm_df)

    if weekly_type.empty:
        st.warning("No Rearing / Layers feed price trend could be built. Check that the farm report has Week Ending, Entity Stage/Age, Feed Delivered, and $FeedInventoryIn values.")
        return

    fig = px.line(
        weekly_type,
        x="Week Ending",
        y="Delivered Price $/t",
        color="Type",
        markers=True,
        category_orders={"Type": ["Rearing", "Layers"]},
        title="Weighted delivered feed price by week — Rearing vs Layers",
    )
    fig.update_layout(height=390, margin=dict(l=20, r=20, t=50, b=20), legend_title_text="Type")
    fig.update_yaxes(tickprefix="$", title="Delivered Price $/t")
    st.plotly_chart(fig, use_container_width=True)

def render_brood_layer_price_perspective(feedmill_df, farm_df=None):
    """
    render_brood_layer_price_perspective(feedmill, farm)
    Replaces the raw Weekly feedmill summary with a useful interpretation:
    Business / Brood / Layer average delivered feed price by week.
    """
    try:
        if feedmill_df is None or feedmill_df.empty:
            st.info("No feedmill delivery data available for price movement perspective.")
            return

        df = feedmill_df.copy()

        week_col = None
        for c in ["Week Ending", "Week ending", "Week_Ending", "week_ending"]:
            if c in df.columns:
                week_col = c
                break

        if week_col is None:
            for c in ["TransDate", "Trans Date", "Date"]:
                if c in df.columns:
                    df["Week Ending"] = pd.to_datetime(df[c], errors="coerce")
                    week_col = "Week Ending"
                    break

        if week_col is None:
            st.info("Price movement perspective needs a Week Ending column in the feedmill data.")
            return

        df["__week"] = pd.to_datetime(df[week_col], errors="coerce")
        df = df[df["__week"].notna()].copy()
        if df.empty:
            return

        tonnes_col = None
        for c in ["Tonnes", "Delivered Tonnes", "Feed Delivered", "Quantity", "Qty", "Delivered Qty"]:
            if c in df.columns:
                tonnes_col = c
                break

        cost_col = None
        for c in ["Delivered_Cost", "Delivered Cost", "Cost", "Amount", "Total Cost", "DeliveredCost"]:
            if c in df.columns:
                cost_col = c
                break

        price_col = None
        for c in ["Delivered Price $/t", "Delivered Price", "Delivered_Price", "Price $/t", "$/t", "Rate"]:
            if c in df.columns:
                price_col = c
                break

        if tonnes_col is None:
            st.info("Price movement perspective needs delivered tonnes in the feedmill data.")
            return

        df["__tonnes"] = pd.to_numeric(df[tonnes_col], errors="coerce").fillna(0)

        if cost_col is not None:
            df["__cost"] = pd.to_numeric(df[cost_col], errors="coerce").fillna(0)
        elif price_col is not None:
            df["__price_raw"] = pd.to_numeric(df[price_col], errors="coerce")
            df["__cost"] = df["__price_raw"].fillna(0) * df["__tonnes"]
        else:
            st.info("Price movement perspective needs delivered cost or delivered price in the feedmill data.")
            return

        df = df[df["__tonnes"].gt(0)].copy()
        if df.empty:
            st.info("No positive delivered tonnes found for price movement perspective.")
            return

        stage_col = None
        for c in ["Entity Stage", "Stage", "Flock Stage"]:
            if c in df.columns:
                stage_col = c
                break

        age_col = None
        for c in ["Age", "Flock Age", "Age Weeks", "Age in weeks"]:
            if c in df.columns:
                age_col = c
                break

        if stage_col is not None:
            stage_text = df[stage_col].astype(str).str.lower()
            df["__type"] = np.where(
                stage_text.str.contains("brood|rear|rearing", na=False),
                "Brood",
                np.where(stage_text.str.contains("lay|layer", na=False), "Layer", "Other"),
            )
        elif age_col is not None:
            ages = pd.to_numeric(df[age_col], errors="coerce")
            df["__type"] = np.where(ages.le(18), "Brood", np.where(ages.gt(18) & ages.le(90), "Layer", "Other"))
        else:
            df["__type"] = "Other"

        if df["__type"].eq("Other").all() and farm_df is not None and not farm_df.empty:
            flock_feed_col = None
            for c in ["Complex Flock No", "Entity No", "Flock No", "Flock"]:
                if c in df.columns:
                    flock_feed_col = c
                    break

            flock_farm_col = None
            for c in ["Complex Flock No", "Flock No", "Flock"]:
                if c in farm_df.columns:
                    flock_farm_col = c
                    break

            if flock_feed_col and flock_farm_col:
                farm_lookup_cols = [flock_farm_col]
                if "Entity Stage" in farm_df.columns:
                    farm_lookup_cols.append("Entity Stage")
                if "Age" in farm_df.columns:
                    farm_lookup_cols.append("Age")
                lookup = farm_df[farm_lookup_cols].drop_duplicates(subset=[flock_farm_col]).copy()
                df = df.merge(lookup, left_on=flock_feed_col, right_on=flock_farm_col, how="left", suffixes=("", "_farm"))

                if "Entity Stage_farm" in df.columns:
                    stage_text = df["Entity Stage_farm"].astype(str).str.lower()
                elif "Entity Stage" in df.columns:
                    stage_text = df["Entity Stage"].astype(str).str.lower()
                else:
                    stage_text = pd.Series("", index=df.index)

                if "Age_farm" in df.columns:
                    ages = pd.to_numeric(df["Age_farm"], errors="coerce")
                elif "Age" in df.columns:
                    ages = pd.to_numeric(df["Age"], errors="coerce")
                else:
                    ages = pd.Series(np.nan, index=df.index)

                df["__type"] = np.where(
                    stage_text.str.contains("brood|rear|rearing", na=False) | ages.le(18),
                    "Brood",
                    np.where(stage_text.str.contains("lay|layer", na=False) | (ages.gt(18) & ages.le(90)), "Layer", "Other"),
                )

        def weighted_avg(group):
            tonnes = group["__tonnes"].sum()
            cost = group["__cost"].sum()
            if tonnes <= 0:
                return np.nan
            return cost / tonnes

        weeks = sorted(df["__week"].dropna().unique())[-5:]
        rows = []
        for wk in weeks:
            wkdf = df[df["__week"].eq(wk)].copy()
            business_avg = weighted_avg(wkdf)

            brood_df = wkdf[wkdf["__type"].eq("Brood")]
            layer_df = wkdf[wkdf["__type"].eq("Layer")]

            brood_avg = weighted_avg(brood_df) if not brood_df.empty else np.nan
            layer_avg = weighted_avg(layer_df) if not layer_df.empty else np.nan

            rows.append({
                "Week Ending": pd.to_datetime(wk),
                "Business Avg $/t": business_avg,
                "Brood Avg $/t": brood_avg,
                "Layer Avg $/t": layer_avg,
                "Tonnes": wkdf["__tonnes"].sum(),
                "Brood Tonnes": brood_df["__tonnes"].sum() if not brood_df.empty else 0,
                "Layer Tonnes": layer_df["__tonnes"].sum() if not layer_df.empty else 0,
            })

        summary = pd.DataFrame(rows)
        if summary.empty:
            return

        summary["Business Δ"] = summary["Business Avg $/t"].diff()
        summary["Brood Δ"] = summary["Brood Avg $/t"].diff()
        summary["Layer Δ"] = summary["Layer Avg $/t"].diff()

        def note_for_row(row):
            b = row.get("Business Δ", np.nan)
            brood = row.get("Brood Δ", np.nan)
            layer = row.get("Layer Δ", np.nan)

            if pd.isna(b):
                return "First visible week"
            if pd.isna(brood) and pd.isna(layer):
                return "No Brood/Layer split available"
            if pd.isna(brood):
                return "Layer movement only"
            if pd.isna(layer):
                return "Brood movement only"
            if abs(layer) > abs(brood) + 2:
                return "Layer driving movement"
            if abs(brood) > abs(layer) + 2:
                return "Brood driving movement"
            if b > 2:
                return "Both broadly dearer"
            if b < -2:
                return "Both broadly improved"
            return "Minimal movement"

        summary["Notes"] = summary.apply(note_for_row, axis=1)

        latest = summary.iloc[-1]
        latest_business = latest["Business Avg $/t"]
        latest_brood = latest["Brood Avg $/t"]
        latest_layer = latest["Layer Avg $/t"]
        business_delta = latest["Business Δ"] if pd.notna(latest["Business Δ"]) else np.nan
        weekly_impact = business_delta * latest["Tonnes"] if pd.notna(business_delta) else np.nan

        def money_or_dash(value):
            if pd.isna(value):
                return "—"
            return f"${value:,.2f}/t"

        def delta_or_dash(value):
            if pd.isna(value):
                return "—"
            return f"{value:+,.2f}/t"

        def card_colour(value):
            if pd.isna(value):
                return ("#F8FAFC", "#475569")
            if value > 0:
                return ("#FEF2F2", "#991B1B")
            if value < 0:
                return ("#ECFDF3", "#166534")
            return ("#EFF6FF", "#1D4ED8")

        delta_bg, delta_fg = card_colour(business_delta)
        weekly_impact_text = "—" if pd.isna(weekly_impact) else f"${weekly_impact:,.0f}"

        st.markdown("### Price Movement Perspective")
        st.caption("Explains the delivered feed price graph by splitting weighted average price into Business, Brood/Rearing, and Layer movement.")

        st.markdown(
            f"""
            <div style="display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-bottom:14px;">
                <div style="background:white; border:1px solid #E5E7EB; border-radius:14px; padding:14px;">
                    <div style="font-size:11px; text-transform:uppercase; color:#64748B; font-weight:900;">Business Avg This Week</div>
                    <div style="font-size:23px; font-weight:950; color:#0F172A;">{money_or_dash(latest_business)}</div>
                    <div style="font-size:12px; color:#64748B;">Weighted delivered price</div>
                </div>
                <div style="background:{delta_bg}; border:1px solid #E5E7EB; border-radius:14px; padding:14px;">
                    <div style="font-size:11px; text-transform:uppercase; color:#64748B; font-weight:900;">Change vs Last Week</div>
                    <div style="font-size:23px; font-weight:950; color:{delta_fg};">{delta_or_dash(business_delta)}</div>
                    <div style="font-size:12px; color:#64748B;">~{weekly_impact_text} weekly impact</div>
                </div>
                <div style="background:white; border:1px solid #E5E7EB; border-radius:14px; padding:14px;">
                    <div style="font-size:11px; text-transform:uppercase; color:#64748B; font-weight:900;">Brood Avg This Week</div>
                    <div style="font-size:23px; font-weight:950; color:#0F172A;">{money_or_dash(latest_brood)}</div>
                    <div style="font-size:12px; color:#64748B;">Rearing / Brood deliveries</div>
                </div>
                <div style="background:white; border:1px solid #E5E7EB; border-radius:14px; padding:14px;">
                    <div style="font-size:11px; text-transform:uppercase; color:#64748B; font-weight:900;">Layer Avg This Week</div>
                    <div style="font-size:23px; font-weight:950; color:#0F172A;">{money_or_dash(latest_layer)}</div>
                    <div style="font-size:12px; color:#64748B;">Layer deliveries</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        display = summary.copy()
        display["Week Ending"] = display["Week Ending"].dt.strftime("%d/%m/%Y")
        display_cols = [
            "Week Ending",
            "Business Avg $/t",
            "Business Δ",
            "Brood Avg $/t",
            "Brood Δ",
            "Layer Avg $/t",
            "Layer Δ",
            "Notes",
        ]
        display = display[display_cols]

        def style_delta_cols(row):
            styles = pd.Series("", index=row.index)
            for col in ["Business Δ", "Brood Δ", "Layer Δ"]:
                if col not in row.index:
                    continue
                val = pd.to_numeric(row[col], errors="coerce")
                if pd.isna(val):
                    styles[col] = "background-color:#F8FAFC; color:#94A3B8; font-weight:800;"
                elif val > 0:
                    styles[col] = "background-color:#FEE2E2; color:#991B1B; font-weight:900;"
                elif val < 0:
                    styles[col] = "background-color:#DCFCE7; color:#166534; font-weight:900;"
                else:
                    styles[col] = "background-color:#EFF6FF; color:#1D4ED8; font-weight:900;"
            return styles

        fmt = {
            "Business Avg $/t": lambda x: "—" if pd.isna(x) else f"${x:,.2f}",
            "Business Δ": lambda x: "—" if pd.isna(x) else f"{x:+,.2f}",
            "Brood Avg $/t": lambda x: "—" if pd.isna(x) else f"${x:,.2f}",
            "Brood Δ": lambda x: "—" if pd.isna(x) else f"{x:+,.2f}",
            "Layer Avg $/t": lambda x: "—" if pd.isna(x) else f"${x:,.2f}",
            "Layer Δ": lambda x: "—" if pd.isna(x) else f"{x:+,.2f}",
        }

        st.markdown("#### Brood vs Layer price by week")
        st.dataframe(
            display.style.apply(style_delta_cols, axis=1).format(fmt),
            use_container_width=True,
            hide_index=True,
            height=230,
        )

        if pd.isna(business_delta):
            overall = "There is not enough prior-week data to calculate movement yet."
        elif business_delta > 2:
            overall = "Overall delivered feed price increased this week."
        elif business_delta < -2:
            overall = "Overall delivered feed price eased this week."
        else:
            overall = "Overall delivered feed price was broadly steady this week."

        brood_delta = latest.get("Brood Δ", np.nan)
        layer_delta = latest.get("Layer Δ", np.nan)

        if pd.notna(brood_delta) and pd.notna(layer_delta):
            if abs(layer_delta) > abs(brood_delta) + 2:
                driver = "Layer pricing appears to be the main driver of the movement."
            elif abs(brood_delta) > abs(layer_delta) + 2:
                driver = "Brood/Rearing pricing appears to be the main driver of the movement."
            else:
                driver = "Brood and Layer pricing moved broadly together."
        elif pd.notna(layer_delta):
            driver = "Only Layer movement is available for the latest comparison."
        elif pd.notna(brood_delta):
            driver = "Only Brood/Rearing movement is available for the latest comparison."
        else:
            driver = "The Brood/Layer split is not available for the latest comparison."

        impact_text = ""
        if pd.notna(weekly_impact):
            if weekly_impact > 0:
                impact_text = f" At this week's tonnes, that represents about ${weekly_impact:,.0f} higher weekly feed cost than last week."
            elif weekly_impact < 0:
                impact_text = f" At this week's tonnes, that represents about ${abs(weekly_impact):,.0f} lower weekly feed cost than last week."

        st.markdown(
            f"""
            <div style="border:1px solid #D9E2EC; background:#F8FAFC; border-radius:14px; padding:14px 16px; margin-top:10px;">
                <div style="font-weight:950; color:#0F172A; margin-bottom:6px;">What changed this week?</div>
                <div style="color:#334155; font-size:13px; line-height:1.5;">
                    {overall} {driver}{impact_text}
                    Review ration/formula changes, transport impact, raw material movement, and recon confidence before treating the movement as a farm performance issue.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    except Exception as e:
        st.caption(f"Price movement perspective unavailable: {e}")




def clean_display_farm_name_series(df, farm_name_col="Farm Name", farm_no_col="Farm No"):
    """
    Prevents missing farm names showing as 'nan' in user-facing tables.
    Uses Farm No as fallback where possible.
    """
    if df is None or df.empty:
        return pd.Series(dtype="object")

    if farm_name_col in df.columns:
        names = df[farm_name_col].astype(str).str.strip()
    else:
        names = pd.Series("", index=df.index)

    missing = names.str.lower().isin(["", "nan", "none", "nat", "<na>"])

    if farm_no_col in df.columns:
        farm_no = df[farm_no_col].astype(str).str.strip()
        farm_no_missing = farm_no.str.lower().isin(["", "nan", "none", "nat", "<na>"])
        names = np.where(
            missing & ~farm_no_missing,
            "Unknown farm " + farm_no,
            names,
        )
        names = pd.Series(names, index=df.index)
        missing = names.astype(str).str.strip().str.lower().isin(["", "nan", "none", "nat", "<na>"])

    names = np.where(missing, "Unknown / unmapped farm", names)
    return pd.Series(names, index=df.index)



def render_farm_recon_score_insights(farm_df, farm_summary_df):
    """
    Insights block: Farm score shown in a premium tracker-style table.
    Worst farms appear first. The table focuses on who still needs follow-up,
    while still showing recent score direction.
    """
    try:
        if farm_df is None or farm_df.empty:
            return

        if "Week Ending" in farm_df.columns:
            week_values = pd.to_datetime(farm_df["Week Ending"], errors="coerce").dropna().sort_values().unique()
            recent_weeks = list(week_values[-5:])
        else:
            recent_weeks = [pd.Timestamp.today()]

        if not recent_weeks:
            recent_weeks = [pd.Timestamp.today()]

        farm_week_rows = []

        for wk in recent_weeks:
            recon = build_current_recon_static_week_df(farm_df, farm_summary_df, pd.to_datetime(wk))
            recon = add_recon_readiness_scores(recon)
            if recon is None or recon.empty:
                continue
            if "Farm Name" not in recon.columns:
                continue

            agg_kwargs = {
                "Sheds": pd.NamedAgg(column="Recon Readiness %", aggfunc="size"),
                "Farm_Score": pd.NamedAgg(column="Recon Readiness %", aggfunc="mean"),
                "Follow_Up_Rows": pd.NamedAgg(column="Recon Readiness %", aggfunc=lambda s: (pd.to_numeric(s, errors="coerce") < 100).sum()),
            }
            if "Recon Match Type" in recon.columns:
                agg_kwargs["Missing_Data"] = pd.NamedAgg(column="Recon Match Type", aggfunc=lambda s: s.astype(str).eq("Missing selected week data").sum())
            else:
                recon["__missing_data"] = 0
                agg_kwargs["Missing_Data"] = pd.NamedAgg(column="__missing_data", aggfunc="sum")

            if "Variance OK" in recon.columns:
                agg_kwargs["Outside_3t"] = pd.NamedAgg(column="Variance OK", aggfunc=lambda s: (~s.fillna(False)).sum())
            else:
                recon["__outside_3t"] = 0
                agg_kwargs["Outside_3t"] = pd.NamedAgg(column="__outside_3t", aggfunc="sum")

            if "Area Manager" in recon.columns:
                agg_kwargs["Area Manager"] = pd.NamedAgg(column="Area Manager", aggfunc="first")

            weekly = recon.groupby("Farm Name", dropna=False).agg(**agg_kwargs).reset_index()
            weekly["Week Ending"] = pd.to_datetime(wk)
            weekly["Farm_Score"] = weekly["Farm_Score"].round(0).astype(int)
            weekly["Follow-up %"] = ((weekly["Follow_Up_Rows"] / weekly["Sheds"]).fillna(0) * 100).round(0).astype(int)
            farm_week_rows.append(weekly)

        if not farm_week_rows:
            return

        all_scores = pd.concat(farm_week_rows, ignore_index=True)
        all_scores["Week Ending"] = pd.to_datetime(all_scores["Week Ending"], errors="coerce")
        latest_week = all_scores["Week Ending"].max()
        latest = all_scores[all_scores["Week Ending"].eq(latest_week)].copy()
        if latest.empty:
            return

        def delta_text(delta):
            if pd.isna(delta):
                return "—"
            delta = float(delta)
            if delta > 0:
                return f"↑ +{delta:.0f}%"
            if delta < 0:
                return f"↓ {delta:.0f}%"
            return "→ 0%"

        series_history = {}
        delta_history = {}
        for farm_name, grp in all_scores.groupby("Farm Name", dropna=False):
            hist = grp.sort_values("Week Ending")
            scores = [int(round(float(x))) for x in pd.to_numeric(hist["Farm_Score"], errors="coerce").dropna().tolist()]
            if not scores:
                scores = [0]
            series_history[str(farm_name)] = ",".join(str(x) for x in scores[-5:])
            if len(scores) >= 2:
                delta_history[str(farm_name)] = round(float(scores[-1]) - float(scores[-2]), 1)
            else:
                delta_history[str(farm_name)] = np.nan

        latest["Farm Score %"] = latest["Farm_Score"].astype(int)
        latest["Farm Score Series"] = latest["Farm Name"].astype(str).map(series_history)
        latest["vs Last Week Num"] = latest["Farm Name"].astype(str).map(delta_history)
        latest["vs Last Week"] = latest["vs Last Week Num"].apply(delta_text)
        latest["Farm Score"] = latest["Farm Score %"].astype(int).astype(str) + "%"

        def build_farm_focus_note(row):
            score = pd.to_numeric(row.get("Farm Score %"), errors="coerce")
            sheds = pd.to_numeric(row.get("Sheds"), errors="coerce")
            follow = pd.to_numeric(row.get("Follow_Up_Rows"), errors="coerce")
            missing = pd.to_numeric(row.get("Missing_Data"), errors="coerce")
            outside = pd.to_numeric(row.get("Outside_3t"), errors="coerce")

            score = 0 if pd.isna(score) else int(score)
            sheds = 0 if pd.isna(sheds) else int(sheds)
            follow = 0 if pd.isna(follow) else int(follow)
            missing = 0 if pd.isna(missing) else int(missing)
            outside = 0 if pd.isna(outside) else int(outside)

            if sheds > 0 and follow == 0 and missing == 0 and outside == 0 and score >= 95:
                return "Ready for pricing"
            if missing > 0 and outside > 0:
                return f"{missing} shed(s) missing data; {outside} outside ±3t"
            if missing > 0:
                return f"{missing} shed(s) missing data"
            if outside > 0:
                return f"{outside} shed(s) outside ±3t"
            if follow > 0:
                return f"Review {follow} shed(s) needing follow-up"
            if score >= 80:
                return "Mostly complete; minor follow-up"
            return "Follow-up needed"

        latest["Status"] = latest.apply(build_farm_focus_note, axis=1)
        latest = latest.rename(columns={
            "Follow_Up_Rows": "Sheds Needing Follow-up",
            "Missing_Data": "Missing Data",
            "Outside_3t": "Outside ±3t",
        })

        latest = latest.sort_values(
            ["Farm Score %", "Follow-up %", "Sheds Needing Follow-up", "Farm Name"],
            ascending=[True, False, False, True],
        ).reset_index(drop=True)

        st.markdown("### Farm score")
        st.caption(
            "Worst farms at the top. Farm score shows pricing-readiness. A Feed Inventory EndVar between -3,000 kg and +3,000 kg is treated as acceptable."
        )

        latest["Farm Name"] = clean_display_farm_name_series(latest, "Farm Name", "Farm No")
        display = latest.copy()
        if "Area Manager" not in display.columns:
            display["Area Manager"] = ""

        visible_cols = [
            "Farm Name",
            "Farm Score",
            "vs Last Week",
            "Sheds",
            "Sheds Needing Follow-up",
            "Missing Data",
            "Outside ±3t",
            "Status",
        ]
        visible_cols = [c for c in visible_cols if c in display.columns]
        helper_cols = [c for c in ["Farm Score %", "vs Last Week Num", "Farm Score Series"] if c in display.columns]
        grid_df = display[visible_cols + helper_cols].copy()

        # Short display names keep the Farm Score table inside the screen width.
        grid_df = grid_df.rename(columns={
            "Sheds Needing Follow-up": "Follow-up",
            "Missing Data": "Missing",
            "Outside ±3t": "±3t Var",
            "vs Last Week": "vs Last",
        })
        visible_cols = [c if c not in {
            "Sheds Needing Follow-up": "Follow-up",
            "Missing Data": "Missing",
            "Outside ±3t": "±3t Var",
            "vs Last Week": "vs Last",
        } else {
            "Sheds Needing Follow-up": "Follow-up",
            "Missing Data": "Missing",
            "Outside ±3t": "±3t Var",
            "vs Last Week": "vs Last",
        }[c] for c in visible_cols]

        if not HAS_AGGRID:
            st.dataframe(grid_df[visible_cols], use_container_width=True, hide_index=True, height=760)
            st.divider()
            return

        gb = GridOptionsBuilder.from_dataframe(grid_df)
        gb.configure_default_column(
            resizable=True,
            sortable=True,
            filter=True,
            wrapText=False,
            autoHeight=False,
            minWidth=70,
            flex=1,
        )

        for c in helper_cols:
            gb.configure_column(c, hide=True)

        if "Farm Name" in grid_df.columns:
            gb.configure_column("Farm Name", pinned="left", minWidth=180, flex=2)

        base_style = JsCode("""
        function(params) {
            return {
                fontSize:'13px',
                fontWeight:'600',
                color:'#0F172A',
                display:'flex',
                alignItems:'center'
            };
        }
        """)

        score_style = JsCode("""
        function(params) {
            const score = Number(params.data['Farm Score %']);
            if (isNaN(score)) {
                return {backgroundColor:'#F8FAFC', color:'#475569', fontWeight:'800'};
            }
            if (score >= 95) {
                return {backgroundColor:'#ECFDF3', color:'#166534', fontWeight:'900'};
            }
            if (score >= 80) {
                return {backgroundColor:'#FEF3C7', color:'#92400E', fontWeight:'900'};
            }
            return {backgroundColor:'#FEF2F2', color:'#B91C1C', fontWeight:'900'};
        }
        """)

        score_renderer = JsCode("""
        class FarmScoreArrowRenderer {
            init(params) {
                this.eGui = document.createElement('div');
                const score = Number(params.data['Farm Score %']);
                const raw = String(params.data['Farm Score Series'] || '');
                const values = raw.split(',').map(x => Number(x)).filter(x => !isNaN(x));
                const spark = this.buildSpark(values);
                this.eGui.innerHTML = `
                    <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;width:100%;">
                        <div style="font-weight:900;font-size:13px;min-width:42px;">${isNaN(score) ? '' : score + '%'}</div>
                        <div style="flex:1;display:flex;justify-content:flex-end;">${spark}</div>
                    </div>`;
            }
            buildSpark(values) {
                if (!values || values.length === 0) {
                    return '<div style="color:#94A3B8;font-size:12px;">—</div>';
                }
                const width = 72, height = 18, pad = 2;
                const usableW = width - pad * 2;
                const usableH = height - pad * 2;
                const points = values.map((v, i) => {
                    const x = pad + (values.length === 1 ? usableW / 2 : (i * usableW / (values.length - 1)));
                    const y = pad + (100 - Math.max(0, Math.min(100, v))) / 100 * usableH;
                    return [x, y];
                });
                const last = points[points.length - 1];
                const prev = points.length > 1 ? points[points.length - 2] : [last[0] - 8, last[1]];
                let color = '#1D4ED8';
                if (last[1] < prev[1]) color = '#15803D';
                else if (last[1] > prev[1]) color = '#B91C1C';
                const poly = points.map(p => p.join(',')).join(' ');
                const angle = Math.atan2(last[1] - prev[1], last[0] - prev[0]);
                const size = 4;
                const a1 = angle + Math.PI * 0.82;
                const a2 = angle - Math.PI * 0.82;
                const p1x = last[0] + size * Math.cos(a1);
                const p1y = last[1] + size * Math.sin(a1);
                const p2x = last[0] + size * Math.cos(a2);
                const p2y = last[1] + size * Math.sin(a2);
                return `
                <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
                    <polyline points="${poly}" fill="none" stroke="${color}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="${last[0]}" cy="${last[1]}" r="1.8" fill="${color}" />
                    <polygon points="${last[0]},${last[1]} ${p1x},${p1y} ${p2x},${p2y}" fill="${color}" />
                </svg>`;
            }
            getGui() { return this.eGui; }
        }
        """)

        delta_style = JsCode("""
        function(params) {
            const delta = Number(params.data['vs Last Week Num']);
            if (isNaN(delta)) {
                return {backgroundColor:'#F8FAFC', color:'#64748B', fontWeight:'800'};
            }
            if (delta > 0) {
                return {backgroundColor:'#DCFCE7', color:'#166534', fontWeight:'900'};
            }
            if (delta < 0) {
                return {backgroundColor:'#FEE2E2', color:'#B91C1C', fontWeight:'900'};
            }
            return {backgroundColor:'#DBEAFE', color:'#1D4ED8', fontWeight:'900'};
        }
        """)

        count_style = JsCode("""
        function(params) {
            const val = Number(params.value);
            if (isNaN(val)) {
                return {color:'#475569', fontWeight:'800'};
            }
            if (val <= 0) {
                return {backgroundColor:'#ECFDF3', color:'#166534', fontWeight:'900'};
            }
            if (val <= 2) {
                return {backgroundColor:'#FEF3C7', color:'#92400E', fontWeight:'900'};
            }
            return {backgroundColor:'#FEF2F2', color:'#B91C1C', fontWeight:'900'};
        }
        """)

        status_style = JsCode("""
        function(params) {
            const val = String(params.value || '').toLowerCase();
            if (val.includes('ready for pricing')) {
                return {backgroundColor:'#DCFCE7', color:'#166534', fontWeight:'800'};
            }
            if (val.includes('outside ±3t') && !val.includes('missing')) {
                return {backgroundColor:'#FEF3C7', color:'#92400E', fontWeight:'800'};
            }
            if (val.includes('minor follow-up') || val.includes('review')) {
                return {backgroundColor:'#FEF3C7', color:'#92400E', fontWeight:'800'};
            }
            return {backgroundColor:'#FEE2E2', color:'#991B1B', fontWeight:'800'};
        }
        """)

        status_renderer = JsCode("""
        class FarmStatusRenderer {
            init(params) {
                this.eGui = document.createElement('div');
                const text = String(params.value || '');
                this.eGui.innerHTML = `<div style="white-space:normal;line-height:1.25;padding-top:3px;padding-bottom:3px;font-size:12px;font-weight:700;">${text}</div>`;
            }
            getGui() { return this.eGui; }
        }
        """)

        for c in visible_cols:
            if c in grid_df.columns:
                gb.configure_column(c, cellStyle=base_style)

        if "Farm Score" in grid_df.columns:
            gb.configure_column("Farm Score", minWidth=135, flex=1.35, cellStyle=score_style, cellRenderer=score_renderer)
        if "vs Last" in grid_df.columns:
            gb.configure_column("vs Last", minWidth=95, flex=0.95, cellStyle=delta_style)
        if "Sheds" in grid_df.columns:
            gb.configure_column("Sheds", minWidth=65, flex=0.65)
        for c in ["Follow-up", "Missing", "±3t Var"]:
            if c in grid_df.columns:
                gb.configure_column(c, minWidth=95, flex=0.95, cellStyle=count_style)
        if "Status" in grid_df.columns:
            gb.configure_column("Status", minWidth=230, flex=2.6, cellStyle=status_style, cellRenderer=status_renderer, wrapText=True, autoHeight=True)

        gb.configure_grid_options(
            suppressHorizontalScroll=True,
            alwaysShowHorizontalScroll=False,
            domLayout="normal",
            onFirstDataRendered=JsCode("function(params) { params.api.sizeColumnsToFit(); }"),
            onGridSizeChanged=JsCode("function(params) { params.api.sizeColumnsToFit(); }"),
        )

        AgGrid(
            grid_df,
            gridOptions=gb.build(),
            height=760,
            fit_columns_on_grid_load=True,
            allow_unsafe_jscode=True,
            update_mode=GridUpdateMode.NO_UPDATE if GridUpdateMode else None,
            theme="alpine",
        )

        st.divider()

    except Exception as e:
        st.caption(f"Farm score unavailable: {e}")


def render_service_manager_recon_score_block(farm_df, farm_summary_df, selected_manager=None):
    """
    Compact Service Manager / Tech Advisor recon score block.

    This belongs on the Service Manager Focus page, not the main Insights page.
    Styling is intentionally soft and support-focused.
    """
    try:
        if farm_df is None or farm_df.empty:
            return

        week_col = "Week Ending" if "Week Ending" in farm_df.columns else None
        if week_col:
            selected_week = pd.to_datetime(farm_df[week_col], errors="coerce").dropna().max()
        else:
            selected_week = pd.Timestamp.today()

        if pd.isna(selected_week):
            selected_week = pd.Timestamp.today()

        recon = build_current_recon_static_week_df(farm_df, farm_summary_df, pd.to_datetime(selected_week))
        recon = add_recon_readiness_scores(recon)

        if recon is None or recon.empty:
            return

        manager_col = "Area Manager" if "Area Manager" in recon.columns else None
        if manager_col is None:
            return

        if selected_manager and selected_manager != "All":
            recon = recon[recon[manager_col].astype(str).eq(str(selected_manager))].copy()

        if recon.empty:
            return

        recon["Needs Follow-up"] = recon["Recon Readiness %"].lt(100)
        recon["High Priority Row"] = recon["Recon Readiness Status"].eq("High Priority")
        recon["Missing Selected Week"] = recon.get("Recon Match Type", "").astype(str).eq("Missing selected week data")

        sm = (
            recon.groupby(manager_col, dropna=False)
            .agg(
                Farms=("Farm Name", "nunique") if "Farm Name" in recon.columns else ("Recon Readiness %", "size"),
                Sheds=("Recon Readiness %", "size"),
                Avg_Readiness=("Recon Readiness %", "mean"),
                Sheds_Needing_Follow_Up=("Needs Follow-up", "sum"),
                High_Priority=("High Priority Row", "sum"),
                Missing_Data=("Missing Selected Week", "sum"),
                Outside_3t=("Variance OK", lambda s: (~s).sum()),
            )
            .reset_index()
        )

        sm["Avg_Readiness"] = sm["Avg_Readiness"].round(0).astype(int)
        sm["Follow-up %"] = ((sm["Sheds_Needing_Follow_Up"] / sm["Sheds"]).fillna(0) * 100).round(0).astype(int)
        sm["Support Focus"] = sm.apply(
            lambda r: "Support focus" if r["Follow-up %"] >= 50 else ("Review suggested" if r["Follow-up %"] >= 20 else "On track"),
            axis=1,
        )

        sm = sm.rename(
            columns={
                manager_col: "Service Manager",
                "Avg_Readiness": "Recon Readiness %",
                "Sheds_Needing_Follow_Up": "Sheds Needing Follow-up",
                "Outside_3t": "Outside ±3t",
                "Missing_Data": "Missing Data",
            }
        )

        sm = sm.sort_values(["Follow-up %", "Sheds Needing Follow-up"], ascending=[False, False])

        st.markdown("### Service Manager recon score")
        st.caption(
            "Support view only: highlights where recon/data-entry follow-up may be useful before pricing is trusted."
        )

        display_cols = [
            "Service Manager",
            "Farms",
            "Sheds",
            "Recon Readiness %",
            "Follow-up %",
            "Sheds Needing Follow-up",
            "Missing Data",
            "Outside ±3t",
            "Support Focus",
        ]
        display_cols = [c for c in display_cols if c in sm.columns]
        display = sm[display_cols].copy()

        def style_sm_score(row):
            styles = pd.Series("", index=row.index)

            follow = pd.to_numeric(row.get("Follow-up %", 0), errors="coerce")
            readiness = pd.to_numeric(row.get("Recon Readiness %", 0), errors="coerce")

            green = "background-color:#F0FDF4; color:#166534; font-weight:800;"
            amber = "background-color:#FFFBEB; color:#92400E; font-weight:800;"
            red = "background-color:#FEF2F2; color:#991B1B; font-weight:800;"

            # Only colour the interpretation fields, not the whole row.
            if "Follow-up %" in row.index:
                if follow >= 50:
                    styles["Follow-up %"] = red
                elif follow >= 20:
                    styles["Follow-up %"] = amber
                else:
                    styles["Follow-up %"] = green

            if "Recon Readiness %" in row.index:
                if readiness >= 90:
                    styles["Recon Readiness %"] = green
                elif readiness >= 70:
                    styles["Recon Readiness %"] = amber
                else:
                    styles["Recon Readiness %"] = red

            if "Support Focus" in row.index:
                focus = str(row.get("Support Focus", ""))
                if focus == "Support focus":
                    styles["Support Focus"] = red
                elif focus == "Review suggested":
                    styles["Support Focus"] = amber
                else:
                    styles["Support Focus"] = green

            return styles

        fmt = {
            "Recon Readiness %": "{:.0f}%",
            "Follow-up %": "{:.0f}%",
        }

        st.dataframe(
            display.style.apply(style_sm_score, axis=1).format(fmt, na_rep=""),
            use_container_width=True,
            hide_index=True,
            height=180 if selected_manager and selected_manager != "All" else 240,
        )

    except Exception as e:
        st.caption(f"Service Manager recon score unavailable: {e}")



def render_insights_top_recon_readiness(farm_df, farm_summary_df):
    """
    Top-of-Insights recon readiness section.
    This is deliberately visible before the price graph.
    """
    try:
        if farm_df is None or farm_df.empty:
            return

        week_col = "Week Ending" if "Week Ending" in farm_df.columns else None
        if week_col:
            selected_week = pd.to_datetime(farm_df[week_col], errors="coerce").dropna().max()
        else:
            selected_week = pd.Timestamp.today()

        if pd.isna(selected_week):
            selected_week = pd.Timestamp.today()

        recon = build_current_recon_static_week_df(farm_df, farm_summary_df, pd.to_datetime(selected_week))
        recon = add_recon_readiness_scores(recon)

        if recon.empty:
            return

        st.markdown("### Recon Readiness Issues")
        st.caption("Readiness score: 100% means all key recon fields are entered or acceptable. Feed Inventory EndVar is acceptable within ±3,000 kg.")

        avg_score = recon["Recon Readiness %"].mean()
        ready_rows = recon["Recon Readiness Status"].eq("Ready").sum()
        follow_up_rows = recon["Recon Readiness Status"].isin(["Needs Follow-up", "High Priority"]).sum()
        outside_var = (~recon["Variance OK"]).sum()

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            kpi_card("Avg readiness", f"{avg_score:.0f}%", "Across active shed rows")
        with c2:
            kpi_card("Ready", f"{ready_rows:,}", "Rows at 100%")
        with c3:
            kpi_card("Needs follow-up", f"{follow_up_rows:,}", "Rows below 85%")
        with c4:
            kpi_card("Outside ±3t", f"{outside_var:,}", "Stock variance review")

        # Farm-level summary first.
        group_cols = [c for c in ["Area Manager", "Farm Name"] if c in recon.columns]
        if group_cols:
            farm_summary = (
                recon.groupby(group_cols, dropna=False)
                .agg(
                    Rows=("Recon Readiness %", "size"),
                    Avg_Readiness=("Recon Readiness %", "mean"),
                    Ready_Rows=("Recon Readiness Status", lambda s: (s == "Ready").sum()),
                    Follow_Up_Rows=("Recon Readiness Status", lambda s: s.isin(["Needs Follow-up", "High Priority"]).sum()),
                    Issues=("Recon Issue Count", "sum"),
                    Outside_3t=("Variance OK", lambda s: (~s).sum()),
                )
                .reset_index()
            )
            farm_summary["Avg_Readiness"] = farm_summary["Avg_Readiness"].round(0).astype(int)
            farm_summary = farm_summary.sort_values(["Avg_Readiness", "Issues"], ascending=[True, False])

            farm_summary = farm_summary.rename(columns={
                "Avg_Readiness": "Recon Readiness %",
                "Ready_Rows": "Ready Rows",
                "Follow_Up_Rows": "Follow-up Rows",
                "Outside_3t": "Outside ±3t",
            })

            st.markdown("#### Farm readiness summary")
            st.dataframe(
                farm_summary.style.apply(style_recon_readiness_table, axis=1).format({"Recon Readiness %": "{:.0f}%"}),
                use_container_width=True,
                hide_index=True,
                height=260,
            )

        # Shed-level issue detail.
        detail_cols = [
            "Area Manager",
            "Farm Name",
            "Shed / Flock",
            "Entity Stage",
            "Age",
            "Recon Readiness %",
            "Recon Readiness Status",
            "Recon Issue Count",
            "Recon Issue Summary",
            "Feed Inventory (EndVar)",
        ]
        detail_cols = [c for c in detail_cols if c in recon.columns]
        detail = recon.sort_values(["Recon Readiness %", "Farm Name", "Shed / Flock"], ascending=[True, True, True])[detail_cols]

        st.markdown("#### Shed rows needing attention")
        st.dataframe(
            detail.style.apply(style_recon_readiness_table, axis=1).format({
                "Recon Readiness %": "{:.0f}%",
                "Feed Inventory (EndVar)": "{:,.0f}",
            }, na_rep=""),
            use_container_width=True,
            hide_index=True,
            height=360,
        )

        st.divider()

    except Exception as e:
        st.warning(f"Recon readiness insights could not be built: {e}")



def render_insights_recon_readiness(recon_df):
    """
    Insights block showing which farms/sheds need recon support and why.
    """
    if recon_df is None or recon_df.empty:
        st.info("No recon rows available for readiness scoring.")
        return

    scored = add_recon_readiness_scores(recon_df)

    st.markdown("### Recon readiness issues")
    st.markdown(
        """
        <div class="pf-note">
        This section scores each shed/farm on whether key recon fields are entered and usable.
        100% means the main recon fields are complete. Feed Inventory EndVar is treated as acceptable when it is within ±3,000 kg.
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Average readiness", f"{scored['Recon Readiness %'].mean():.0f}%", "Across visible recon rows")
    with c2:
        kpi_card("Ready rows", f"{scored['Recon Readiness Status'].eq('Ready').sum():,}", "100% complete")
    with c3:
        kpi_card("Needs follow-up", f"{scored['Recon Readiness Status'].isin(['Needs Follow-up', 'High Priority']).sum():,}", "Support required")
    with c4:
        kpi_card("Outside ±3t", f"{(~scored['Variance OK']).sum():,}", "Stock variance review")

    display_cols = [
        "Area Manager",
        "Farm Name",
        "Shed / Flock",
        "Entity Stage",
        "Age",
        "Recon Readiness %",
        "Recon Readiness Status",
        "Recon Issue Count",
        "Recon Issue Summary",
        "Feed Inventory (Beg)",
        "Feed Delivered",
        "Feed Consumed",
        "Feed Inventory (End)",
        "Feed Inventory (EndCalc)",
        "Feed Inventory (EndVar)",
    ]
    display_cols = [c for c in display_cols if c in scored.columns]

    display = scored.sort_values(
        ["Recon Readiness %", "Farm Name", "Shed / Flock"],
        ascending=[True, True, True],
    )[display_cols].copy()

    fmt = {
        "Recon Readiness %": "{:.0f}%",
        "Feed Inventory (Beg)": "{:,.0f}",
        "Feed Delivered": "{:,.0f}",
        "Feed Consumed": "{:,.0f}",
        "Feed Inventory (End)": "{:,.0f}",
        "Feed Inventory (EndCalc)": "{:,.0f}",
        "Feed Inventory (EndVar)": "{:,.0f}",
    }
    fmt = {k: v for k, v in fmt.items() if k in display.columns}

    st.dataframe(
        display.style.apply(style_recon_readiness_table, axis=1).format(fmt, na_rep=""),
        use_container_width=True,
        hide_index=True,
        height=520,
    )


def build_current_recon_static_week_df(farm_df, farm_summary_df, selected_week_ending):
    """
    Builds Current Recon from a static farm/shed list, then overlays selected
    week data using the Week Ending column.

    Missing selected-week data stays visible and becomes red/actionable.
    """
    base = build_static_shed_register(farm_df, farm_summary_df)

    if base.empty:
        return pd.DataFrame()

    selected_week_ending = pd.to_datetime(selected_week_ending).normalize()

    df = farm_df.copy()
    week_values = get_explicit_week_ending_series(df)
    week_df = df[week_values.eq(selected_week_ending)].copy()

    if week_df.empty:
        week_prepared = pd.DataFrame(columns=["Farm Name", "Shed / Flock"])
    else:
        week_prepared = build_current_recon_df(week_df, farm_summary_df)

    if week_prepared.empty:
        week_prepared = pd.DataFrame(columns=["Farm Name", "Shed / Flock"])

    # Drop duplicate selected-week rows per farm/shed to avoid exploding the static list.
    if not week_prepared.empty:
        week_prepared = week_prepared.drop_duplicates(["Farm Name", "Shed / Flock"], keep="last")

    join_cols = ["Farm Name", "Shed / Flock"]

    # Columns from selected week that should overlay onto the static register.
    overlay_cols = [
        "Farm Name",
        "Shed / Flock",
        "Begin Date",
        "End Date",
        "Raw End Date",
        "Recon Week Ending",
        "Recon Match Type",
        "Entity Stage",
        "Age",
        "Bird Inv (End)",
        "Feed Inventory (Beg)",
        "Feed Delivered",
        "Feed Consumed",
        "Feed Inventory (End)",
        "Feed Inventory (EndCalc)",
        "Feed Inventory (EndVar)",
        "Bird Inv OK",
        "Beginning Stock OK",
        "Feed Delivered OK",
        "Feed Consumed OK",
        "Closing Stock OK",
        "EndCalc OK",
        "Variance OK",
        "Opening Stock Review",
        "Deliveries Review",
        "Closing Stock Review",
        "Current Recon Status",
        "Support Note",
    ]

    overlay_cols = [c for c in overlay_cols if c in week_prepared.columns]

    merged = base.merge(
        week_prepared[overlay_cols],
        on=join_cols,
        how="left",
        suffixes=("", "_week"),
    )

    # Coalesce week stage/age over static values where available.
    for col in ["Entity Stage", "Age"]:
        week_col = f"{col}_week"
        if week_col in merged.columns:
            merged[col] = merged[week_col].combine_first(merged[col])
            merged = merged.drop(columns=[week_col])

    # Week/date fields.
    # These must exist even when no selected-week row was joined onto a
    # static farm/shed row.
    for date_col in ["Begin Date", "End Date", "Raw End Date"]:
        if date_col not in merged.columns:
            merged[date_col] = pd.NaT if date_col != "Raw End Date" else ""

    if "Recon Week Ending" not in merged.columns:
        merged["Recon Week Ending"] = selected_week_ending
    else:
        merged["Recon Week Ending"] = merged["Recon Week Ending"].fillna(selected_week_ending)

    has_selected_week_data = merged["Begin Date"].notna() | merged["End Date"].notna()

    default_match_type = pd.Series(
        np.where(
            has_selected_week_data,
            "Week Ending column",
            "Missing selected week data",
        ),
        index=merged.index,
    )

    if "Recon Match Type" not in merged.columns:
        merged["Recon Match Type"] = default_match_type
    else:
        merged["Recon Match Type"] = merged["Recon Match Type"].where(
            merged["Recon Match Type"].notna(),
            default_match_type,
        )

    # Numeric columns: missing selected week data should show as 0/red.
    numeric_cols = [
        "Bird Inv (End)",
        "Feed Inventory (Beg)",
        "Feed Delivered",
        "Feed Consumed",
        "Feed Inventory (End)",
        "Feed Inventory (EndCalc)",
        "Feed Inventory (EndVar)",
    ]

    for col in numeric_cols:
        if col not in merged.columns:
            merged[col] = 0
        merged[col] = pd.to_numeric(merged[col], errors="coerce").fillna(0)

    # Recalculate OK flags after filling missing rows.
    merged["Bird Inv OK"] = merged["Bird Inv (End)"].gt(0)
    merged["Beginning Stock OK"] = merged["Feed Inventory (Beg)"].gt(0)
    merged["Feed Delivered OK"] = merged["Feed Delivered"].gt(0)
    merged["Feed Consumed OK"] = merged["Feed Consumed"].gt(0)
    merged["Closing Stock OK"] = merged["Feed Inventory (End)"].gt(0)
    merged["EndCalc OK"] = merged["Feed Inventory (EndCalc)"].notna()
    merged["Variance OK"] = merged["Feed Inventory (EndVar)"].apply(is_endvar_within_tolerance)
    merged["Opening Stock Review"] = ~merged["Beginning Stock OK"]
    merged["Deliveries Review"] = ~merged["Feed Delivered OK"]
    merged["Closing Stock Review"] = ~merged["Closing Stock OK"]

    def static_status(row):
        if str(row.get("Recon Match Type", "")) == "Missing selected week data":
            return "Data Missing for Selected Week"

        if not bool(row.get("Closing Stock OK", False)):
            return "Closing Stock Missing"

        if not bool(row.get("Beginning Stock OK", False)):
            return "Opening Stock Missing"

        if not bool(row.get("Feed Delivered OK", False)):
            return "No Feed Delivered"

        if not bool(row.get("Variance OK", False)):
            return "Stock Variance Review"

        if not bool(row.get("Feed Consumed OK", False)):
            return "Feed Consumed Missing"

        if not bool(row.get("Bird Inv OK", False)):
            return "Bird Inventory Missing"

        return "Ready for Pricing"

    merged["Current Recon Status"] = merged.apply(static_status, axis=1)

    def static_note(row):
        if str(row.get("Recon Match Type", "")) == "Missing selected week data":
            return "No selected-week data found. Please check whether this farm/shed has been entered for the selected week."

        notes = []

        if not bool(row.get("Closing Stock OK", False)):
            notes.append("Closing stock is missing or zero.")

        if not bool(row.get("Beginning Stock OK", False)):
            notes.append("Opening stock is missing or zero.")

        if not bool(row.get("Feed Delivered OK", False)):
            notes.append("No feed delivery/receival captured.")

        if not bool(row.get("Variance OK", False)):
            try:
                notes.append(f"Stock variance {float(row.get('Feed Inventory (EndVar)', 0)):,.0f} needs review.")
            except Exception:
                notes.append("Stock variance needs review.")

        if not bool(row.get("Feed Consumed OK", False)):
            notes.append("Feed consumed is missing or zero.")

        if not bool(row.get("Bird Inv OK", False)):
            notes.append("Bird inventory is missing or zero.")

        return " ".join(notes) if notes else "Ready for pricing review."

    merged["Support Note"] = merged.apply(static_note, axis=1)

    if "Farm Name" in merged.columns:

        merged["Farm Name"] = clean_display_farm_name_series(merged, "Farm Name", "Farm No")

    return merged.sort_values(["Area Manager", "Farm Name", "Shed No", "Shed / Flock"]).reset_index(drop=True)



def add_week_price_trend_columns(df):
    """
    Adds plain-text trend columns beside weekly $/t columns.

    Streamlit's st.dataframe column_config can override pandas Styler colours,
    so this helper creates visible movement indicators that work reliably:
      ↑ Dearer
      ↓ Cheaper
      → Same
      — No comparison
      No data
    """
    if df is None or df.empty:
        return df

    out = df.copy()
    week_cols = get_week_price_columns(out)

    if len(week_cols) < 2:
        return out

    # Build a new column order with a trend column after every comparable week.
    new_order = []
    previous_week_col = None

    for col in out.columns:
        new_order.append(col)

        if col in week_cols:
            if previous_week_col is None:
                trend_col = f"{col} Trend"
                out[trend_col] = "— No comparison"
                new_order.append(trend_col)
            else:
                trend_col = f"{col} Trend"

                current = pd.to_numeric(out[col], errors="coerce")
                previous = pd.to_numeric(out[previous_week_col], errors="coerce")

                out[trend_col] = np.select(
                    [
                        current.isna(),
                        previous.isna(),
                        current.gt(previous),
                        current.lt(previous),
                        current.eq(previous),
                    ],
                    [
                        "No data",
                        "— No comparison",
                        "↑ Dearer",
                        "↓ Cheaper",
                        "→ Same",
                    ],
                    default="— No comparison",
                )
                new_order.append(trend_col)

            previous_week_col = col

    # Avoid duplicate columns in case helper is run twice.
    new_order = [c for i, c in enumerate(new_order) if c in out.columns and c not in new_order[:i]]
    return out[new_order]


def style_week_trend_text(row):
    """
    Colours the plain-text trend columns.
    """
    styles = pd.Series("", index=row.index)

    for col in row.index:
        if not str(col).endswith(" Trend"):
            continue

        value = str(row.get(col, ""))

        if "Dearer" in value:
            styles[col] = "background-color:#FEE2E2; color:#991B1B; font-weight:900;"
        elif "Cheaper" in value:
            styles[col] = "background-color:#DCFCE7; color:#166534; font-weight:900;"
        elif "Same" in value:
            styles[col] = "background-color:#F8FAFC; color:#334155; font-weight:700;"
        else:
            styles[col] = "background-color:#F8FAFC; color:#94A3B8;"

    return styles


def render_week_price_table_with_trends(df, *, height=620):
    """
    Render the 5-week price table using AgGrid when available.

    Weekly price cells are coloured directly:
    red   = dearer than previous available week
    green = cheaper than previous available week
    grey  = no comparison / unchanged / missing

    No extra trend columns are shown.
    """
    if df is None or df.empty:
        st.info("No 5-week price rows to display.")
        return

    st.caption("Weekly price colours: red = dearer than previous available week, green = cheaper, grey = no comparison / unchanged.")

    week_cols = get_week_price_columns(df)
    display_df = df.copy()

    # Remove old generated trend columns if present.
    trend_cols = [c for c in display_df.columns if str(c).endswith(" Trend")]
    if trend_cols:
        display_df = display_df.drop(columns=trend_cols)

    # Hidden previous-week comparison columns for AgGrid styling.
    previous_col = None
    for col in week_cols:
        prev_col = f"__prev__{col}"
        if previous_col is None:
            display_df[prev_col] = np.nan
        else:
            display_df[prev_col] = pd.to_numeric(display_df[previous_col], errors="coerce")
        previous_col = col

    visible_df = display_df[[c for c in display_df.columns if not str(c).startswith("__prev__")]]

    if not HAS_AGGRID:
        st.warning("AgGrid is not installed. Install streamlit-aggrid to enable in-cell price colouring.")
        st.dataframe(
            visible_df,
            use_container_width=True,
            hide_index=True,
            height=height,
        )
        return

    gb = GridOptionsBuilder.from_dataframe(display_df)

    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filter=True,
        wrapText=False,
        autoHeight=False,
    )

    for col in display_df.columns:
        if str(col).startswith("__prev__"):
            gb.configure_column(col, hide=True)

    for col in ["Farm No", "Farm Name", "Area Manager", "Progress Status"]:
        if col in display_df.columns:
            gb.configure_column(col, pinned="left", width=105 if col == "Farm No" else 160)

    money_formatter = JsCode("""
    function(params) {
        if (params.value === null || params.value === undefined || params.value === '' || isNaN(Number(params.value))) {
            return 'None';
        }
        return '$' + Number(params.value).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }
    """)

    price_cell_style = JsCode("""
    function(params) {
        if (params.value === null || params.value === undefined || params.value === '' || isNaN(Number(params.value))) {
            return {'backgroundColor': '#F8FAFC', 'color': '#94A3B8', 'fontWeight': '700'};
        }

        const previousField = '__prev__' + params.colDef.field;
        const previous = params.data ? params.data[previousField] : null;

        if (previous === null || previous === undefined || previous === '' || isNaN(Number(previous))) {
            return {'backgroundColor': '#F8FAFC', 'color': '#334155', 'fontWeight': '800'};
        }

        const currentValue = Number(params.value);
        const previousValue = Number(previous);

        if (currentValue > previousValue) {
            return {'backgroundColor': '#FEE2E2', 'color': '#991B1B', 'fontWeight': '900'};
        }

        if (currentValue < previousValue) {
            return {'backgroundColor': '#DCFCE7', 'color': '#166534', 'fontWeight': '900'};
        }

        return {'backgroundColor': '#F8FAFC', 'color': '#334155', 'fontWeight': '800'};
    }
    """)

    movement_cell_style = JsCode("""
    function(params) {
        if (params.value === null || params.value === undefined || params.value === '' || isNaN(Number(params.value))) {
            return {'backgroundColor': '#F8FAFC', 'color': '#94A3B8'};
        }

        const value = Number(params.value);

        if (value > 0) {
            return {'backgroundColor': '#FEE2E2', 'color': '#991B1B', 'fontWeight': '900'};
        }

        if (value < 0) {
            return {'backgroundColor': '#DCFCE7', 'color': '#166534', 'fontWeight': '900'};
        }

        return {'backgroundColor': '#F8FAFC', 'color': '#334155', 'fontWeight': '800'};
    }
    """)

    for col in week_cols:
        gb.configure_column(
            col,
            type=["numericColumn"],
            width=125,
            valueFormatter=money_formatter,
            cellStyle=price_cell_style,
        )

    for col in ["Farm Movement $/t", "Business Movement $/t", "Business-Adjusted Movement $/t"]:
        if col in display_df.columns:
            gb.configure_column(
                col,
                type=["numericColumn"],
                width=145,
                valueFormatter=money_formatter,
                cellStyle=movement_cell_style,
            )

    if "Current Recon Confidence" in display_df.columns:
        gb.configure_column("Current Recon Confidence", width=155)

    AgGrid(
        display_df,
        gridOptions=gb.build(),
        height=height,
        fit_columns_on_grid_load=False,
        allow_unsafe_jscode=True,
        update_mode=GridUpdateMode.NO_UPDATE if GridUpdateMode else None,
        theme="alpine",
    )



def get_week_price_columns(df):
    """
    Detects weekly price columns such as:
    Week 12/04 $/t
    Week 19/04 $/t
    Week 03/05 $/t

    Excludes generated helper columns such as:
    Week 19/04 $/t Trend
    """
    if df is None or df.empty:
        return []

    cols = []
    for c in df.columns:
        text = str(c)
        low = text.lower()

        if (
            low.startswith("week ")
            and "$/t" in low
            and "trend" not in low
        ):
            cols.append(c)

    def extract_date_key(col):
        text = str(col)
        m = re.search(r"(\d{1,2})/(\d{1,2})", text)
        if not m:
            return pd.Timestamp.max

        day = int(m.group(1))
        month = int(m.group(2))

        try:
            return pd.Timestamp(year=pd.Timestamp.today().year, month=month, day=day)
        except Exception:
            return pd.Timestamp.max

    return sorted(cols, key=extract_date_key)



def style_weekly_price_trend(row):
    """
    Row-wise style for weekly farm price columns.

    - Green: price decreased from previous available week
    - Red: price increased from previous available week
    - Neutral: unchanged or no previous comparable week
    """
    styles = pd.Series("", index=row.index)

    week_cols = get_week_price_columns(pd.DataFrame(columns=row.index))

    green_style = "background-color:#ECFDF3;color:#15803D;font-weight:850;"
    red_style = "background-color:#FEF2F2;color:#DC2626;font-weight:850;"
    neutral_style = "background-color:#F8FAFC;color:#334155;"

    previous_value = None

    for col in week_cols:
        value = pd.to_numeric(row.get(col), errors="coerce")

        if pd.isna(value):
            styles[col] = "background-color:#F8FAFC;color:#94A3B8;"
            continue

        if previous_value is None or pd.isna(previous_value):
            styles[col] = neutral_style
        else:
            if value > previous_value:
                styles[col] = red_style
            elif value < previous_value:
                styles[col] = green_style
            else:
                styles[col] = neutral_style

        previous_value = value

    # Movement columns.
    for col in ["Farm Movement $/t", "Business Movement $/t", "Business-Adjusted Movement $/t"]:
        if col in row.index:
            val = pd.to_numeric(row.get(col), errors="coerce")
            if pd.notna(val):
                if val > 0:
                    styles[col] = red_style
                elif val < 0:
                    styles[col] = green_style
                else:
                    styles[col] = neutral_style

    return styles





def style_weekly_price_trend_any_table(df):
    """
    Conditional formatting for tables with Week xx/xx $/t columns.
    Compares each weekly price against the previous available weekly price
    in the same row.

    This returns a pandas Styler used directly by st.dataframe.
    """
    if df is None or df.empty:
        return df

    week_cols = get_week_price_columns(df)
    movement_cols = [
        c for c in [
            "Farm Movement $/t",
            "Business Movement $/t",
            "Business-Adjusted Movement $/t",
        ]
        if c in df.columns
    ]

    green_style = "background-color: #DCFCE7; color: #166534; font-weight: 900;"
    red_style = "background-color: #FEE2E2; color: #991B1B; font-weight: 900;"
    neutral_style = "background-color: #F8FAFC; color: #334155;"
    missing_style = "background-color: #F8FAFC; color: #94A3B8;"

    def row_style(row):
        styles = pd.Series("", index=row.index)
        previous_value = None

        for col in week_cols:
            value = pd.to_numeric(row.get(col), errors="coerce")

            if pd.isna(value):
                styles[col] = missing_style
                continue

            if previous_value is None or pd.isna(previous_value):
                styles[col] = neutral_style
            elif value > previous_value:
                styles[col] = red_style
            elif value < previous_value:
                styles[col] = green_style
            else:
                styles[col] = neutral_style

            previous_value = value

        for col in movement_cols:
            value = pd.to_numeric(row.get(col), errors="coerce")
            if pd.isna(value):
                styles[col] = missing_style
            elif value > 0:
                styles[col] = red_style
            elif value < 0:
                styles[col] = green_style
            else:
                styles[col] = neutral_style

        return styles

    fmt = {}
    for col in week_cols + movement_cols:
        fmt[col] = lambda x: "None" if pd.isna(x) else f"${float(x):,.2f}"

    return (
        df.style
        .apply(row_style, axis=1)
        .format(fmt, na_rep="None")
    )



def dataframe_with_week_price_formatting(df, *, height=560, hide_index=True):
    """
    Wrapper used in farm ranking / 5-week progress tables.
    If the dataframe has Week ... $/t columns, apply trend formatting.
    Otherwise render normally.
    """
    if df is None or df.empty:
        st.info("No rows to display.")
        return

    week_cols = get_week_price_columns(df)
    movement_cols = [
        c for c in [
            "Farm Movement $/t",
            "Business Movement $/t",
            "Business-Adjusted Movement $/t",
        ]
        if c in df.columns
    ]

    if week_cols or movement_cols:
        st.dataframe(
            style_weekly_price_trend_any_table(df),
            use_container_width=True,
            hide_index=hide_index,
            height=height,
        )
    else:
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=hide_index,
            height=height,
        )


def render_weekly_price_table(df, height=520):
    """
    Render a farm/feed price table with conditional formatting across weekly
    $/t columns.
    """
    if df is None or df.empty:
        st.info("No price movement rows available.")
        return

    week_cols = get_week_price_columns(df)
    movement_cols = [c for c in ["Farm Movement $/t", "Business Movement $/t", "Business-Adjusted Movement $/t"] if c in df.columns]

    fmt = {}
    for col in week_cols + movement_cols:
        fmt[col] = money_fmt

    styled = (
        df.style
        .apply(style_weekly_price_trend, axis=1)
        .format(fmt, na_rep="None")
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=height,
    )


def render_current_recon_page(farm_df, farm_summary_df):
    """
    Recon completion and data-quality board.

    Date window:
    - Monday: previous Monday to Sunday
    - Tuesday-Sunday: current Monday to today
    """
    st.markdown('<div class="pf-section-title">Current Recon</div>', unsafe_allow_html=True)

    available_week_endings, recon_date_col = get_available_recon_week_endings(farm_df)

    today = pd.Timestamp.today().normalize()
    current_week_ending = week_ending_from_date(pd.Series([today]), "Sunday").iloc[0].normalize()

    combined_week_endings = list(available_week_endings or [])
    if current_week_ending not in [pd.to_datetime(x).normalize() for x in combined_week_endings if pd.notna(x)]:
        combined_week_endings.append(current_week_ending)

    combined_week_endings = (
        pd.Series(pd.to_datetime(combined_week_endings))
        .dropna()
        .dt.normalize()
        .drop_duplicates()
        .sort_values(ascending=False)
        .tolist()
    )

    selected_week_ending = st.selectbox(
        "Week ending date",
        options=combined_week_endings,
        index=combined_week_endings.index(current_week_ending) if current_week_ending in combined_week_endings else 0,
        format_func=lambda d: pd.to_datetime(d).strftime("%d/%m/%Y"),
        key="current_recon_week_selector_manual",
        help="Pick the Sunday week ending you want to review.",
    )

    window_start, window_end = recon_window_from_week_ending(selected_week_ending)
    window_label = f"Selected week ending {pd.to_datetime(selected_week_ending).strftime('%d/%m/%Y')}"

    farm_window_df, window_note = filter_farm_recon_to_window(farm_df, window_start, window_end)

    if farm_window_df.empty:
        st.warning(
            f"{window_note} The uploaded Amino Farm report may not contain rows for "
            f"{window_start.strftime('%d/%m/%Y')} to {window_end.strftime('%d/%m/%Y')}."
        )
        return



    # Build from a static farm/shed register, then overlay the selected week.
    # This shows missing selected-week data as red instead of hiding missing sheds.
    recon_all = build_current_recon_static_week_df(farm_df, farm_summary_df, window_end)
    recon_all = add_recon_readiness_scores(recon_all)

    if recon_all.empty:
        st.info("No farm/shed register rows found for Current Recon.")
        return

    include_inactive_rows = False

    if "Include In Current Recon" not in recon_all.columns:
        recon_all["Include In Current Recon"] = True

    if include_inactive_rows:
        recon = recon_all.copy()
    else:
        recon = recon_all[recon_all["Include In Current Recon"].astype(bool)].copy()

    if recon.empty:
        st.success("No active/current recon rows found for the selected week. Turn on 'Include inactive / zero rows' if you want to audit the full Amino export.")
        return

    filter_col1, filter_col2, filter_col3 = st.columns([1.3, 1.3, 1])
    with filter_col1:
        manager_options = ["All"] + sorted(recon["Area Manager"].dropna().astype(str).unique().tolist())
        selected_manager = st.selectbox("Service Manager", manager_options, key="current_recon_manager_filter")
    with filter_col2:
        farm_options = ["All"] + sorted(recon["Farm Name"].dropna().astype(str).unique().tolist())
        selected_farm = st.selectbox("Farm", farm_options, key="current_recon_farm_filter")
    with filter_col3:
        outstanding_only = st.checkbox("Show only outstanding", value=False, key="current_recon_outstanding_only")

    view = recon.copy()

    if selected_manager != "All":
        view = view[view["Area Manager"].astype(str).eq(selected_manager)].copy()

    if selected_farm != "All":
        view = view[view["Farm Name"].astype(str).eq(selected_farm)].copy()

    if outstanding_only:
        view = view[~view["Current Recon Status"].eq("Ready for Pricing")].copy()

    if view.empty:
        st.success("No outstanding recon rows for the selected filters.")
        return

    if "Amino Status" not in view.columns:
        view["Amino Status"] = ""

    if "Include In Current Recon" not in view.columns:
        view["Include In Current Recon"] = True

    display = view[
        [
            "Area Manager",
            "Farm Name",
            "Shed / Flock",
            "Shed No",
            "Begin Date",
            "End Date",
            "Raw End Date",
            "Recon Week Ending",
            "Recon Match Type",
            "Entity Stage",
            "Age",
            "Bird Inv (End)",
            "Feed Inventory (Beg)",
            "Feed Delivered",
            "Feed Consumed",
            "Feed Inventory (End)",
            "Feed Inventory (EndCalc)",
            "Feed Inventory (EndVar)",
            "Recon Readiness %",
            "Recon Readiness Status",
            "Current Recon Status",
            "Support Note",
            "Bird Inv OK",
            "Beginning Stock OK",
            "Feed Delivered OK",
            "Feed Consumed OK",
            "Closing Stock OK",
            "EndCalc OK",
            "Variance OK",
            "Opening Stock Review",
            "Deliveries Review",
            "Closing Stock Review",
            "Include In Current Recon",
            "Amino Status",
        ]
    ].copy()

    display = display.rename(columns={"Area Manager": "Service Manager"})

    status_cols = {
        "Bird Inv (End)": "Bird Inv OK",
        "Feed Inventory (Beg)": "Beginning Stock OK",
        "Feed Delivered": "Feed Delivered OK",
        "Feed Consumed": "Feed Consumed OK",
        "Feed Inventory (End)": "Closing Stock OK",
        "Feed Inventory (EndCalc)": "EndCalc OK",
    }

    def style_current_recon(row):
        styles = pd.Series("", index=row.index)

        status = row.get("Current Recon Status", "")

        if status in ["Data Missing for Selected Week", "Closing Stock Missing"]:
            styles.loc[:] = "border-left: 4px solid #DC2626;"
        elif status in ["Opening Stock Missing", "No Feed Delivered", "Stock Variance Review", "Feed Consumed Missing", "Bird Inventory Missing"]:
            styles.loc[:] = "border-left: 4px solid #F59E0B;"
        elif status == "Ready for Pricing":
            styles.loc[:] = "border-left: 4px solid #16A34A;"

        red_style = "background-color: #FEF2F2; color: #DC2626; font-weight: 900;"
        green_style = "background-color: #ECFDF3; color: #15803D; font-weight: 900;"
        amber_style = "background-color: #FFFBEB; color: #D97706; font-weight: 900;"

        def num_value(col):
            try:
                return float(pd.to_numeric(row.get(col, 0), errors="coerce"))
            except Exception:
                return 0.0

        # Direct value rules for Current Recon.
        bird_ok = num_value("Bird Inv (End)") > 0
        beginning_ok = num_value("Feed Inventory (Beg)") > 0
        delivered_ok = num_value("Feed Delivered") > 0
        consumed_ok = num_value("Feed Consumed") > 0
        closing_ok = num_value("Feed Inventory (End)") > 0
        endcalc_ok = pd.notna(row.get("Feed Inventory (EndCalc)", None))
        variance_ok = is_endvar_within_tolerance(row.get("Feed Inventory (EndVar)", 0))

        if "Bird Inv (End)" in row.index:
            styles["Bird Inv (End)"] = green_style if bird_ok else red_style

        if "Feed Inventory (Beg)" in row.index:
            styles["Feed Inventory (Beg)"] = green_style if beginning_ok else red_style

        if "Feed Delivered" in row.index:
            styles["Feed Delivered"] = green_style if delivered_ok else red_style

        if "Feed Consumed" in row.index:
            styles["Feed Consumed"] = green_style if consumed_ok else red_style

        if "Feed Inventory (End)" in row.index:
            styles["Feed Inventory (End)"] = green_style if closing_ok else red_style

        if "Feed Inventory (EndCalc)" in row.index:
            styles["Feed Inventory (EndCalc)"] = green_style if endcalc_ok else red_style

        if "Feed Inventory (EndVar)" in row.index:
            styles["Feed Inventory (EndVar)"] = green_style if variance_ok else red_style

        if "Current Recon Status" in row.index:
            if status == "Ready for Pricing":
                styles["Current Recon Status"] = green_style
            elif status in ["Opening Stock Missing", "No Feed Delivered", "Stock Variance Review", "Feed Consumed Missing", "Bird Inventory Missing"]:
                styles["Current Recon Status"] = amber_style
            else:
                styles["Current Recon Status"] = red_style

        return styles

    hide_cols = list(status_cols.values()) + ['Bird Inv OK', 'Beginning Stock OK', 'Feed Delivered OK', 'Feed Consumed OK', 'Closing Stock OK', 'EndCalc OK', 'Variance OK', 'Opening Stock Review', 'Deliveries Review', 'Closing Stock Review', 'Include In Current Recon', 'Amino Status']
    hide_cols = list(dict.fromkeys(hide_cols))

    # Remove internal checkbox / calculation columns from the visible table.
    # The style function now uses the visible numeric values directly, so these
    # columns do not need to be present in the rendered dataframe.
    display = display.drop(columns=[c for c in hide_cols if c in display.columns], errors="ignore")

    
    styled = (
        display
        .style
        .apply(style_current_recon, axis=1)
        .format(
            {
                "Begin Date": lambda x: "" if pd.isna(x) else pd.to_datetime(x).strftime("%d/%m/%Y"),
                "End Date": lambda x: "" if pd.isna(x) else pd.to_datetime(x).strftime("%d/%m/%Y"),
                "Recon Week Ending": lambda x: "" if pd.isna(x) else pd.to_datetime(x).strftime("%d/%m/%Y"),
                "Age": "{:,.0f}",
                "Bird Inv (End)": "{:,.0f}",
                "Feed Inventory (Beg)": "{:,.0f}",
                "Feed Delivered": "{:,.0f}",
                "Feed Consumed": "{:,.0f}",
                "Feed Inventory (End)": "{:,.0f}",
                "Feed Inventory (EndCalc)": "{:,.0f}",
                "Feed Inventory (EndVar)": "{:,.0f}",
            },
            na_rep="Needs entry",
        )
    )

    st.dataframe(
        styled,
        use_container_width=True,
        hide_index=True,
        height=980,
    )

    st.markdown("### Service Manager summary")

    mgr_summary = (
        recon.groupby("Area Manager", dropna=False)
        .agg(
            Rows=("Farm Name", "size"),
            Complete=("Current Recon Status", lambda s: s.eq("Complete").sum()),
            Closing_Stock_To_Complete=("Current Recon Status", lambda s: s.eq("Closing Stock to Complete").sum()),
            Opening_Stock_Review=("Current Recon Status", lambda s: s.eq("Opening Stock Review").sum()),
            Deliveries_To_Review=("Current Recon Status", lambda s: s.eq("Deliveries to Review").sum()),
            Variance_To_Review=("Current Recon Status", lambda s: s.eq("Variance to Review").sum()),
            Not_Ready=("Current Recon Status", lambda s: s.ne("Complete").sum()),
        )
        .reset_index()
        .rename(columns={"Area Manager": "Service Manager"})
        .sort_values(["Not_Ready", "Variance_To_Review"], ascending=[False, False])
    )

    st.dataframe(
        mgr_summary,
        use_container_width=True,
        hide_index=True,
    )


def classify_price_progress(adj_movement, weeks_available):
    if weeks_available < 2 or pd.isna(adj_movement):
        return "Not Enough Data"
    if adj_movement <= -10:
        return "Improving"
    if adj_movement <= 10:
        return "Holding Steady"
    if adj_movement <= 25:
        return "Review Suggested"
    return "Support Opportunity"


def price_progress_note(row):
    status = row.get("Progress Status", "")
    movement = row.get("Business-Adjusted Movement $/t", np.nan)
    confidence = row.get("Current Recon Confidence", np.nan)
    pricing_status = row.get("Current Pricing Status", "")

    if status == "Not Enough Data":
        return "Not enough weekly delivery history yet to judge price movement fairly."

    if pricing_status in ["Price Not Ready", "Support Needed"] or (pd.notna(confidence) and confidence < 70):
        return "Price movement should be reviewed together with recon support before final comparison."

    if status == "Improving":
        return "Price movement is better than the business trend over the 5-week view."

    if status == "Holding Steady":
        return "Price movement is broadly in line with the business trend."

    if status == "Review Suggested":
        return "Price is moving above the business trend. Review ration mix, delivery cost, and feed movement."

    if status == "Support Opportunity":
        return "Price is moving materially above the business trend. Supportive review is recommended this week."

    return "Review price movement and recon confidence together."


def build_farm_price_progress(feedmill, farm_summary):
    """
    Builds latest 5-week farm price progression from feedmill deliveries.
    Uses weighted delivered price $/t and adjusts farm movement against the business movement.
    """
    if feedmill is None or feedmill.empty or "Week Ending" not in feedmill.columns:
        return pd.DataFrame(), pd.DataFrame()

    df = feedmill.copy()
    df = df[df["Week Ending"].notna()].copy()
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    latest_weeks = sorted(df["Week Ending"].dropna().unique())[-5:]
    df = df[df["Week Ending"].isin(latest_weeks)].copy()

    business = (
        df.groupby("Week Ending", dropna=False)
        .agg(Tonnes=("Tonnes Delivered", "sum"), Delivered_Cost=("Delivered Cost", "sum"))
        .reset_index()
        .sort_values("Week Ending")
    )
    business["Business Price $/t"] = np.where(
        business["Tonnes"] > 0,
        business["Delivered_Cost"] / business["Tonnes"],
        np.nan,
    )

    if len(business) >= 2:
        business_movement = business["Business Price $/t"].iloc[-1] - business["Business Price $/t"].iloc[0]
    else:
        business_movement = np.nan

    weekly = (
        df.groupby(["Farm No", "Farm Name", "Week Ending"], dropna=False)
        .agg(Tonnes=("Tonnes Delivered", "sum"), Delivered_Cost=("Delivered Cost", "sum"))
        .reset_index()
        .sort_values(["Farm Name", "Week Ending"])
    )
    weekly["Delivered Price $/t"] = np.where(
        weekly["Tonnes"] > 0,
        weekly["Delivered_Cost"] / weekly["Tonnes"],
        np.nan,
    )

    advisor_cols = [
        "Farm No", "Area Manager", "Price Confidence Score", "Pricing Status",
        "Closing Stock To Complete", "Closing Stock Variance kg",
    ]
    advisor_map = farm_summary[[c for c in advisor_cols if c in farm_summary.columns]].drop_duplicates("Farm No")
    weekly = weekly.merge(advisor_map, on="Farm No", how="left")
    weekly["Area Manager"] = weekly.get("Area Manager", "Unassigned").fillna("Unassigned")

    rows = []
    for (farm_no, farm_name), grp in weekly.groupby(["Farm No", "Farm Name"], dropna=False):
        grp = grp.sort_values("Week Ending").copy()
        valid = grp[grp["Delivered Price $/t"].notna()].copy()
        weeks_available = valid["Week Ending"].nunique()

        first_price = valid["Delivered Price $/t"].iloc[0] if not valid.empty else np.nan
        latest_price = valid["Delivered Price $/t"].iloc[-1] if not valid.empty else np.nan
        farm_movement = latest_price - first_price if weeks_available >= 2 else np.nan
        adjusted = farm_movement - business_movement if pd.notna(farm_movement) and pd.notna(business_movement) else np.nan
        status = classify_price_progress(adjusted, weeks_available)

        row = {
            "Farm No": farm_no,
            "Farm Name": farm_name,
            "Area Manager": grp["Area Manager"].dropna().iloc[0] if grp["Area Manager"].notna().any() else "Unassigned",
            "Weeks With Deliveries": weeks_available,
            "First Week Price $/t": first_price,
            "Latest Week Price $/t": latest_price,
            "Farm Movement $/t": farm_movement,
            "Business Movement $/t": business_movement,
            "Business-Adjusted Movement $/t": adjusted,
            "Progress Status": status,
            "Current Recon Confidence": grp["Price Confidence Score"].dropna().iloc[0] if "Price Confidence Score" in grp.columns and grp["Price Confidence Score"].notna().any() else np.nan,
            "Current Pricing Status": grp["Pricing Status"].dropna().iloc[0] if "Pricing Status" in grp.columns and grp["Pricing Status"].notna().any() else "Review Suggested",
            "Closing Stock To Complete": grp["Closing Stock To Complete"].dropna().iloc[0] if "Closing Stock To Complete" in grp.columns and grp["Closing Stock To Complete"].notna().any() else 0,
            "Closing Stock Variance kg": grp["Closing Stock Variance kg"].dropna().iloc[0] if "Closing Stock Variance kg" in grp.columns and grp["Closing Stock Variance kg"].notna().any() else 0,
        }

        # Add a fixed 5-week display, newest weeks still shown left-to-right by date.
        for wk in latest_weeks:
            label = pd.to_datetime(wk).strftime("%d/%m")
            wk_row = grp[grp["Week Ending"].eq(wk)]
            row[f"Week {label} $/t"] = wk_row["Delivered Price $/t"].iloc[0] if not wk_row.empty else np.nan

        rows.append(row)

    progress = pd.DataFrame(rows)
    if progress.empty:
        return progress, business

    progress["Focus Note"] = progress.apply(price_progress_note, axis=1)
    status_order = {
        "Support Opportunity": 0,
        "Review Suggested": 1,
        "Not Enough Data": 2,
        "Holding Steady": 3,
        "Improving": 4,
    }
    progress["_status_order"] = progress["Progress Status"].map(status_order).fillna(9)
    progress = progress.sort_values(["_status_order", "Business-Adjusted Movement $/t"], ascending=[True, False]).drop(columns=["_status_order"])

    return progress, business


def build_support_tasks(farm_summary, feedmill, farm, progress):
    """
    Builds a practical support-task list. Supportive language only.
    """
    tasks = []

    if farm_summary is None or farm_summary.empty:
        return pd.DataFrame()

    # Feedmill vs farm-delivered check.
    mill_by_farm = pd.DataFrame()
    farm_by_farm = pd.DataFrame()
    if feedmill is not None and not feedmill.empty:
        mill_by_farm = feedmill.groupby("Farm No", dropna=False).agg(
            Mill_Delivered_kg=("Net kg", "sum"),
            Farm_Name_Mill=("Farm Name", "first"),
        ).reset_index()
    if farm is not None and not farm.empty:
        farm_by_farm = farm.groupby("Farm No", dropna=False).agg(
            Farm_Delivered_kg=("Farm Delivered kg", "sum"),
            Beginning_Stock_kg=("Beginning Stock kg", "sum"),
            Consumed_kg=("Consumed kg", "sum"),
            Farm_Name_Recon=("Farm Name", "first"),
        ).reset_index()

    delivery_check = pd.merge(mill_by_farm, farm_by_farm, on="Farm No", how="outer") if not mill_by_farm.empty or not farm_by_farm.empty else pd.DataFrame()
    if not delivery_check.empty:
        delivery_check["Mill_Delivered_kg"] = pd.to_numeric(delivery_check.get("Mill_Delivered_kg", 0), errors="coerce").fillna(0)
        delivery_check["Farm_Delivered_kg"] = pd.to_numeric(delivery_check.get("Farm_Delivered_kg", 0), errors="coerce").fillna(0)
        delivery_check["Delivery Difference kg"] = delivery_check["Mill_Delivered_kg"] - delivery_check["Farm_Delivered_kg"]

    for _, row in farm_summary.iterrows():
        farm_no = row.get("Farm No", "")
        farm_name = row.get("Farm Name", "")
        advisor = row.get("Area Manager", "Unassigned")
        confidence = row.get("Price Confidence Score", np.nan)
        pricing_status = row.get("Pricing Status", "")

        if pd.to_numeric(row.get("Closing Stock To Complete", 0), errors="coerce") > 0:
            tasks.append({
                "Task Area": "Closing bin stock readings",
                "Farm No": farm_no,
                "Farm Name": farm_name,
                "Area Manager": advisor,
                "Priority": "Support Needed",
                "Why it matters": "Closing stock is still to complete, so the price is not ready to finalise.",
                "Suggested action": "Help the farm confirm and enter physical bin readings before Monday 12pm.",
                "Price Confidence Score": confidence,
                "Pricing Status": pricing_status,
            })

        if abs(pd.to_numeric(row.get("Closing Stock Variance kg", 0), errors="coerce")) > 1000:
            tasks.append({
                "Task Area": "Stock variance review",
                "Farm No": farm_no,
                "Farm Name": farm_name,
                "Area Manager": advisor,
                "Priority": "Review Suggested",
                "Why it matters": "Actual closing stock and calculated closing stock are not lining up.",
                "Suggested action": "Review opening stock, feed deliveries, transfers, and closing bin reading for this farm.",
                "Price Confidence Score": confidence,
                "Pricing Status": pricing_status,
            })

    # Opening stock support from raw farm report.
    if farm is not None and not farm.empty:
        opening_rows = farm[
            (pd.to_numeric(farm.get("Beginning Stock kg", 0), errors="coerce").fillna(0).abs() <= 0.001)
            & (pd.to_numeric(farm.get("Consumed kg", 0), errors="coerce").fillna(0) > 0)
            & (pd.to_numeric(farm.get("Farm Delivered kg", 0), errors="coerce").fillna(0) <= 0)
        ].copy()
        if not opening_rows.empty:
            opening_summary = opening_rows.groupby(["Farm No", "Farm Name"], dropna=False).size().reset_index(name="Rows")
            advisor_lookup = farm_summary.set_index("Farm No")["Area Manager"].to_dict() if "Area Manager" in farm_summary.columns else {}
            confidence_lookup = farm_summary.set_index("Farm No")["Price Confidence Score"].to_dict() if "Price Confidence Score" in farm_summary.columns else {}
            status_lookup = farm_summary.set_index("Farm No")["Pricing Status"].to_dict() if "Pricing Status" in farm_summary.columns else {}
            for _, r in opening_summary.iterrows():
                tasks.append({
                    "Task Area": "Opening stock confirmation",
                    "Farm No": r.get("Farm No", ""),
                    "Farm Name": r.get("Farm Name", ""),
                    "Area Manager": advisor_lookup.get(r.get("Farm No", ""), "Unassigned"),
                    "Priority": "Review Suggested",
                    "Why it matters": "Opening stock is zero while feed consumption exists and no delivery was captured for the row.",
                    "Suggested action": "Confirm whether opening stock should have been entered for the period.",
                    "Price Confidence Score": confidence_lookup.get(r.get("Farm No", ""), np.nan),
                    "Pricing Status": status_lookup.get(r.get("Farm No", ""), "Review Suggested"),
                })

    # Delivery capture support.
    if not delivery_check.empty:
        advisor_lookup = farm_summary.set_index("Farm No")["Area Manager"].to_dict() if "Area Manager" in farm_summary.columns else {}
        name_lookup = farm_summary.set_index("Farm No")["Farm Name"].to_dict() if "Farm Name" in farm_summary.columns else {}
        confidence_lookup = farm_summary.set_index("Farm No")["Price Confidence Score"].to_dict() if "Price Confidence Score" in farm_summary.columns else {}
        status_lookup = farm_summary.set_index("Farm No")["Pricing Status"].to_dict() if "Pricing Status" in farm_summary.columns else {}
        delivery_issues = delivery_check[delivery_check["Delivery Difference kg"].abs() > 1000].copy()
        for _, r in delivery_issues.iterrows():
            farm_no = r.get("Farm No", "")
            tasks.append({
                "Task Area": "Feed deliveries captured",
                "Farm No": farm_no,
                "Farm Name": name_lookup.get(farm_no, r.get("Farm_Name_Mill", r.get("Farm_Name_Recon", ""))),
                "Area Manager": advisor_lookup.get(farm_no, "Unassigned"),
                "Priority": "Support Needed",
                "Why it matters": f"Feedmill delivered and farm-reported delivered feed differ by about {r.get('Delivery Difference kg', 0):,.0f} kg.",
                "Suggested action": "Check whether all feed deliveries were captured in Amino for the farm period.",
                "Price Confidence Score": confidence_lookup.get(farm_no, np.nan),
                "Pricing Status": status_lookup.get(farm_no, "Review Suggested"),
            })

    # Price movement support from progress table.
    if progress is not None and not progress.empty:
        price_issues = progress[progress["Progress Status"].isin(["Review Suggested", "Support Opportunity"])].copy()
        for _, r in price_issues.iterrows():
            tasks.append({
                "Task Area": "Price movement review",
                "Farm No": r.get("Farm No", ""),
                "Farm Name": r.get("Farm Name", ""),
                "Area Manager": r.get("Area Manager", "Unassigned"),
                "Priority": r.get("Progress Status", "Review Suggested"),
                "Why it matters": "Delivered price is moving above the business trend over the 5-week view.",
                "Suggested action": "Review ration mix, delivery cost, timing, and recon confidence before final comparison.",
                "Price Confidence Score": r.get("Current Recon Confidence", np.nan),
                "Pricing Status": r.get("Current Pricing Status", "Review Suggested"),
            })

    out = pd.DataFrame(tasks)
    if out.empty:
        return out

    priority_order = {"Support Opportunity": 0, "Support Needed": 1, "Review Suggested": 2, "Not Enough Data": 3}
    out["_priority_order"] = out["Priority"].map(priority_order).fillna(9)
    out = out.drop_duplicates(["Task Area", "Farm No", "Suggested action"]).sort_values(["_priority_order", "Area Manager", "Farm Name"]).drop(columns=["_priority_order"])
    return out


def build_advisor_focus(progress, support_tasks, farm_summary):
    if farm_summary is None or farm_summary.empty:
        return pd.DataFrame()

    base = farm_summary.groupby("Area Manager", dropna=False).agg(
        Farms=("Farm No", "nunique"),
        Avg_Confidence=("Price Confidence Score", "mean"),
        Support_Queue=("Pricing Status", lambda s: s.isin(["Support Needed", "Price Not Ready"]).sum()),
    ).reset_index()

    if progress is not None and not progress.empty:
        prog = progress.groupby("Area Manager", dropna=False).agg(
            Improving=("Progress Status", lambda s: (s == "Improving").sum()),
            Holding_Steady=("Progress Status", lambda s: (s == "Holding Steady").sum()),
            Review_Suggested=("Progress Status", lambda s: (s == "Review Suggested").sum()),
            Support_Opportunity=("Progress Status", lambda s: (s == "Support Opportunity").sum()),
            Avg_Business_Adjusted_Movement=("Business-Adjusted Movement $/t", "mean"),
        ).reset_index()
        base = base.merge(prog, on="Area Manager", how="left")

    if support_tasks is not None and not support_tasks.empty:
        task_theme = (
            support_tasks.groupby(["Area Manager", "Task Area"], dropna=False)
            .size()
            .reset_index(name="Task Count")
            .sort_values(["Area Manager", "Task Count"], ascending=[True, False])
            .drop_duplicates("Area Manager")
            .rename(columns={"Task Area": "Main Support Theme"})
        )
        base = base.merge(task_theme[["Area Manager", "Main Support Theme", "Task Count"]], on="Area Manager", how="left")

    for col in ["Improving", "Holding_Steady", "Review_Suggested", "Support_Opportunity", "Task Count"]:
        if col not in base.columns:
            base[col] = 0
        base[col] = pd.to_numeric(base[col], errors="coerce").fillna(0).astype(int)

    if "Avg_Business_Adjusted_Movement" not in base.columns:
        base["Avg_Business_Adjusted_Movement"] = np.nan

    if "Main Support Theme" not in base.columns:
        base["Main Support Theme"] = "No clear repeated theme"
    base["Main Support Theme"] = base["Main Support Theme"].fillna("No clear repeated theme")

    def advisor_note(row):
        if row.get("Support_Opportunity", 0) > 0:
            return "Focus on farms where price movement is above the business trend, but check recon confidence first."
        if row.get("Support_Queue", 0) > 0:
            return "Focus on recon completion and support tasks so pricing can be finalised confidently."
        if row.get("Improving", 0) > 0 and row.get("Review_Suggested", 0) == 0:
            return "Good progress showing. Keep current support rhythm in place."
        return "Monitor weekly movement and support any farms with incomplete recon."

    base["Suggested Advisor Focus"] = base.apply(advisor_note, axis=1)
    base = base.sort_values(["Support_Opportunity", "Support_Queue", "Avg_Business_Adjusted_Movement"], ascending=[False, False, False])
    return base



# ------------------------------------------------------------
# Header / Upload / Data load
# ------------------------------------------------------------
st.markdown(
    """
    <div class="pf-hero">
        <h1>Pace Feed Price Control</h1>
        <p>Supportive weekly dashboard for feed price tracking, recon confidence, and farms needing help before Monday 12pm cutoff.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# Make sure status legend CSS exists before rendering legend.
try:
    inject_progress_table_styles()
except Exception:
    pass



# Safe defaults for upload widgets.
feedmill_file = None
farm_file = None
farm_master_file = None

with st.sidebar:
    st.header("Upload reports")

    feedmill_file = st.file_uploader(
        "Amino feedmill report",
        type=["xlsx", "xls"],
        key="feedmill",
    )

    farm_file = st.file_uploader(
        "Amino farm report",
        type=["xlsx", "xls"],
        key="farm",
    )

    farm_master_file = st.file_uploader(
        "Optional Service Manager / Tech Advisor mapping",
        type=["csv", "xlsx", "xls"],
        key="farm_master",
        help=r"If left blank, the app will use C:\Pace Feed Price Control\Files to Upload\Tech Advisor Name List.csv if it exists.",
    )

# Persist sidebar uploads immediately so refresh/restart can reuse them.
if feedmill_file is not None:
    save_uploaded_file_slot("feedmill", feedmill_file)

if farm_file is not None:
    save_uploaded_file_slot("farm", farm_file)

if farm_master_file is not None:
    save_uploaded_file_slot("advisor", farm_master_file)

with st.sidebar:
    runtime_advisor = get_runtime_upload_as_file("advisor")
    disk_advisor = get_saved_upload_path("advisor")
    if runtime_advisor is not None:
        st.success(f"Service Manager mapping saved in app memory: {getattr(runtime_advisor, 'name', 'advisor mapping')}")
    elif disk_advisor is not None:
        st.success(f"Service Manager mapping saved: {disk_advisor.name}")

with st.sidebar:
    saved_advisor_path = get_saved_upload_path("advisor")
    if saved_advisor_path is not None:
        st.success(f"Service Manager mapping saved: {saved_advisor_path.name}")
    else:
        st.caption(r"Mapping file: upload Service Manager / Tech Advisor mapping, or use local file C:\Pace Feed Price Control\Files to Upload\Tech Advisor Name List.csv")

    st.divider()
    week_ending_day = "Sunday"
    st.caption("Week ending: Sunday")
    st.caption("Recon review: use during week, at cutoff, or historically")
    st.caption("Uploaded files are saved and should reload after page refresh.")
    st.caption("Support-first language is built in: the app highlights where help is needed, not where people have failed.")

if (feedmill_file is None and get_saved_upload_path('feedmill') is None) or (farm_file is None and get_saved_upload_path('farm') is None):
    st.info("Upload the Amino feedmill report and Amino farm report to begin. Saved files will reload automatically once uploaded.")
    st.markdown(
        """
        <div class="pf-note">
        <strong>Version focus:</strong> use the feedmill and farm recon reports to show weekly price movement, current recon readiness, and Service Manager support priorities before the Monday 12pm cutoff.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

raw_feedmill = read_upload_or_saved('feedmill', feedmill_file)
raw_farm = read_upload_or_saved('farm', farm_file)
farm_master = read_farm_master(farm_master_file)

# Safe default for weekly reporting/recon logic.
week_ending_day = "Sunday"

feedmill = prepare_feedmill(raw_feedmill, week_ending_day)
farm = prepare_farm_recon(raw_farm)
farm_summary = build_farm_summary(feedmill, farm, farm_master)

if farm_master is None or farm_master.empty:
    st.warning(
        "Service Manager mapping is not loaded. Upload the Service Manager / Tech Advisor mapping file in the sidebar or Upload page so Service Manager names populate after refresh."
    )

weekly_feedmill = build_weekly_feedmill(feedmill)

# Latest five weeks only for primary trend.
if not weekly_feedmill.empty:
    latest_weeks = weekly_feedmill["Week Ending"].dropna().sort_values().tail(5)
    weekly_5 = weekly_feedmill[weekly_feedmill["Week Ending"].isin(latest_weeks)].copy()
else:
    weekly_5 = pd.DataFrame()

# Top KPIs.
# Feedmill tonnes remains upload-wide; delivered price cards use the last completed Sunday week only.
total_tonnes = feedmill["Tonnes Delivered"].sum() if not feedmill.empty and "Tonnes Delivered" in feedmill.columns else 0

last_week_price_kpis = calc_avg_delivered_price_by_type_last_full_week(feedmill, farm)
last_full_week_end = last_week_price_kpis["week_ending"]
last_full_week_label = last_full_week_end.strftime("%d/%m/%Y") if pd.notna(last_full_week_end) else "latest completed week"

avg_rearing_price = last_week_price_kpis["rearing_avg"]
avg_layer_price = last_week_price_kpis["layer_avg"]

farms_in_view = farm_summary["Farm No"].nunique() if not farm_summary.empty else 0
support_needed = farm_summary["Pricing Status"].isin(["Support Needed", "Price Not Ready"]).sum() if not farm_summary.empty else 0
ready = farm_summary["Pricing Status"].eq("Ready to Finalise").sum() if not farm_summary.empty else 0

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    kpi_card("Feedmill tonnes", fmt_num(total_tonnes, 1), "Total delivered tonnes in uploaded feedmill file")
with c2:
    kpi_card("Avg delivered price - Rearing", fmt_currency(avg_rearing_price, 2) + "/t", f"Week ending {last_full_week_label}")
with c3:
    kpi_card("Avg delivered price - Layers", fmt_currency(avg_layer_price, 2) + "/t", f"Week ending {last_full_week_label}")
with c4:
    kpi_card("Farms in view", f"{farms_in_view:,}", "Unique farms across uploaded reports")
with c5:
    kpi_card("Support queue", f"{support_needed:,}", "Farms where price is not ready or recon support is suggested")


farm_progress, business_progress = build_farm_price_progress(feedmill, farm_summary)
support_tasks_df = build_support_tasks(farm_summary, feedmill, farm, farm_progress)
advisor_focus_df = build_advisor_focus(farm_progress, support_tasks_df, farm_summary)

# ------------------------------------------------------------
# Tabs
# ------------------------------------------------------------
st.markdown('<div class="pf-menu-spacer"></div>', unsafe_allow_html=True)
tabs = st.tabs([
    "Insights",
    "Current Recon",
    "5-Week Progress",
    "Service Manager Focus",
    "Support Tasks",
    "Upload",
])

# ------------------------------------------------------------
# Overview
# ------------------------------------------------------------
with tabs[0]:

    # Compact farm recon score
    render_farm_recon_score_insights(farm, farm_summary)


    st.markdown('<div class="pf-section-title">5-week delivered feed price trend</div>', unsafe_allow_html=True)
    render_rearing_layer_trend_chart(feedmill, farm)

    render_brood_layer_price_perspective(feedmill, farm)

# ------------------------------------------------------------
# ------------------------------------------------------------
# Upload
# ------------------------------------------------------------
with tabs[5]:
    render_upload_page()

# Current Recon
# ------------------------------------------------------------
with tabs[1]:
    render_current_recon_page(farm, farm_summary)

# ------------------------------------------------------------
# 5-Week Progress
# ------------------------------------------------------------
with tabs[2]:
    st.markdown('<div class="pf-section-title">5-Week Price Progression</div>', unsafe_allow_html=True)

    # Farm progression table with SVG icons and conditional formatting.
    # This renders when the progression dataframe has already been built in this tab.
    try:
        if "progress_df" in locals() and progress_df is not None and not progress_df.empty:
            st.markdown("#### Farm progression table")
            render_progress_html_table(progress_df, max_rows=80)
    except Exception:
        pass

    st.markdown(
        """
        <div class="pf-note">
        This view tracks delivered feed price by farm over the latest 5 Sunday week-ending periods. 
        Movement is adjusted against the business average so farms are not unfairly flagged when the whole business price moves.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if farm_progress.empty:
        st.warning("No farm-level 5-week price progression could be built from the uploaded feedmill report.")
    else:
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            kpi_card("Improving", f"{(farm_progress['Progress Status'] == 'Improving').sum():,}", "Farms moving better than business trend")
        with p2:
            kpi_card("Holding steady", f"{(farm_progress['Progress Status'] == 'Holding Steady').sum():,}", "Farms broadly in line with business trend")
        with p3:
            kpi_card("Review suggested", f"{(farm_progress['Progress Status'] == 'Review Suggested').sum():,}", "Farms moving above business trend")
        with p4:
            kpi_card("Support opportunity", f"{(farm_progress['Progress Status'] == 'Support Opportunity').sum():,}", "Farms needing focused support this week")

        chart_df = farm_progress[farm_progress["Progress Status"].isin(["Support Opportunity", "Review Suggested", "Improving"])].copy()
        chart_df = chart_df.sort_values("Business-Adjusted Movement $/t", ascending=False).head(20)
        if not chart_df.empty:
            fig = px.bar(
                chart_df,
                x="Farm Name",
                y="Business-Adjusted Movement $/t",
                color="Progress Status",
                color_discrete_map=PROGRESS_STATUS_COLOURS,
                title="Farm movement vs business trend — focus farms",
                hover_data=["Area Manager", "Latest Week Price $/t", "Current Pricing Status"],
            )
            fig.update_layout(height=500, margin=dict(l=20, r=20, t=50, b=120), xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No focus farms to chart yet.")

        week_cols = [c for c in farm_progress.columns if c.startswith("Week ")]
        display_cols = [
            "Farm No", "Farm Name", "Area Manager", "Progress Status",
            "Weeks With Deliveries", *week_cols,
            "Farm Movement $/t", "Business Movement $/t", "Business-Adjusted Movement $/t",
            "Current Pricing Status", "Current Recon Confidence", "Focus Note",
        ]
        display_cols = [c for c in display_cols if c in farm_progress.columns]
        render_week_price_table_with_trends(farm_progress[display_cols], height=620)

# ------------------------------------------------------------
# Service Manager Focus
# ------------------------------------------------------------
with tabs[3]:
    render_service_manager_focus_page(feedmill, farm_summary)

    st.markdown(
        """
        <div class="pf-note">
        This page translates farm movement and recon quality into a weekly focus view for each Service Manager. 
        It is designed to show where support is most useful, not to rank people negatively.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if farm_master_file is None and farm_master.empty:
        st.info(
            r"Service Manager reporting will activate when this file exists: "
            r"C:\Pace Feed Price Control\Files to Upload\Tech Advisor Name List.csv. "
            "You can also upload a mapping file manually in the sidebar."
        )
    elif farm_master_file is None and not farm_master.empty:
        st.success(r"Using local Service Manager file from C:\Pace Feed Price Control\Files to Upload.")

    if advisor_focus_df.empty:
        st.warning("No Service Manager focus view could be built yet.")
    else:
        c1, c2 = st.columns([1, 1])
        with c1:
            fig = px.bar(
                advisor_focus_df,
                x="Area Manager",
                y="Support_Queue",
                title="Farms needing recon support by Service Manager",
            )
            fig.update_layout(height=390, margin=dict(l=20, r=20, t=50, b=90), xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            fig = px.bar(
                advisor_focus_df,
                x="Area Manager",
                y="Avg_Business_Adjusted_Movement",
                title="Average price movement vs business trend",
            )
            fig.update_layout(height=390, margin=dict(l=20, r=20, t=50, b=90), xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            advisor_focus_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Avg_Confidence": st.column_config.NumberColumn(format="%.0f"),
                "Avg_Business_Adjusted_Movement": st.column_config.NumberColumn(format="$%.2f"),
            },
        )


# ------------------------------------------------------------
# Support Tasks
# ------------------------------------------------------------
with tabs[2]:
    st.markdown('<div class="pf-section-title">Support Tasks</div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="pf-note">
        This turns the data into practical support work: opening stock, feed deliveries captured, closing bin stock readings, stock variance, and price movement review.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if support_tasks_df.empty:
        st.success("No major support tasks were detected from the uploaded reports.")
    else:
        task_summary = (
            support_tasks_df.groupby("Task Area", dropna=False)
            .agg(Farms=("Farm No", "nunique"), Advisors=("Area Manager", "nunique"))
            .reset_index()
            .sort_values("Farms", ascending=False)
        )

        c1, c2 = st.columns([0.9, 1.1])
        with c1:
            fig = px.bar(
                task_summary,
                x="Task Area",
                y="Farms",
                title="Support tasks by theme",
            )
            fig.update_layout(height=390, margin=dict(l=20, r=20, t=50, b=120), xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            advisor_task = (
                support_tasks_df.groupby(["Area Manager", "Task Area"], dropna=False)
                .size()
                .reset_index(name="Tasks")
            )
            fig = px.bar(
                advisor_task,
                x="Area Manager",
                y="Tasks",
                color="Task Area",
                title="Support tasks by Service Manager",
            )
            fig.update_layout(height=390, margin=dict(l=20, r=20, t=50, b=90), xaxis_tickangle=-35)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="pf-section-title">Training opportunities</div>', unsafe_allow_html=True)
        top_task = task_summary.iloc[0] if not task_summary.empty else None
        if top_task is not None:
            st.markdown(
                f"""
                <div class="pf-note">
                <strong>Main training opportunity:</strong> {top_task['Task Area']} is the most common support theme, affecting {int(top_task['Farms'])} farm(s).<br>
                <strong>Suggested action:</strong> Run a short refresher with farm managers on this task and show why it affects fair feed-price finalisation.
                </div>
                """,
                unsafe_allow_html=True,
            )

        selected_tasks = st.multiselect(
            "Task area filter",
            options=sorted(support_tasks_df["Task Area"].dropna().unique().tolist()),
            default=sorted(support_tasks_df["Task Area"].dropna().unique().tolist()),
        )
        task_view = support_tasks_df[support_tasks_df["Task Area"].isin(selected_tasks)].copy()
        st.dataframe(
            task_view,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Price Confidence Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"),
            },
        )

