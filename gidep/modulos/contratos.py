"""Oficios de Contratos de Agencia Fiscal: archiva solo oficios finales firmados del proceso.

Reglas:
  * Se excluyen memorandos, borradores TEMP, contratos adjuntos y oficios ajenos al proceso.
  * La firma electrónica final debe verificarse.
  * Destino por referencia contractual exacta; el acreedor solo es evidencia complementaria.
  * El nombre final conserva el número real del oficio y el descriptor aprendido:
    «BC-OF-2026-0712 (Envío Borrador Contrato).pdf».
  * Solo una coincidencia única de al menos 99 % se archiva automáticamente.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..demo import cargar, chip

DESCRIPTORES = ["Envío Borrador Contrato", "Envío Contrato Firmado", "Suscripción Contrato", "Correcciones", "Revisión"]
ACREEDORES = ["BANCOS", "BID", "BIRF", "CAF", "GOBIERNOS"]
UMBRAL = 99
TONOS = {"Archivado": "ok", "Por revisar": "warn", "Excluido": "muted"}


def evaluar(doc: dict, conocidos: dict) -> dict:
    nombre = Path(doc["archivo"]).stem
    if "TEMP" in nombre.upper():
        return {"estado": "Excluido", "confianza": 0, "detalle": "Borrador TEMP: nunca se archiva.", "ruta": "—"}
    if doc["encabezado"].upper() != "OFICIO":
        return {"estado": "Excluido", "confianza": 0, "detalle": f"Es un {doc['encabezado'].lower()}, no un oficio.", "ruta": "—"}
    if "agencia fiscal" not in doc["asunto"].lower():
        return {"estado": "Excluido", "confianza": 0, "detalle": "No pertenece al flujo de agencia fiscal.", "ruta": "—"}
    descriptor = next((d for d in DESCRIPTORES if d.lower() in doc["asunto"].lower()), "Oficio")
    if not doc["firma_final"]:
        return {"estado": "Por revisar", "confianza": 0, "detalle": "No se pudo verificar la firma electrónica final.", "ruta": "—"}
    ref = re.search(r"\b[A-Z]+-CT-\d{4}-\d{2}\b", doc["texto"].upper())
    if ref and ref.group(0) in conocidos:
        acr = conocidos[ref.group(0)]
        return {"estado": "Archivado", "confianza": 100, "detalle": f"Referencia contractual {ref.group(0)} exacta.",
                "ruta": f"{acr}/Contratos Agencia Fiscal/{nombre} ({descriptor}).pdf"}
    acr = next((a for a in ACREEDORES if re.search(rf"\b{a}\b", doc["texto"].upper())), None)
    if acr:
        return {"estado": "Por revisar", "confianza": 85,
                "detalle": f"Solo el acreedor ({acr}) coincide; se necesita la referencia contractual (≥ {UMBRAL} %).",
                "ruta": f"{acr}/Contratos Agencia Fiscal/…"}
    return {"estado": "Por revisar", "confianza": 0, "detalle": "Sin referencia ni acreedor reconocible.", "ruta": "—"}


def resultados() -> list[dict]:
    conocidos = cargar("contratos_conocidos")
    return [{**d, **evaluar(d, conocidos)} for d in cargar("bandeja_contratos")]


def vista() -> dict:
    res = resultados()
    return {
        "titulo": "Oficios de Contratos de Agencia Fiscal",
        "subtitulo": "Reconoce y archiva únicamente oficios finales firmados del flujo de contratos de agencia fiscal, "
                     "con el número real del oficio y el descriptor aprendido de los expedientes.",
        "kpis": [
            {"valor": sum(r["estado"] == "Archivado" for r in res), "etiqueta": "Archivados (≥ 99 %)", "tono": "ok"},
            {"valor": sum(r["estado"] == "Por revisar" for r in res), "etiqueta": "Por revisar", "tono": "warn"},
            {"valor": sum(r["estado"] == "Excluido" for r in res), "etiqueta": "Excluidos", "tono": "muted"},
        ],
        "secciones": [{
            "titulo": "Documentos en la bandeja",
            "columnas": ["Archivo", "Encabezado", "Asunto", "Confianza", "Decisión", "Destino", "Estado"],
            "filas": [[r["archivo"], r["encabezado"].title(), r["asunto"], f"{r['confianza']} %", r["detalle"], r["ruta"],
                       chip(r["estado"], TONOS[r["estado"]])] for r in res],
        }],
        "reglas": [
            "Se excluyen memorandos, borradores TEMP, contratos adjuntos y oficios de pago.",
            "La firma electrónica final debe poder verificarse.",
            f"Solo una coincidencia única de al menos {UMBRAL} % se archiva; lo demás queda en revisión.",
            "La copia se verifica por contenido, se conserva el original y no se reemplaza ningún archivo distinto.",
        ],
    }
