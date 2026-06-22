# ⚽ BETLAB AI — Guía rápida de uso

Sistema de **value betting** en mercados de **goles**: 1X2 · Over/Under 2.5 · BTTS.
Datos reales y gratuitos (football-data.org + base internacional + The Odds API).

> Filosofía: **menos picks, pero con mejor expectativa matemática.** El sistema
> se "calla" cuando no tiene datos suficientes — eso te protege.

---

## 1. Abrir el entorno (cada vez)

```powershell
cd $HOME\gastos\betlab-ai
.\.venv\Scripts\Activate.ps1
```
Si al activar sale error de "scripts disabled":
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 2. Configuración (.env) — se hace una sola vez

**Para el Mundial (selecciones, historial completo):**
```powershell
"FOOTBALLDATA_TOKEN=tu_token_football_data" | Set-Content .env
"FD_COMPETITION=INTL"                        | Add-Content .env
"ODDS_API_KEY=tu_clave_odds"                 | Add-Content .env
"ODDS_SPORT=soccer_fifa_world_cup"           | Add-Content .env
"INTL_SINCE=2018"                            | Add-Content .env
"MIN_HISTORY=5"                              | Add-Content .env
"MIN_CONFIDENCE=78"                          | Add-Content .env
"BANKROLL=200"                               | Add-Content .env
```

**Para ligas de clubes (cuando estén en temporada):** usá el dashboard
(selector de liga) o cambiá en .env, por ejemplo Brasileirão:
```
FD_COMPETITION=BSA:2025,BSA:2026
ODDS_SPORT=soccer_brazil_campeonato
```

## 3. Rutina del día que vas a apostar

```powershell
python main.py pipeline        # baja resultados + cuotas y recalcula picks
streamlit run dashboard/app.py # abrí el dashboard en http://localhost:8501
```
En el dashboard mirás **Estrategia del día**: Pick Premium, Top 5 y Combinadas.

> Más cómodo aún: en la barra lateral del dashboard, elegí la **liga** y apretá
> **🔄 Actualizar datos**. Hace todo solo.

## 4. Después de que se jueguen los partidos

```powershell
python main.py pipeline
```
Liquida tus apuestas y actualiza **Performance + bankroll** (el sistema aprende
y ajusta el riesgo solo).

---

## Cómo leer un pick
- **EV** = valor esperado. Positivo y razonable (ej. +3% a +30%) = buena apuesta.
  EV exageradamente alto (+100%+) = desconfiá (poca data).
- **Confianza** (0-100): 80+ Elite/Strong/Value. Cuanto más alta, mejor.
- **Stake**: cuánto apostar, ya calculado con Kelly fraccionado (gestión de riesgo).

## Recordatorios honestos
- Esto es **ayuda matemática, no certezas**. Ninguna apuesta es segura.
- **Nunca apuestes lo que no puedas perder.** El bankroll de prueba es chico a propósito.
- El **Mundial** tiene más azar que las ligas (partidos únicos): tratá los picks
  como valor estadístico y usá stakes prudentes.
- El sistema rinde mejor en **ligas de clubes en temporada** (historial rico).

## Mercados cubiertos
| Mercado | Estado |
|---|---|
| 1X2 (local/empate/visitante) | ✅ |
| Over/Under 2.5 goles | ✅ |
| BTTS (ambos marcan) | ✅ |
| Córners / Tarjetas | ❌ (sin datos gratis; posible a futuro con ligas de pago) |

## Comandos útiles
```powershell
python main.py pipeline      # todo: ingesta + picks + reporte
python main.py strategies    # recalcular picks sin re-descargar
python main.py backtest      # backtesting del modelo
python main.py report        # genera reports\reporte_diario.html
```
