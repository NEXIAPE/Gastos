"""
MODULE 8 - REPORT GENERATOR
===========================

Genera `reporte_diario.html` con el TOP 10 de apuestas del día. Cada fila
muestra: PARTIDO, MERCADO, CUOTA, PROBABILIDAD, EV y STAKE.

No depende de librerías de plantillas externas: construye HTML autocontenido
con estilos embebidos para que el reporte sea portable.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config import REPORTS_DIR
from models.roi import roi_metrics
from models.value_bet import ValueBet

MARKET_LABELS = {
    "1X2": "1X2",
    "BTTS": "Ambos marcan",
    "OU_2.5": "Over/Under 2.5",
}
SELECTION_LABELS = {
    "HOME": "Local", "DRAW": "Empate", "AWAY": "Visitante",
    "OVER": "Over", "UNDER": "Under", "YES": "Sí", "NO": "No",
}


def _label_market(m: str) -> str:
    return MARKET_LABELS.get(m, m.replace("OU_", "Over/Under "))


def _label_selection(s: str) -> str:
    return SELECTION_LABELS.get(s, s)


def _tier_class(tier: str) -> str:
    return {"Elite Pick": "elite", "Strong Pick": "strong",
            "Lean": "lean"}.get(tier, "nobet")


def generate_report(bets: list[ValueBet], top_n: int = 10,
                    output_path: Path | str | None = None) -> Path:
    """Crea el HTML del reporte diario y devuelve su ruta."""
    output_path = Path(output_path) if output_path else REPORTS_DIR / "reporte_diario.html"
    top = bets[:top_n]
    metrics = roi_metrics()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    rows_html = "".join(
        f"""
        <tr>
            <td class="rank">{i}</td>
            <td class="match">{b.match}</td>
            <td>{_label_market(b.market)} · <strong>{_label_selection(b.selection)}</strong></td>
            <td class="num">{b.odd:.2f}</td>
            <td class="num">{b.model_prob * 100:.1f}%</td>
            <td class="num ev">+{b.ev * 100:.1f}%</td>
            <td class="num conf">{b.confidence:.0f}</td>
            <td><span class="tier {_tier_class(b.tier)}">{b.tier}</span></td>
            <td class="num">{b.stake_pct * 100:.2f}% · {b.stake_amount:.2f}€</td>
        </tr>"""
        for i, b in enumerate(top, start=1)
    ) or '<tr><td colspan="9" class="empty">No se detectaron picks con confianza &gt; 80 hoy.</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BETLAB AI · Reporte Diario</title>
<style>
  :root {{ --bg:#0d1117; --card:#161b22; --line:#30363d; --txt:#e6edf3;
           --muted:#8b949e; --accent:#2ea043; --accent2:#58a6ff; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--txt);
          font-family:'Segoe UI',Roboto,Arial,sans-serif; padding:32px; }}
  .wrap {{ max-width:1000px; margin:0 auto; }}
  header {{ display:flex; align-items:baseline; justify-content:space-between;
            border-bottom:2px solid var(--accent); padding-bottom:12px; }}
  h1 {{ margin:0; font-size:28px; letter-spacing:1px; }}
  h1 span {{ color:var(--accent); }}
  .meta {{ color:var(--muted); font-size:13px; }}
  .cards {{ display:flex; gap:16px; margin:24px 0; flex-wrap:wrap; }}
  .kpi {{ background:var(--card); border:1px solid var(--line); border-radius:10px;
          padding:16px 20px; flex:1; min-width:140px; }}
  .kpi .v {{ font-size:22px; font-weight:700; }}
  .kpi .l {{ color:var(--muted); font-size:12px; text-transform:uppercase; }}
  table {{ width:100%; border-collapse:collapse; background:var(--card);
           border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
  th, td {{ padding:12px 14px; text-align:left; border-bottom:1px solid var(--line); }}
  th {{ background:#1c2330; color:var(--muted); font-size:12px; text-transform:uppercase; }}
  td.num {{ text-align:right; font-variant-numeric:tabular-nums; }}
  td.rank {{ color:var(--accent2); font-weight:700; width:40px; }}
  td.match {{ font-weight:600; }}
  td.ev {{ color:var(--accent); font-weight:700; }}
  td.conf {{ font-weight:700; }}
  .tier {{ padding:3px 10px; border-radius:12px; font-size:12px; font-weight:700;
           white-space:nowrap; }}
  .tier.elite  {{ background:#bb8009; color:#fff; }}
  .tier.strong {{ background:#1f6feb; color:#fff; }}
  .tier.lean   {{ background:#3a3f48; color:#cbd2d9; }}
  .tier.nobet  {{ background:#444; color:#aaa; }}
  td.empty {{ text-align:center; color:var(--muted); padding:32px; }}
  tr:last-child td {{ border-bottom:none; }}
  footer {{ color:var(--muted); font-size:12px; margin-top:20px; text-align:center; }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>BET<span>LAB</span> AI</h1>
      <div class="meta">Reporte diario · {generated}</div>
    </header>

    <div class="cards">
      <div class="kpi"><div class="v">{len(top)}</div><div class="l">Top picks</div></div>
      <div class="kpi"><div class="v">{metrics['roi'] * 100:.1f}%</div><div class="l">ROI histórico</div></div>
      <div class="kpi"><div class="v">{metrics['profit']:.2f}€</div><div class="l">Profit acumulado</div></div>
      <div class="kpi"><div class="v">{metrics['win_rate'] * 100:.1f}%</div><div class="l">Win rate</div></div>
    </div>

    <h2>TOP {top_n} APUESTAS DEL DÍA</h2>
    <table>
      <thead>
        <tr>
          <th>#</th><th>Partido</th><th>Mercado</th><th>Cuota</th>
          <th>Probabilidad</th><th>EV</th><th>Confianza</th><th>Tier</th><th>Stake</th>
        </tr>
      </thead>
      <tbody>{rows_html}
      </tbody>
    </table>

    <footer>
      Generado por BETLAB AI · Poisson + Expected Value + Score de Confianza (10 factores) + Kelly fraccionado.<br>
      Solo se muestran picks con Score de Confianza &gt; 80 (Strong / Elite).<br>
      Las apuestas conllevan riesgo. Este reporte es una herramienta de análisis estadístico, no una garantía.
    </footer>
  </div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
