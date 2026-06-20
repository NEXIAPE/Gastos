# ⚽ BETLAB AI

Sistema de **detección de apuestas de valor (Value Bets)** en fútbol con
**autoevaluación, optimización continua y generación automática de picks
diarios**. Todo se basa en **probabilidad matemática**, nunca en intuición.

> Filosofía: **no generar más picks, sino menos picks con mejor expectativa
> matemática.** La rentabilidad y la gestión de riesgo priman sobre la cantidad.

---

## 1. Arquitectura

```
        API-Football            The Odds API           (o DATOS DEMO)
             │  M1 Data Ingestion      │  M2 Odds Scraper
             ▼                         ▼
        ┌──────────────────────────────────────────────────────────┐
        │                    SQLite (database/)                     │
        │  leagues·teams·fixtures·match_stats·injuries·odds         │
        │  team_ratings·value_bets·bet_log·league_ratings·no_bets   │
        │  bankroll_state·backtest_results                          │
        └───┬───────────────┬───────────────┬──────────────────────┘
            ▼               ▼               ▼
   M1 Performance    M2 League       Team Strength + Elo + xG
      Tracker         Analyzer       (ratings dinámicos)
   ROI·Yield·DD     Elite/Good/            │
   profit/mercado   Neutral/Avoid          ▼
   profit/liga      → ajusta conf.   M4 POISSON MODEL (P 1X2/Over/BTTS)
                          │                 │
                          ▼                 ▼
                   M5 CONFIDENCE SCORE (0-100, 11 factores)
                   Elite≥90 · Strong≥85 · Value≥80 · No Bet<80
                          │
                          ▼
                   M3 NO BET ENGINE  (bajas, rotaciones, amistoso,
                          │           info insuf., EV<5%, edge<3%)
                          ▼
                   VALUE BET ENGINE (EV = prob·cuota − 1)
                          │
            M4 Bankroll Manager ──► stake (Kelly frac. + reglas de riesgo)
                          │         NORMAL / REDUCED / CONSERVATION
                          ▼
   ┌──────────────────────┴───────────────────────────────┐
   ▼ M7 Dashboard (Streamlit)        ▼ M6 Daily Report (HTML)
   Estrategia·Performance·Ligas       A) Pick Premium  B) Top 5
   ·Backtest·No-Bet·Factores          C/D/E) Combinadas Cons/Mod/Agr

        M7 BACKTESTING: Poisson vs +Elo vs +Elo+xG  → auto-selección
```

---

## 2. Árbol de carpetas

```
betlab-ai/
├── config.py                  # Configuración central (env, rutas, parámetros)
├── main.py                    # Orquestador CLI (pipeline + comandos)
├── install.sh · requirements.txt · .env.example · README.md
│
├── data/                      # Artefactos de datos
├── database/
│   ├── schema.sql             # Esquema SQLite completo
│   ├── db.py                  # Capa de acceso
│   └── __init__.py
├── services/
│   ├── api_football.py        # M1 - cliente API-Football
│   ├── odds_api.py            # M2 - cliente The Odds API
│   ├── data_ingestion.py      # Orquestador de ingesta
│   ├── demo_data.py           # Dataset demo multi-liga (~2 años)
│   └── __init__.py
├── models/
│   ├── poisson_model.py       # Modelo de Poisson
│   ├── team_strength.py       # Ratings de ataque/defensa (xG)
│   ├── elo.py                 # Elo Rating dinámico
│   ├── confidence.py          # M5 - Score de Confianza (11 factores)
│   ├── nobet.py               # M3 - No Bet Engine
│   ├── bankroll.py            # M4 - Bankroll Manager
│   ├── kelly.py               # Kelly fraccionado
│   ├── value_bet.py           # Value Bet Engine (integra todo)
│   ├── strategies.py          # M6 - Pick premium, Top 5, combinadas
│   ├── performance.py         # M1 - Performance Tracker
│   ├── league_analyzer.py     # M2 - League Analyzer
│   ├── backtest.py            # M7 - Backtesting de variantes
│   ├── roi.py                 # Liquidación de apuestas
│   └── __init__.py
├── dashboard/
│   └── app.py                 # M7 - Dashboard Streamlit
└── reports/
    ├── report_generator.py    # M6 - reporte_diario.html
    └── __init__.py
```

---

## 3. Base de datos (SQLite)

| Tabla | Contenido |
|-------|-----------|
| `leagues`,`teams`,`fixtures` | Catálogo y partidos. |
| `match_stats` | Goles, xG, posesión, tiros por equipo/partido. |
| `injuries` | Lesiones / sanciones. |
| `odds` | Histórico de cuotas (1X2, O/U, BTTS, AH) con timestamp. |
| `team_ratings` | Ataque, defensa, ventaja local, forma. |
| `value_bets` | Picks del día con EV, confianza, tier y stake. |
| `bet_log` | Track record: fecha, liga, mercado, cuota, prob, EV, stake, resultado, P/L. |
| `league_ratings` | **League Analyzer**: ROI/Yield/Accuracy/tier/multiplicador. |
| `no_bets` | **No Bet Engine**: partidos descartados + motivo. |
| `bankroll_state` | **Bankroll Manager**: capital, modo, multiplicador. |
| `backtest_results` | **Backtesting**: métricas por variante de modelo. |

