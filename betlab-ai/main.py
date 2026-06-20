"""
BETLAB AI - Orquestador principal (CLI)
=======================================

Ejecuta el pipeline completo de extremo a extremo:

    python main.py pipeline          # ingesta -> ratings -> value bets -> reporte
    python main.py ingest [FECHA]    # solo ingesta de datos y cuotas
    python main.py value             # detecta value bets sobre datos existentes
    python main.py report            # regenera el reporte_diario.html
    python main.py settle            # liquida apuestas con resultado conocido
    python main.py initdb            # crea/recrea el esquema de la base de datos
    python main.py demo              # siembra datos demo

Se ejecuta desde el directorio betlab-ai/ (imports absolutos por paquete).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Garantiza que el directorio del proyecto esté en sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import settings  # noqa: E402
from database import init_db  # noqa: E402


def cmd_initdb(_args) -> None:
    init_db()
    print(f"✔ Base de datos inicializada en {settings_db_path()}")


def cmd_demo(_args) -> None:
    from services.demo_data import seed_database

    seed_database()
    print("✔ Datos demo generados.")


def cmd_ingest(args) -> None:
    from services.data_ingestion import ingest

    summary = ingest(target_date=args.date)
    if summary.get("demo"):
        print("⚠ Sin claves de API: se generaron datos demo.")
    else:
        print(f"✔ Ingesta completada: {summary}")


def cmd_value(_args) -> None:
    from models.value_bet import detect_value_bets

    bets = detect_value_bets()
    print(f"✔ {len(bets)} picks (EV > {settings.min_ev:.0%} y confianza > "
          f"{settings.min_confidence:.0f}).")
    for b in bets[:10]:
        print(f"  · {b.match:<30} {b.market:<7} {b.selection:<5} "
              f"cuota={b.odd:<5} EV=+{b.ev:.1%} conf={b.confidence:>4.0f} "
              f"[{b.tier}] stake={b.stake_amount:.2f}€")


def cmd_report(_args) -> None:
    from reports.report_generator import generate_report

    path = generate_report()
    print(f"✔ Reporte generado: {path}")


def cmd_settle(_args) -> None:
    from models.performance import metrics
    from models.roi import settle_by_results

    n = settle_by_results()
    m = metrics()
    print(f"✔ {n} apuestas liquidadas. ROI={m['roi']:.1%} yield={m['yield']:.1%} "
          f"profit={m['profit']:.2f}€")


def cmd_leagues(_args) -> None:
    from models.league_analyzer import analyze

    df = analyze(initial_bankroll=settings.bankroll)
    if df.empty:
        print("Sin historial de apuestas para analizar ligas.")
        return
    print("✔ Clasificación de ligas:")
    for _, r in df.iterrows():
        print(f"  · {r['league']:<24} {r['tier']:<16} "
              f"yield={r['yield']:+.1%} roi={r['roi']:+.1%} "
              f"acc={r['accuracy']:.0%} bets={int(r['bets'])} "
              f"(x{r['confidence_multiplier']:.2f})")


def cmd_performance(_args) -> None:
    from models.performance import metrics, profit_by_league, profit_by_market

    m = metrics(settings.bankroll)
    print(f"✔ Performance: bets={m['bets']} profit={m['profit']:.2f}€ "
          f"ROI={m['roi']:.1%} yield={m['yield']:.1%} hit={m['hit_rate']:.0%} "
          f"maxDD={m['max_drawdown']:.1%}")
    print("  Profit por mercado:")
    for _, r in profit_by_market().iterrows():
        print(f"    {r['market']:<8} {r['profit']:+.2f}€ ({int(r['bets'])} bets)")
    print("  Profit por liga:")
    for _, r in profit_by_league().iterrows():
        print(f"    {r['league']:<24} {r['profit']:+.2f}€ ({int(r['bets'])} bets)")


def cmd_bankroll(_args) -> None:
    from models.bankroll import get_state

    s = get_state()
    print(f"✔ Bankroll: {s.current:.2f}€ / inicial {s.initial:.2f}€ "
          f"(peak {s.peak:.2f}€, drawdown {s.drawdown:.1%})")
    print(f"  Modo: {s.mode} · stake×{s.stake_multiplier} · "
          f"confianza mínima {s.min_confidence:.0f} · "
          f"combinadas {'sí' if s.allow_parlays else 'NO'}")


def cmd_backtest(_args) -> None:
    from models.backtest import run_backtest

    results, best = run_backtest()
    if not results:
        print("Histórico insuficiente para backtesting.")
        return
    print("✔ Backtesting (out-of-sample):")
    print(f"  {'Modelo':<18}{'Acc':>7}{'ROI':>9}{'Yield':>9}{'MaxDD':>8}{'Profit':>11}{'Bets':>7}")
    for r in results:
        print(f"  {r.model:<18}{r.accuracy:>6.0%}{r.roi:>8.1%}{r.yield_:>8.1%}"
              f"{r.drawdown:>7.1%}{r.profit:>10.2f}€{r.bets:>7}")
    print(f"  → Modelo más rentable: {best}")


def cmd_strategies(_args) -> None:
    _print_strategies()


def _print_strategies() -> None:
    from models.strategies import build_strategies

    rep = build_strategies()
    sl = {"HOME": "Local", "DRAW": "Empate", "AWAY": "Visitante", "OVER": "Over",
          "UNDER": "Under", "YES": "BTTS Sí", "NO": "BTTS No"}

    print(f"\n=== ESTRATEGIA DIARIA (modo bankroll: {rep.bankroll_mode}) ===")
    if rep.premium:
        b = rep.premium
        print(f"\nA) PICK PREMIUM DEL DÍA  ·  {b.match}")
        print(f"   {b.market} {sl.get(b.selection, b.selection)} | cuota {b.odd} | "
              f"prob {b.model_prob:.0%} | EV +{b.ev:.1%} | conf {b.confidence:.0f} "
              f"[{b.tier}] | stake {b.stake_amount:.2f}€")
    else:
        print("\nA) PICK PREMIUM DEL DÍA: no hay pick elegible hoy.")

    print("\nB) TOP 5 VALUE BETS")
    if not rep.top5:
        print("   (vacío)")
    for i, b in enumerate(rep.top5, 1):
        print(f"   {i}. {b.match:<26} {b.market:<6} {sl.get(b.selection, b.selection):<10} "
              f"cuota {b.odd:<5} EV +{b.ev:.1%} conf {b.confidence:.0f} "
              f"stake {b.stake_amount:.2f}€")

    labels = {"Conservadora": "C) COMBINADA CONSERVADORA (máx 2)",
              "Moderada": "D) COMBINADA MODERADA (máx 3)",
              "Agresiva": "E) COMBINADA AGRESIVA (máx 5)"}
    if rep.parlays_blocked:
        print("\nC/D/E) Combinadas BLOQUEADAS por el modo conservación del bankroll.")
    elif not rep.has_combos:
        print("\nNO HAY COMBINADAS DE VALOR HOY.")
    else:
        for p in rep.parlays:
            print(f"\n{labels.get(p.name, p.name)}")
            for leg in p.legs:
                print(f"   - {leg.match:<26} {leg.market:<6} "
                      f"{sl.get(leg.selection, leg.selection):<10} @ {leg.odd}")
            print(f"   Cuota total: {p.total_odd} | Prob. conjunta: {p.joint_prob:.1%} "
                  f"| EV: +{p.ev:.1%} | Riesgo: {p.risk}")


def cmd_pipeline(args) -> None:
    from models.bankroll import get_state
    from models.league_analyzer import analyze
    from models.performance import metrics
    from models.roi import log_value_bets, settle_by_results
    from models.value_bet import detect_value_bets
    from reports.report_generator import generate_report
    from services.data_ingestion import ingest

    print("→ 1/7 Ingesta de datos y cuotas...")
    summary = ingest(target_date=args.date)
    print(f"   {summary}")

    print("→ 2/7 Liquidando apuestas con resultado conocido...")
    print(f"   {settle_by_results()} liquidadas.")

    print("→ 3/7 Bankroll Manager (gestión de riesgo)...")
    state = get_state()
    print(f"   Modo {state.mode} · bankroll {state.current:.2f}€ · DD {state.drawdown:.1%}")

    print("→ 4/7 League Analyzer (clasificación y ajuste de confianza)...")
    league_df = analyze(initial_bankroll=settings.bankroll)
    print(f"   {len(league_df)} ligas clasificadas.")

    print("→ 5/7 Detección de picks (No Bet + Poisson + EV + Confianza + Kelly)...")
    bets = detect_value_bets()
    print(f"   {len(bets)} picks (confianza ≥ {state.min_confidence:.0f}).")

    print("→ 6/7 Registro de picks en el historial...")
    print(f"   {log_value_bets()} apuestas registradas como PENDING.")

    print("→ 7/7 Generación del reporte diario...")
    path = generate_report()
    print(f"   {path}")

    m = metrics(settings.bankroll)
    print(f"✔ Pipeline completado. ROI histórico {m['roi']:.1%} · yield {m['yield']:.1%}.")
    _print_strategies()


def settings_db_path() -> str:
    from config import DB_PATH

    return str(DB_PATH)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BETLAB AI - Detector de value bets.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("pipeline", help="Ejecuta todo el pipeline.")
    p.add_argument("--date", default=None, help="Fecha YYYY-MM-DD (def: hoy).")
    p.set_defaults(func=cmd_pipeline)

    p = sub.add_parser("ingest", help="Ingesta de datos y cuotas.")
    p.add_argument("date", nargs="?", default=None, help="Fecha YYYY-MM-DD.")
    p.set_defaults(func=cmd_ingest)

    sub.add_parser("value", help="Detecta value bets.").set_defaults(func=cmd_value)
    sub.add_parser("strategies", help="Pick premium, top 5 y combinadas.").set_defaults(func=cmd_strategies)
    sub.add_parser("leagues", help="Clasifica ligas (League Analyzer).").set_defaults(func=cmd_leagues)
    sub.add_parser("performance", help="Métricas del track record.").set_defaults(func=cmd_performance)
    sub.add_parser("bankroll", help="Estado y modo del bankroll.").set_defaults(func=cmd_bankroll)
    sub.add_parser("backtest", help="Backtesting de variantes de modelo.").set_defaults(func=cmd_backtest)
    sub.add_parser("report", help="Regenera el reporte HTML.").set_defaults(func=cmd_report)
    sub.add_parser("settle", help="Liquida apuestas con resultado.").set_defaults(func=cmd_settle)
    sub.add_parser("initdb", help="Inicializa la base de datos.").set_defaults(func=cmd_initdb)
    sub.add_parser("demo", help="Genera datos demo.").set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
