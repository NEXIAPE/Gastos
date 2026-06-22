"""
ALMACENAMIENTO PERSISTENTE - SUPABASE (opcional)
================================================

Guarda las apuestas y depósitos de cada usuario en una base Postgres de
Supabase, vía su API REST (PostgREST). Así los datos sobreviven a reinicios
de la app (Streamlit Cloud borra el SQLite local al dormir).

Se activa cuando hay SUPABASE_URL y SUPABASE_KEY configurados; si no, el
sistema usa SQLite (uso local) de forma transparente.

Tablas esperadas (crear en Supabase):
    bets(id bigint identity pk, owner text, note text, odd float8,
         stake float8, status text default 'PENDING', profit float8 default 0,
         created_at timestamptz default now(), settled_at timestamptz)
    deposits(owner text primary key, amount float8)
"""

from __future__ import annotations

from typing import Any

import requests

from config import settings

TIMEOUT = 20


def enabled() -> bool:
    return bool(settings.supabase_url and settings.supabase_key)


def _base() -> str:
    return settings.supabase_url.rstrip("/") + "/rest/v1"


def _headers(extra: dict | None = None) -> dict:
    h = {
        "apikey": settings.supabase_key,
        "Authorization": f"Bearer {settings.supabase_key}",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def _profit(status: str, odd: float, stake: float) -> float:
    if status == "WON":
        return round(stake * (odd - 1.0), 2)
    if status == "LOST":
        return round(-stake, 2)
    return 0.0


# --- Apuestas --------------------------------------------------------------
def add_bet(owner: str, note: str, odd: float, stake: float) -> int | None:
    payload = {"owner": owner, "note": note, "odd": float(odd),
               "stake": float(stake), "status": "PENDING", "profit": 0}
    r = requests.post(f"{_base()}/bets", json=payload,
                      headers=_headers({"Prefer": "return=representation"}), timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return data[0]["id"] if data else None


def list_bets(owner: str) -> list[dict[str, Any]]:
    r = requests.get(f"{_base()}/bets",
                     params={"owner": f"eq.{owner}", "order": "id.desc"},
                     headers=_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for b in r.json():
        out.append({
            "id": b["id"], "note": b.get("note"), "odd": b.get("odd"),
            "stake_amount": b.get("stake"), "status": b.get("status"),
            "profit": b.get("profit") or 0.0,
            "placed_at": b.get("created_at"), "settled_at": b.get("settled_at"),
        })
    return out


def _get(bet_id: int) -> dict | None:
    r = requests.get(f"{_base()}/bets", params={"id": f"eq.{bet_id}"},
                     headers=_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    return d[0] if d else None


def update_bet(bet_id: int, odd: float, stake: float, note: str | None) -> None:
    b = _get(bet_id)
    if not b:
        return
    odd, stake = float(odd), float(stake)
    payload = {"odd": odd, "stake": stake,
               "profit": _profit(b.get("status", "PENDING"), odd, stake)}
    if note is not None:
        payload["note"] = note
    requests.patch(f"{_base()}/bets", params={"id": f"eq.{bet_id}"}, json=payload,
                   headers=_headers(), timeout=TIMEOUT).raise_for_status()


def set_status(bet_id: int, status: str) -> None:
    b = _get(bet_id)
    if not b:
        return
    profit = _profit(status, float(b["odd"]), float(b["stake"]))
    payload = {"status": status, "profit": profit}
    requests.patch(f"{_base()}/bets", params={"id": f"eq.{bet_id}"}, json=payload,
                   headers=_headers(), timeout=TIMEOUT).raise_for_status()


def delete_bet(bet_id: int) -> None:
    requests.delete(f"{_base()}/bets", params={"id": f"eq.{bet_id}"},
                    headers=_headers(), timeout=TIMEOUT).raise_for_status()


# --- Depósito --------------------------------------------------------------
def get_deposit(owner: str) -> float:
    r = requests.get(f"{_base()}/deposits",
                     params={"owner": f"eq.{owner}", "select": "amount"},
                     headers=_headers(), timeout=TIMEOUT)
    r.raise_for_status()
    d = r.json()
    try:
        return float(d[0]["amount"]) if d else 0.0
    except (ValueError, TypeError, KeyError):
        return 0.0


def set_deposit(owner: str, amount: float) -> None:
    payload = {"owner": owner, "amount": float(amount)}
    requests.post(f"{_base()}/deposits", json=payload,
                  headers=_headers({"Prefer": "resolution=merge-duplicates"}),
                  timeout=TIMEOUT).raise_for_status()
