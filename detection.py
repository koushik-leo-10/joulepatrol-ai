import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

CANON = {
'global_active_power': 'active_kw',
'global_reactive_power': 'reactive_kw',
'voltage': 'voltage',
'sub_metering_1': 'sub1',
'sub_metering_2': 'sub2',
'sub_metering_3': 'sub3',
}
NEEDED = list(CANON.values())

def load_data(src):
    try:
        df = pd.read_csv(
        src,
        sep=None,
        engine="python",
        na_values=['?', '']
        )
    except Exception as e:
        raise ValueError(f"Unable to read CSV: {e}")
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
    df = df.rename(columns=CANON)
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    elif 'date' in df.columns and 'time' in df.columns:
        df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'], dayfirst=True, errors='coerce')
    else:
        raise ValueError('Need a Timestamp column, or Date and Time columns')
    missing = [c for c in NEEDED if c not in df.columns]
    if missing:
        raise ValueError('Missing columns: ' + ', '.join(missing))
    for c in NEEDED:
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['timestamp'] + NEEDED)
    return df[['timestamp'] + NEEDED].sort_values('timestamp').reset_index(drop=True)

def analyze(df, night_start=1, night_end=5, threshold_w=150, tariff=8.0, co2_kg_per_kwh=0.8, contamination=0.01):
    d = df.copy()
    d['active_w'] = d['active_kw'] * 1000
    metered = d[['sub1', 'sub2', 'sub3']].sum(axis=1)
    d['unmetered_wh'] = (d['active_w'] / 60 - metered).clip(lower=0)
    apparent = np.sqrt(d['active_kw'] ** 2 + d['reactive_kw'] ** 2)
    d['power_factor'] = np.where(apparent > 0, d['active_kw'] / apparent, 1.0)
    d['hour'] = d['timestamp'].dt.hour
    d['date'] = d['timestamp'].dt.date
    d['is_night'] = (d['hour'] >= night_start) & (d['hour'] < night_end)
    d['night_excess'] = d['is_night'] & (d['active_w'] > threshold_w)
    if not d['is_night'].any():
        raise ValueError('No readings inside the night window')
    
    daily = (d[d['is_night']].groupby('date')['active_w'].quantile(0.10).rename('standby_w').reset_index())
    daily['standby_kwh'] = daily['standby_w'] * 24 / 1000
    feats = ['active_kw', 'reactive_kw', 'voltage', 'sub1', 'sub2', 'sub3', 'hour']
    model = IsolationForest(n_estimators=100, contamination=contamination, random_state=42, n_jobs=-1)
    d['anomaly'] = model.fit_predict(d[feats]) == -1

    night = d[d['is_night']]
    zone_w = {z: float(night[z].mean() * 60) for z in ['sub1', 'sub2', 'sub3']}
    zone_w['unmetered'] = float(night['unmetered_wh'].mean() * 60)

    standby_kwh = float(daily['standby_kwh'].sum())
    summary = {
        'standby_kwh': standby_kwh,
        'cost': standby_kwh * tariff,
        'co2_kg': standby_kwh * co2_kg_per_kwh,
        'night_excess_minutes': int(d['night_excess'].sum()),
        'anomalies': int(d['anomaly'].sum()),
        'low_pf_pct': float((d['power_factor'] < 0.9).mean() * 100),
    }
    return d, daily, zone_w, summary