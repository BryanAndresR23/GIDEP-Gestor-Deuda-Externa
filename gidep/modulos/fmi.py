"""FMI · Mensajes Swift: reconoce de qué proceso es cada mensaje del FMI y lo archiva.

El MT298 de intereses y comisiones se guarda solo en Pagos Intereses y Comisiones/<trimestre>
con el nombre «Swift MT298 ddMmmAAAA»; los demás muestran su carpeta y nombre sugeridos para
guardarlos con un clic. El original siempre se conserva en la carpeta de mensajes.
"""
from __future__ import annotations

from ..demo import HOY, MESES_CORTO, cargar, chip, fecha, fmt_fecha

PROCESOS = [
    ("CHARGES AND INTEREST", "Intereses y comisiones", "Pagos Intereses y Comisiones/{anio}-T{trim}"),
    ("REPURCHASE", "Recompras", "Recompras/{anio}"),
    ("PRINCIPAL", "Capital", "Capital/{anio}"),
    ("COMMITMENT FEE", "Comisión de compromiso", "Comisión de Compromiso/{anio}"),
    ("REMUNERATION", "Remuneraciones", "Remuneraciones/{anio}-T{trim}"),
    ("ALLOCATION CHARGES", "Cargos por asignaciones", "Cargos por Asignaciones/{anio}-T{trim}"),
    ("ASSESSMENT", "Cargo de evaluación", "Cargo de Evaluación/{anio}"),
    ("DISBURSEMENT", "Desembolsos", "Desembolsos/{anio}"),
    ("HOLIDAY", "Feriados", "Feriados/{anio}"),
]
TONOS = {"Archivado": "ok", "Por archivar": "warn", "Revisar": "bad"}


def clasificar(mensaje: dict) -> dict:
    f = fecha(mensaje["fecha"])
    texto = mensaje["texto"].upper()
    for clave, proceso, carpeta in PROCESOS:
        if clave in texto:
            nombre = f"Swift {mensaje['tipo']} {f.day:02d}{MESES_CORTO[f.month - 1]}{f.year}.pdf"
            ruta = carpeta.format(anio=f.year, trim=(f.month - 1) // 3 + 1) + "/" + nombre
            automatico = proceso == "Intereses y comisiones" and mensaje["tipo"] == "MT298"
            return {"proceso": proceso, "ruta": ruta, "estado": "Archivado" if automatico else "Por archivar"}
    return {"proceso": "Sin reconocer", "ruta": "—", "estado": "Revisar"}


def resultados() -> list[dict]:
    return [{**m, **clasificar(m)} for m in sorted(cargar("fmi"), key=lambda m: m["fecha"], reverse=True)]


def vista() -> dict:
    res = resultados()
    return {
        "titulo": "FMI · Mensajes Swift",
        "subtitulo": "Reconoce el proceso de cada mensaje del FMI (intereses y comisiones, capital, recompras, comisión "
                     "de compromiso, remuneraciones, cargos por asignaciones, evaluación, desembolsos y feriados).",
        "kpis": [
            {"valor": sum(fecha(r["fecha"]) == HOY for r in res), "etiqueta": "Mensajes de hoy", "tono": "info"},
            {"valor": sum(r["estado"] == "Por archivar" for r in res), "etiqueta": "Por archivar (carpeta sugerida)", "tono": "warn"},
            {"valor": sum(r["estado"] == "Revisar" for r in res), "etiqueta": "Sin carpeta reconocida", "tono": "bad"},
            {"valor": sum(r["estado"] == "Archivado" for r in res), "etiqueta": "Archivados automáticamente", "tono": "ok"},
        ],
        "secciones": [{
            "titulo": "Mensajes del FMI",
            "columnas": ["Fecha", "Tipo", "Texto del mensaje", "Proceso", "Carpeta y nombre", "Estado"],
            "filas": [[fmt_fecha(r["fecha"]), r["tipo"], r["texto"], r["proceso"], r["ruta"],
                       chip(r["estado"], TONOS[r["estado"]])] for r in res],
        }],
        "reglas": [
            "El MT298 de intereses y comisiones se archiva solo, por trimestre, como «Swift MT298 ddMmmAAAA».",
            "Los demás procesos muestran su carpeta y nombre para guardarlos con un clic.",
            "El original siempre se queda en la carpeta de mensajes del FMI.",
        ],
    }
