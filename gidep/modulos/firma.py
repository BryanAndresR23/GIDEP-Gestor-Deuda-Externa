"""Firma EC: controla los mensajes que necesitan una o dos firmas electrónicas.

Tres flujos independientes: Deuda Externa, Automáticos y Bancos. Un mensaje con dos firmas
se traslada a la carpeta del día (año/mes/día). Solo después de verificar por tamaño y
contenido que llegó bien, se elimina de origen su versión exacta con una firma. Si el destino
ya tiene un archivo distinto con el mismo nombre, es un conflicto y no se toca nada.
"""
from __future__ import annotations

from collections import OrderedDict

from ..demo import cargar, chip, fecha, fmt_fecha

TONOS = {"Por firmar": "warn", "Listo para copiar": "info", "Ya archivado": "ok", "Conflicto": "bad"}


def estado(doc: dict) -> str:
    if doc["firmas"] < 2:
        return "Por firmar"
    return {"none": "Listo para copiar", "same": "Ya archivado"}.get(doc["destino"], "Conflicto")


def destino(doc: dict) -> str:
    f = fecha(doc["fecha"])
    return f"{doc['flujo']}/{f.year}/{f.month:02d}/{f.day:02d}/{doc['archivo']}"


def resultados() -> list[dict]:
    return [{**d, "estado": estado(d), "ruta": destino(d)} for d in cargar("firmas")]


def vista() -> dict:
    res = resultados()
    flujos = OrderedDict()
    for r in res:
        flujos.setdefault(r["flujo"], []).append(r)
    kpis = [{"valor": sum(r["estado"] == "Por firmar" for r in items), "etiqueta": f"{flujo}: pendientes de firma",
             "tono": "warn"} for flujo, items in flujos.items()]
    kpis += [{"valor": sum(r["estado"] == "Listo para copiar" for r in res), "etiqueta": "Doble firma, listos para copiar", "tono": "info"},
             {"valor": sum(r["estado"] == "Conflicto" for r in res), "etiqueta": "Conflictos", "tono": "bad"}]
    return {
        "titulo": "Firma EC",
        "subtitulo": "Control independiente de los mensajes de Deuda Externa, Automáticos y Bancos: avisa cuando un "
                     "documento requiere firma y traslada los que ya tienen las dos firmas.",
        "kpis": kpis,
        "secciones": [{
            "titulo": flujo,
            "columnas": ["Archivo", "Firmas", "Fecha", "Carpeta del día", "Estado"],
            "filas": [[r["archivo"], f"{r['firmas']} de 2", fmt_fecha(r["fecha"]), r["ruta"],
                       chip(r["estado"], TONOS[r["estado"]])] for r in items],
        } for flujo, items in flujos.items()],
        "reglas": [
            "Con una firma, el mensaje queda pendiente y se avisa al segundo firmante.",
            "Con dos firmas, se copia a la carpeta del día (año/mes/día).",
            "Solo tras verificar tamaño y contenido en destino se elimina de origen la versión con una firma.",
            "Si el destino tiene un archivo distinto con el mismo nombre, es un conflicto: no se toca nada.",
        ],
    }
