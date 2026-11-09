"""Centro de Control Diario: consolida pendientes y alertas de todos los monitores."""
from __future__ import annotations

from . import agenda, archivo_quipux, comprobantes, contratos, desembolsos, firma, fmi, validacion


def alertas() -> list[dict]:
    a = agenda.resumen()
    val = validacion.resultados()
    des = desembolsos.resultados()
    fm = fmi.resultados()
    aq = archivo_quipux.procesar()
    ct = contratos.resultados()
    fi = firma.resultados()
    co = comprobantes.resultados()
    filas = [
        ("agenda", "Agenda Diaria", f"{a['hoy']} pagos para hoy", a["hoy"], "warn"),
        ("agenda", "Agenda Diaria", f"{a['vencidos']} pagos vencidos", a["vencidos"], "bad"),
        ("validacion", "Validación de Pagos", f"{sum(v['estado'] == 'Con errores' for v in val)} pagos con errores",
         sum(v["estado"] == "Con errores" for v in val), "bad"),
        ("firma", "Firma EC", f"{sum(f['estado'] == 'Por firmar' for f in fi)} mensajes esperan firma",
         sum(f["estado"] == "Por firmar" for f in fi), "warn"),
        ("firma", "Firma EC", f"{sum(f['estado'] == 'Conflicto' for f in fi)} conflictos al trasladar",
         sum(f["estado"] == "Conflicto" for f in fi), "bad"),
        ("desembolsos", "Desembolsos", f"{sum(d['estado'] == 'Por archivar' for d in des)} desembolsos por archivar",
         sum(d["estado"] == "Por archivar" for d in des), "info"),
        ("fmi", "FMI · Mensajes Swift", f"{sum(m['estado'] != 'Archivado' for m in fm)} mensajes sin archivar",
         sum(m["estado"] != "Archivado" for m in fm), "info"),
        ("comprobantes", "Comprobantes y ACK", f"{sum(c['estado'] == 'Revisar' for c in co)} comprobantes por revisar",
         sum(c["estado"] == "Revisar" for c in co), "warn"),
        ("archivo-quipux", "Archivo Quipux", f"{sum(x['estado'] == 'Por revisar' for x in aq)} documentos por revisar",
         sum(x["estado"] == "Por revisar" for x in aq), "warn"),
        ("contratos", "Contratos de Agencia Fiscal", f"{sum(x['estado'] == 'Por revisar' for x in ct)} oficios por revisar",
         sum(x["estado"] == "Por revisar" for x in ct), "warn"),
    ]
    return [{"modulo": m, "nombre": n, "texto": t, "cuenta": c, "tono": tono} for m, n, t, c, tono in filas]
