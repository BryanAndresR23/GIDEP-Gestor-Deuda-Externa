"""Desembolsos: vigila los Swift entrantes y avisa cuando llega un desembolso.

Lee el mensaje, reconoce al acreedor por el ordenante, identifica el préstamo y
propone la carpeta Acreedor/Desembolsos/Mes/Préstamo (la crea si no existe).
Si el acreedor no es de deuda externa, el mensaje se descarta; si se reconoce el
acreedor pero no el préstamo, queda para revisión.
"""
from __future__ import annotations

import re
from datetime import timedelta

from ..demo import HOY, MESES, cargar, chip, fecha, fmt_fecha, fmt_monto, prestamos

ORDENANTES = [
    ("INTER-AMERICAN DEVELOPMENT BANK", "BID"), ("IDB", "BID"),
    ("CORPORACION ANDINA", "CAF"), ("CAF", "CAF"),
    ("INTERNATIONAL BANK FOR RECONSTRUCTION", "BIRF"), ("WORLD BANK", "BIRF"), ("IBRD", "BIRF"),
    ("INTERNATIONAL FUND FOR AGRICULTURAL", "FIDA"), ("IFAD", "FIDA"),
    ("NORDIC COOPERATION", "GOBIERNOS"), ("EXIMBANK ORIENTE", "GOBIERNOS"),
    ("EUROPEAN CREDIT BANK", "BANCOS"), ("INTERNATIONAL MONETARY FUND", "FMI"), ("BOND", "BONOS"),
]
TONOS = {"Por archivar": "warn", "Revisar": "warn", "Archivado": "ok", "Descartado": "muted"}


def acreedor(mensaje: dict) -> str | None:
    texto = f"{mensaje['ordenante']} {mensaje['referencia']}".upper()
    return next((a for clave, a in ORDENANTES if clave in texto), None)


def clasificar(mensaje: dict, catalogo: dict) -> dict:
    acr = acreedor(mensaje)
    if not acr:
        return {"estado": "Descartado", "detalle": "No es un desembolso de un acreedor de deuda externa.", "ruta": "—"}
    m = re.search(r"\bPR-\d{4}\b", mensaje["referencia"].upper())
    ref = m.group(0) if m else None
    if not ref or ref not in catalogo or catalogo[ref]["acreedor"] != acr:
        return {"estado": "Revisar", "detalle": f"Acreedor {acr} reconocido, pero el mensaje no identifica el préstamo.",
                "ruta": f"{acr}/Desembolsos/…"}
    mes = MESES[fecha(mensaje["fecha"]).month - 1]
    return {"estado": "Archivado" if mensaje["archivado"] else "Por archivar",
            "detalle": f"Desembolso de {acr} para el préstamo {ref}.",
            "ruta": f"{acr}/Desembolsos/{mes}/{ref}/Swift {mensaje['tipo']}.pdf"}


def resultados() -> list[dict]:
    cat = prestamos()
    return [{**m, **clasificar(m, cat)} for m in sorted(cargar("desembolsos"), key=lambda m: m["fecha"], reverse=True)]


def vista() -> dict:
    res = resultados()
    hoy = [r for r in res if fecha(r["fecha"]) == HOY and r["estado"] != "Descartado"]
    return {
        "titulo": "Desembolsos",
        "subtitulo": "Vigila los Swift que llegan a la carpeta de mensajes entrantes y avisa cuando entra un desembolso "
                     "de un acreedor de deuda externa. Guarda solo el Swift en la carpeta del préstamo.",
        "kpis": [
            {"valor": len(hoy), "etiqueta": "Desembolsos de hoy", "tono": "info"},
            {"valor": sum(r["estado"] == "Por archivar" for r in res), "etiqueta": "Por archivar", "tono": "warn"},
            {"valor": sum(r["estado"] == "Revisar" for r in res), "etiqueta": "Posibles desembolsos por revisar", "tono": "warn"},
            {"valor": sum(r["estado"] == "Archivado" and fecha(r["fecha"]) >= HOY - timedelta(days=10) for r in res),
             "etiqueta": "Archivados (últimos 10 días)", "tono": "ok"},
        ],
        "secciones": [{
            "titulo": "Mensajes recibidos",
            "columnas": ["Fecha", "Tipo", "Ordenante", "Referencia", "Monto", "Carpeta de destino", "Estado"],
            "filas": [[fmt_fecha(r["fecha"]), r["tipo"], r["ordenante"].title(), r["referencia"],
                       fmt_monto(r["monto"], r["moneda"]), r["ruta"], chip(r["estado"], TONOS[r["estado"]])]
                      for r in res],
        }],
        "reglas": [
            "El acreedor se reconoce por el ordenante del mensaje (BID, CAF, Banco Mundial, FIDA, gobiernos, bancos, FMI, bonos).",
            "Solo se archiva cuando el préstamo citado existe en el catálogo y pertenece a ese acreedor.",
            "Los pagos comerciales que llegan a la misma carpeta se descartan sin generar alertas.",
        ],
    }
