"""Comprobantes Contables y ACK: relaciona cada comprobante con la confirmación del Swift.

Criterios de coincidencia (con su peso): referencia TF/GS/NC exacta (40), préstamo (25),
fecha valor (15) y monto con moneda (20). Se muestra el método usado y la confianza:
  * >= 80 %: listo para archivar comprobante y ACK juntos.
  * 50-79 %: revisar; nunca se archiva por suposición.
  * Sin ACK aún: se archiva primero el comprobante y el expediente se completa cuando llegue.
Las transferencias internas (DTR100 + NC-01 + referencia del préstamo) no requieren ACK.
"""
from __future__ import annotations

from ..demo import MESES, cargar, chip, fecha, fmt_fecha, fmt_monto, prestamos

PESOS = {"referencia": 40, "prestamo": 25, "fecha": 15, "monto": 20}
TONOS = {"Listo para archivar": "ok", "Transferencia interna": "ok", "Revisar": "warn", "Esperando ACK": "info"}


def evidencia(comp: dict, ack: dict) -> tuple[int, list[str]]:
    usado = []
    if ack["ref"] == comp["ref"]:
        usado.append("referencia")
    if ack.get("prestamo") and ack["prestamo"] == comp["prestamo"]:
        usado.append("prestamo")
    if ack["fecha"] == comp["fecha_valor"]:
        usado.append("fecha")
    if ack["monto"] == comp["monto"] and ack["moneda"] == comp["moneda"]:
        usado.append("monto")
    return sum(PESOS[u] for u in usado), usado


def es_transferencia_interna(comp: dict) -> bool:
    t = comp.get("texto", "").upper()
    return comp.get("transferencia_interna") and "DTR100" in t and "NC-01" in t and comp["prestamo"] in t


def relacionar(comp: dict, acks: list[dict]) -> dict:
    if es_transferencia_interna(comp):
        return {"estado": "Transferencia interna", "ack": "No requiere", "confianza": 100,
                "metodo": "DTR100 + NC-01 + préstamo"}
    mejor = max(((evidencia(comp, a), a) for a in acks), key=lambda x: x[0][0], default=((0, []), None))
    (puntos, usado), ack = mejor
    if puntos >= 80:
        estado = "Listo para archivar"
    elif puntos >= 50:
        estado = "Revisar"
    else:
        estado = "Esperando ACK"
    nombres = {"referencia": "referencia", "prestamo": "préstamo", "fecha": "fecha", "monto": "monto"}
    return {"estado": estado, "ack": ack["archivo"] if ack and puntos >= 50 else "—", "confianza": puntos,
            "metodo": " + ".join(nombres[u] for u in usado) if puntos >= 50 else
            ("posible coincidencia, insuficiente" if puntos else "sin coincidencias")}


def resultados() -> list[dict]:
    acks, cat = cargar("acks"), prestamos()
    filas = []
    for c in cargar("comprobantes"):
        r = relacionar(c, acks)
        p = cat[c["prestamo"]]
        mes = MESES[fecha(c["fecha_valor"]).month - 1]
        filas.append({**c, **r, "ruta": f"{p['acreedor']}/Pagos/2026/{mes}/{c['prestamo']}/"})
    return filas


def vista() -> dict:
    res = resultados()
    return {
        "titulo": "Comprobantes Contables y ACK",
        "subtitulo": "Revisa las carpetas de los analistas, lee cada comprobante y lo relaciona con su ACK del Swift "
                     "para archivarlos juntos en la carpeta del préstamo.",
        "kpis": [
            {"valor": len(res), "etiqueta": "Comprobantes detectados", "tono": "info"},
            {"valor": sum(r["estado"] in ("Listo para archivar", "Transferencia interna") for r in res), "etiqueta": "Listos para archivar", "tono": "ok"},
            {"valor": sum(r["estado"] == "Revisar" for r in res), "etiqueta": "Revisar", "tono": "warn"},
            {"valor": sum(r["estado"] == "Esperando ACK" for r in res), "etiqueta": "Esperando ACK", "tono": "info"},
        ],
        "secciones": [{
            "titulo": "Comprobantes y su confirmación",
            "columnas": ["Comprobante", "Responsable", "Préstamo", "Referencia", "Monto", "ACK", "Método · confianza", "Destino", "Estado"],
            "filas": [[r["archivo"], r["responsable"], r["prestamo"], r["ref"], fmt_monto(r["monto"], r["moneda"]),
                       r["ack"], f"{r['metodo']} · {r['confianza']} %", r["ruta"], chip(r["estado"], TONOS[r["estado"]])]
                      for r in res],
        }],
        "reglas": [
            "Pesos de la evidencia: referencia 40, préstamo 25, fecha valor 15, monto y moneda 20.",
            "≥ 80 %: se archivan comprobante y ACK juntos. 50-79 %: revisión manual.",
            "Si el ACK aún no llega, se archiva el comprobante y el expediente se completa después.",
            "Las transferencias internas (DTR100 + NC-01 + préstamo) no requieren ACK.",
        ],
    }