---

## 4. Módulos avanzados

### M1 · Performance Tracker (`models/performance.py`)
Registra cada apuesta (fecha, liga, partido, mercado, cuota, probabilidad, EV,
stake, resultado, P/L) y calcula **ROI, Yield, Profit, Hit Rate, Drawdown
máximo, Profit por mercado y por liga**, con datos para gráficos históricos.

### M2 · League Analyzer (`models/league_analyzer.py`)
Clasifica cada competición por ROI/Yield/Accuracy/EV histórico en
**Elite / Good / Neutral / Avoid League** y ajusta automáticamente la confianza
de las predicciones futuras (multiplicador ×1.10 / ×1.05 / ×1.00 / ×0.85).

### M3 · No Bet Engine (`models/nobet.py`)
Marca un partido o selección como **NO BET** mostrando **siempre el motivo**:
demasiadas bajas importantes, rotaciones masivas, amistoso, información
insuficiente, **EV < 5%**, o diferencia de probabilidades **< 3%**.

### M4 · Bankroll Manager (`models/bankroll.py`)
Gestión automática de riesgo sobre el drawdown:

| Drawdown | Modo | Efecto |
|----------|------|--------|
| > 10% | **REDUCED** | Stakes al 50%. |
| > 20% | **CONSERVATION** | Solo confianza > 90, stake máx. 1%, **sin combinadas**. |
| — | NORMAL | Operación estándar. |

### M5 · Confidence Score (`models/confidence.py`)
Score único **0-100** con 11 factores (incluye los 8 pedidos): **Poisson, xG,
Elo, Forma reciente (5 y 10), Lesiones, Fatiga, Movimiento de cuotas, H2H** +
rendimiento local/visitante, y **ajuste por liga**.

| Score | Tier |
|-------|------|
| 90-100 | 🟡 Elite Pick |
| 85-89 | 🔵 Strong Pick |
| 80-84 | 🟢 Value Pick |
| < 80 | ⚫ No Bet |

### M6 · Daily Report (`reports/report_generator.py` + `models/strategies.py`)
Genera cada día: **A) Pick Premium** (mayor EV ajustado por riesgo),
**B) Top 5 Value Bets**, **C/D/E) Combinadas** Conservadora (máx 2) /
Moderada (máx 3) / Agresiva (máx 5), cada una con **cuota, probabilidad
conjunta, EV, stake y nivel de riesgo**. Una combinada con **EV negativo se
descarta**; si no hay ninguna con valor: **"NO HAY COMBINADAS DE VALOR HOY"**.

### M7 · Backtesting (`models/backtest.py`)
Simulación walk-forward (train/test) sobre ~2 años comparando **Poisson**,
**Poisson+Elo** y **Poisson+Elo+xG** por Accuracy, ROI, Yield, Drawdown y
Profit, y **selecciona automáticamente el modelo más rentable**.

---

## 5. Uso

```bash
cd betlab-ai
./install.sh                       # venv + deps + DB + demo + backtest

python main.py pipeline            # flujo diario completo (7 pasos)
python main.py strategies          # Pick premium, Top 5 y combinadas
python main.py leagues             # clasificación de ligas
python main.py performance         # métricas del track record
python main.py bankroll            # estado y modo del bankroll
python main.py backtest            # comparación de modelos
python main.py report              # genera reports/reporte_diario.html

streamlit run dashboard/app.py     # panel interactivo
```

El **pipeline** ejecuta: ingesta → liquidación → Bankroll Manager →
League Analyzer → detección de picks (No Bet + Poisson + EV + Confianza +
Kelly) → registro → reporte + estrategia.

> **Sin claves de API** se genera un dataset **demo determinista** (4 ligas con
> perfiles Elite/Good/Neutral/Avoid, ~2 años de historial y track record) para
> ejercitar todo el sistema al instante.

---

## 6. Configuración (`.env`)

Claves de API, umbrales (`MIN_EV`, `MIN_CONFIDENCE`, `MIN_PROB_EDGE`,
`ODD_MIN/MAX`), No Bet (`MAX_KEY_INJURIES`, `MIN_HISTORY`), Kelly
(`KELLY_FRACTION`, `BANKROLL`, `MAX_STAKE_PCT`) y Bankroll Manager
(`DD_REDUCE`, `DD_CONSERVE`, `CONSERVE_MIN_CONF`, `CONSERVE_MAX_STAKE`).
Ver `.env.example`.

---

> ⚠️ Las apuestas conllevan riesgo. BETLAB AI es una **herramienta de análisis
> estadístico**, no una garantía de beneficios. Úsala con responsabilidad.
