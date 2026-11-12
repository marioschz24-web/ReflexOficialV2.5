import os, statistics, tempfile, time
os.environ["REFLEX_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

from fastapi.testclient import TestClient
from app.main import app
from app import model

c = TestClient(app)
c.__enter__()  # dispara startup (crea tablas)


def nuevo(**kw):
    r = c.post("/api/perfiles", json=kw)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# --- Paridad con la app (valores que ven los participantes) ---
def test_proyeccion_persona_tipo():
    r = c.get(f"/api/perfiles/{nuevo()}/proyeccion").json()
    assert r["meses"] == 18 and r["cuota"] == 418_214 and r["carga_pct"] == 27.3
    assert r["ahorro_mensual"] == 390_000 and r["nivel"] == "justo"


def test_caminos_coinciden_con_app():
    cam = {x["id"]: x for x in c.get(f"/api/perfiles/{nuevo()}/caminos").json()}
    assert (cam["via_rapida"]["meses"], cam["lento_seguro"]["meses"], cam["ajustar"]["meses"]) == (18, 46, 20)
    assert (cam["via_rapida"]["carga_pct"], cam["lento_seguro"]["carga_pct"], cam["ajustar"]["carga_pct"]) == (27.3, 23.5, 18.8)


def test_editar_perfil_cambia_resultado():
    pid = nuevo()
    r = c.patch(f"/api/perfiles/{pid}", json={"adj": 50_000}).json()
    assert r["proyeccion"]["meses"] < 18
    assert c.get(f"/api/perfiles/{pid}").json()["adj"] == 50_000


def test_imprevisto_retrasa_o_mantiene():
    pid = nuevo()
    r = c.post(f"/api/perfiles/{pid}/imprevistos", json={"tipo": "salud", "monto": 2_000_000}).json()
    assert r["meses_despues"] >= r["meses_antes"] and r["retraso_meses"] >= 1


def test_habitos_aplicados_suman_ahorro():
    S = model.perfil_base(ap={"del": True, "sus": True})
    assert model.ahorro_habitos(S) == 32_000 + 20_000


def test_pronostico():
    r = c.get("/api/pronostico/ali").json()
    assert len(r["p50"]) == len(r["p10"]) == len(r["p90"]) > 0
    assert all(a <= b <= d for a, b, d in zip(r["p10"], r["p50"], r["p90"]))


def test_lecciones_progreso():
    pid = nuevo()
    c.post(f"/api/perfiles/{pid}/lecciones", json={"leccion": "cae", "correcta": False})
    p = c.post(f"/api/perfiles/{pid}/lecciones", json={"leccion": "cae", "correcta": True}).json()
    assert p == [{"leccion": "cae", "intentos": 2, "correcta": 1}]


def test_eventos_resumen():
    for t in [("inicio", None), ("error", None), ("fin", 1), ("seq", 6)]:
        assert c.post("/api/eventos", json={"sesion": "s1", "participante": "P1", "tarea": "T2", "tipo": t[0], "valor": t[1]}).status_code == 201
    r = c.get("/api/eventos/s1/resumen").json()["tareas"]["T2"]
    assert r["exito"] is True and r["errores"] == 1 and r["seq"] == 6 and r["segundos"] >= 0


# --- Errores RFC 7807 ---
def test_404_problem_json():
    r = c.get("/api/perfiles/noexiste/proyeccion")
    assert r.status_code == 404 and r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["title"] == "No encontrado"


def test_422_validacion():
    r = c.post("/api/perfiles", json={"pie": 90, "e1": -5, "campo_raro": 1})
    assert r.status_code == 422
    campos = {e["campo"] for e in r.json()["errores"]}
    assert {"pie", "e1", "campo_raro"} <= campos


def test_seq_fuera_de_rango():
    r = c.post("/api/eventos", json={"sesion": "s2", "tipo": "seq", "valor": 9})
    assert r.status_code == 422


# --- Rendimiento ---
def test_latencia_p95_bajo_200ms():
    pid = nuevo()
    ts = []
    for _ in range(100):
        t0 = time.perf_counter()
        assert c.get(f"/api/perfiles/{pid}/proyeccion").status_code == 200
        ts.append((time.perf_counter() - t0) * 1000)
    p95 = statistics.quantiles(ts, n=20)[18]
    print(f"\nproyeccion: mediana {statistics.median(ts):.1f} ms · p95 {p95:.1f} ms")
    assert p95 < 200


def test_app_servida_en_raiz():
    r = c.get("/")
    assert r.status_code == 200 and "Reflex" in r.text and "api/salud" in r.text
