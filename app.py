# app.py
import math
from datetime import date
import json
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

# --- map clicks (optional) ---
try:
    from streamlit_plotly_events import plotly_events
    HAVE_PLOTLY_EVENTS = True
except Exception:
    HAVE_PLOTLY_EVENTS = False

st.set_page_config(page_title="Housing Affordability — Sydney (SA2, synthetic)", layout="wide")

# ---------- utils ----------
def mulberry32(seed: int):
    a = seed & 0xFFFFFFFF
    def rnd():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = (a ^ (a >> 15)) * (1 | a)
        t = (t + ((t ^ (t >> 7)) * (61 | t))) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296
    return rnd

def range_months(start: date, end: date):
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append(date(y, m, 1))
        m += 1
        if m == 13:
            m = 1; y += 1
    return months

def money(x):
    try: x = float(x)
    except: x = 0.0
    return f"A$ {int(round(x)):,.0f}"

def color_scale_gyr(invert=False):
    scale = [
        [0.0, "rgb(0,128,0)"],
        [0.5, "rgb(255,215,0)"],
        [1.0, "rgb(220,20,60)"]
    ]
    return list(reversed(scale)) if invert else scale

def annuity_monthly(L, r_annual, years):
    L = max(0.0, float(L)); m = float(r_annual)/12.0; n = max(1, int(round(years*12)))
    if L == 0: return 0.0
    if m == 0: return L / n
    return (m*L) / (1 - (1+m)**(-n))

def principal_from_monthly(payment, r_annual, years):
    m = float(r_annual)/12.0; n = max(1, int(round(years*12)))
    if m == 0: return float(payment)*n
    return float(payment) * (1 - (1+m)**(-n)) / m

RENT_BEDROOM_COEFFS = {1:1.00, 2:1.35, 3:1.75}
PRICE_BEDROOM_COEFFS = {1:0.85, 2:1.00, 3:1.25}

# ---------- synthetic series (12 SA2) ----------
@st.cache_data
def load_synthetic():
    rng = mulberry32(20250926)
    sa2 = [f"SA2_{i:02d}" for i in range(1,13)]
    months = range_months(date(2015,1,1), date(2025,9,1))
    rows = []
    for code in sa2:
        price = 650000 + rng()*950000
        rent  = 420 + rng()*480
        income= 70000 + rng()*55000
        gp = 0.0018 + (rng()-0.5)*0.0008
        gr = 0.0012 + (rng()-0.5)*0.0006
        gi = 0.0009 + (rng()-0.5)*0.0005
        for t, dt in enumerate(months):
            seas = 1 + 0.02*math.sin(2*math.pi*(t%12)/12)
            price *= 1 + gp + max(-0.003, min(0.003, (rng()-0.5)*0.002))
            rent  *= 1 + gr + max(-0.002, min(0.002, (rng()-0.5)*0.0016))
            income*= 1 + gi + max(-0.0015, min(0.0015, (rng()-0.5)*0.0012))
            P  = max(250000, price*seas + (rng()-0.5)*24000)
            Rw = max(250,    rent*seas  + (rng()-0.5)*16)
            I  = max(40000,  income*(0.995+(rng()-0.5)*0.004))
            rows.append(dict(date=dt.strftime("%Y-%m"), SA2_CODE=code,
                             MedianPrice=P, MedianRent_week=Rw, MedianIncome_annual=I))
    df = pd.DataFrame(rows)
    # 3x4 grid positions
    grid = pd.DataFrame({
        "SA2_CODE": sa2,
        "row": [0,0,0,0, 1,1,1,1, 2,2,2,2],
        "col": [0,1,2,3, 0,1,2,3, 0,1,2,3]
    })
    return df, grid, months

