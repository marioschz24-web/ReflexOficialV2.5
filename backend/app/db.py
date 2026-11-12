"""Persistencia en SQLite (archivo único, cero configuración)."""
import json, os, sqlite3, uuid
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.environ.get("REFLEX_DB", os.path.join(os.path.dirname(__file__), "..", "data", "reflex.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS perfiles (
  id          TEXT PRIMARY KEY,
  datos       TEXT NOT NULL,              -- JSON con ingresos, gastos, ahorro, vivienda
  creado_en   TEXT NOT NULL,
  actualizado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lecciones (
  perfil_id   TEXT NOT NULL REFERENCES perfiles(id) ON DELETE CASCADE,
  leccion     TEXT NOT NULL,
  intentos    INTEGER NOT NULL DEFAULT 0 CHECK (intentos >= 0),
  correcta    INTEGER NOT NULL DEFAULT 0 CHECK (correcta IN (0,1)),
  actualizado TEXT NOT NULL,
  PRIMARY KEY (perfil_id, leccion)
);
CREATE TABLE IF NOT EXISTS eventos (       -- telemetría de los tests de usabilidad
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  sesion      TEXT NOT NULL,
  participante TEXT,
  tarea       TEXT,
  tipo        TEXT NOT NULL CHECK (tipo IN ('inicio','fin','error','ayuda','seq')),
  valor       REAL,
  ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_eventos_sesion ON eventos(sesion, tarea);
"""


def ahora():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@contextmanager
def conexion():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conexion() as c:
        c.executescript(SCHEMA)


def crear_perfil(datos: dict) -> str:
    pid = uuid.uuid4().hex[:12]
    t = ahora()
    with conexion() as c:
        c.execute("INSERT INTO perfiles VALUES (?,?,?,?)", (pid, json.dumps(datos), t, t))
    return pid


def leer_perfil(pid: str):
    with conexion() as c:
        r = c.execute("SELECT datos FROM perfiles WHERE id=?", (pid,)).fetchone()
    return json.loads(r["datos"]) if r else None


def guardar_perfil(pid: str, datos: dict):
    with conexion() as c:
        c.execute("UPDATE perfiles SET datos=?, actualizado=? WHERE id=?", (json.dumps(datos), ahora(), pid))


def registrar_leccion(pid, leccion, correcta):
    with conexion() as c:
        c.execute("""INSERT INTO lecciones VALUES (?,?,1,?,?)
                     ON CONFLICT(perfil_id, leccion) DO UPDATE SET
                       intentos = intentos + 1,
                       correcta = MAX(correcta, excluded.correcta),
                       actualizado = excluded.actualizado""",
                  (pid, leccion, int(correcta), ahora()))
        return [dict(r) for r in c.execute(
            "SELECT leccion, intentos, correcta FROM lecciones WHERE perfil_id=? ORDER BY leccion", (pid,))]


def progreso(pid):
    with conexion() as c:
        return [dict(r) for r in c.execute(
            "SELECT leccion, intentos, correcta FROM lecciones WHERE perfil_id=? ORDER BY leccion", (pid,))]


def registrar_evento(e: dict):
    with conexion() as c:
        c.execute("INSERT INTO eventos (sesion,participante,tarea,tipo,valor,ts) VALUES (?,?,?,?,?,?)",
                  (e["sesion"], e.get("participante"), e.get("tarea"), e["tipo"], e.get("valor"), ahora()))


def eventos_de(sesion):
    with conexion() as c:
        return [dict(r) for r in c.execute("SELECT * FROM eventos WHERE sesion=? ORDER BY id", (sesion,))]
