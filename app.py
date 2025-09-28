# app.py
import math
import json
import requests
import numpy as np
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import date
from streamlit_plotly_events import plotly_events  # <-- клики по Plotly

st.set_page_config(page_title="Housing Affordability — Sydney (Synthetic SA2)",
                   layout="wide")

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

def annuity_monthly(L, r_annual, years):
    L = max(0.0, float(L))
    m = float(r_annual)/12.0
    n = max(1, int(round(years*12)))
    if L == 0: return 0.0
    if m == 0: return L / n
    return (m*L) / (1 - (1+m)**(-n))

def principal_from_monthly(payment, r_annual, years):
    m = float(r_annual)/12.0
    n = max(1, int(round(years*12)))
    if m == 0: return float(payment)*n
    return float(payment) * (1 - (1+m)**(-n)) / m

RENT_BEDROOM_COEFFS = {1:1.00, 2:1.35, 3:1.75}
PRICE_BEDROOM_COEFFS = {1:0.85, 2:1.00, 3:1.25}

# ---------- synthetic data ----------
@st.cache_data
def load_synthetic():
    rng = mulberry32(20250926)
    sa2 = [f"SA2_{i:02d}" for i in range(1,13)]
    months = range_months(date(2015,1,1), date(2025,9,1))
    rows = []
    for i, code in enumerate(sa2):
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
    # grid layout indices for 3x4 map
    grid = pd.DataFrame({
        "SA2_CODE": sa2,
        "row": [0,0,0,0, 1,1,1,1, 2,2,2,2],
        "col": [0,1,2,3, 0,1,2,3, 0,1,2,3]
    })
    return df, grid, months

df, grid, months = load_synthetic()
last_month = months[-1].strftime("%Y-%m")

# ---------- real SA2 GeoJSON loader (mini subset) ----------
@st.cache_data(show_spinner=False)
def load_sa2_geojson_subset(n=12):
    """
    Пытаемся скачать сиднейский SA2-слой из публичных репозиториев,
    берём первые n полигонов и ПЕРЕИМЕНОВЫВАЕМ их коды в SA2_01..SA2_nn,
    чтобы они привязались к нашей синтетике.
    Если ничего не удалось — возвращаем None.
    """
    urls = [
        # Несколько вариантов, любой подойдёт
        "https://raw.githubusercontent.com/tonywr71/GeoJson-Data/master/australia/sa2/sydney_sa2.json",
        "https://raw.githubusercontent.com/centreborelli/geo-aus/master/ABS/2016/SA2/sa2_2016_sydney_simplified.geojson",
        "https://raw.githubusercontent.com/wcharczuk/geojson/master/australia/nsw/sydney_sa2.json",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=20)
            if r.ok:
                gj = r.json()
                feats = gj.get("features", [])
                if not feats:
                    continue
                feats = feats[:n]  # мини-подмножество
                # Переименуем коды в SA2_01.. чтобы склеилось с данными
                new_feats = []
                for i, f in enumerate(feats, start=1):
                    props = f.get("properties", {}) or {}
                    props["SA2_NAME"] = props.get("SA2_NAME21") or props.get("SA2_NAME16") or props.get("SA2_NAME") or f"SA2_{i:02d}"
                    props["SA2_CODE"] = f"SA2_{i:02d}"
                    new_feats.append({"type": "Feature", "properties": props, "geometry": f.get("geometry")})
                return {"type":"FeatureCollection","features":new_feats}
        except Exception:
            pass
    return None

GJ_SA2 = load_sa2_geojson_subset(n=12)
have_real_polygons = GJ_SA2 is not None

# ---------- sidebar ----------
st.sidebar.title("Настройки")
segment = st.sidebar.radio("Режим", ["Покупка (buyers)", "Аренда (tenants)"], index=0)
segment_key = "buyers" if segment.startswith("Покупка") else "tenants"

metric = st.sidebar.selectbox("Слой карты",
                              ["RTI","PTI","Median Rent","Median Price","Median Income","Payment Cap Gap"],
                              index=0)
bedrooms = st.sidebar.slider("Спален", 1, 3, 2)
preset = st.sidebar.selectbox("Период", ["5y","3y","1y","Max"], index=0)

use_real = st.sidebar.checkbox("Реальные SA2 полигоны", value=have_real_polygons)
st.sidebar.caption("Если отключить — будет компактная 3×4 сетка.")

sa2_all = grid["SA2_CODE"].tolist()
if "selected_sa2" not in st.session_state:
    st.session_state.selected_sa2 = sa2_all[:3]
selected = st.sidebar.multiselect("Сравнение районов (до 3)",
                                  sa2_all[:6], default=st.session_state.selected_sa2,
                                  max_selections=3)

