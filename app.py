
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="Дэшборд доступности жилья — Sydney (SA2)",
    layout="wide",
)

st.title("🏠 Дэшборд доступности жилья — Sydney (SA2, синтетические данные)")
st.caption(
    "Сборка в рамках **Dashboard proposal design**. Метрики: Median Rent, Median House Price, "
    "Median Household Income, PTI (Price-to-Income), RTI (Rent-to-Income), покупательские расчёты (Years_to_Deposit, MTI). "
    "Все данные синтетические, геометрия SA2 — упрощённая сетка вокруг Сиднея."
)

# -------------------- SYNTHETIC GEOJSON (12 SA2-like cells) --------------------
def build_geojson_grid(n_rows=3, n_cols=4, lat0=-33.98, lon0=151.00, dlat=0.055, dlon=0.065):
    """
    Build a simple rectangular grid as a placeholder for SA2 polygons around Sydney.
    Returns (geojson, centers_df).
    """
    features = []
    centers = []
    idx = 1
    for r in range(n_rows):
        for c in range(n_cols):
            lat_min = lat0 + r * dlat
            lat_max = lat0 + (r + 1) * dlat
            lon_min = lon0 + c * dlon
            lon_max = lon0 + (c + 1) * dlon
            sa2_code = f"SA2_{idx:02d}"
            polygon = [
                [
                    [lon_min, lat_min],
                    [lon_max, lat_min],
                    [lon_max, lat_max],
                    [lon_min, lat_max],
                    [lon_min, lat_min],
                ]
            ]
            features.append({
                "type": "Feature",
                "id": sa2_code,
                "properties": {"SA2_CODE": sa2_code, "SA2_NAME": sa2_code},
                "geometry": {"type": "Polygon", "coordinates": polygon}
            })
            centers.append({"SA2_CODE": sa2_code, "lat": (lat_min+lat_max)/2, "lon": (lon_min+lon_max)/2})
            idx += 1

    fc = {"type": "FeatureCollection", "features": features}
    centers_df = pd.DataFrame(centers)
    return fc, centers_df

GEOJSON, SA2_CENTERS = build_geojson_grid()

# -------------------- SYNTHETIC TIMESERIES --------------------
def synthetic_series(seed=42):
    rng = np.random.default_rng(seed)
    months = pd.date_range("2015-01-01", "2025-09-01", freq="MS")

    rows = []
    for i, sa2 in enumerate(SA2_CENTERS["SA2_CODE"]):
        # Base levels (per area)
        price_base = rng.uniform(650_000, 1_600_000)  # median purchase price
        rent_base = rng.uniform(420, 900)             # weekly rent
        income_base = rng.uniform(70_000, 125_000)    # household income (annual)

        # Monthly growth rates with small random walk
        g_price = 0.0018 + rng.normal(0, 0.0004)     # ~2.1%/yr avg
        g_rent = 0.0012 + rng.normal(0, 0.0003)      # ~1.4%/yr avg
        g_income = 0.0009 + rng.normal(0, 0.00025)   # ~1.1%/yr avg

        price = price_base
        rent = rent_base
        income = income_base

        for t, dt in enumerate(months):
            # Add gentle seasonality and noise
            seas = 1.0 + 0.02 * math.sin(2 * math.pi * (t % 12) / 12.0)
            price *= (1 + g_price + np.clip(rng.normal(0, 0.001), -0.003, 0.003))
            rent *= (1 + g_rent + np.clip(rng.normal(0, 0.0008), -0.002, 0.002))
            income *= (1 + g_income + np.clip(rng.normal(0, 0.0006), -0.0015, 0.0015))

            price_t = max(250_000, price * seas + rng.normal(0, 12_000))
            rent_t = max(250, rent * seas + rng.normal(0, 8))
            income_t = max(40_000, income * (0.995 + rng.normal(0, 0.002)))

            rows.append({
                "date": dt,
                "SA2_CODE": sa2,
                "MedianPrice": price_t,
                "MedianRent_week": rent_t,
                "MedianIncome_annual": income_t,
            })

    df = pd.DataFrame(rows)
    # Derived metrics
    df["PTI"] = df["MedianPrice"] / df["MedianIncome_annual"]
    df["RTI"] = (df["MedianRent_week"] * 52) / df["MedianIncome_annual"]
    return df

