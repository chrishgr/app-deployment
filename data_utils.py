# data_utils.py
from pathlib import Path
import pandas as pd
import streamlit as st

@st.cache_data(show_spinner=False)
def load_df(path: str):
    """Leser en pandas-DataFrame fra pickle og returnerer (df, err)."""
    p = Path(path)
    if not p.exists():
        return None, f"Finner ikke fil: {p}"
    try:
        df = pd.read_pickle(p)
    except Exception as e:
        return None, f"Kunne ikke lese pickle: {e}"
    return df, None

# data_utils.py
def get_unique_values(df: pd.DataFrame, column_string: str):
    """Sorterte unike verdier fra en kolonne (takler både liste- og skalarverdier)."""
    s = df[column_string]
    # Sjekk om noen rader er liste-aktige
    is_listy = s.dtype == "O" and s.apply(lambda x: isinstance(x, (list, set, tuple))).any()

    vals = set()
    if is_listy:
        for v in s.dropna():
            if isinstance(v, (list, set, tuple)):
                for item in v:
                    txt = str(item).strip()
                    if txt:
                        vals.add(txt)
    else:
        for v in s.dropna().astype(str).str.strip():
            if v:
                vals.add(v)

    return sorted(vals)


# def get_unique_values(df: pd.DataFrame, column_string: str):
#     """Sorterte unike verdier fra en kolonne (uten NaN/tomme strenger)."""
#     # s = series.dropna().astype(str).str.strip()
#     # return sorted([v for v in s.unique() if v])
#     return set([item for value in df[column_string].values for item in value])