# ---------- real SA2 polygons (auto-load) ----------
# ABS ASGS 2021 → SA2 (FeatureServer), returns GeoJSON with the needed fields.
ABS_QUERY = (
    "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/SA2/FeatureServer/0/query"
    "?f=geojson"
    "&where=gccsa_name_2021%3D%27Greater%20Sydney%27"
    "&outFields=sa2_code_2021,sa2_name_2021"
    "&outSR=4326"
    "&geometryPrecision=5"
)

GITHUB_FALLBACK = "https://raw.githubusercontent.com/centreborelli/geo-aus/master/ABS/2016/SA2/sa2_2016_sydney_simplified.geojson"

@st.cache_data(ttl=24*3600)
def load_sa2_geojson(max_features=15):
    # 1) ABS ArcGIS (Greater Sydney)
    try:
        r = requests.get(ABS_QUERY, timeout=15)
        if r.ok:
            gj = r.json()
            if isinstance(gj, dict) and gj.get("features"):
                feats = sorted(gj["features"], key=lambda f: f.get("properties",{}).get("sa2_name_2021",""))[:max_features]
                gj = {"type":"FeatureCollection","features":feats}
                return gj, "abs"
    except Exception:
        pass
    # 2) GitHub fallback (simplified Sydney contours)
    try:
        r = requests.get(GITHUB_FALLBACK, timeout=15)
        if r.ok:
            gj = r.json()
            if isinstance(gj, dict) and gj.get("features"):
                feats = gj["features"][:max_features]
                gj = {"type":"FeatureCollection","features":feats}
                return gj, "github"
    except Exception:
        pass
    return None, "none"

# ---------- init data ----------
df, grid, months = load_synthetic()
last_month = months[-1].strftime("%Y-%m")

# ---------- sidebar ----------
st.sidebar.title("Settings")
segment = st.sidebar.radio("Mode", ["Buyers", "Tenants"], index=0)
segment_key = "buyers" if segment.startswith("Buyers") else "tenants"
metric = st.sidebar.selectbox("Map layer", ["RTI","PTI","Median Rent","Median Price","Median Income","Payment Cap Gap"], index=0)
bedrooms = st.sidebar.slider("Bedrooms", 1, 3, 2)
preset = st.sidebar.selectbox("Period", ["Max","5y","3y","1y"], index=0)

use_real_geo = st.sidebar.checkbox("Real SA2 polygons", True,
                                   help="If off — shows a compact 3×4 grid.")

sa2_all = grid["SA2_CODE"].tolist()

# --- selection state
if "selected_sa2" not in st.session_state:
    st.session_state.selected_sa2 = sa2_all[:3]
if "focus_sa2" not in st.session_state:
    st.session_state.focus_sa2 = st.session_state.selected_sa2[0]

selected_from_ui = st.sidebar.multiselect("Compare SA2 (up to 3)", options=sa2_all,
                                          default=st.session_state.selected_sa2, key="ms_sa2")
# keep up to 3
selected_from_ui = list(selected_from_ui)[:3]
if selected_from_ui != st.session_state.selected_sa2:
    st.session_state.selected_sa2 = selected_from_ui
if st.session_state.focus_sa2 not in st.session_state.selected_sa2:
    st.session_state.focus_sa2 = st.session_state.selected_sa2[0] if st.session_state.selected_sa2 else sa2_all[0]

st.sidebar.divider()
st.sidebar.markdown("**Buying — finances**")
income_user   = st.sidebar.number_input("Income /yr (A$)", value=95000, min_value=0, step=1000)
savings       = st.sidebar.number_input("Savings (A$)", value=40000, min_value=0, step=1000)
deposit_pct   = st.sidebar.slider("Deposit (%)", 5, 30, 20)
interest      = st.sidebar.slider("Mortgage rate (%/yr)", 2.0, 10.0, 6.0, step=0.1)
mortgage_years= st.sidebar.slider("Mortgage term (years)", 1, 30, 25)
max_monthly   = st.sidebar.number_input("Max monthly payment (A$)", value=2500, min_value=0, step=50)

