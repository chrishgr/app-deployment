import streamlit as st
import pandas as pd
from pathlib import Path
from io import BytesIO
from data_utils import load_df, get_unique_values  # all databehandling i egen modul

# --- Side-konfigurasjon ---
st.set_page_config(page_title="SME - syntetiske datasett", layout="wide")
st.title("Database: drøftingsnotater for klinisk etiske komitéer (syntetisk data)")

# --- Last inn data ---
with st.sidebar:
    st.header("⚙️ Fil")
    file_path = st.text_input(
        "Sti til pickle-fil (.pkl)",
        value="data/cases_all.pkl",
        help="Skriv inn sti til en pandas-DataFrame lagret med to_pickle()",
        key="file_path_input",
    )

if not file_path:
    st.info("Skriv inn en gyldig sti til .pkl i sidepanelet.")
    st.stop()

df, err = load_df(file_path)
if err:
    st.error(err)
    st.stop()

# --- Hjelpefunksjoner ---
def ensure_listlike(series: pd.Series):
    """Gjør verdier til lister når kolonnen egentlig inneholder tags (liste pr rad)."""
    return series.apply(lambda v: v if isinstance(v, (list, tuple, set)) else ([] if pd.isna(v) else [str(v)]))

def multiselect_with_counts(df_in: pd.DataFrame, col: str, label: str = None, key: str = None, return_mask: bool = False):
    """
    Viser en multiselect og returnerer enten en filtrert DataFrame (default)
    eller en boolean maske (hvis return_mask=True).
    """
    if label is None:
        label = col
    if key is None:
        key = f"{col}_ms"

    all_options = get_unique_values(df_in, col)
    if not all_options:
        st.info(f"Ingen verdier å filtrere på i kolonnen «{col}».")
        mask = pd.Series(True, index=df_in.index)
        if return_mask:
            return mask, []
        return df_in, []

    s = ensure_listlike(df_in[col]) if col in df_in.columns else pd.Series([[]]*len(df_in))
    counts = {opt: int(s.apply(lambda lst: opt in set(lst)).sum()) for opt in all_options}
    and_mode = st.toggle("Match alle valgte (AND)", value=False, key=f"{key}_andtoggle")
    lab_to_val = {f"{opt} ({counts[opt]})": opt for opt in all_options}
    sel_labels = st.multiselect(label, options=list(lab_to_val.keys()), default=[], key=key)
    selected = [lab_to_val[lbl] for lbl in sel_labels]

    # --- Maske-generering ---
    if not selected:
        mask = pd.Series(True, index=df_in.index)
    elif s.empty:
        st.warning(f"Kolonnen «{col}» finnes ikke i dataene.")
        mask = pd.Series(True, index=df_in.index)
    else:
        sel_set = set(selected)
        if and_mode:
            mask = s.apply(lambda lst: sel_set.issubset(set(lst)))
        else:
            mask = s.apply(lambda lst: len(sel_set.intersection(set(lst))) > 0)

    # Returner enten maske eller filtrert dataframe
    if return_mask:
        return mask, selected
    else:
        return df_in[mask], selected

# --- Start av filtrering ---
st.subheader("🔍 Filtrer")
df_view = df.copy()

# --- 1) Filtrer på HELSETJENESTE først ---
if "helsetjeneste" in df_view.columns:
    st.write("**Helsetjeneste**")
    s_helse = df_view["helsetjeneste"].astype(str).str.lower().fillna("")
    spes_mask = s_helse.str.contains("spesialist")
    komm_mask = s_helse.str.contains("komm") | s_helse.str.contains("omsorg")
    cnt_spec = int(spes_mask.sum())
    cnt_komm = int(komm_mask.sum())
    
    check_col1, check_col2, _ = st.columns([1, 2, 1])
    with check_col1:
        spes_choice = st.checkbox(f"Spesialist ({cnt_spec})", key="helse_spes_check")
    with check_col2:
        komm_choice = st.checkbox(f"Kommunale helse- og omsorgstjenester ({cnt_komm})", key="helse_komm_check")

    if spes_choice and komm_choice:
        df_view = df_view[spes_mask | komm_mask]
    elif spes_choice:
        df_view = df_view[spes_mask]
    elif komm_choice:
        df_view = df_view[komm_mask]