@st.cache_data(show_spinner=False)
def load_data():
    df = synthetic_series(seed=20250926)
    return df

DATA = load_data()

# Bedroom coefficients (experimental but transparent)
BEDROOM_COEFFS = {1: 1.00, 2: 1.35, 3: 1.75}

# -------------------- SIDEBAR CONTROLS --------------------
with st.sidebar:
    st.header("⚙️ Настройки")
    st.subheader("Временной горизонт")
    preset = st.selectbox("Период", ["Max", "5 лет", "3 года", "1 год"], index=1)
    if preset == "Max":
        start_date = DATA["date"].min().date()
    elif preset == "5 лет":
        start_date = (DATA["date"].max() - pd.DateOffset(years=5)).date()
    elif preset == "3 года":
        start_date = (DATA["date"].max() - pd.DateOffset(years=3)).date()
    else:
        start_date = (DATA["date"].max() - pd.DateOffset(years=1)).date()

    # Optional custom override
    start_date = st.date_input("Начало периода (YYYY-MM-DD)", value=start_date)
    end_date = st.date_input("Конец периода (YYYY-MM-DD)", value=DATA["date"].max().date())

    st.markdown("---")
    st.subheader("Карта: слой")
    layer = st.selectbox(
        "Метрика для заливки карты",
        [
            "Median Rent (week)",
            "Median Price",
            "Median Income (annual)",
            "PTI (Price-to-Income)",
            "RTI (Rent-to-Income)",
        ],
        help="Выбери, чем окрасить полигоны SA2 на карте"
    )

    st.markdown("---")
    st.subheader("Аренда")
    bedrooms = st.slider(
        "Число спален (оценочно)", 1, 3, 2,
        help="Экспериментально: корректируем медианную аренду с учётом 1/2/3 спален по коэффициентам."
    )

    st.markdown("---")
    st.subheader("Покупка (ваши параметры)")
    savings = st.number_input("Ваши накопления (A$)", min_value=0, value=40_000, step=5_000)
    income_user = st.number_input("Ваш годовой доход (A$)", min_value=10_000, value=95_000, step=5_000)

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        saving_rate = st.slider("Доля дохода на накопления (Saving Rate, %)", 5, 40, 20, step=1) / 100.0
        deposit_pct = st.slider("Первоначальный взнос (Deposit, %)", 5, 30, 20, step=1) / 100.0
    with col_s2:
        interest = st.slider("Ставка по ипотеке (годовых, %)", 2.0, 10.0, 6.0, step=0.1) / 100.0
        years = st.selectbox("Срок ипотеки (лет)", [25, 30], index=0)

    st.markdown("---")
    st.subheader("Сравнение районов")
    all_sa2 = sorted(DATA["SA2_CODE"].unique())
    default_sel = all_sa2[:3]
    selected_sa2 = st.multiselect("Выбери до 3 районов для сравнения", options=all_sa2, default=default_sel, max_selections=3)

# -------------------- FILTER BY DATE --------------------
mask = (DATA["date"].dt.date >= start_date) & (DATA["date"].dt.date <= end_date)
DF = DATA.loc[mask].copy()
if DF.empty:
    st.error("За выбранный период данных нет (синтетика). Измени диапазон дат.")
    st.stop()

latest_date = DF["date"].max()

# -------------------- AGGREGATE FOR MAP (LATEST MONTH) --------------------
latest = DF.loc[DF["date"] == latest_date].copy()
latest["MedianRent_week_adj"] = latest["MedianRent_week"] * BEDROOM_COEFFS.get(bedrooms, 1.0)
latest["PTI"] = latest["MedianPrice"] / latest["MedianIncome_annual"]
latest["RTI"] = (latest["MedianRent_week_adj"] * 52) / latest["MedianIncome_annual"]

if layer == "Median Rent (week)":
    color_col = "MedianRent_week_adj"
    color_title = f"Median Rent (за неделю), {bedrooms}BR (A$)"
elif layer == "Median Price":
    color_col = "MedianPrice"
    color_title = "Median House Price (A$)"
elif layer == "Median Income (annual)":
    color_col = "MedianIncome_annual"
    color_title = "Median Household Income (A$/год)"
elif layer == "PTI (Price-to-Income)":
    color_col = "PTI"
    color_title = "PTI (цена/доход)"
else:
    color_col = "RTI"
    color_title = f"RTI (аренда/доход), {bedrooms}BR"

