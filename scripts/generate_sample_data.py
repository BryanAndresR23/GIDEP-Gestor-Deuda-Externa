#!/usr/bin/env python3
"""
Genera reportes FICTICIOS para probar la conciliación de deuda externa.

Crea, por cada periodo, dos libros de Excel con la misma forma que los
reportes reales (pero con datos inventados):

* Reporte del Banco Central  -> hojas "Giros del Exterior" (desembolsos que
  entran) y "Giros al Exterior" (pagos que salen), con el detalle por préstamo
  y una fila "TOTAL <agrupación>" debajo de cada grupo.
* Reporte del Ministerio     -> hoja "Resumen" con una fila por organismo,
  subtotales padre (MULTILATERAL, ...) y una columna de Observaciones.

En marzo se siembran tres diferencias típicas para que el diagnóstico tenga
algo que explicar: un pago directo, un diferencial cambiario y un desfase de
fecha. Febrero cuadra completo (solo diferencias de redondeo < USD 0,50).

Uso:
    python scripts/generate_sample_data.py            # escribe en data/sample
"""
from __future__ import annotations

import random
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

OUT = Path(__file__).resolve().parent.parent / "data" / "sample"
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]
CONCEPTOS = ["Desembolsos", "Amortizaciones", "Intereses", "Comisiones",
             "Intereses Condonados", "Interés por Mora"]

# Agrupaciones tal como las escribe el Banco (nombre largo) -> organismo del Ministerio
BANCO_GRUPOS = {
    "BANCO INTERAMERICANO DE DESARROLLO - BID": "BID",
    "BANCO MUNDIAL - BIRF": "BIRF",
    "CORPORACIÓN ANDINA DE FOMENTO - CAF": "CAF",
    "FONDO INTERNACIONAL DE DESARROLLO AGRÍCOLA - FIDA": "FIDA",
    "FONDO LATINOAMERICANO DE RESERVAS - FLAR": "FLAR",
    "FONDO MONETARIO INTERNACIONAL - FMI": "FMI",
    "EXIMBANK ORIENTE - EXIM": "GOBIERNOS",          # sub-prestamista ficticio
    "AGENCIA NÓRDICA DE COOPERACIÓN - ANC": "GOBIERNOS",
    "BANCO EUROPEO DE CRÉDITO - BEC": "BANCOS",
    "OTROS": "BANCOS",                                 # intereses de banco custodio
    "BONOS SOBERANOS 2030": "BONOS",
}

# Estructura del Resumen del Ministerio: (organismo, padre o None)
MINISTERIO_FILAS = [
    ("MULTILATERAL", None),
    ("BID", "MULTILATERAL"), ("BIRF", "MULTILATERAL"), ("CAF", "MULTILATERAL"),
    ("FIDA", "MULTILATERAL"), ("FLAR", "MULTILATERAL"),
    ("INSTITUCIÓN FINANCIERA INTERNACIONAL", None),
    ("FMI", "INSTITUCIÓN FINANCIERA INTERNACIONAL"),
    ("GOBIERNOS", None), ("BANCOS", None), ("BONOS", None),
]

HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
HEADER_FONT = Font(bold=True, color="FFFFFF")
BOLD = Font(bold=True)


def montos_base(rng: random.Random) -> dict:
    """Montos USD por grupo del Banco y concepto (lo que realmente se movió)."""
    escala = {"BID": 9e6, "BIRF": 7e6, "CAF": 8e6, "FIDA": 6e5, "FLAR": 3e6, "FMI": 1.2e7,
              "GOBIERNOS": 2.5e6, "BANCOS": 1.8e6, "BONOS": 2.2e7}
    datos = {}
    for grupo, org in BANCO_GRUPOS.items():
        s = escala[org] * rng.uniform(0.35, 0.65)
        d = {c: 0.0 for c in CONCEPTOS}
        if org in ("BID", "BIRF", "CAF", "FIDA") or grupo.endswith("ANC"):
            d["Desembolsos"] = round(s * rng.uniform(0.6, 1.4), 2)
        if org != "BONOS" and grupo != "OTROS":
            d["Amortizaciones"] = round(s * rng.uniform(0.3, 0.7), 2)
        d["Intereses"] = round(s * rng.uniform(0.04, 0.12), 2)
        if org in ("BID", "BIRF", "CAF", "FIDA", "GOBIERNOS"):
            d["Comisiones"] = round(s * rng.uniform(0.002, 0.006), 2)
        if org == "CAF":
            d["Intereses Condonados"] = round(s * rng.uniform(0.005, 0.01), 2)
        if org == "BANCOS" and grupo != "OTROS":
            d["Interés por Mora"] = round(s * rng.uniform(0.0005, 0.0015), 2)
        datos[grupo] = d
    return datos


