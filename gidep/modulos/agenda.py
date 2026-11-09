"""Agenda Diaria de Pagos: qué préstamos deben pagarse según los oficios recibidos.

Reglas:
  * La fecha de débito tiene prioridad sobre la fecha valor cuando el oficio trae ambas.
  * Estados: programado, para hoy, en proceso (ya registrado en el sistema de giros),
    vencido, procesado o por revisar.
  * Si el oficio no identifica el préstamo con evidencia suficiente, no se asigna por
    suposición: queda "por revisar".
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from ..demo import HOY, cargar, chip, fecha, fmt_fecha, fmt_monto, ultima_lectura

TONOS = {"Para hoy": "warn", "En proceso": "info", "Vencido": "bad", "Procesado": "ok",
         "Programado": "muted", "Por revisar": "warn"}


def fecha_operativa(oficio: dict):
    return fecha(oficio.get("fecha_debito")) or fecha(oficio.get("fecha_valor"))


def estado(oficio: dict, hoy=HOY) -> str:
    if not oficio.get("prestamo") or not oficio.get("evidencia_suficiente"):
        return "Por revisar"
    if oficio.get("procesado"):
        return "Procesado"
    f = fecha_operativa(oficio)
    if f < hoy:
        return "Vencido"
    if f == hoy:
        return "En proceso" if oficio.get("registrado_sgi") else "Para hoy"
    return "Programado"


def pagos(hoy=HOY) -> list[dict]:
    filas = [{**o, "estado": estado(o, hoy), "fecha_op": fecha_operativa(o)} for o in cargar("agenda")]
    return sorted(filas, key=lambda o: (o["fecha_op"], o["oficio"]))


def resumen(hoy=HOY) -> dict:
    filas = pagos(hoy)
    semana = hoy + timedelta(days=7)
    cuenta = defaultdict(int)
    for f in filas:
        cuenta[f["estado"]] += 1
    return {
        "hoy": cuenta["Para hoy"] + cuenta["En proceso"],
        "proximos_7": sum(1 for f in filas if f["estado"] == "Programado" and f["fecha_op"] <= semana),
        "vencidos": cuenta["Vencido"],
        "registrados": sum(1 for f in filas if f["registrado_sgi"]),
        "procesados": cuenta["Procesado"],
        "por_revisar": cuenta["Por revisar"],
    }


def vista() -> dict:
    filas = pagos()
    r = resumen()
    pendiente = defaultdict(float)
    for f in filas:
        if f["estado"] not in ("Procesado", "Por revisar"):
            pendiente[f["moneda"]] += f["monto"]
    return {
        "titulo": "Agenda Diaria de Pagos",
        "subtitulo": "Préstamos que deben pagarse según la fecha valor o fecha de débito indicada en los oficios. "
                     f"Revisión automática cada cinco minutos · última lectura {ultima_lectura()}.",
        "kpis": [
            {"valor": r["hoy"], "etiqueta": "Pagos para hoy", "tono": "warn"},
            {"valor": r["proximos_7"], "etiqueta": "Próximos 7 días", "tono": "info"},
            {"valor": r["vencidos"], "etiqueta": "Vencidos", "tono": "bad"},
            {"valor": r["registrados"], "etiqueta": "Registrados en el sistema de giros", "tono": "info"},
            {"valor": r["procesados"], "etiqueta": "Procesados", "tono": "ok"},
            {"valor": r["por_revisar"], "etiqueta": "Por revisar", "tono": "warn"},
        ],
        "secciones": [
            {"titulo": f"Pagos programados · hoy {fmt_fecha(HOY.isoformat())}",
             "columnas": ["Oficio", "Préstamo", "Acreedor", "Fecha operativa", "Vencimiento", "Monto", "Estado"],
             "filas": [[f["oficio"], f["prestamo"] or "—", f["acreedor"],
                        fmt_fecha(f["fecha_op"].isoformat()) + (" (débito)" if f.get("fecha_debito") else ""),
                        fmt_fecha(f["vencimiento"]), fmt_monto(f["monto"], f["moneda"]),
                        chip(f["estado"], TONOS[f["estado"]])] for f in filas]},
            {"titulo": "Total pendiente por moneda",
             "columnas": ["Moneda", "Monto pendiente"],
             "filas": [[m, fmt_monto(v, m)] for m, v in sorted(pendiente.items())]},
        ],
        "reglas": [
            "La fecha de débito tiene prioridad sobre la fecha valor cuando el oficio trae ambas.",
            "Un pago registrado en el sistema de giros pasa de «Para hoy» a «En proceso».",
            "Si el oficio no identifica el préstamo, queda «Por revisar»: nunca se asigna por suposición.",
        ],
    }
