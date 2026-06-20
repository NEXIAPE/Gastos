# ⚽ BETLAB AI

Sistema de **detección de apuestas de valor (Value Bets)** en fútbol basado
**100% en probabilidad matemática** — sin intuición. Combina un modelo de
Poisson, ratings dinámicos de equipos, cálculo de Expected Value y staking por
criterio de Kelly fraccionado, con un dashboard en Streamlit y un generador de
reportes diarios.

---

## 1. Arquitectura

```
                 ┌──────────────────────────────────────────────┐
                 │                   FUENTES                     │
                 │   API-Football            The Odds API        │
                 └───────┬───────────────────────┬──────────────┘
                         │                        │
              MODULE 1   │                        │  MODULE 2
           Data Ingestion▼                        ▼ Odds Scraper
                 ┌──────────────────────────────────────────────┐
                 │                  SQLite (database/)           │
                 │  leagues · teams · fixtures · match_stats     │
                 │  injuries · odds · team_ratings · value_bets  │
                 │  bet_log                                      │
                 └───────┬───────────────────────┬──────────────┘
                         │                        │
        MODULE 3 ▼ Team Strength        MODULE 4 ▼ Poisson Model
        (ataque/defensa,                (goles esperados, P(1X2),
         home adv, forma)                P(Over2.5), P(BTTS))
                         └───────────┬────────────┘
                                     ▼
                        MODULE 5 · Value Bet Engine
                        EV = (P_modelo × cuota) − 1   →  EV > 5%
                                     ▼
                  SCORE DE CONFIANZA (0-100) · 10 factores
            xG · Elo · Forma5 · Forma10 · Lesiones · Fatiga ·
            Rend.Local · Rend.Visitante · H2H · Mov.Cuotas
            → Elite(90+) / Strong(80+) / Lean(70+) / No Bet ; filtro > 80
                                     ▼
                        MODULE 6 · Kelly Criterion (25%)
                        stake sugerido · riesgo · % bankroll
                                     ▼
              ┌──────────────────────┴───────────────────────┐
   MODULE 7 ▼ Dashboard (Streamlit)            MODULE 8 ▼ Report Generator
   Top Picks · EV% · ROI · historial · charts  reporte_diario.html
```

El flujo lo orquesta `main.py` (CLI) y se visualiza en `dashboard/app.py`.

---

## 2. Árbol de carpetas

```
betlab-ai/
├── config.py                  # Configuración central (env, rutas, parámetros)
├── main.py                    # Orquestador CLI del pipeline
├── install.sh                 # Script de instalación
├── requirements.txt
├── .env.example               # Plantilla de variables de entorno
├── README.md
│
├── data/                      # Artefactos de datos (CSV/JSON exportados)
│
├── database/                  # MODULE base de datos
│   ├── schema.sql             #   Esquema SQLite completo
│   ├── db.py                  #   Capa de acceso (conexión, upsert, query_df)
│   └── __init__.py
│
├── services/                  # MODULES 1 y 2 (ingesta)
│   ├── api_football.py        #   MODULE 1 - cliente API-Football
│   ├── odds_api.py            #   MODULE 2 - cliente The Odds API
│   ├── data_ingestion.py      #   Orquestador de ingesta
│   ├── demo_data.py           #   Datos sintéticos (modo demo)
│   └── __init__.py
│
├── models/                    # MODULES 3-6 (analítica)
│   ├── team_strength.py       #   MODULE 3 - ratings dinámicos
│   ├── poisson_model.py       #   MODULE 4 - distribución de Poisson
│   ├── elo.py                 #   Elo Rating dinámico
│   ├── confidence.py          #   Score de Confianza (10 factores) + tier
│   ├── value_bet.py           #   MODULE 5 - Value Bet Engine (EV + confianza)
│   ├── kelly.py               #   MODULE 6 - Kelly fraccionado
│   ├── roi.py                 #   Registro de resultados + ROI
│   └── __init__.py
│
├── dashboard/                 # MODULE 7
│   └── app.py                 #   Dashboard Streamlit
│
└── reports/                   # MODULE 8
    ├── report_generator.py    #   Genera reporte_diario.html
    └── __init__.py
```

---

## 3. Base de datos (SQLite)

Definida en `database/schema.sql`. Tablas principales:

| Tabla          | Contenido                                                        |
|----------------|------------------------------------------------------------------|
| `leagues`      | Ligas y temporadas.                                              |
| `teams`        | Equipos.                                                         |
| `fixtures`     | Partidos (fecha, estado, equipos, goles).                       |
| `match_stats`  | Estadísticas por equipo/partido: goles, xG, posesión, tiros.    |
| `injuries`     | Lesiones reportadas.                                            |
| `odds`         | Histórico de cuotas (1X2, Over/Under, BTTS, Asian Handicap).    |
| `team_ratings` | Ratings dinámicos: ataque, defensa, home adv, forma.            |
| `value_bets`   | Value bets detectadas con EV y stake.                           |
| `bet_log`      | Apuestas registradas + resultado (para ROI).                    |

Inicializar: `python main.py initdb`.

---

## 4. Módulos

