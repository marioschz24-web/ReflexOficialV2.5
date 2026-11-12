"""Contratos de entrada/salida (validación con pydantic)."""
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

Monto = Field(ge=0, le=50_000_000)


class PerfilEntrada(BaseModel):
    """Todos los campos son opcionales: lo que no venga toma el valor de la persona tipo (Josefina)."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    e1: Optional[int] = Field(None, ge=0, le=50_000_000, description="Sueldo empleo principal (CLP/mes)")
    e2: Optional[int] = Field(None, ge=0, le=50_000_000, description="Segundo empleo (CLP/mes)")
    par: Optional[int] = Field(None, ge=0, le=50_000_000, description="Aporte de la pareja (CLP/mes)")
    fam: Optional[int] = Field(None, ge=0, le=50_000_000)
    sal: Optional[int] = Field(None, ge=0, le=50_000_000)
    arr: Optional[int] = Field(None, ge=0, le=50_000_000, description="Arriendo")
    ali: Optional[int] = Field(None, ge=0, le=50_000_000)
    otr: Optional[int] = Field(None, ge=0, le=50_000_000)
    delivery: Optional[int] = Field(None, ge=0, le=50_000_000, alias="del")
    sus: Optional[int] = Field(None, ge=0, le=50_000_000)
    com: Optional[int] = Field(None, ge=0, le=50_000_000)
    pen: Optional[int] = Field(None, ge=0, le=50_000_000)
    ah0: Optional[int] = Field(None, ge=0, le=1_000_000_000, description="Ahorro disponible")
    inv: Optional[int] = Field(None, ge=0, le=1_000_000_000, description="Ahorro invertido")
    q: Optional[Literal["sola", "pareja"]] = None
    val: Optional[int] = Field(None, ge=10_000_000, le=1_000_000_000, description="Valor de la vivienda")
    pie: Optional[float] = Field(None, ge=5, le=50, description="% de pie")
    plazo: Optional[int] = Field(None, ge=5, le=40)
    tasa: Optional[float] = Field(None, ge=0, le=20)
    rj: Optional[float] = Field(None, ge=0, le=15, description="Alza anual de precios de vivienda %")
    adj: Optional[int] = Field(None, ge=-5_000_000, le=5_000_000, description="Ajuste mensual manual")
    ap: Optional[dict[Literal["del", "sus", "com"], bool]] = None


class Proyeccion(BaseModel):
    ahorro_mensual: int
    meta_pie: int
    pie: int
    meses: Optional[int] = Field(description="Meses para juntar el pie; null si no se alcanza en 10 años")
    meses_sin_imprevistos: Optional[int]
    cuota: int
    carga_pct: float
    nivel: Literal["holgado", "justo", "sobre_limite"]
    tasa_efectiva: float
    minimo_liquidez: int
    serie: list[int]


class ImprevistoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tipo: Literal["salud", "auto", "hijo", "hogar", "arriendo", "ingreso"]
    monto: Optional[int] = Field(None, ge=0, le=20_000_000, description="Solo para gastos únicos; si falta se sugiere uno según tu perfil")


class LeccionEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    leccion: str = Field(min_length=1, max_length=40, pattern=r"^[a-z0-9_-]+$")
    correcta: bool


class EventoEntrada(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sesion: str = Field(min_length=1, max_length=40)
    participante: Optional[str] = Field(None, max_length=10)
    tarea: Optional[Literal["T1", "T2", "T3", "T4"]] = None
    tipo: Literal["inicio", "fin", "error", "ayuda", "seq"]
    valor: Optional[float] = Field(None, description="SEQ 1–7, o 1/0 para éxito al cerrar la tarea")
