"""Acceso a los datos ficticios de la demo y utilidades compartidas por los módulos."""
from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "demo"
RUNTIME = ROOT / "instance"            # lo que la demo escribe (ignorado por Git)

HOY = date(2026, 3, 16)                # "hoy" fijo para que los estados sean reproducibles
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]
MESES_CORTO = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


@lru_cache(maxsize=None)
def cargar(nombre: str):
    return json.loads((DATA / f"{nombre}.json").read_text(encoding="utf-8"))


def texto(nombre: str) -> str:
    return (DATA / nombre).read_text(encoding="utf-8")


def prestamos() -> dict:
    return {p["prestamo"]: p for p in cargar("prestamos")}


def por_id_deuda() -> dict:
    return {p["id_deuda"]: p for p in cargar("prestamos")}


def fecha(iso: str | None) -> date | None:
    return date.fromisoformat(iso) if iso else None


def fmt_fecha(iso: str | None) -> str:
    f = fecha(iso)
    return f"{f.day:02d}‑{MESES_CORTO[f.month - 1]}‑{f.year}" if f else "—"   # guiones que no parten la línea


def fmt_monto(valor, moneda: str = "") -> str:
    if valor is None:
        return "—"
    decimales = 0 if moneda == "JPY" else 2
    texto_ = f"{valor:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{moneda} {texto_}".strip()


def chip(etiqueta: str, tono: str) -> dict:
    """Celda con estado de color: tono = ok | warn | bad | info | muted."""
    return {"chip": etiqueta, "tono": tono}


def ultima_lectura() -> str:
    return datetime.now().strftime("%H:%M")


def runtime(nombre: str) -> Path:
    RUNTIME.mkdir(exist_ok=True)
    return RUNTIME / nombre