def repartir(total: float, partes: int, rng: random.Random) -> list[float]:
    """Divide un total en 'partes' préstamos que suman exactamente el total."""
    if partes == 1 or total == 0:
        return [round(total, 2)] + [0.0] * (partes - 1)
    cortes = sorted(rng.uniform(0.15, 0.85) for _ in range(partes - 1))
    pesos = [b - a for a, b in zip([0] + cortes, cortes + [1])]
    valores = [round(total * p, 2) for p in pesos]
    valores[-1] = round(total - sum(valores[:-1]), 2)
    return valores


def escribir_encabezado(ws, fila: int, titulos: list[str]):
    for c, t in enumerate(titulos, start=1):
        cell = ws.cell(fila, c, t)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)


def reporte_banco(datos: dict, anio: int, mes: int, rng: random.Random, ruta: Path):
    wb = Workbook()
    ws_in = wb.active
    ws_in.title = "Giros del Exterior"
    ws_out = wb.create_sheet("Giros al Exterior")
    for ws, titulo in ((ws_in, "Desembolsos recibidos"), (ws_out, "Pagos de servicio de deuda")):
        ws["A1"] = f"BANCO CENTRAL (FICTICIO) - {titulo}"
        ws["A1"].font = Font(bold=True, size=12)
        ws["A2"] = f"Desde: 01/{mes:02d}/{anio}  Hasta: 28/{mes:02d}/{anio}"

    # --- Giros del Exterior: desembolsos -----------------------------------
    escribir_encabezado(ws_in, 4, ["Fecha Valor", "Agrupación del Exterior", "No. Préstamo",
                                   "Prestamista", "Moneda", "Valor (USD)"])
    r = 5
    for grupo, d in datos.items():
        if not d["Desembolsos"]:
            continue
        valores = repartir(d["Desembolsos"], rng.randint(1, 3), rng)
        for i, v in enumerate(valores):
            ws_in.cell(r, 1, date(anio, mes, rng.randint(2, 27)).strftime("%d/%m/%Y"))
            ws_in.cell(r, 2, grupo if i == 0 else "")          # etiqueta solo en la 1ª fila
            ws_in.cell(r, 3, f"PR-{rng.randint(1000, 9999)}")
            ws_in.cell(r, 4, grupo.split(" - ")[0].title())
            ws_in.cell(r, 5, "USD")
            ws_in.cell(r, 6, v)
            r += 1
        ws_in.cell(r, 1, f"TOTAL {grupo.split(' - ')[-1]}").font = BOLD
        ws_in.cell(r, 6, round(sum(valores), 2)).font = BOLD
        r += 1

    # --- Giros al Exterior: pagos (el orden de columnas varía entre meses) ---
    conceptos_pago = ["Amortizaciones", "Intereses", "Comisiones", "Interés por Mora",
                      "Intereses Condonados"]
    titulos = {"Amortizaciones": "Capital (USD)", "Intereses": "Interés (USD)",
               "Comisiones": "Comisión (USD)", "Interés por Mora": "Interés Mora (USD)",
               "Intereses Condonados": "Condonado (USD)"}
    if mes % 2 == 1:   # en meses impares el Banco mueve 'Condonado' antes de 'Mora'
        conceptos_pago = ["Amortizaciones", "Intereses", "Comisiones",
                          "Intereses Condonados", "Interés por Mora"]
    escribir_encabezado(ws_out, 4, ["Fecha Valor", "Agrupación al Exterior",
                                    "No. Referencia Préstamo", "Prestamista"]
                        + [titulos[c] for c in conceptos_pago])
    r = 5
    for grupo, d in datos.items():
        n = rng.randint(1, 3)
        partes = {c: repartir(d[c], n, rng) for c in conceptos_pago}
        if not any(d[c] for c in conceptos_pago):
            continue
        for i in range(n):
            ws_out.cell(r, 1, date(anio, mes, rng.randint(2, 27)).strftime("%d/%m/%Y"))
            ws_out.cell(r, 2, grupo if i == 0 else "")
            ws_out.cell(r, 3, f"PR-{rng.randint(1000, 9999)}")
            ws_out.cell(r, 4, grupo.split(" - ")[0].title())
            for j, c in enumerate(conceptos_pago, start=5):
                ws_out.cell(r, j, partes[c][i])
            r += 1
        ws_out.cell(r, 1, f"TOTAL {grupo.split(' - ')[-1]}").font = BOLD
        for j, c in enumerate(conceptos_pago, start=5):
            ws_out.cell(r, j, round(d[c], 2)).font = BOLD
        r += 1

    for ws in (ws_in, ws_out):
        for letra, ancho in zip("ABCDEFGHI", (12, 46, 22, 40, 16, 16, 16, 18, 16)):
            ws.column_dimensions[letra].width = ancho
    wb.save(ruta)