# ---------- filtering ----------
end_idx = len(months)-1
start_idx = 0 if preset=="Max" else max(0, end_idx-{"5y":60,"3y":36,"1y":12}[preset])
month_set = set([d.strftime("%Y-%m") for d in months[start_idx:]])
dfp = df[df["date"].isin(month_set)].copy()

# ---------- latest snapshot & metrics ----------
brR = RENT_BEDROOM_COEFFS.get(bedrooms,1.0)
brP = PRICE_BEDROOM_COEFFS.get(bedrooms,1.0)

snap = (dfp[dfp["date"]==last_month]
        .assign(MedianRent_week_adj=lambda x: x.MedianRent_week*brR,
                MedianPrice_adj=lambda x: x.MedianPrice*brP,
                PTI=lambda x: x.MedianPrice_adj/x.MedianIncome_annual,
                RTI=lambda x: (x.MedianRent_week_adj*52)/x.MedianIncome_annual))

focus_sa2 = st.session_state.focus_sa2
focus_row = snap[snap.SA2_CODE==focus_sa2].iloc[0] if not snap[snap.SA2_CODE==focus_sa2].empty else snap.iloc[0]

price_adj = float(focus_row.MedianPrice_adj)
income = float(income_user)
deposit_target = deposit_pct/100 * price_adj
loan_principal = max(0.0, price_adj - deposit_target)
monthly_payment = annuity_monthly(loan_principal, interest/100.0, mortgage_years)
mti = (monthly_payment*12) / max(1e-9, income)

# Cap-gap baseline (fixed 25y)
LcapMap = principal_from_monthly(max_monthly, interest/100.0, 25)
cap_gap = (snap.assign(L_needed=lambda x: x.MedianPrice_adj*(1-deposit_pct/100.0))
                .assign(gap=lambda x: (x.L_needed - LcapMap)/x.MedianPrice_adj)
                [["SA2_CODE","gap"]])

def value_for_metric_row(row):
    if metric=="Median Rent":   return row.MedianRent_week_adj
    if metric=="Median Price":  return row.MedianPrice_adj
    if metric=="Median Income": return row.MedianIncome_annual
    if metric=="PTI":           return row.PTI
    if metric=="Payment Cap Gap":
        g = cap_gap.loc[cap_gap.SA2_CODE==row.SA2_CODE,"gap"]
        return float(g.iloc[0]) if not g.empty else np.nan
    return row.RTI

vals_all = snap.apply(value_for_metric_row, axis=1)
vmin, vmax = float(np.nanmin(vals_all)), float(np.nanmax(vals_all))
higher_is_bad = metric in ["Median Price","Median Rent","PTI","RTI","Payment Cap Gap"]

# ---------- header ----------
st.markdown("## 🏠 Housing affordability dashboard — Sydney (SA2, synthetic)")
st.caption(f"Metric: **{metric}**. Selected: {', '.join(st.session_state.selected_sa2)}")

# ---------- maps ----------
def map_grid_fig():
    dfm = snap.merge(grid, on="SA2_CODE")
    dfm["val"] = dfm.apply(value_for_metric_row, axis=1)
    W,H = 400, 300
    w, h = W/4.0, H/3.0
    fig = go.Figure()
    for _, r in dfm.iterrows():
        x0, y0 = r["col"]*w, r["row"]*h
        x1, y1 = x0+w, y0+h
        t = 0 if vmax==vmin else (r["val"]-vmin)/(vmax-vmin)
        c = px.colors.sample_colorscale(color_scale_gyr(not higher_is_bad), t)[0]
        fig.add_shape(type="rect", x0=x0+2, x1=x1-2, y0=y0+2, y1=y1-2,
                      line=dict(color="#111" if r["SA2_CODE"]==focus_sa2 else "white",
                                width=3 if r["SA2_CODE"]==focus_sa2 else 2),
                      fillcolor=c)
        fig.add_trace(go.Scatter(
            x=[(x0+x1)/2], y=[(y0+y1)/2], mode="text",
            text=[r["SA2_CODE"]], hovertext=f"{r['SA2_CODE']} — {metric}: {r['val']:.3g}",
            hoverinfo="text", name=r["SA2_CODE"]
        ))
    fig.update_xaxes(visible=False, range=[0,W])
    fig.update_yaxes(visible=False, range=[H,0])
    fig.update_layout(height=360, margin=dict(l=10,r=10,t=10,b=10),
                      plot_bgcolor="white", paper_bgcolor="white",
                      showlegend=False)
    return fig

