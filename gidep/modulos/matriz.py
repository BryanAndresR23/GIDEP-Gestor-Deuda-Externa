"""Matriz de Préstamos Realizados: registra cada giro leyendo la pantalla del sistema de giros.

En el gestor real se pega una captura y se lee con OCR en el propio equipo; en esta demo
se pega el texto de la pantalla. La fila solo se agrega cuando todas las verificaciones
están en verde, y nunca se duplica una referencia.
"""
from __future__ import annotations

import json
import re
import unicodedata

from ..demo import HOY, cargar, chip, fecha, fmt_fecha, fmt_monto, prestamos, runtime

CAMPOS = {"referencia": "Referencia", "prestamo": "Préstamo", "acreedor": "Acreedor",
          "fecha_valor": "Fecha valor", "moneda": "Moneda", "monto": "Monto",
          "tipo_cambio": "Tipo de cambio", "monto_usd": "Monto USD", "corresponsal": "Corresponsal"}
MONEDAS = {"USD", "EUR", "JPY", "GBP", "CHF", "CAD", "CNY"}


def _clave(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes).strip().lower()


ETIQUETAS = {_clave(v): k for k, v in CAMPOS.items()}


def leer_texto(texto: str) -> dict:
    datos = {}
    for linea in texto.splitlines():
        if ":" not in linea:
            continue
        etiqueta, valor = linea.split(":", 1)
        campo = ETIQUETAS.get(_clave(etiqueta))
        if campo:
            datos[campo] = valor.strip()
    return datos


def _num(valor):
    try:
        return float(str(valor).replace(",", ""))
    except (TypeError, ValueError):
        return None


def matriz_actual() -> list[dict]:
    ruta = runtime("matriz.json")
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return list(cargar("matriz"))


def verificar(datos: dict, matriz: list[dict] | None = None) -> list[tuple[str, bool, str]]:
    matriz = matriz_actual() if matriz is None else matriz
    cat = prestamos()
    faltan = [CAMPOS[c] for c in CAMPOS if not datos.get(c)]
    checks = [("Todas las casillas leídas", not faltan, "Faltan: " + ", ".join(faltan) if faltan else "Completo")]
    p = cat.get(datos.get("prestamo", ""))
    checks.append(("Préstamo existe y corresponde al acreedor",
                   bool(p and p["acreedor"] == datos.get("acreedor")),
                   f"{datos.get('prestamo')} · {datos.get('acreedor')}"))
    try:
        fv = fecha(datos.get("fecha_valor"))
        ok_fecha = fv is not None and fv <= HOY
    except ValueError:
        ok_fecha = False
    checks.append(("Fecha valor válida y no futura", ok_fecha, datos.get("fecha_valor", "—")))
    checks.append(("Moneda ISO válida", datos.get("moneda") in MONEDAS, datos.get("moneda", "—")))
    monto, tc, usd = _num(datos.get("monto")), _num(datos.get("tipo_cambio")), _num(datos.get("monto_usd"))
    cuadra = None not in (monto, tc, usd) and tc > 0 and abs(monto / tc - usd) <= 0.01
    checks.append(("Monto USD = monto / tipo de cambio", cuadra,
                   f"{monto} / {tc} = {round(monto / tc, 2) if monto and tc else '—'} · leído {usd}"))
    duplicada = any(f["referencia"] == datos.get("referencia") for f in matriz)
    checks.append(("Referencia no registrada antes", not duplicada,
                   "Ya existe en la matriz" if duplicada else datos.get("referencia", "—")))
    return checks


def agregar(datos: dict) -> bool:
    checks = verificar(datos)
    if not all(ok for _, ok, _ in checks):
        return False
    matriz = matriz_actual()
    matriz.append({"referencia": datos["referencia"], "prestamo": datos["prestamo"], "acreedor": datos["acreedor"],
                   "fecha_valor": datos["fecha_valor"], "moneda": datos["moneda"], "monto": _num(datos["monto"])})
    runtime("matriz.json").write_text(json.dumps(matriz, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def tabla_matriz() -> dict:
    filas = sorted(matriz_actual(), key=lambda f: f["fecha_valor"], reverse=True)
    return {"titulo": "Matriz de préstamos realizados",
            "columnas": ["Referencia", "Préstamo", "Acreedor", "Fecha valor", "Monto"],
            "filas": [[f["referencia"], f["prestamo"], f["acreedor"], fmt_fecha(f["fecha_valor"]),
                       fmt_monto(f["monto"], f["moneda"])] for f in filas]}


def chips_verificacion(checks):
    return [[nombre, detalle, chip("OK" if ok else "Falla", "ok" if ok else "bad")] for nombre, ok, detalle in checks]