else:
    st.info("Finner ikke kolonnen «helsetjeneste» i datasettet.")

# --- 2) Kombiner Fagområde og Tags med valgbar logikk ---
st.markdown("---")
st.write("#### Kombiner Fagområde og Tags")
st.caption("Velg hvordan filtrene under skal kombineres.")

combine_choice = st.radio(
    "Logisk operator mellom Fagområde og Tags:",
    options=["OR (vis treff fra minst ett filter)", "AND (vis kun treff som er i begge filtrene)"],
    index=1,
    horizontal=True,
    key="main_combiner"
)
use_and_logic = combine_choice.startswith("AND")

col1, col2 = st.columns(2)

if use_and_logic:
    # AND-logikk: Filtrene er avhengige og kjøres i sekvens (cascading).
    # Valg i Fagområde vil begrense alternativene som vises i Tags.
    st.info("ℹ️ AND-modus er aktiv. Valg i 'Fagområde' oppdaterer dynamisk listen over tilgjengelige 'Tags'.")
    
    with col1:
        # Steg 1: Filtrer på fagområde. Returnerer en ny, filtrert dataframe.
        df_after_fag, _ = multiselect_with_counts(
            df_view, "fagområde", label="Fagområde", key="fagomraader_ms"
        )

    with col2:
        # Steg 2: Filtrer på tags, men bruk den allerede filtrerte dataframen fra steg 1.
        df_after_tags, _ = multiselect_with_counts(
            df_after_fag, "tags", label="Tags", key="tags_ms"
        )
    
    # Det endelige resultatet er den sist filtrerte dataframen.
    df_final = df_after_tags

else:
    # OR-logikk: Filtrene er uavhengige. Begge baseres på den samme df_view.
    with col1:
        mask_fag, sel_fag = multiselect_with_counts(
            df_view, "fagområde", label="Fagområde", key="fagomraader_ms", return_mask=True
        )

    with col2:
        mask_tags, sel_tags = multiselect_with_counts(
            df_view, "tags", label="Tags", key="tags_ms", return_mask=True
        )

    # Kombiner maskene med OR-logikk
    if sel_fag and sel_tags:
        final_mask = mask_fag | mask_tags
    elif sel_fag:
        final_mask = mask_fag
    elif sel_tags:
        final_mask = mask_tags
    else:
        final_mask = pd.Series(True, index=df_view.index)
    
    df_final = df_view[final_mask]

# --- Visning av data ---
st.markdown("---")
#st.dataframe(df_final, use_container_width=True) #Bruk denne istedenfor teksten nedenfor dersom ønske om å bar vise fram uten å kunne ekspandere radene. 
st.caption(f"Viser {len(df_final):,} rader × {df_final.shape[1]} kolonner")
# --- Interaktiv tabell: klikk en celle for å vise hele raden ---
event = st.dataframe(
    df_final,
    use_container_width=True,   # behold denne hvis du bruker den i dag
    hide_index=True,
    on_select="rerun",          # aktiverer seleksjoner og returnerer event-data
    selection_mode="single-cell",
    key="df_final_view",
)

sel = event.selection
if sel and sel.cells:
    row_idx, col_name = sel.cells[-1]   # (radposisjon, kolonnenavn)
    row = df_final.iloc[row_idx]
    # --- Vis/skjul detaljene i en expander (default lukket) ---
    with st.expander("🔎 Vis rad-detaljer", expanded=False):
        st.write(f"Valgt celle: **{col_name} = {row[col_name]}**")

        # Ren tekst: "Kolonne: verdi" pr. linje
        lines = [f"**{col}:**\n{val}" for col, val in row.items()]
        st.markdown("\n\n".join(lines))

# --- Lagre filtrert DataFrame