# -------------------- MAP --------------------
st.subheader("🗺️ Карта Сиднея (SA2 — упрощённые полигоны)")
map_fig = px.choropleth_mapbox(
    latest,
    geojson={"type": "FeatureCollection", "features": [f for f in GEOJSON["features"]]},
    featureidkey="id",
    locations="SA2_CODE",
    color=color_col,
    color_continuous_scale="Viridis",
    range_color=None,
    mapbox_style="carto-positron",
    zoom=9,
    center={"lat": SA2_CENTERS["lat"].mean(), "lon": SA2_CENTERS["lon"].mean()},
    opacity=0.65,
    hover_data={
        "SA2_CODE": True,
        "MedianPrice": ":,.0f",
        "MedianRent_week_adj": ":,.0f",
        "MedianIncome_annual": ":,.0f",
        "PTI": ":.1f",
        "RTI": ":.2f",
    },
)
map_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), coloraxis_colorbar_title=color_title)
st.plotly_chart(map_fig, use_container_width=True)

# -------------------- COMPARISON TABLE --------------------
st.subheader("📊 Сравнение выбранных районов")
if not selected_sa2:
    selected_sa2 = default_sel

cmp = latest.loc[latest["SA2_CODE"].isin(selected_sa2), [
    "SA2_CODE", "MedianPrice", "MedianRent_week_adj", "MedianIncome_annual", "PTI", "RTI"
]].copy()
cmp.rename(columns={
    "SA2_CODE": "Район (SA2)",
    "MedianPrice": "Median Price (A$)",
    "MedianRent_week_adj": f"Median Rent ({bedrooms}BR, A$/нед)",
    "MedianIncome_annual": "Median Income (A$/год)",
    "PTI": "PTI",
    "RTI": "RTI",
}, inplace=True)
st.dataframe(cmp.style.format({
    "Median Price (A$)": "{:,.0f}",
    f"Median Rent ({bedrooms}BR, A$/нед)": "{:,.0f}",
    "Median Income (A$/год)": "{:,.0f}",
    "PTI": "{:.1f}",
    "RTI": "{:.2f}",
}), use_container_width=True)

# -------------------- BUYER CALCULATOR --------------------
st.subheader("🏡 Покупка: персональные расчёты")

def annuity_payment_monthly(L, r_annual, years):
    if L <= 0:
        return 0.0
    m = r_annual / 12.0
    n = years * 12
    if m == 0:
        return L / n
    return (m * L) / (1 - (1 + m) ** (-n))

# Use the first selected SA2 for buyer calc context
sa2_ref = selected_sa2[0]
row_ref = latest.loc[latest["SA2_CODE"] == sa2_ref].iloc[0]
median_price_ref = float(row_ref["MedianPrice"])
median_income_ref = float(row_ref["MedianIncome_annual"])

deposit_target = deposit_pct * median_price_ref
years_to_deposit = max(0.0, (deposit_target - float(savings))) / max(1e-9, (saving_rate * float(income_user)))

loan_principal = max(0.0, median_price_ref - deposit_target)
pay_monthly = annuity_payment_monthly(loan_principal, float(interest), int(years))
mti = (pay_monthly * 12.0) / max(1e-9, float(income_user))

cc1, cc2, cc3, cc4 = st.columns(4)
cc1.metric("Оценочная цена (Median Price)", f"A$ {median_price_ref:,.0f}")
cc2.metric("Требуемый депозит", f"A$ {deposit_target:,.0f}")
cc3.metric("Лет до депозита", f"{years_to_deposit:.1f} yrs")
cc4.metric("MTI (платёж/доход)", f"{mti*100:.1f}%")

# Insights / warnings
if years_to_deposit > 25:
    st.error("⚠️ При текущих параметрах депозит будет копиться более 25 лет — покупка жилья в этом районе малореалистична.")
elif years_to_deposit > 15:
    st.warning("⚠️ На накопление депозита потребуется более 15 лет. Рассмотрите увеличение Saving Rate, другой район или меньший Deposit%.")

if mti >= 0.40:
    st.error("⚠️ MTI ≥ 40% — высокая долговая нагрузка по ипотеке относительно вашего дохода.")
elif mti >= 0.30:
    st.warning("⚠️ MTI 30–40% — повышенная нагрузка по ипотеке.")

