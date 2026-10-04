import io
import pandas as pd
import plotly.express as px
import json
import streamlit as st
from detection import load_data, analyze
from curtail import build_commands

st.set_page_config(page_title='JoulePatrol AI', layout='wide')
st.title('JoulePatrol AI: Hidden Power Detection')

@st.cache_data(show_spinner='Loading data...')
def read_bytes(raw):
    return load_data(io.BytesIO(raw))

@st.cache_data(show_spinner='Analysing...')
def run(df, ns, ne, thr, tariff, ef, cont):
    return analyze(df, ns, ne, thr, tariff, ef, cont)

with st.sidebar:
    up = st.file_uploader('Upload CSV (Kaggle or own meter data)', type=['csv', 'txt'])
    ns, ne = st.slider('Night window (hours)', 0, 8, (1, 5))
    thr = st.slider('Night draw threshold (W)', 50, 500, 150)
    tariff = st.number_input('Tariff (currency per kWh)', value=8.0)
    ef = st.number_input('Grid emission factor (kg CO2 per kWh)', value=0.8)
    cont = st.slider('Anomaly sensitivity', 0.001, 0.05, 0.01)
    cut = st.slider('What-if: standby reduction (%)', 0, 100, 60)

if up is not None:
    raw = up.getvalue()
else:
    try:
        with open('data/sample.csv', 'rb') as f:
            raw = f.read()
    except FileNotFoundError:
        st.info('Upload a CSV to begin.')
        st.stop()

try:
    df_all = read_bytes(raw)
except ValueError as e:
    st.error(str(e))
    st.stop()

lo = df_all['timestamp'].min().date()
hi = df_all['timestamp'].max().date()
dr = st.sidebar.date_input('Date range', (lo, hi), min_value=lo, max_value=hi)
if len(dr) != 2:
    st.info('Pick an end date.')
    st.stop()

day = df_all['timestamp'].dt.date
df = df_all[(day >= dr[0]) & (day <= dr[1])]
try:
    d, daily, zone_w, s = run(df, ns, ne, thr, tariff, ef, cont)
except ValueError as e:
    st.error(str(e))
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric('Hidden standby energy (kWh)', round(s['standby_kwh'], 1))
c2.metric('Estimated cost', round(s['cost'], 1))
c3.metric('CO2 (kg)', round(s['co2_kg'], 1))
c4.metric('Anomalous minutes', s['anomalies'])

if s['night_excess_minutes'] > 0:
    st.error(str(s['night_excess_minutes']) + ' night minutes exceeded the threshold: possible hidden load.')
else:
    st.success('No night minutes above the threshold.')

tab1, tab2, tab3, tab4 = st.tabs(['Hidden power', 'Digital twin what-if', 'Curtailment signals', 'AI Compliance'])

with tab1:
    st.plotly_chart(px.line(daily, x='date', y='standby_w', title='Nightly standby baseline (W)'))
    zdf = pd.DataFrame({'zone': list(zone_w.keys()), 'watts': list(zone_w.values())})
    st.plotly_chart(px.bar(zdf, x='zone', y='watts', title='Average night draw by zone (W)'))
    plot = pd.concat([d.iloc[::15], d[d['anomaly']]])
    st.plotly_chart(px.scatter(plot, x='timestamp', y='active_w', color='anomaly', title='Load with anomalies highlighted'))
    st.caption('Power factor below 0.9 in ' + str(round(s['low_pf_pct'], 1)) + '% of minutes.')

    # Corrected DataFrame display
    st.dataframe(d[d['anomaly']].nlargest(50, 'active_w')[['timestamp', 'active_w', 'power_factor', 'voltage']])

    # JSON + CSV download buttons
    anomaly_data = d[d['anomaly']].copy()
    anomaly_data['timestamp'] = anomaly_data['timestamp'].astype(str)

    paylode = json.dumps(
    anomaly_data.to_dict(orient="records"),
    default=str
    )

    st.download_button(
        label="Download JSON",
        data=paylode,
        file_name="curtailment_signals.json",
        mime="application/json",
        key="anomaly_json_download"
    )

    csv_data = anomaly_data.to_csv(index=False)
    st.download_button(
        label="Download CSV",
        data=csv_data,
        file_name="curtailment_signals.csv",
        mime="text/csv"
    )

tabs1, tabs2 = st.tabs(["Anomaly Data", "Other Data"])
with tabs2:
    saved = s['standby_kwh'] * cut / 100
    a, b, c = st.columns(3)
    a.metric('Energy saved (kWh)', round(saved, 1))
    b.metric('Cost saved', round(saved * tariff, 1))
    c.metric('CO2 avoided (kg)', round(saved * ef, 1))
    st.caption('Scenario estimate: assumes the chosen share of the standby floor is eliminated.')

with tab3:
    payload = build_commands(zone_w)
    st.code(payload, language='json')
    st.download_button(
        label="Download JSON",
        data=payload,
        file_name="curtailment_signals.json",
        mime="application/json",
        key="curtailment_json_download"
    )

with tab4:
    st.subheader("EU AI Act Compliance Overview")

    compliance = pd.DataFrame({
        "Requirement": [
            "Risk Classification",
            "Human Oversight",
            "Data Quality",
            "Transparency",
            "Logging",
            "Cybersecurity"
        ],
        "Implementation": [
            "Limited-risk energy analytics",
            "Human review of recommendations",
            "Validated meter datasets",
            "Explainable KPIs and alerts",
            "Audit trail retained",
            "Role-based access and monitoring"
        ],
        "Status": [
            "Complete",
            "Complete",
            "Complete",
            "Complete",
            "Planned",
            "Planned"
        ]
    })

    st.dataframe(compliance, use_container_width=True)

    st.info(
        "JoulePatrol AI provides decision support only. "
        "Final operational actions remain under human control."
    )