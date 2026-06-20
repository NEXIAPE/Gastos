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
    print(f"✔ {len(bets)} value bets detectadas (EV > {settings.min_ev:.0%}).")
    for b in bets[:10]:
        print(f"  · {b.match:<32} {b.market:<7} {b.selection:<5} "
              f"cuota={b.odd:<5} prob={b.model_prob:.0%} EV=+{b.ev:.1%} "
              f"stake={b.stake_amount:.2f}€")


def cmd_report(_args) -> None:
    from models.value_bet import detect_value_bets
    from reports.report_generator import generate_report

    bets = detect_value_bets()
    path = generate_report(bets)
    print(f"✔ Reporte generado: {path}")


def cmd_settle(_args) -> None:
    from models.roi import roi_metrics, settle_by_results

    n = settle_by_results()
    m = roi_metrics()
    print(f"✔ {n} apuestas liquidadas. ROI={m['roi']:.1%} profit={m['profit']:.2f}€")


def cmd_pipeline(args) -> None:
    from models.roi import log_value_bets
    from models.value_bet import detect_value_bets
    from reports.report_generator import generate_report
    from services.data_ingestion import ingest

    print("→ 1/4 Ingesta de datos y cuotas...")
    summary = ingest(target_date=args.date)
    print(f"   {summary}")

    print("→ 2/4 Detección de value bets (ratings + Poisson + EV + Kelly)...")
    bets = detect_value_bets()
    print(f"   {len(bets)} value bets con EV > {settings.min_ev:.0%}.")

    print("→ 3/4 Registro de picks en el historial...")
    logged = log_value_bets()
    print(f"   {logged} apuestas registradas como PENDING.")

    print("→ 4/4 Generación del reporte diario...")
    path = generate_report(bets)
    print(f"   {path}")
    print("✔ Pipeline completado.")


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