def map_real_fig():
    gj, source = load_sa2_geojson(max_features=15)
    if not gj:
        return None, "no-geo"

    # Tie first N polygons to our SA2_01.. codes
    feats = gj["features"]
    n = min(12, len(feats))
    codes = [f"SA2_{i+1:02d}" for i in range(n)]
    for i, f in enumerate(feats[:n]):
        props = f.setdefault("properties", {})
        props["loc_code"] = codes[i]

    # metric values
    snap_map = snap.set_index("SA2_CODE")
    values = [value_for_metric_row(snap_map.loc[c]) if c in snap_map.index else np.nan for c in codes]
    df_map = pd.DataFrame({"SA2_CODE": codes, "val": values})

    fig = px.choropleth(
        df_map, geojson={"type":"FeatureCollection","features":feats[:n]},
        locations="SA2_CODE", color="val",
        featureidkey="properties.loc_code",
        color_continuous_scale=color_scale_gyr(not higher_is_bad),
        range_color=(vmin, vmax),
        projection="mercator"
    )
    fig.update_geos(fitbounds="geojson", visible=False)
    fig.update_layout(
        height=520, margin=dict(l=0,r=0,t=0,b=0),
        coloraxis_colorbar=dict(title=metric)
    )
    return fig, source

with st.container():
    c1, c2 = st.columns([1,2.2])
    with c1:
        st.subheader("Map: layer")
    with c2:
        if use_real_geo:
            fig_real, src = map_real_fig()
            if fig_real is None:
                st.warning("Failed to load real SA2 — showing compact grid.")
                fig = map_grid_fig()
                if HAVE_PLOTLY_EVENTS:
                    clicks = plotly_events(fig, click_event=True, hover_event=False, select_event=False, key="grid_click")
                    if clicks:
                        code = clicks[0].get("text") or clicks[0].get("name")
                        if isinstance(code, str):
                            sel = list(st.session_state.selected_sa2)
                            if code in sel: sel.remove(code)
                            elif len(sel) < 3: sel.append(code)
                            st.session_state.selected_sa2 = sel
                            st.session_state.focus_sa2 = code
                else:
                    st.plotly_chart(fig, use_container_width=True)
            else:
                if HAVE_PLOTLY_EVENTS:
                    clicks = plotly_events(fig_real, click_event=True, hover_event=False, select_event=False, key="real_click")
                    if clicks:
                        code_clicked = clicks[0].get("location")  # our loc_code = SA2_xx
                        if isinstance(code_clicked, str):
                            sel = list(st.session_state.selected_sa2)
                            if code_clicked in sel: sel.remove(code_clicked)
                            elif len(sel) < 3: sel.append(code_clicked)
                            st.session_state.selected_sa2 = sel
                            st.session_state.focus_sa2 = code_clicked
                else:
                    st.plotly_chart(fig_real, use_container_width=True)
                src_label = "ABS ArcGIS" if src=="abs" else ("GitHub" if src=="github" else "—")
                st.caption(f"Polygon source: {src_label}")
        else:
            fig = map_grid_fig()
            if HAVE_PLOTLY_EVENTS:
                clicks = plotly_events(fig, click_event=True, hover_event=False, select_event=False, key="grid_click2")
                if clicks:
                    code = clicks[0].get("text") or clicks[0].get("name")
                    if isinstance(code, str):
                        sel = list(st.session_state.selected_sa2)
                        if code in sel: sel.remove(code)
                        elif len(sel) < 3: sel.append(code)
                        st.session_state.selected_sa2 = sel
                        st.session_state.focus_sa2 = code
            else:
                st.plotly_chart(fig, use_container_width=True)

