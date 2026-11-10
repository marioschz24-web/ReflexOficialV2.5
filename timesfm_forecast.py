"""
Pronóstico diario de gastos variables para el gemelo digital de Reflex.

Uso:
  python timesfm_forecast.py --statsforecast       # modelo estadístico (AutoETS), pip install statsforecast
  python timesfm_forecast.py --baseline            # modelo simple, sin dependencias pesadas
  python timesfm_forecast.py                        # TimesFM 3.0 (necesita torch + pesos de Hugging Face)
  python timesfm_forecast.py --today 2026-10-15 --out forecast.json

Entrada (opcional): gastos_diarios.csv con columnas  date,ali,del,otr,com  (pesos chilenos por día,
formato YYYY-MM-DD, desde 2026-10-01 hasta ayer). Si no existe, se usa una historia SINTÉTICA de ejemplo.

Salida: forecast.json -> en el prototipo, botón "Cargar pronóstico TimesFM (.json)".
"""
import argparse, csv, datetime as dt, json, os
import numpy as np

CATS = ["ali", "del", "otr", "com"]  # supermercado, delivery, transporte, compras
START, END = dt.date(2026, 10, 1), dt.date(2026, 12, 31)


def synthetic(end):
    """Historia de ejemplo (NO son datos reales de nadie)."""
    rng = np.random.default_rng(7)
    first = dt.date(2025, 10, 1)
    n = (end - first).days + 1
    days = [first + dt.timedelta(i) for i in range(n)]
    wd = np.array([d.weekday() for d in days])
    dom = np.array([d.day for d in days])
    prof = {"ali": [.5, .5, .6, .6, .9, 2.3, 1.6], "del": [.5, .6, .6, .8, 1.9, 1.8, 1.2],
            "otr": [1.3, 1.3, 1.3, 1.3, 1.3, .5, .3], "com": [.6, .6, .7, .8, 1.1, 1.8, 1.4]}
    month = {"ali": 260000, "del": 80000, "otr": 110000, "com": 90000}
    out = {}
    for k in CATS:
        p = np.array(prof[k])[wd]
        p = p / p.mean()
        bump = np.where(dom >= 28, 1.35, 1.0) if k == "com" else 1.0
        out[k] = (month[k] / 30.4 * p * bump * rng.lognormal(0, 0.45, n)).round(-2)
    return days, out


def load_history(today):
    end = today - dt.timedelta(days=1)
    if os.path.exists("gastos_diarios.csv"):
        rows = list(csv.DictReader(open("gastos_diarios.csv", encoding="utf-8")))
        days = [dt.date.fromisoformat(r["date"]) for r in rows]
        return days, {k: np.array([float(r[k]) for r in rows]) for k in CATS}
    return synthetic(end)


def baseline(s, wd_hist, wd_fut):
    """Nivel de las últimas 8 semanas x perfil por día de semana; bandas con la dispersión reciente."""
    s = np.asarray(s, float)
    lvl = s[-56:].mean()
    prof = np.array([s[-182:][wd_hist[-182:] == i].mean() for i in range(7)])
    prof = prof / prof.mean()
    ratio = s[-120:] / np.maximum(lvl * prof[wd_hist[-120:]], 1)
    q10, q50, q90 = np.quantile(ratio, [.1, .5, .9])
    f = lvl * prof[wd_fut]
    return f * q10, f * q50, f * q90


def statsforecast_forecast(days, series, horizon, today):
    """AutoETS (suavizamiento exponencial con estacionalidad semanal) + intervalo del 80% (p10 a p90)."""
    import pandas as pd
    from statsforecast import StatsForecast
    from statsforecast.models import AutoETS
    df = pd.concat([pd.DataFrame({"unique_id": k, "ds": pd.to_datetime(days), "y": np.asarray(series[k], float)})
                    for k in CATS])
    sf = StatsForecast(models=[AutoETS(season_length=7)], freq="D")
    out = sf.forecast(df=df, h=horizon, level=[80]).reset_index()
    res = {}
    for k in CATS:
        o = out[out["unique_id"] == k].sort_values("ds")
        res[k] = (np.maximum(o["AutoETS-lo-80"].to_numpy(), 0), np.maximum(o["AutoETS"].to_numpy(), 0),
                  np.maximum(o["AutoETS-hi-80"].to_numpy(), 0))
    return res


def timesfm_forecast(series, horizon):
    from timesfm3 import TimesFM3Evaluator, ModelConfig  # viene del repo google-research/timesfm
    cfg = ModelConfig(checkpoint_path="google/timesfm-3.0-pytorch", per_core_batch_size=8, device="cpu")
    model = TimesFM3Evaluator(cfg)
    ctx = [np.asarray(series[k][-512:], dtype=np.float32) for k in CATS]
    outs = list(model.predict_batch(ctx, horizon=horizon, return_quantiles=True, use_symmetric_averaging=False))
    # quantiles: (horizon, 9) -> deciles 0.1 ... 0.9
    return {k: (np.maximum(o.quantiles[:, 0], 0), np.maximum(o.quantiles[:, 4], 0), np.maximum(o.quantiles[:, 8], 0))
            for k, o in zip(CATS, outs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true")
    ap.add_argument("--statsforecast", action="store_true")
    ap.add_argument("--today", default=dt.date.today().isoformat())
    ap.add_argument("--out", default="forecast.json")
    a = ap.parse_args()
    today = dt.date.fromisoformat(a.today)
    days, hist = load_history(today)
    by_date = {d: i for i, d in enumerate(days)}
    horizon = (END - today).days + 1
    fut = [today + dt.timedelta(i) for i in range(horizon)]
    wd_h = np.array([d.weekday() for d in days])
    wd_f = np.array([d.weekday() for d in fut])
    if a.statsforecast:
        fc = statsforecast_forecast(days, hist, horizon, today)
    elif a.baseline:
        fc = {k: baseline(hist[k], wd_h, wd_f) for k in CATS}
    else:
        fc = timesfm_forecast(hist, horizon)
    res = {"src": "statsforecast" if a.statsforecast else "baseline" if a.baseline else "timesfm", "start": START.isoformat(), "generated": today.isoformat(), "cats": {}}
    for k in CATS:
        c = {"p10": [], "p50": [], "p90": []}
        d = START
        while d <= END:
            if d < today:  # pasado: dato real (sin incertidumbre)
                v = float(hist[k][by_date[d]]) if d in by_date else 0.0
                lo = mid = hi = v
            else:
                i = (d - today).days
                lo, mid, hi = (float(x[i]) for x in fc[k])
            c["p10"].append(int(round(lo, -2)))
            c["p50"].append(int(round(mid, -2)))
            c["p90"].append(int(round(hi, -2)))
            d += dt.timedelta(1)
        res["cats"][k] = c
    json.dump(res, open(a.out, "w"), separators=(",", ":"))
    print("Listo:", a.out, "| fuente:", res["src"], "| dias:", (END - START).days + 1)


if __name__ == "__main__":
    main()
