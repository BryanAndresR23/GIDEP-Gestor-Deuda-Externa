"""Condonados CAF: prepara los intereses condonados de CAF del mes.

Suma los intereses condonados de los estados de cuenta de cada préstamo, los compara con
el valor del reporte de conciliación y, antes de aplicar cualquier cambio, crea un respaldo.
"""
from __future__ import annotations

from ..demo import cargar, chip, fmt_monto


def vista() -> dict:
    datos = cargar("condonados")
    total = round(sum(e["interes_condonado_usd"] for e in datos["estados_cuenta"]), 2)
    reporte = datos["valor_reporte_banco"]
    cuadra = abs(total - reporte) <= 0.50
    return {
        "titulo": "Condonados CAF",
        "subtitulo": f"Carga mensual de intereses condonados de CAF · periodo {datos['periodo']}. "
                     "Se revisa y respalda antes de aplicar cambios al reporte.",
        "kpis": [
            {"valor": len(datos["estados_cuenta"]), "etiqueta": "Estados de cuenta leídos", "tono": "info"},
            {"valor": fmt_monto(total, "USD"), "etiqueta": "Total condonado (estados de cuenta)", "tono": "info"},
            {"valor": fmt_monto(reporte, "USD"), "etiqueta": "Valor en el reporte del Banco Central", "tono": "info"},
            {"valor": "Coincide" if cuadra else "Diferencia", "etiqueta": "Resultado", "tono": "ok" if cuadra else "bad"},
        ],
        "secciones": [{
            "titulo": "Estados de cuenta de CAF",
            "columnas": ["Préstamo", "Archivo", "Interés condonado"],
            "filas": [[e["prestamo"], e["archivo"], fmt_monto(e["interes_condonado_usd"], "USD")]
                      for e in datos["estados_cuenta"]] + [["Total", "", fmt_monto(total, "USD")]],
        }, {
            "titulo": "Aplicación al reporte",
            "columnas": ["Paso", "Estado"],
            "filas": [["1. Respaldo del reporte antes de modificarlo", chip("Listo", "ok")],
                      ["2. Importar las dos hojas del reporte descargado", chip("Listo", "ok")],
                      ["3. Comparar total de estados de cuenta vs. reporte",
                       chip("Coincide" if cuadra else "Diferencia", "ok" if cuadra else "bad")],
                      ["4. Aplicar al reporte", chip("Listo para aplicar" if cuadra else "Bloqueado", "info" if cuadra else "bad")]],
        }],
        "reglas": [
            "Antes de cambiar el reporte se crea siempre una copia de respaldo.",
            "Solo se aplica si el total de los estados de cuenta coincide con el reporte (tolerancia USD 0,50).",
        ],
    }
