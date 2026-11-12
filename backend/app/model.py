"""Modelo de cálculo de Reflex (port 1:1 de las funciones JS de la app).

Funciones puras: reciben un perfil (dict) y devuelven resultados. Sin I/O,
así se pueden testear y reutilizar desde la API o desde scripts.
"""
from __future__ import annotations
import math
from copy import deepcopy

DEFAULTS = dict(
    e1=1_050_000, e2=480_000, par=700_000, fam=420_000, sal=140_000, arr=560_000,
    ali=260_000, otr=110_000, del_=80_000, sus=40_000, com=90_000, pen=90_000,
    ah0=2_400_000, inv=1_000_000, q=None, ev={}, ap={}, de={}, evA={},
    tasa=4.0, rsv=50_000, rj=4.0, gc=1.6, uf=41_264, plazo=30,
    val=85_000_000, pie=10.0, adj=0,
)
# "del" es palabra reservada en Python: internamente se usa "del_", en JSON se expone "del".

REC = {"del_": 0.4, "sus": 0.5, "com": 0.3}  # fracción recortable por hábito
RK = ["del_", "sus", "com"]

EV = {
    "salud":    {"n": "Gasto de salud familiar",       "t": "once", "m": 4},
    "auto":     {"n": "Reparación del auto o la moto", "t": "once", "m": 8},
    "hijo":     {"n": "Arreglo urgente en la casa",    "t": "once", "m": 6},
    "hogar":    {"n": "Falla un electrodoméstico",     "t": "once", "m": 10},
    "arriendo": {"n": "Sube el arriendo",              "t": "rent", "m": 5},
    "ingreso":  {"n": "Baja tu segundo empleo",        "t": "job",  "m": 7},
}
EVK = list(EV)

CAMINOS = {  # [valor vivienda, % pie]
    "via_rapida":   {"nombre": "La vía rápida",       "val": 85_000_000, "pie": 10},
    "lento_seguro": {"nombre": "Lento pero seguro",   "val": 85_000_000, "pie": 20},
    "ajustar":      {"nombre": "Ajustar la vivienda", "val": 62_000_000, "pie": 15},
}


def perfil_base(**over) -> dict:
    p = deepcopy(DEFAULTS)
    p.update(over)
    return p


def gastos_totales(S):
    return S["fam"] + S["sal"] + S["arr"] + S["ali"] + S["otr"] + S["del_"] + S["sus"] + S["com"] + S["pen"]


def recorte(S, k):
    return round(S[k] * REC[k] / 1000) * 1000


def ahorro_habitos(S):
    return sum(recorte(S, k) for k in RK if S["ap"].get(k.rstrip("_")) or S["ap"].get(k))


def deudas_extra(S):
    return sum(x["a"] for lista in S["de"].values() for x in lista)


def meta(S, m):
    """Pie + gastos de compra, reajustado por alza de precios a m meses."""
    return S["val"] * (S["pie"] + S["gc"]) / 100 * (1 + S["rj"] / 100) ** (m / 12)


def tasa_efectiva(S):
    return S["tasa"] + (0.5 if S["pie"] < 20 else 0.2 if S["pie"] < 30 else 0)


def monto_sugerido(S, k):
    r = lambda x: round(x / 10_000) * 10_000
    if k == "salud":
        return max(150_000, r(4 * S["sal"]))
    if k == "auto":
        return max(150_000, r(4 * S["otr"]))
    if k == "hijo":
        return max(100_000, r(0.5 * S["arr"]))
    return max(100_000, r(1.15 * S["ali"]))


def monto_evento(S, k):
    v = S["evA"].get(k)
    return v if v is not None else monto_sugerido(S, k)


def simular(S, con_eventos=True, extra=None, ajuste=None):
    base = (S["e1"] + S["e2"] + S["par"] - gastos_totales(S) - S["rsv"]
            + (ahorro_habitos(S) if extra is None else extra)
            + (S["adj"] if ajuste is None else ajuste))
    goal = meta(S, 0)
    liq, inv = float(S["ah0"]), float(S["inv"])
    serie, minimo, m = [liq + inv], liq, 0
    if liq + inv >= goal:
        return {"meses": 0, "serie": serie, "minimo": minimo}
    while m < 120:
        m += 1
        inv *= 1 + 0.04 / 12
        f = base
        if con_eventos and m == 1:
            f -= deudas_extra(S)
        if con_eventos:
            for k in EVK:
                if not S["ev"].get(k):
                    continue
                e = EV[k]
                if e["t"] == "once" and m == e["m"]:
                    f -= monto_evento(S, k)
                if e["t"] == "rent" and m >= e["m"]:
                    f -= S["arr"] * 0.08
                if e["t"] == "job" and e["m"] <= m < e["m"] + 3:
                    f -= S["e2"] * 0.5
        liq += f
        minimo = min(minimo, liq)
        serie.append(liq + inv - (meta(S, m) - goal))
        if liq + inv >= meta(S, m):
            return {"meses": m, "serie": serie, "minimo": minimo}
    return {"meses": None, "serie": serie[:61], "minimo": minimo}


def cuota(S, P):
    r, n = tasa_efectiva(S) / 1200, S["plazo"] * 12
    return P * (r / (1 - (1 + r) ** -n) + 0.0004)  # +0,04% seguros


def calcular(S):
    ing = S["e1"] + S["e2"]
    ah = ing + S["par"] - gastos_totales(S) - S["rsv"] + ahorro_habitos(S) + S["adj"]
    pie_m = S["val"] * S["pie"] / 100
    R, R0 = simular(S, True), simular(S, False)
    c = cuota(S, S["val"] - pie_m)
    base = ing + S["par"] if S["q"] == "pareja" else ing
    pct = c / base * 100 if base > 0 else 0
    nivel = "holgado" if pct <= 25 else "justo" if pct <= 30 else "sobre_limite"
    return {
        "ahorro_mensual": round(ah), "meta_pie": round(meta(S, 0)), "pie": round(pie_m),
        "meses": R["meses"], "meses_sin_imprevistos": R0["meses"],
        "cuota": round(c), "carga_pct": round(pct, 1), "nivel": nivel,
        "tasa_efectiva": tasa_efectiva(S), "minimo_liquidez": round(R["minimo"]),
        "serie": [round(x) for x in R["serie"]],
    }


def ncdf(z):
    t = 1 / (1 + 0.2316419 * abs(z))
    d = 0.3989423 * math.exp(-z * z / 2)
    p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    return 1 - p if z > 0 else p


def prob_positivo(q, sd):
    return ncdf(q / sd) if sd > 0 else (1.0 if q >= 0 else 0.0)
