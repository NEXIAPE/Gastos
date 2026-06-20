"""
MODULE 6 - DAILY REPORT
=======================

Genera `reporte_diario.html` autocontenido con:

  * Estado del Bankroll Manager (modo de riesgo).
  * A) PICK PREMIUM DEL DÍA  (mayor EV ajustado por riesgo).
  * B) TOP 5 VALUE BETS.
  * C/D/E) COMBINADAS Conservadora / Moderada / Agresiva
           (cuota, probabilidad, EV, stake y riesgo; descarte de EV negativo).
  * Partidos descartados por el No Bet Engine con su motivo.
  * Clasificación de ligas (League Analyzer).
  * Resumen de Performance (ROI, Yield, Hit Rate, Drawdown).

Si no hay combinadas con valor: "NO HAY COMBINADAS DE VALOR HOY".
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config import REPORTS_DIR, settings
from database import query_df
from models.bankroll import get_state
from models.performance import metrics as perf_metrics
from models.strategies import StrategyReport, build_strategies

SEL_LABELS = {"HOME": "Local", "DRAW": "Empate", "AWAY": "Visitante",
              "OVER": "Over 2.5", "UNDER": "Under 2.5", "YES": "BTTS Sí", "NO": "BTTS No"}
MARKET_LABELS = {"1X2": "1X2", "BTTS": "BTTS", "OU_2.5": "O/U 2.5"}
TIER_CLASS = {"Elite Pick": "elite", "Strong Pick": "strong", "Value Pick": "value"}
LEAGUE_CLASS = {"Elite League": "elite", "Good League": "strong",
                "Neutral League": "value", "Avoid League": "avoid"}


def _sel(s: str) -> str:
    return SEL_LABELS.get(s, s)


def _mkt(m: str) -> str:
    return MARKET_LABELS.get(m, m)


def generate_report(report: StrategyReport | None = None,
                    output_path: Path | str | None = None) -> Path:
    """Ensambla el reporte diario completo y devuelve su ruta."""
    if report is None:
        report = build_strategies()
    state = get_state()
    perf = perf_metrics(settings.bankroll)
    output_path = Path(output_path) if output_path else REPORTS_DIR / "reporte_diario.html"
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    html = f"""<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>BETLAB AI · Reporte Diario</title>
<style>
  :root {{ --bg:#0d1117; --card:#161b22; --line:#30363d; --txt:#e6edf3;
           --muted:#8b949e; --accent:#2ea043; --blue:#1f6feb; }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);color:var(--txt);
        font-family:'Segoe UI',Roboto,Arial,sans-serif;padding:28px}}
  .wrap{{max-width:1040px;margin:0 auto}}
  header{{display:flex;justify-content:space-between;align-items:baseline;
          border-bottom:2px solid var(--accent);padding-bottom:10px}}
  h1{{margin:0;font-size:26px;letter-spacing:1px}} h1 span{{color:var(--accent)}}
  h2{{font-size:17px;margin:26px 0 10px;border-left:3px solid var(--blue);padding-left:10px}}
  .meta{{color:var(--muted);font-size:13px}}
  .cards{{display:flex;gap:12px;margin:18px 0;flex-wrap:wrap}}
  .kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;
        padding:12px 16px;flex:1;min-width:120px}}
  .kpi .v{{font-size:20px;font-weight:700}} .kpi .l{{color:var(--muted);font-size:11px;text-transform:uppercase}}
  table{{width:100%;border-collapse:collapse;background:var(--card);
         border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:8px}}
  th,td{{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);font-size:14px}}
  th{{background:#1c2330;color:var(--muted);font-size:11px;text-transform:uppercase}}
  td.num{{text-align:right;font-variant-numeric:tabular-nums}}
  td.ev{{color:var(--accent);font-weight:700}} tr:last-child td{{border-bottom:none}}
  .badge{{padding:2px 9px;border-radius:11px;font-size:11px;font-weight:700;white-space:nowrap}}
  .elite{{background:#bb8009;color:#fff}} .strong{{background:#1f6feb;color:#fff}}
  .value{{background:#2ea043;color:#fff}} .avoid{{background:#a8324a;color:#fff}}
  .premium{{background:linear-gradient(90deg,#162447,#1f6feb22);border:1px solid var(--blue);
            border-radius:12px;padding:16px 18px;margin-bottom:6px}}
  .premium .big{{font-size:18px;font-weight:700}}
  .mode{{padding:4px 12px;border-radius:11px;font-weight:700;font-size:12px}}
  .mode.NORMAL{{background:#2ea04322;color:#3fb950;border:1px solid #2ea043}}
  .mode.REDUCED{{background:#bb800922;color:#d29922;border:1px solid #bb8009}}
  .mode.CONSERVATION{{background:#a8324a22;color:#f85149;border:1px solid #a8324a}}
  .warn{{color:#d29922;font-weight:600}} .empty{{color:var(--muted);text-align:center;padding:20px}}
  .parlay{{background:var(--card);border:1px solid var(--line);border-radius:10px;
           padding:14px 16px;margin-bottom:12px}}
  .parlay h3{{margin:0 0 8px;font-size:15px}} .leg{{font-size:13px;color:#cbd2d9;margin:3px 0}}
  .ptot{{margin-top:8px;font-size:13px}} .ptot b{{color:var(--accent)}}
  footer{{color:var(--muted);font-size:12px;margin-top:24px;text-align:center}}
</style></head><body><div class="wrap">
  <header>
    <h1>BET<span>LAB</span> AI</h1>
    <div class="meta">Reporte diario · {generated} ·
      <span class="mode {state.mode}">BANKROLL: {state.mode}</span></div>
  </header>

  <div class="cards">
    <div class="kpi"><div class="v">{state.current:.0f}€</div><div class="l">Bankroll</div></div>
    <div class="kpi"><div class="v">{perf['roi'] * 100:.1f}%</div><div class="l">ROI</div></div>
    <div class="kpi"><div class="v">{perf['yield'] * 100:.1f}%</div><div class="l">Yield</div></div>
    <div class="kpi"><div class="v">{perf['hit_rate'] * 100:.0f}%</div><div class="l">Hit rate</div></div>
    <div class="kpi"><div class="v">{perf['max_drawdown'] * 100:.0f}%</div><div class="l">Max DD</div></div>
    <div class="kpi"><div class="v">{len(report.pool)}</div><div class="l">Picks elegibles</div></div>
  </div>

  {_premium_html(report)}
  <h2>B) TOP 5 VALUE BETS</h2>
  {_top5_html(report)}

  <h2>Combinadas</h2>
  {_parlays_html(report)}

  <h2>🚫 Partidos descartados (No Bet Engine)</h2>
  {_nobets_html()}

  <h2>🏆 Clasificación de ligas (League Analyzer)</h2>
  {_leagues_html()}

  <footer>
    BETLAB AI · Poisson + xG + Elo + Confianza (Performance, League, No-Bet, Bankroll).<br>
    Filosofía: menos picks, mejor expectativa matemática. Las apuestas conllevan riesgo.
  </footer>
</div></body></html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _premium_html(report: StrategyReport) -> str:
    b = report.premium
    if not b:
        return ('<h2>A) PICK PREMIUM DEL DÍA</h2>'
                '<div class="premium"><span class="empty">No hay pick elegible hoy.</span></div>')
    tier_cls = TIER_CLASS.get(b.tier, "value")
    return f"""<h2>A) PICK PREMIUM DEL DÍA <span class="meta">(mayor EV ajustado por riesgo)</span></h2>
    <div class="premium">
      <div class="big">{b.match} · {_mkt(b.market)} {_sel(b.selection)}
        <span class="badge {tier_cls}">{b.tier}</span></div>
      <div class="meta" style="margin-top:6px">
        Cuota <b style="color:#fff">{b.odd}</b> · Probabilidad {b.model_prob * 100:.0f}% ·
        EV <b style="color:#3fb950">+{b.ev * 100:.1f}%</b> · Confianza {b.confidence:.0f}/100 ·
        Stake <b style="color:#fff">{b.stake_amount:.2f}€</b> · Riesgo {b.risk}</div>
    </div>"""


def _top5_html(report: StrategyReport) -> str:
    if not report.top5:
        return '<table><tr><td class="empty">No hay value bets elegibles hoy.</td></tr></table>'
    rows = "".join(
        f"<tr><td>{i}</td><td>{b.match}</td><td>{_mkt(b.market)} · <b>{_sel(b.selection)}</b></td>"
        f"<td class='num'>{b.odd:.2f}</td><td class='num'>{b.model_prob * 100:.0f}%</td>"
        f"<td class='num ev'>+{b.ev * 100:.1f}%</td>"
        f"<td class='num'>{b.confidence:.0f} <span class='badge {TIER_CLASS.get(b.tier,'value')}'>{b.tier.split()[0]}</span></td>"
        f"<td class='num'>{b.stake_amount:.2f}€</td><td>{b.risk}</td></tr>"
        for i, b in enumerate(report.top5, 1))
    return (f"<table><thead><tr><th>#</th><th>Partido</th><th>Mercado</th><th>Cuota</th>"
            f"<th>Prob</th><th>EV</th><th>Confianza</th><th>Stake</th><th>Riesgo</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


def _parlays_html(report: StrategyReport) -> str:
    if report.parlays_blocked:
        return ('<p class="warn">⚠ Combinadas bloqueadas: el bankroll está en modo '
                'CONSERVACIÓN (solo apuestas simples de máxima confianza).</p>')
    if not report.has_combos:
        return '<p class="warn" style="font-size:16px">NO HAY COMBINADAS DE VALOR HOY.</p>'
    names = {"Conservadora": "C) COMBINADA CONSERVADORA (máx. 2)",
             "Moderada": "D) COMBINADA MODERADA (máx. 3)",
             "Agresiva": "E) COMBINADA AGRESIVA (máx. 5)"}
    blocks = []
    for p in report.parlays:
        legs = "".join(
            f"<div class='leg'>• {leg.match} · {_mkt(leg.market)} <b>{_sel(leg.selection)}</b> "
            f"@ {leg.odd:.2f}</div>" for leg in p.legs)
        blocks.append(
            f"<div class='parlay'><h3>{names.get(p.name, p.name)}</h3>{legs}"
            f"<div class='ptot'>Cuota total <b>{p.total_odd:.2f}</b> · "
            f"Probabilidad conjunta {p.joint_prob * 100:.1f}% · "
            f"EV <b>+{p.ev * 100:.1f}%</b> · Riesgo: {p.risk}</div></div>")
    return "".join(blocks)


def _nobets_html() -> str:
    df = query_df("SELECT match, reasons FROM no_bets ORDER BY id")
    if df.empty:
        return '<table><tr><td class="empty">Ningún partido descartado.</td></tr></table>'
    rows = "".join(f"<tr><td>{r['match']}</td><td class='warn'>{r['reasons']}</td></tr>"
                   for _, r in df.iterrows())
    return f"<table><thead><tr><th>Partido</th><th>Motivo del descarte</th></tr></thead><tbody>{rows}</tbody></table>"


def _leagues_html() -> str:
    df = query_df(
        "SELECT lg.name AS league, lr.tier, lr.yield, lr.roi, lr.accuracy, lr.bets, "
        "       lr.confidence_multiplier AS mult "
        "FROM league_ratings lr JOIN leagues lg ON lg.id = lr.league_id "
        "ORDER BY lr.yield DESC")
    if df.empty:
        return '<table><tr><td class="empty">Sin clasificación de ligas todavía.</td></tr></table>'
    rows = "".join(
        f"<tr><td>{r['league']}</td>"
        f"<td><span class='badge {LEAGUE_CLASS.get(r['tier'],'value')}'>{r['tier']}</span></td>"
        f"<td class='num'>{r['yield'] * 100:+.1f}%</td><td class='num'>{r['roi'] * 100:+.1f}%</td>"
        f"<td class='num'>{r['accuracy'] * 100:.0f}%</td><td class='num'>{int(r['bets'])}</td>"
        f"<td class='num'>x{r['mult']:.2f}</td></tr>" for _, r in df.iterrows())
    return (f"<table><thead><tr><th>Liga</th><th>Clasificación</th><th>Yield</th><th>ROI</th>"
            f"<th>Accuracy</th><th>Bets</th><th>Ajuste conf.</th></tr></thead><tbody>{rows}</tbody></table>")
