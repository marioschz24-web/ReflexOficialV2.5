"""API de Reflex — gemelo financiero para juntar el pie.

Arranque:  uvicorn app.main:app --reload   ·   Docs: http://localhost:8000/docs
Errores en formato RFC 7807 (application/problem+json).
"""
import json, os, time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import db, model
from .schemas import EventoEntrada, ImprevistoEntrada, LeccionEntrada, PerfilEntrada, Proyeccion

@asynccontextmanager
async def lifespan(_app):
    db.init()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Reflex API",
    version="1.0.0",
    description="Servicios del prototipo Reflex (Desafío Bci Labs). No es una oferta de Bci.",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

FORECAST = json.load(open(os.path.join(os.path.dirname(__file__), "..", "data", "forecast_statsforecast.json")))
CATEGORIAS = {"ali": "Supermercado", "del": "Delivery", "otr": "Transporte", "com": "Compras"}


# ---------- Errores RFC 7807 ----------
def problema(status, titulo, detalle, request: Request, **extra):
    body = {"type": f"https://reflex.app/errores/{status}", "title": titulo, "status": status,
            "detail": detalle, "instance": str(request.url.path), **extra}
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


class NoEncontrado(Exception):
    def __init__(self, que):
        self.que = que


@app.exception_handler(NoEncontrado)
async def _404(request, exc):
    return problema(404, "No encontrado", f"No existe {exc.que}.", request)


@app.exception_handler(RequestValidationError)
async def _422(request, exc):
    errores = [{"campo": ".".join(str(x) for x in e["loc"][1:]), "mensaje": e["msg"]} for e in exc.errors()]
    return problema(422, "Datos no válidos", "Revisa los campos marcados.", request, errores=errores)


@app.exception_handler(StarletteHTTPException)
async def _http(request, exc):
    return problema(exc.status_code, "Error", str(exc.detail), request)


# ---------- Latencia (cabecera Server-Timing) ----------
@app.middleware("http")
async def tiempo(request: Request, call_next):
    t0 = time.perf_counter()
    resp = await call_next(request)
    resp.headers["Server-Timing"] = f"app;dur={(time.perf_counter() - t0) * 1000:.1f}"
    return resp


# ---------- Helpers ----------
def a_modelo(entrada: dict) -> dict:
    d = {k: v for k, v in entrada.items() if v is not None}
    if "delivery" in d:
        d["del_"] = d.pop("delivery")
    return d


def perfil_o_404(pid):
    datos = db.leer_perfil(pid)
    if datos is None:
        raise NoEncontrado(f"el perfil {pid}")
    return model.perfil_base(**datos)


# ---------- Endpoints ----------
@app.get("/api/salud", tags=["sistema"])
def salud():
    return {"estado": "ok", "version": app.version}


@app.post("/api/perfiles", status_code=201, tags=["perfiles"])
def crear_perfil(p: PerfilEntrada):
    datos = a_modelo(p.model_dump())
    pid = db.crear_perfil(datos)
    return {"id": pid, "proyeccion": model.calcular(model.perfil_base(**datos))}


@app.get("/api/perfiles/{pid}", tags=["perfiles"])
def ver_perfil(pid: str):
    S = perfil_o_404(pid)
    S["del"] = S.pop("del_")
    return S


@app.patch("/api/perfiles/{pid}", tags=["perfiles"])
def editar_perfil(pid: str, p: PerfilEntrada):
    perfil_o_404(pid)
    datos = {**db.leer_perfil(pid), **a_modelo(p.model_dump())}
    db.guardar_perfil(pid, datos)
    return {"id": pid, "proyeccion": model.calcular(model.perfil_base(**datos))}


@app.get("/api/perfiles/{pid}/proyeccion", response_model=Proyeccion, tags=["plan"])
def proyeccion(pid: str):
    return model.calcular(perfil_o_404(pid))


