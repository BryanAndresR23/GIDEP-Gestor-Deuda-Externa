"""Conciliación de Deuda Externa: flujo en pestañas sobre el motor de conciliación.

Pestañas: Recepción de reportes · Conciliación de carteras · Gestión de observaciones ·
Emisión del oficio de respuesta.

Regla de control de sesión: los resultados históricos no se cargan solos. Carteras,
observaciones y oficio permanecen vacíos hasta que el usuario procesa dos reportes nuevos
en la sesión actual, para que un periodo anterior no se tome por la conciliación vigente.
"""
from __future__ import annotations

import uuid

from conciliacion import engine

from ..demo import MESES, fmt_monto

_RESULTADOS: dict[str, dict] = {}          # resultado por sesión (solo en memoria)


def guardar(sesion: dict, resultado: dict):
    clave = sesion.get("conciliacion_id") or uuid.uuid4().hex
    sesion["conciliacion_id"] = clave
    _RESULTADOS[clave] = resultado


def actual(sesion: dict) -> dict | None:
    return _RESULTADOS.get(sesion.get("conciliacion_id", ""))


def texto_periodo(periodo: str) -> str:
    anio, mes = periodo.split("-")
    return f"{MESES[int(mes) - 1]} {anio}"


def oficio_respuesta(res: dict, usuario: str) -> str:
    s = res["resumen"]
    lineas = [
        "OFICIO DE RESPUESTA — CONCILIACIÓN DE DEUDA EXTERNA PÚBLICA",
        f"Periodo: {texto_periodo(res['periodo'])}",
        "",
        "Señores Ministerio de Finanzas:",
        "",
        f"Se concilió el servicio de deuda externa del periodo {texto_periodo(res['periodo'])}. "
        f"De {s['conciliados'] + s['diferencias']} rubros revisados, {s['conciliados']} concilian dentro de la tolerancia "
        f"de USD {engine.TOLERANCIA:.2f} y {s['diferencias']} presentan diferencia:",
        "",
    ]
    for d in res["diagnostico"]:
        rubros = "; ".join(f"{k} {fmt_monto(v, 'USD')}" for k, v in d["rubros"].items())
        lineas.append(f"• {d['acreedor']} — {rubros}. {d['tipo']}: {d['por_que']} {d['accion']}")
    if not res["diagnostico"]:
        lineas.append("• No existen diferencias que reportar.")
    lineas += ["", "Atentamente,", "", usuario, "Gestión de Deuda Externa (demo)"]
    return "\n".join(lineas)