# ---------- comparison table ----------
st.subheader("📊 Selected SA2 comparison")
sel_now = st.session_state.selected_sa2
tbl = (snap[snap.SA2_CODE.isin(sel_now)]
       .merge(cap_gap, on="SA2_CODE", how="left")
       .loc[:, ["SA2_CODE","MedianPrice_adj","MedianRent_week_adj","MedianIncome_annual","PTI","RTI","gap"]]
       .rename(columns={
           "SA2_CODE":"SA2",
           "MedianPrice_adj":"Median Price",
           f"MedianRent_week_adj":f"Median Rent ({bedrooms}BR, /wk)",
           "MedianIncome_annual":"Income (/yr)",
           "gap":"Payment Cap Gap"
       }))
tbl_display = tbl.copy()
tbl_display["Median Price"] = tbl_display["Median Price"].map(money)
tbl_display[f"Median Rent ({bedrooms}BR, /wk)"] = tbl_display[f"Median Rent ({bedrooms}BR, /wk)"].map(money)
tbl_display["Income (/yr)"] = tbl_display["Income (/yr)"].map(money)
tbl_display["PTI"] = tbl_display["PTI"].map(lambda x: f"{x:.1f}")
tbl_display["RTI"] = tbl_display["RTI"].map(lambda x: f"{x*100:.1f}%")
tbl_display["Payment Cap Gap"] = tbl_display["Payment Cap Gap"].map(
    lambda g: ("✅ " if (isinstance(g,(int,float)) and g<=0) else "❌ ") + (f"{g*100:.1f}%" if pd.notna(g) else "—")
)
st.dataframe(tbl_display, use_container_width=True, hide_index=True)

# ---------- buyer / tenant panels ----------
st.subheader("🔧 Parameters & calculations")
if segment_key == "buyers":
    buyer_mode = st.radio("Buyer mode", ["Budget","25y → MTI","Term → income"], horizontal=True)
    monthly25 = annuity_monthly(loan_principal, interest/100.0, 25)
    mti25 = (monthly25*12)/max(1e-9,income)
    LcapUser = principal_from_monthly(max_monthly, interest/100.0, mortgage_years)
    P_affordable = LcapUser / max(1e-9, 1 - deposit_pct/100.0)
    income_required_fixedSR = (monthly_payment*12)/0.25

    cA, cB, cC = st.columns(3)
    cA.metric("Price (size-adjusted)", money(price_adj))
    cB.metric("Minimum deposit", money(deposit_target))
    cC.metric("Your income /yr", money(income))

    if buyer_mode == "Budget":
        c1, c2, c3 = st.columns(3)
        c1.metric("Affordable price", money(P_affordable), help="From your monthly limit and current rate/term")
        c2.metric("Payment (/mo)", money(monthly_payment))
        c3.metric("MTI (income share)", f"{mti*100:.1f}%")
    elif buyer_mode == "25y → MTI":
        c1, c2, c3 = st.columns(3)
        c1.metric("Payment at 25y", money(monthly25)+"/mo")
        c2.metric("MTI (25y)", f"{mti25*100:.1f}%")
        c3.metric("Price", money(price_adj))
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Income needed at MTI=25%", money(income_required_fixedSR))
        c2.metric("Payment (/mo)", money(monthly_payment))
        c3.metric("Price", money(price_adj))

    if mti >= 0.40:
        st.warning("MTI ≥ 40% — high mortgage burden.")
    elif mti >= 0.30:
        st.warning("MTI 30–40% — elevated burden.")
