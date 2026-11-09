"""Retenciones CAF: retención mensual de los gobiernos locales (GAD) que provisionan su deuda CAF.

El monto sale de la tabla del convenio o del oficio que envía el GAD. El gestor muestra los
datos para registrarlos en el sistema de giros, genera el Excel y controla que el oficio
esté firmado y el comprobante archivado. Los GAD de esta demo son ficticios.
"""
from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from ..demo import cargar, chip, fmt_monto


def estado(g: dict) -> tuple[str, str]:
    if g["monto"] is None:
        return "Esperando oficio del GAD", "warn"
    if not g["oficio_firmado"]:
        return "Oficio sin firma", "bad"
    if not g["comprobante_archivado"]:
        return "Falta archivar comprobante", "warn"
    return "Completo", "ok"


def vista() -> dict:
    datos = cargar("retenciones")
    gads = datos["gad"]
    total = sum(g["monto"] or 0 for g in gads)
    return {
        "titulo": "Retenciones CAF",
        "subtitulo": f"Retención mensual de los GAD que provisionan su deuda CAF · periodo {datos['periodo']}.",
        "acciones": [{"etiqueta": "Generar Excel para el sistema de giros", "url": "/modulo/retenciones/excel"}],
        "kpis": [
            {"valor": len(gads), "etiqueta": "GAD con convenio", "tono": "info"},
            {"valor": fmt_monto(total, "USD"), "etiqueta": "Total a retener", "tono": "info"},
            {"valor": sum(estado(g)[0] == "Completo" for g in gads), "etiqueta": "Completos", "tono": "ok"},
            {"valor": sum(estado(g)[0] != "Completo" for g in gads), "etiqueta": "Pendientes", "tono": "warn"},
        ],
        "secciones": [{
            "titulo": "Datos para el sistema de giros",
            "columnas": ["GAD", "Préstamo", "Fuente del monto", "Cuenta del GAD", "Monto", "Estado"],
            "filas": [[g["gad"], g["prestamo"], g["fuente"], g["cuenta_gad"], fmt_monto(g["monto"], "USD"),
                       chip(*estado(g))] for g in gads],
        }],
        "reglas": [
            "El monto sale de la tabla del convenio o del oficio que envía cada GAD.",
            "Se reconoce la firma del oficio y se archivan oficio y comprobante en la carpeta del préstamo.",
        ],
    }


def excel() -> BytesIO:
    datos = cargar("retenciones")
    wb = Workbook()
    ws = wb.active
    ws.title = "Retenciones CAF"
    ws.append([f"Retenciones CAF - periodo {datos['periodo']} (datos ficticios)"])
    ws["A1"].font = Font(bold=True, size=12)
    ws.append([])
    ws.append(["GAD", "Préstamo", "Fuente", "Cuenta del GAD", "Monto USD", "Estado"])
    for c in ws[3]:
        c.font, c.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F3A5F")
    for g in datos["gad"]:
        ws.append([g["gad"], g["prestamo"], g["fuente"], g["cuenta_gad"], g["monto"], estado(g)[0]])
    for letra, ancho in zip("ABCDEF", (32, 12, 20, 16, 14, 28)):
        ws.column_dimensions[letra].width = ancho
    salida = BytesIO()
    wb.save(salida)
    salida.seek(0)
    return salida