st.caption("Формулы: Years_to_Deposit = max(0, Deposit − Savings) / (SavingRate × Income); "
           "MTI = (MonthlyPayment × 12) / Income. MonthlyPayment — аннуитет при выбранной ставке и сроке.")

# -------------------- RENTER VIEW (RTI for user income) --------------------
st.subheader("🏘️ Аренда: нагрузка RTI с учётом комнатности")

rti_user = (row_ref["MedianRent_week_adj"] * 52.0) / max(1e-9, float(income_user))
c1, c2 = st.columns(2)
c1.metric(f"Оценочная аренда ({bedrooms}BR, неделя)", f"A$ {row_ref['MedianRent_week_adj']:,.0f}")
c2.metric("RTI (аренда/ваш доход)", f"{rti_user*100:.1f}%")

if rti_user >= 0.30:
    st.error("⚠️ RTI ≥ 30% — высокий арендный стресс.")
elif rti_user >= 0.25:
    st.warning("⚠️ RTI 25–30% — пограничная нагрузка.")

st.caption("RTI = (MedianRent_week_adjusted × 52) / Income. Коэффициенты комнатности: 1BR=1.00, 2BR=1.35, 3BR=1.75 (оценочно).")

# -------------------- TIME SERIES --------------------
st.subheader("📈 Динамика во времени")
tabs = st.tabs(["Median Rent", "Median Price", "PTI", "RTI"])

def plot_metric(metric_col, title, yfmt=None):
    dsel = DF.loc[DF["SA2_CODE"].isin(selected_sa2), ["date", "SA2_CODE", metric_col]].copy()
    if metric_col == "MedianRent_week":
        # apply bedroom coeffs for timeseries too
        dsel[metric_col] = dsel[metric_col] * BEDROOM_COEFFS.get(bedrooms, 1.0)

    fig = px.line(
        dsel,
        x="date", y=metric_col,
        color="SA2_CODE",
        labels={"date": "Дата", metric_col: title, "SA2_CODE": "SA2"},
    )
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    if yfmt == "money":
        fig.update_yaxes(tickprefix="A$ ")
    st.plotly_chart(fig, use_container_width=True)

with tabs[0]:
    plot_metric("MedianRent_week", f"Median Rent ({bedrooms}BR, неделя)", yfmt="money")
with tabs[1]:
    plot_metric("MedianPrice", "Median House Price", yfmt="money")
with tabs[2]:
    plot_metric("PTI", "PTI (цена/доход)")
with tabs[3]:
    # Need RTI with bedroom adj => recompute on-the-fly from DF
    temp = DF.loc[DF["SA2_CODE"].isin(selected_sa2), ["date", "SA2_CODE", "MedianRent_week", "MedianIncome_annual"]].copy()
    temp["MedianRent_week_adj"] = temp["MedianRent_week"] * BEDROOM_COEFFS.get(bedrooms, 1.0)
    temp["RTI_adj"] = (temp["MedianRent_week_adj"] * 52) / temp["MedianIncome_annual"]
    fig_rti = px.line(temp, x="date", y="RTI_adj", color="SA2_CODE",
                      labels={"date": "Дата", "RTI_adj": "RTI (аренда/доход)", "SA2_CODE": "SA2"})
    fig_rti.update_layout(margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig_rti, use_container_width=True)

# -------------------- EXPLANATIONS --------------------
with st.expander("ℹ️ Пояснения метрик и порогов"):
    st.markdown("""
**PTI (Price-to-Income)** — отношение медианной цены жилья к годовому доходу домаохозяйства. Значения > 8–10 указывают на низкую доступность.
                
**RTI (Rent-to-Income)** — доля дохода, уходящая на аренду: (Median Rent × 52) / Income. Порог арендного стресса — **30%**.
                
**MTI (Mortgage-to-Income)** — доля дохода, уходящая на ипотечный платеж: (Monthly Payment × 12) / Income.
                
**Years_to_Deposit** — лет до накопления депозита: max(0, Deposit − Savings) / (SavingRate × Income).
                
Комнатность (1/2/3 спальни) учитывается коэффициентами **1.00 / 1.35 / 1.75** (оценочно, режим «Бета»).
    """)

st.caption("⚠️ Данные синтетические. Геометрия SA2 упрощена. При подключении реальных источников на уровне SA2 логика дэшборда сохраняется без изменений.")