| Módulo | Archivo | Función |
|--------|---------|---------|
| **1 · Data Ingestion** | `services/api_football.py`, `data_ingestion.py` | Fixtures, equipos, goles, xG, posesión, tiros, lesiones, forma → SQLite. |
| **2 · Odds Scraper** | `services/odds_api.py` | 1X2, Over/Under, BTTS, Asian Handicap → histórico de cuotas. |
| **3 · Team Strength** | `models/team_strength.py` | Ataque, defensa, ventaja local, rendimiento visitante, forma → rating dinámico. |
| **4 · Poisson Model** | `models/poisson_model.py` | Goles esperados local/visitante; P(resultado), P(Over 2.5), P(BTTS), P(victoria). |
| **Elo Rating** | `models/elo.py` | Rating Elo dinámico con ventaja de localía y margen de goles. |
| **Score de Confianza** | `models/confidence.py` | Combina 10 factores en un score 0-100 + tier (Elite/Strong/Lean/No Bet). |
| **5 · Value Bet Engine** | `models/value_bet.py` | `EV = (P_modelo × cuota) − 1`; muestra solo `EV > 5%` **y** confianza `> 80`. |
| **6 · Kelly Criterion** | `models/kelly.py` | Kelly fraccionado al 25%: stake sugerido, riesgo, % bankroll. |
| **7 · Dashboard** | `dashboard/app.py` | Streamlit: Top Picks, EV%, ROI acumulado, historial, gráficos. |
| **8 · Report Generator** | `reports/report_generator.py` | `reporte_diario.html` con el TOP 10 (partido, mercado, cuota, prob, EV, stake). |

---

## 5. Instalación

```bash
cd betlab-ai
./install.sh                    # crea venv, instala deps, inicializa DB y datos demo
```

Manual:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # rellena tus claves (opcional)
python main.py initdb
```

> **Sin claves de API** el sistema arranca en **modo DEMO** con datos sintéticos
> deterministas, de modo que puedes probar todo el pipeline al instante.

---

## 6. Uso

```bash
# Pipeline completo: ingesta → ratings → value bets → registro → reporte
python main.py pipeline

# Pasos individuales
python main.py ingest 2026-06-20   # ingesta de una fecha
python main.py value               # detectar value bets
python main.py report              # generar reports/reporte_diario.html
python main.py settle              # liquidar apuestas con resultado conocido

# Dashboard interactivo
streamlit run dashboard/app.py
```

---

## 7. Configuración

Todos los parámetros viven en `.env` (ver `.env.example`):

| Variable | Por defecto | Significado |
|----------|-------------|-------------|
| `API_FOOTBALL_KEY` | — | Clave de API-Football. |
| `ODDS_API_KEY` | — | Clave de The Odds API. |
| `MIN_EV` | `0.05` | EV mínimo para considerar valor (5%). |
| `MIN_CONFIDENCE` | `80` | Score de Confianza mínimo (solo Strong/Elite). |
| `KELLY_FRACTION` | `0.25` | Fracción de Kelly aplicada. |
| `BANKROLL` | `1000` | Bankroll inicial (€). |
| `MAX_STAKE_PCT` | `0.10` | Tope de stake por apuesta. |
| `HOME_ADVANTAGE` | `1.35` | Ventaja de localía por defecto. |

---

## 8. Score Final de Confianza (10 factores)

Sobre cada candidata a value bet (EV > 5%) se calcula un **Score de Confianza
de 0 a 100** (`models/confidence.py` + `models/elo.py`). Cada factor se orienta
a la selección concreta y devuelve un valor 0-100 (>50 = apoya la apuesta); el
score es su media ponderada, renormalizada según los factores aplicables al
mercado.

| # | Factor | Peso | Qué mide |
|---|--------|------|----------|
| 1 | **Expected Goals (xG)** | 14 | Calidad de creación/concesión (xG a favor − en contra). |
| 2 | **Elo Rating** | 16 | Fuerza global dinámica (con ventaja de localía y margen de goles). |
| 3 | **Forma últimos 5** | 10 | Puntos por partido recientes (corto plazo). |
| 4 | **Forma últimos 10** | 8 | Puntos por partido (medio plazo). |
| 5 | **Lesiones ponderadas** | 8 | Bajas del equipo vs. del rival. |
| 6 | **Fatiga por calendario** | 6 | Días de descanso desde el último partido. |
| 7 | **Rendimiento local** | 10 | Puntos del local jugando en casa. |
| 8 | **Rendimiento visitante** | 10 | Puntos del visitante jugando fuera. |
| 9 | **Historial H2H** | 8 | Resultados directos previos (y % Over / BTTS). |
| 10 | **Movimiento de cuotas** | 10 | Si la cuota se ha acortado desde la apertura (entrada de dinero). |

**Clasificación del score:**

| Score | Tier | Acción |
|-------|------|--------|
| 90-100 | 🟡 **Elite Pick** | Máxima confianza |
| 80-89 | 🔵 **Strong Pick** | Alta confianza |
| 70-79 | ⚪ Lean | Confianza moderada |
| < 70 | ⚫ No Bet | Descartar |

> **Solo se muestran apuestas con Score > 80** (Strong y Elite). Configurable
> con `MIN_CONFIDENCE`.

---

## 9. Metodología (probabilidad, no intuición)

1. **Ratings** — ataque y defensa relativos a la media de la liga, mezclando
   goles reales con xG para reducir ruido; se ajustan por ventaja de localía,
   rendimiento visitante y forma reciente.
2. **Poisson** — `λ_local` y `λ_visitante` derivan de los ratings; la matriz
   conjunta de marcadores da P(1X2), P(Over X.5) y P(BTTS).
3. **Expected Value** — `EV = P_modelo × cuota − 1`. Solo se reportan apuestas
   con `EV > MIN_EV` (mercado infravalorando el evento).
4. **Kelly fraccionado** — stake = `¼ · f*` con tope de protección, maximizando
   crecimiento logarítmico del bankroll con varianza controlada.
5. **ROI** — cada pick se registra y, al conocerse el resultado, se liquida para
   medir profit, ROI, yield y win rate históricos.

---

> ⚠️ Las apuestas conllevan riesgo. BETLAB AI es una **herramienta de análisis
> estadístico**, no una garantía de beneficios. Úsala con responsabilidad.
