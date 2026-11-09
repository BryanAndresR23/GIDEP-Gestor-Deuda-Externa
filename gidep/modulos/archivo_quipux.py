"""Archivo Quipux: archiva los oficios de pago que llegan a la bandeja de descargas.

Reglas:
  * Al activarse por primera vez crea una línea base: lo que ya estaba es "histórico
    protegido" y no se toca.
  * Cada documento se identifica por su huella SHA-256 (los duplicados no se archivan dos veces).
  * Solo se procesa lo que es de deuda externa pública: un oficio debe mencionarla junto con una
    instrucción de pago, intereses, capital, amortización o transferencia. Lo demás se ignora.
  * Destino: primero por préstamo o identificador de deuda exacto; después por número de oficio.
  * Un estado de cuenta o formulario genérico se vincula al oficio del mismo lote solo si hay un
    único oficio con destino exacto y un único documento de cada tipo.
  * Nombres finales: «Oficio No. X.pdf», «Estado Cuenta.pdf», «Formulario Transferencia al Exterior.pdf».
  * Se copia, se verifica y nunca se sobrescribe; lo ambiguo queda en revisión.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from ..demo import MESES, cargar, chip, fecha, por_id_deuda, prestamos

INSTRUCCIONES = ("pago", "intereses", "capital", "amortización", "transferencia")
NOMBRES = {"Oficio": "Oficio No. {oficio}.pdf", "Estado de cuenta": "Estado Cuenta.pdf",
           "Formulario": "Formulario Transferencia al Exterior.pdf"}
TONOS = {"Archivado": "ok", "Por revisar": "warn", "Ignorado": "muted", "Histórico protegido": "muted",
         "Duplicado": "muted"}


def huella(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def tipo_documento(texto: str) -> str:
    t = texto.lower()
    if ("oficio" in t or "memorando" in t) and "deuda externa pública" in t and any(i in t for i in INSTRUCCIONES):
        return "Oficio"
    if "estado de cuenta" in t:
        return "Estado de cuenta"
    if "formulario" in t and "transferencia al exterior" in t:
        return "Formulario"
    return "Ignorado"


def extraer(texto: str) -> dict:
    t = texto.upper()
    pr = re.search(r"\bPR-\d{4}\b", t)
    dx = re.search(r"\bDX-\d{6}\b", t)
    of = re.search(r"\bMF-SFP-\d{4}-\d{4}-O\b", t)
    fv = re.search(r"FECHA VALOR (\d{4}-\d{2}-\d{2})", t)
    return {"prestamo": pr.group(0) if pr else None, "id_deuda": dx.group(0) if dx else None,
            "oficio": of.group(0) if of else None, "fecha_valor": fv.group(1) if fv else None}


def destino_oficio(datos: dict) -> tuple[dict | None, str]:
    cat, ids = prestamos(), por_id_deuda()
    if datos["prestamo"] in cat:
        return cat[datos["prestamo"]], f"préstamo {datos['prestamo']} exacto"
    if datos["id_deuda"] in ids:
        return ids[datos["id_deuda"]], f"identificador {datos['id_deuda']} exacto"
    agenda = {o["oficio"]: o for o in cargar("agenda")}
    if datos["oficio"] in agenda and agenda[datos["oficio"]]["prestamo"]:
        return cat[agenda[datos["oficio"]]["prestamo"]], f"oficio {datos['oficio']} exacto"
    return None, "sin préstamo ni oficio reconocible"


def carpeta(p: dict, fecha_valor: str | None) -> str:
    mes = MESES[fecha(fecha_valor).month - 1] if fecha_valor else "Marzo"
    return f"{p['acreedor']}/Pagos/2026/{mes}/{p['prestamo']}/"


def procesar(bandeja: list[dict] | None = None) -> list[dict]:
    bandeja = bandeja if bandeja is not None else cargar("bandeja_quipux")
    vistos, res = set(), []
    lotes = defaultdict(list)
    for doc in bandeja:
        datos = extraer(doc["texto"])
        tipo = tipo_documento(doc["texto"])
        item = {**doc, **datos, "tipo": tipo, "sha": huella(doc["texto"])[:12]}
        if doc["historico"]:
            item.update(estado="Histórico protegido", detalle="Estaba en la bandeja al crear la línea base.", ruta="—")
        elif item["sha"] in vistos:
            item.update(estado="Duplicado", detalle="Misma huella SHA-256 que un documento ya archivado.", ruta="—")
        elif tipo == "Ignorado":
            item.update(estado="Ignorado", detalle="No es un documento de pago de deuda externa pública.", ruta="—")
        elif tipo == "Oficio":
            p, metodo = destino_oficio(datos)
            if p:
                item.update(estado="Archivado", detalle=f"Destino por {metodo}.",
                            ruta=carpeta(p, datos["fecha_valor"]) + NOMBRES["Oficio"].format(oficio=datos["oficio"]),
                            _prestamo=p)
            else:
                item.update(estado="Por revisar", detalle=f"Oficio de deuda externa {metodo}.", ruta="—")
        else:
            item.update(estado="Pendiente", ruta="—")
        if item["estado"] in ("Archivado", "Pendiente"):
            vistos.add(item["sha"])
        lotes[doc["lote"]].append(item)
        res.append(item)
    for lote, items in lotes.items():                     # documentos genéricos del lote
        oficios = [i for i in items if i["tipo"] == "Oficio" and i["estado"] == "Archivado"]
        for i in items:
            if i["estado"] != "Pendiente":
                continue
            del_tipo = [x for x in items if x["tipo"] == i["tipo"]]
            if len(oficios) == 1 and len(del_tipo) == 1:
                p = oficios[0]["_prestamo"]
                i.update(estado="Archivado", detalle=f"Vinculado al único oficio del lote ({oficios[0]['oficio']}).",
                         ruta=carpeta(p, oficios[0]["fecha_valor"]) + NOMBRES[i["tipo"]])
            else:
                i.update(estado="Por revisar", detalle="No hay un único oficio en el lote al cual vincularlo.")
    for i in res:
        i.pop("_prestamo", None)
    return res


def vista() -> dict:
    res = procesar()
    return {
        "titulo": "Archivo Quipux",
        "subtitulo": "Vigila la bandeja de descargas y archiva oficio, estado de cuenta y formulario en la carpeta "
                     "del préstamo. Huella SHA-256, coincidencia exacta y copia verificada sin sobrescribir.",
        "kpis": [
            {"valor": sum(r["estado"] == "Archivado" for r in res), "etiqueta": "Archivados", "tono": "ok"},
            {"valor": sum(r["estado"] == "Por revisar" for r in res), "etiqueta": "Por revisar", "tono": "warn"},
            {"valor": sum(r["estado"] == "Ignorado" for r in res), "etiqueta": "Ignorados (no son de deuda)", "tono": "muted"},
            {"valor": sum(r["estado"] in ("Histórico protegido", "Duplicado") for r in res),
             "etiqueta": "Históricos o duplicados", "tono": "muted"},
        ],
        "secciones": [{
            "titulo": "Bandeja de descargas",
            "columnas": ["Archivo", "Lote", "Tipo", "Huella", "Decisión", "Destino", "Estado"],
            "filas": [[r["archivo"], r["lote"], r["tipo"], r["sha"], r["detalle"], r["ruta"],
                       chip(r["estado"], TONOS.get(r["estado"], "warn"))] for r in res],
        }],
        "reglas": [
            "Lo que ya estaba al crear la línea base queda como histórico protegido.",
            "Un oficio solo se procesa si menciona deuda externa pública junto con una instrucción de pago.",
            "Destino por préstamo o identificador exacto, luego por número de oficio; lo ambiguo queda en revisión.",
            "Se copia, se verifica el contenido, se conserva el original y nunca se sobrescribe.",
        ],
    }