def reporte_ministerio(datos: dict, anio: int, mes: int, ajustes: dict, ruta: Path):
    """ajustes = {organismo: (concepto, delta, observación)}"""
    org_vals = {org: {c: 0.0 for c in CONCEPTOS} for org, _ in MINISTERIO_FILAS}
    for grupo, d in datos.items():
        org = BANCO_GRUPOS[grupo]
        for c in CONCEPTOS:
            org_vals[org][c] += d[c]
    observaciones = {}
    for org, (concepto, delta, obs) in ajustes.items():
        org_vals[org][concepto] += delta
        if obs:
            observaciones[org] = obs
    for padre in ("MULTILATERAL", "INSTITUCIÓN FINANCIERA INTERNACIONAL"):
        hijos = [o for o, p in MINISTERIO_FILAS if p == padre]
        org_vals[padre] = {c: sum(org_vals[h][c] for h in hijos) for c in CONCEPTOS}

    wb = Workbook()
    ws = wb.active
    ws.title = "Resumen"
    ws["A1"] = f"MINISTERIO DE FINANZAS (FICTICIO) - Servicio de deuda externa - {MESES[mes - 1]} {anio}"
    ws["A1"].font = Font(bold=True, size=12)
    escribir_encabezado(ws, 3, ["Organismo"] + CONCEPTOS + ["Observaciones"])
    r = 4
    for org, padre in MINISTERIO_FILAS:
        ws.cell(r, 1, ("    " if padre else "") + org).font = Font(bold=padre is None)
        for j, c in enumerate(CONCEPTOS, start=2):
            ws.cell(r, j, round(org_vals[org][c], 2))
        ws.cell(r, 8, observaciones.get(org, ""))
        r += 1
    raices = [o for o, p in MINISTERIO_FILAS if p is None]
    ws.cell(r, 1, "TOTAL GENERAL").font = BOLD
    for j, c in enumerate(CONCEPTOS, start=2):
        ws.cell(r, j, round(sum(org_vals[o][c] for o in raices), 2)).font = BOLD
    for letra, ancho in zip("ABCDEFGH", (40, 16, 16, 16, 14, 18, 16, 60)):
        ws.column_dimensions[letra].width = ancho
    wb.save(ruta)


def generar(anio: int, mes: int, semilla: int, ajustes: dict):
    rng = random.Random(semilla)
    datos = montos_base(rng)
    OUT.mkdir(parents=True, exist_ok=True)
    reporte_banco(datos, anio, mes, rng, OUT / f"Reporte_Banco_Central_{anio}-{mes:02d}.xlsx")
    reporte_ministerio(datos, anio, mes, ajustes, OUT / f"Reporte_Ministerio_{anio}-{mes:02d}.xlsx")
    print(f"  {anio}-{mes:02d}: reportes del Banco y del Ministerio generados")


def main():
    print(f"Generando reportes ficticios en {OUT}")
    # Febrero: todo cuadra salvo redondeos menores a la tolerancia
    generar(2026, 2, 202602, {"BID": ("Intereses", 0.31, ""), "FMI": ("Comisiones", -0.12, "")})
    # Marzo: tres diferencias sembradas + un redondeo dentro de tolerancia
    generar(2026, 3, 202603, {
        "CAF": ("Desembolsos", 1_250_000.00,
                "Desembolso pagado de forma directa al proveedor; no pasó por el Banco Central."),
        "FIDA": ("Intereses", 1_843.27,
                 "Préstamo en moneda original EUR: diferencial cambiario en la conversión a USD."),
        "BANCOS": ("Amortizaciones", -15_000.00, ""),
        "BIRF": ("Amortizaciones", 0.44, ""),
    })
    print("Listo.")


if __name__ == "__main__":
    main()