else:
    rent_week = float(focus_row.MedianRent_week*brR)
    rent_month = rent_week*52/12
    rti_user = (rent_week*52)/max(1e-9, income)
    cA, cB, cC = st.columns(3)
    cA.metric(f"Rent {bedrooms}BR (/wk)", money(rent_week))
    cB.metric("Rent (/mo)", money(rent_month))
    cC.metric("RTI", f"{rti_user*100:.1f}%")
    if rti_user >= 0.30:
        st.warning("RTI ≥ 30% — rental stress.")
    elif rti_user >= 0.25:
        st.info("RTI 25–30% — borderline burden.")

# ---------- time series ----------
def ts_with_median(series_key: str):
    RENT = RENT_BEDROOM_COEFFS.get(bedrooms,1.0)
    sub = df[df["date"].isin(month_set)].copy()
    sub["Rent"] = sub["MedianRent_week"]*RENT
    sub["RentMonthly"] = sub["Rent"]*52/12
    sub["Price"] = sub["MedianPrice"]
    sub["PTI"] = sub["MedianPrice"]/sub["MedianIncome_annual"]
    sub["RTI"] = (sub["Rent"]*52)/sub["MedianIncome_annual"]

    lines = []
    for code in (st.session_state.selected_sa2 if st.session_state.selected_sa2 else [sa2_all[0]]):
        d = sub[sub.SA2_CODE==code][["date",series_key]].sort_values("date")
        d = d.rename(columns={series_key: code})
        lines.append(d.set_index("date"))

    med = (sub.groupby("date")[series_key].median().rename("median")).to_frame()
    base = med.copy()
    for s in lines: base = base.join(s, how="left")
    base = base.reset_index().sort_values("date")
    return base

def ts_fig(title, key, thresholds=None):
    data = ts_with_median(key)
    fig = go.Figure()
    if thresholds:
        for (y1,y2,color) in thresholds:
            fig.add_shape(type="rect", xref="paper", x0=0, x1=1, y0=y1, y1=y2,
                          fillcolor=color, opacity=0.12, layer="below", line_width=0)
    for col in data.columns:
        if col in ("date","median"): continue
        fig.add_trace(go.Scatter(x=data["date"], y=data[col], name=col, mode="lines", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=data["date"], y=data["median"], name="Median (city)",
                             mode="lines", line=dict(color="black", width=3)))
    fig.update_layout(title=title, height=340, margin=dict(l=10,r=10,t=40,b=10))
    return fig

st.subheader("📈 Trends")
if segment_key == "tenants":
    c1, c2 = st.columns(2)
    c1.plotly_chart(ts_fig(f"Median Rent ({bedrooms}BR, month)", "RentMonthly"),
                    use_container_width=True)
    c2.plotly_chart(ts_fig("RTI", "RTI",
                           thresholds=[(0,0.25,"green"),(0.25,0.30,"gold"),(0.30,1.0,"crimson")]),
                    use_container_width=True)
else:
    c1, c2 = st.columns(2)
    c1.plotly_chart(ts_fig(f"Median Rent ({bedrooms}BR, week)", "Rent"),
                    use_container_width=True)
    c2.plotly_chart(ts_fig("Median Price", "Price"),
                    use_container_width=True)
    c3, c4 = st.columns(2)
    c3.plotly_chart(ts_fig("PTI", "PTI",
                           thresholds=[(0,8,"green"),(8,10,"gold"),(10,99,"crimson")]),
                    use_container_width=True)
    c4.plotly_chart(ts_fig("RTI", "RTI",
                           thresholds=[(0,0.25,"green"),(0.25,0.30,"gold"),(0.30,1.0,"crimson")]),
                    use_container_width=True)

st.caption("Synthetic data. Colors: green is better/cheaper, red is worse/more expensive. "
           "Polygon layer loads from ABS ArcGIS; when unavailable it falls back to a backup source or the grid.")