@app.get("/api/perfiles/{pid}/caminos", tags=["plan"])
def caminos(pid: str):
    S = perfil_o_404(pid)
    out = []
    for k, c in model.CAMINOS.items():
        r = model.calcular({**S, "val": c["val"], "pie": c["pie"]})
        out.append({"id": k, "nombre": c["nombre"], "valor_vivienda": c["val"], "pie_pct": c["pie"],
                    "meses": r["meses"], "cuota": r["cuota"], "carga_pct": r["carga_pct"], "nivel": r["nivel"]})
    return out


@app.post("/api/perfiles/{pid}/imprevistos", tags=["plan"])
def imprevisto(pid: str, e: ImprevistoEntrada):
    S = perfil_o_404(pid)
    antes = model.calcular(S)
    S2 = {**S, "ev": {**S["ev"], e.tipo: True}, "evA": {**S["evA"]}}
    if e.monto is not None:
        S2["evA"][e.tipo] = e.monto
    despues = model.calcular(S2)
    ev = model.EV[e.tipo]
    return {"imprevisto": ev["n"], "mes": ev["m"],
            "monto": model.monto_evento(S2, e.tipo) if ev["t"] == "once" else None,
            "meses_antes": antes["meses"], "meses_despues": despues["meses"],
            "retraso_meses": (despues["meses"] - antes["meses"]) if None not in (antes["meses"], despues["meses"]) else None,
            "minimo_liquidez": despues["minimo_liquidez"]}


@app.get("/api/pronostico/{cat}", tags=["pronóstico"])
def pronostico(cat: str):
    c = FORECAST["cats"].get(cat)
    if c is None:
        raise NoEncontrado(f"la categoría '{cat}' (usa: {', '.join(CATEGORIAS)})")
    return {"categoria": CATEGORIAS[cat], "modelo": "statsforecast AutoETS", "inicio": FORECAST["start"],
            "p10": c["p10"], "p50": c["p50"], "p90": c["p90"]}


@app.post("/api/perfiles/{pid}/lecciones", tags=["aprende"])
def leccion(pid: str, l: LeccionEntrada):
    perfil_o_404(pid)
    return db.registrar_leccion(pid, l.leccion, l.correcta)


@app.get("/api/perfiles/{pid}/lecciones", tags=["aprende"])
def lecciones(pid: str):
    perfil_o_404(pid)
    return db.progreso(pid)


@app.post("/api/eventos", status_code=201, tags=["usabilidad"])
def evento(e: EventoEntrada):
    if e.tipo == "seq" and not (e.valor is not None and 1 <= e.valor <= 7):
        raise StarletteHTTPException(422, "SEQ debe ir de 1 a 7.")
    db.registrar_evento(e.model_dump())
    return {"ok": True}


@app.get("/api/eventos/{sesion}/resumen", tags=["usabilidad"])
def resumen(sesion: str):
    """Tiempo por tarea (inicio→fin), éxito, errores y SEQ de una sesión de test."""
    from datetime import datetime
    ev = db.eventos_de(sesion)
    if not ev:
        raise NoEncontrado(f"la sesión {sesion}")
    out = {}
    for x in ev:
        t = out.setdefault(x["tarea"] or "-", {"errores": 0, "ayudas": 0})
        if x["tipo"] == "inicio":
            t["_t0"] = x["ts"]
        elif x["tipo"] == "fin":
            t["exito"] = bool(x["valor"])
            if "_t0" in t:
                t["segundos"] = round((datetime.fromisoformat(x["ts"]) - datetime.fromisoformat(t["_t0"])).total_seconds(), 1)
        elif x["tipo"] == "error":
            t["errores"] += 1
        elif x["tipo"] == "ayuda":
            t["ayudas"] += 1
        elif x["tipo"] == "seq":
            t["seq"] = x["valor"]
    for t in out.values():
        t.pop("_t0", None)
    return {"sesion": sesion, "tareas": out}


# ---------- La app (frontend) servida desde el mismo servidor ----------
# Al abrir http://localhost:8000 la app detecta la API y guarda el plan y las lecciones.
STATIC = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC):
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="app")
