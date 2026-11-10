# Reflex · Prototipo

Prototipo académico para el desafío Bci Labs (Taller de Interacción IV, UDD).

**Concepto:** la plataforma crea una versión futura del usuario que evoluciona con sus ingresos, gastos y pagos reales. Cada decisión altera su economía y los meses que necesita para reunir el pie, con las condiciones del crédito a la vista. El usuario prueba escenarios, ve imprevistos si lo decide y los comparte con su pareja. La plataforma le dice la verdad sin presionarlo a comprar.

> Todos los datos son **de ejemplo**. No hay datos reales de Bci ni de ninguna persona.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `index.html` | El prototipo completo. Se abre en cualquier navegador, no necesita instalar nada. |
| `timesfm_forecast.py` | Genera el pronóstico diario de gastos variables (supermercado, delivery, transporte, compras). |
| `forecast_statsforecast.json` | Pronóstico generado con un modelo estadístico (AutoETS). Es el que ya viene dentro de `index.html`. |
| `forecast_baseline.json` | Pronóstico de un modelo simple, para comparar. |

## Ver el prototipo
1. Abre `index.html` en el navegador, o usa el link de GitHub Pages del repositorio.
2. Necesita internet solo para cargar la tipografía.

## Generar el pronóstico
Requiere Python 3.10 o superior.

```
pip install numpy pandas statsforecast
python timesfm_forecast.py --statsforecast --today 2026-10-15
```

Esto crea `forecast.json`. Otras opciones:

| Comando | Qué hace |
|---|---|
| `--statsforecast` | Modelo estadístico AutoETS con estacionalidad semanal y rango del 80%. |
| `--baseline` | Modelo simple, sin dependencias pesadas. |
| (sin opción) | TimesFM 3.0 (ver abajo). |

**Datos de entrada:** si existe un archivo `gastos_diarios.csv` con las columnas `date,ali,del,otr,com` (pesos por día, formato `YYYY-MM-DD`), el script lo usa. Si no, genera una historia sintética de ejemplo.

## Usar el pronóstico en el prototipo
1. Abre `index.html` y avanza hasta **"Tu mes, día a día"**.
2. Al final de la pantalla, toca **"Cargar pronóstico (.json)"** y elige tu `forecast.json`.
3. El calendario, la banda de rango y los días de gasto alto se actualizan.

## Usar TimesFM (opcional)
[TimesFM](https://github.com/google-research/timesfm) es un modelo de Google para pronosticar series de tiempo.

```
git clone https://github.com/google-research/timesfm.git
cd timesfm
python -m venv .venv
source .venv/bin/activate
pip install -e .[torch]
python timesfm_forecast.py --today 2026-10-15
```

- La primera vez descarga los pesos desde Hugging Face.
- **Este modo no fue probado** por el equipo. Si falla, usa `--statsforecast`.
- **Licencia:** los pesos de TimesFM 3.0 son solo para uso **no comercial**. Los pesos hasta la versión 2.5 son Apache-2.0.

## Qué hace el pronóstico y qué no
- Estima el **gasto variable de cada día** con un rango probable, a partir del patrón semanal y de fin de mes.
- **No predice imprevistos.** Esos los decide la persona, como escenarios.
- Es una **proyección con supuestos**, no una predicción de lo que va a pasar.

## Limitaciones conocidas
- Las fechas del pronóstico están fijas entre el 1 de octubre y el 31 de diciembre de 2026. Fuera de ese rango, el calendario usa una agenda de gastos fija.
- La cuota del crédito es una estimación (tasa y plazo editables, con seguros estimados). No es una oferta de Bci.
- La tasa de rendimiento de las inversiones (4% anual) y las fechas de los imprevistos son supuestos de la demo.
- El prototipo no fue probado en todos los dispositivos.

## Créditos
- Prototipo: equipo Reflex, Taller de Interacción IV, Universidad del Desarrollo.
- Pronóstico estadístico: [StatsForecast](https://github.com/Nixtla/statsforecast).
- Modelo de series de tiempo opcional: [TimesFM](https://github.com/google-research/timesfm), Google Research.
