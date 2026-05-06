# Feed Price Dashboard fix
# Purpose:
# 1) Hide rows where Farm Name is blank / None / nan
# 2) Sort the Current Recon table by Recon Readiness % ascending
# 3) Keep the fix safe if the percentage column is stored as text like '29%'

import pandas as pd


def clean_current_recon_table(current_recon_df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply this immediately before rendering the Current Recon table.

    Example:
        current_recon_df = clean_current_recon_table(current_recon_df)
        st.dataframe(current_recon_df, use_container_width=True, hide_index=True)
    """
    if current_recon_df is None or current_recon_df.empty:
        return current_recon_df

    current_recon_df = current_recon_df.copy()

    # ------------------------------------------------------------
    # Hide rows with empty / missing farm names
    # ------------------------------------------------------------
    if "Farm Name" in current_recon_df.columns:
        farm_name_clean = (
            current_recon_df["Farm Name"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        current_recon_df = current_recon_df[
            (farm_name_clean != "")
            & (~farm_name_clean.str.lower().isin(["none", "nan", "null", "-"]))
        ].copy()

    # ------------------------------------------------------------
    # Sort Current Recon table ascending by Recon Readiness %
    # ------------------------------------------------------------
    if "Recon Readiness %" in current_recon_df.columns:
        current_recon_df["_recon_sort"] = pd.to_numeric(
            current_recon_df["Recon Readiness %"]
            .astype(str)
            .str.replace("%", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip(),
            errors="coerce",
        )

        current_recon_df = (
            current_recon_df
            .sort_values("_recon_sort", ascending=True, na_position="last")
            .drop(columns=["_recon_sort"])
        )

    return current_recon_df


# ------------------------------------------------------------------
# QUICK PASTE VERSION
# ------------------------------------------------------------------
# Paste this directly before the Current Recon table is displayed:
#
# current_recon_df = clean_current_recon_table(current_recon_df)
#
# If your dataframe has a different name, replace current_recon_df with
# the dataframe used for the Current Recon table.