st.sidebar.divider()
st.sidebar.markdown("**Покупка — финансы**")
income_user = st.sidebar.number_input("Доход /год (A$)", value=95000, min_value=0, step=1000)
savings = st.sidebar.number_input("Накопления (A$)", value=40000, min_value=0, step=1000)
deposit_pct = st.sidebar.slider("Deposit (%)", 5, 30, 20)
interest = st.sidebar.slider("Ставка ипотеки (% год.)", 2.0, 10.0, 6.0, step=0.1)
mortgage_years = st.sidebar.slider("Срок ипотеки (лет)", 1, 30, 25)
max_monthly = st.sidebar.number_input("Макс. платёж /мес (A$)", value=2500, min_value=0, step=50)

# ---------- filtering ----------
end_idx = len(months)-1
if preset == "Max": start_idx = 0
elif preset == "1y": start_idx = max(0, end_idx-12)
elif preset == "3y": start_idx = max(0, end_idx-36)
else: start_idx = max(0, end_idx-60)
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

# Cap-gap (базовый лимит на 25 лет)
LcapMap = principal_from_monthly(max_monthly, interest/100.0, 25)
cap_gap = (snap.assign(L_needed=lambda x: x.MedianPrice_adj*(1-deposit_pct/100.0))
                .assign(gap=lambda x: (x.L_needed - LcapMap)/x.MedianPrice_adj)
                [["SA2_CODE","gap"]])

def value_for_metric_row(row):
    if metric=="Median Rent": return row.MedianRent_week_adj
    if metric=="Median Price": return row.MedianPrice_adj
    if metric=="Median Income": return row.MedianIncome_annual
    if metric=="PTI": return row.PTI
    if metric=="Payment Cap Gap":
        g = cap_gap.loc[cap_gap.SA2_CODE==row.SA2_CODE,"gap"]
        return float(g.iloc[0]) if not g.empty else np.nan
    return row.RTI

vals = snap.apply(value_for_metric_row, axis=1)
vmin, vmax = float(np.nanmin(vals)), float(np.nanmax(vals))
higher_is_bad = metric in ["Median Price","Median Rent","PTI","RTI","Payment Cap Gap"]

# ---------- MAPS ----------
def render_grid_and_click():
    """Сетка 3×4 + клик по клеткам."""
    dfm = snap.merge(grid, on="SA2_CODE")
    dfm["val"] = dfm.apply(value_for_metric_row, axis=1)
    W,H = 400, 300
    w, h = W/4.0, H/3.0
    fig = go.Figure()

    # Раскрасим клеточки
    for _, r in dfm.iterrows():
        x0, y0 = r["col"]*w, r["row"]*h
        x1, y1 = x0+w, y0+h
        t = 0 if vmax==vmin else (r["val"]-vmin)/(vmax-vmin)
        # зелёный->красный (или наоборот)
        scale = px.colors.sequential.Viridis
        # возьмём свою мини-палитру зел->жёлт->красн
        def clr(t_):
            if t_ <= 0.5:
                # 0..0.5: зелёный -> жёлтый
                k = t_/0.5
                return f"rgb({int(0+255*k)},{int(128+87*k)},0)"
            else:
                # 0.5..1: жёлтый -> красный
                k = (t_-0.5)/0.5
                return f"rgb({int(255+(220-255)*k)},{int(215+(20-215)*k)},{int(0+(60-0)*k)})"
        c = clr(1-t) if higher_is_bad else clr(t)

        fig.add_shape(type="rect", x0=x0+2, x1=x1-2, y0=y0+2, y1=y1-2,
                      line=dict(color="#111" if r["SA2_CODE"] in st.session_state.selected_sa2 else "white",
                                width=3 if r["SA2_CODE"] in st.session_state.selected_sa2 else 2),
                      fillcolor=c)

        # "кликабельный" маркер по центру
        fig.add_trace(go.Scatter(
            x=[(x0+x1)/2], y=[(y0+y1)/2],
            mode="markers+text", text=[r["SA2_CODE"]],
            textposition="middle center",
            marker=dict(size=1, color="rgba(0,0,0,0)"),
            hovertext=f"{r['SA2_CODE']} — {metric}: {r['val']:.3g}",
            hoverinfo="text",
            customdata=[r["SA2_CODE"]],
            showlegend=False
        ))
    fig.update_xaxes(visible=False, range=[0,W])
    fig.update_yaxes(visible=False, range=[H,0])
    fig.update_layout(height=360, margin=dict(l=10,r=10,t=10,b=10),
                      plot_bgcolor="white", paper_bgcolor="white", showlegend=False)

    events = plotly_events(fig, click_event=True, hover_event=False,
                           override_height=360, key="grid_map")
    if events:
        code = (events[0].get("customdata")
                or events[0].get("text")
                or None)
        return code
    return None

def render_sa2_choropleth_and_click():
    """Choropleth по реальным SA2 (мини-набор) + клик."""
    if not GJ_SA2:
        return None

    names_by_code = {f["properties"]["SA2_CODE"]: f["properties"].get("SA2_NAME", f["properties"]["SA2_CODE"])
                     for f in GJ_SA2["features"]}

    dfm = snap.copy()
    dfm["val"] = dfm.apply(value_for_metric_row, axis=1)
    dfm["name"] = dfm["SA2_CODE"].map(names_by_code).fillna(dfm["SA2_CODE"])

    # цветовая шкала: зел->жёлт->красн, инвертируем если "выше = хуже"
    scale_gyr = [(0.0,"rgb(0,128,0)"),(0.5,"rgb(255,215,0)"),(1.0,"rgb(220,20,60)")]
    scale = list(reversed(scale_gyr)) if higher_is_bad else scale_gyr

    fig = px.choropleth(
        dfm, geojson=GJ_SA2, locations="SA2_CODE",
        featureidkey="properties.SA2_CODE",
        color="val", color_continuous_scale=scale,
        hover_data={"name":True,"val":":.3g","SA2_CODE":False},
        projection="mercator"
    )
    fig.update_traces(
        hovertemplate="<b>%{customdata[0]}</b><br>"+metric+": %{z:.3g}<extra></extra>",
        customdata=np.stack([dfm["name"]], axis=-1)
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(height=520, margin=dict(l=10,r=10,t=10,b=10),
                      coloraxis_showscale=False)

    events = plotly_events(fig, click_event=True, hover_event=False,
                           override_height=520, key="sa2_map")
    if events:
        code = events[0].get("location") or None
        return code
    return None

# ---------- layout ----------
st.markdown("## 🏠 Дэшборд доступности жилья — Sydney (SA2, synthetic)")

# ==== MAP + selection ====
c1, c2 = st.columns([1,2])
with c1:
    st.subheader("Карта: слой")
    st.caption(f"Метрика: **{metric}**. Выбрано: {', '.join(st.session_state.selected_sa2)}")
with c2:
    if use_real and GJ_SA2:
        clicked = render_sa2_choropleth_and_click()
    else:
        clicked = render_grid_and_click()

# реакция на клик: переключаем фокус/выбор
if clicked:
    focus_sa2 = clicked
    sel = st.session_state.selected_sa2.copy()
    if clicked in sel:
        sel = [x for x in sel if x != clicked]
    elif len(sel) < 3:
        sel = sel + [clicked]
    st.session_state.selected_sa2 = sel

# синхронизируем с сайдбаром
selected = st.session_state.selected_sa2.copy()
focus_sa2 = selected[0] if selected else grid["SA2_CODE"].iloc[0]

# ---------- расчёты для панелей ----------
focus_row = snap[snap.SA2_CODE==focus_sa2]
focus_row = focus_row.iloc[0] if not focus_row.empty else snap.iloc[0]

price_adj = float(focus_row.MedianPrice_adj)
income = float(income_user)
deposit_target = deposit_pct/100 * price_adj
loan_principal = max(0.0, price_adj - deposit_target)
monthly_payment = annuity_monthly(loan_principal, interest/100.0, mortgage_years)
mti = (monthly_payment*12) / max(1e-9, income)

# ---------- comparison table ----------
st.subheader("📊 Сравнение выбранных SA2")
tbl = (snap[snap.SA2_CODE.isin(selected)]
       .merge(cap_gap, on="SA2_CODE")
       .loc[:, ["SA2_CODE","MedianPrice_adj","MedianRent_week_adj","MedianIncome_annual","PTI","RTI","gap"]]
       .rename(columns={
           "SA2_CODE":"SA2",
           "MedianPrice_adj":"Median Price",
           "MedianRent_week_adj":f"Median Rent ({bedrooms}BR, /нед)",
           "MedianIncome_annual":"Income (/год)",
           "gap":"Payment Cap Gap"
       }))
tbl_display = tbl.copy()
tbl_display["Median Price"] = tbl_display["Median Price"].map(money)
tbl_display[f"Median Rent ({bedrooms}BR, /нед)"] = tbl_display[f"Median Rent ({bedrooms}BR, /нед)"].map(money)
tbl_display["Income (/год)"] = tbl_display["Income (/год)"].map(money)
tbl_display["PTI"] = tbl_display["PTI"].map(lambda x: f"{x:.1f}")
tbl_display["RTI"] = tbl_display["RTI"].map(lambda x: f"{x*100:.1f}%")
tbl_display["Payment Cap Gap"] = tbl_display["Payment Cap Gap"].map(lambda g: ("✅ " if g<=0 else "❌ ") + f"{g*100:.1f}%")
st.dataframe(tbl_display, use_container_width=True, hide_index=True)

# ---------- buyer/tenant panels ----------
st.subheader("🔧 Параметры и расчёты")
if segment_key == "buyers":
    # три режима для покупателей
    mode = st.radio("Режим покупателя",
                    ["По бюджету","25 лет → MTI","Срок → доход"],
                    horizontal=True)

    monthly25 = annuity_monthly(loan_principal, interest/100.0, 25)
    mti25 = (monthly25*12)/max(1e-9,income)
    LcapUser = principal_from_monthly(max_monthly, interest/100.0, mortgage_years)
    P_affordable = LcapUser / max(1e-9, 1 - deposit_pct/100.0)

    # базовые метрики
    cA, cB, cC = st.columns(3)
    cA.metric("Цена (учтён размер)", money(price_adj))
    cB.metric("Минимальный депозит", money(deposit_target))
    cC.metric("Ваш доход /год", money(income))

    if mode == "По бюджету":
        cA.metric(f"Платёж при {mortgage_years} лет", f"{money(monthly_payment)}/мес")
        cB.metric("MTI (доля дохода)", f"{mti*100:.1f}%")
        cC.metric("Доступная цена по лимиту", money(P_affordable))
    elif mode == "25 лет → MTI":
        cA.metric("Платёж (25 лет)", f"{money(monthly25)}/мес")
        cB.metric("MTI (25 лет)", f"{mti25*100:.1f}%")
        cC.metric("Цена (целевая)", money(price_adj))
    else:
        target_mti = st.slider("Целевой MTI (%)", 20, 35, 25, step=1)
        income_required = (monthly_payment*12) / max(1e-9, target_mti/100.0)
        cA.metric("Нужный доход", money(income_required))
        cB.metric("Платёж (/мес)", f"{money(monthly_payment)}/мес")
        cC.metric("Цена", money(price_adj))

    if mti >= 0.40:
        st.warning("MTI ≥ 40% — высокая ипотечная нагрузка.")
    elif mti >= 0.30:
        st.warning("MTI 30–40% — повышенная нагрузка.")
else:
    rent_week = float(focus_row.MedianRent_week*brR)
    rent_month = rent_week*52/12
    rti_user = (rent_week*52)/max(1e-9, income)
    cA, cB, cC = st.columns(3)
    cA.metric(f"Аренда {bedrooms}BR (нед.)", money(rent_week))
    cB.metric("Аренда (мес.)", money(rent_month))
    cC.metric("RTI", f"{rti_user*100:.1f}%")
    if rti_user >= 0.30:
        st.warning("RTI ≥ 30% — арендный стресс.")
    elif rti_user >= 0.25:
        st.info("RTI 25–30% — пограничная нагрузка.")

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
    for code in (selected if selected else [grid["SA2_CODE"].iloc[0]]):
        d = sub[sub.SA2_CODE==code][["date",series_key]].sort_values("date")
        d = d.rename(columns={series_key: code})
        lines.append(d.set_index("date"))

    med = (sub.groupby("date")[series_key]
             .median()
             .rename("median")).to_frame()

    base = med.copy()
    for s in lines:
        base = base.join(s, how="left")
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
        fig.add_trace(go.Scatter(x=data["date"], y=data[col], name=col,
                                 mode="lines", line=dict(width=1.5)))
    fig.add_trace(go.Scatter(x=data["date"], y=data["median"], name="Median (city)",
                             mode="lines", line=dict(color="black", width=3)))
    fig.update_layout(title=title, height=340, margin=dict(l=10,r=10,t=40,b=10))
    return fig

st.subheader("📈 Динамика")
if segment_key == "tenants":
    c1, c2 = st.columns(2)
    c1.plotly_chart(ts_fig(f"Median Rent ({bedrooms}BR, месяц)", "RentMonthly"), use_container_width=True)
    c2.plotly_chart(ts_fig("RTI", "RTI",
                           thresholds=[(0,0.25,"green"),(0.25,0.30,"gold"),(0.30,1.0,"crimson")]),
                    use_container_width=True)
else:
    c1, c2 = st.columns(2)
    c1.plotly_chart(ts_fig(f"Median Rent ({bedrooms}BR, неделя)", "Rent"), use_container_width=True)
    c2.plotly_chart(ts_fig("Median Price", "Price"), use_container_width=True)
    c3, c4 = st.columns(2)
    c3.plotly_chart(ts_fig("PTI", "PTI",
                           thresholds=[(0,8,"green"),(8,10,"gold"),(10,99,"crimson")]),
                    use_container_width=True)
    c4.plotly_chart(ts_fig("RTI", "RTI",
                           thresholds=[(0,0.25,"green"),(0.25,0.30,"gold"),(0.30,1.0,"crimson")]),
                    use_container_width=True)

st.caption("Данные синтетические. Полигональная карта подтянется автоматически при доступе к GeoJSON. Клик по карте добавляет/убирает SA2 в сравнение (до 3).")



