"""
Motor de conciliación de pagos de deuda externa pública.

Cruza, por cada acreedor y concepto de pago, lo que reporta el Ministerio de
Finanzas (hoja "Resumen") contra lo que registró el Banco Central (hojas
"Giros del Exterior" y "Giros al Exterior"), y marca qué cuadra y qué no.

Reglas de negocio:
  1. Las columnas se ubican por su TÍTULO, no por su letra: si un reporte
     mueve o agrega columnas, el cruce sigue tomando el rubro correcto.
  2. El Banco usa nombres largos ("CORPORACIÓN ANDINA DE FOMENTO - CAF") y el
     Ministerio códigos cortos ("CAF"): ALIAS resuelve la equivalencia.
  3. Se concilia al nivel que el Banco desglosa. El Ministerio trae subtotales
     padre (MULTILATERAL, ...) además de sus hijos; se compara contra la fila
     exacta y nunca contra el padre, para no contar dos veces.
  4. Del lado del Banco se usan sus filas "TOTAL <grupo>"; si un reporte no las
     trae, se suma el detalle arrastrando la agrupación hacia abajo.
  5. Estado = CONCILIADO si |Ministerio - Banco| <= TOLERANCIA (USD 0,50).
  6. Las diferencias se explican con las Observaciones del Ministerio
     (pago directo, diferencial cambiario, ...).

Uso por consola:
    python -m conciliacion.engine REPORTE_BANCO.xlsx REPORTE_MINISTERIO.xlsx
"""
from __future__ import annotations

import re
import sys
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

TOLERANCIA = 0.50
CONCEPTOS = ["Desembolsos", "Amortizaciones", "Intereses", "Comisiones",
             "Intereses Condonados", "Interés por Mora"]
HOJA_DESEMBOLSOS = "Giros del Exterior"
HOJA_PAGOS = "Giros al Exterior"

# Títulos de columna: (debe contener todas, no debe contener ninguna)
MINISTERIO_COLS = {
    "Desembolsos": (["desembols"], []),
    "Amortizaciones": (["amortiz"], []),
    "Intereses": (["inter"], ["condon", "mora"]),
    "Comisiones": (["comis"], []),
    "Intereses Condonados": (["condon"], []),
    "Interés por Mora": (["mora"], []),
}
BANCO_PAGOS_COLS = {
    "Amortizaciones": (["capital", "usd"], []),
    "Intereses": (["inter", "usd"], ["mora", "comis", "condon"]),
    "Comisiones": (["comis", "usd"], []),
    "Intereses Condonados": (["condonad", "usd"], []),
    "Interés por Mora": (["mora", "usd"], []),
}
BANCO_DESEMBOLSO_COL = (["valor", "usd"], [])

# Sufijo o palabra del Banco -> organismo del Ministerio
ALIAS = {
    "BID": "BID", "BIRF": "BIRF", "CAF": "CAF", "FIDA": "FIDA", "FLAR": "FLAR", "FMI": "FMI",
    "GOBIERNOS": "GOBIERNOS", "BANCOS": "BANCOS", "BONOS": "BONOS",
    "OTROS": "BANCOS",                       # intereses del banco custodio
    "EXIM": "GOBIERNOS", "ANC": "GOBIERNOS",  # sub-prestamistas que el Ministerio agrupa
    "BEC": "BANCOS",
}
# Universo de conciliación (orden de presentación)
ENTIDADES = ["BID", "BIRF", "CAF", "FIDA", "FLAR", "FMI", "GOBIERNOS", "BANCOS", "BONOS"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


@dataclass
class Fila:
    acreedor: str
    concepto: str
    ministerio: float
    banco: float
    diferencia: float
    estado: str


# --------------------------------------------------------------- utilidades
def normaliza(texto) -> str:
    return re.sub(r"\s+", " ", str(texto or "").strip().upper())


def num(valor) -> float:
    try:
        return float(valor)
    except (TypeError, ValueError):
        return 0.0


def acreedor(nombre_banco: str) -> str:
    """Organismo del Ministerio que corresponde a una agrupación del Banco."""
    g = normaliza(nombre_banco)
    if " - " in g:                                   # "NOMBRE LARGO - SIGLA"
        sigla = g.rsplit(" - ", 1)[1].strip()
        if sigla in ALIAS:
            return ALIAS[sigla]
    for clave, destino in ALIAS.items():             # palabra clave
        if g == clave or re.search(rf"\b{re.escape(clave)}\b", g):
            return destino
    return g                                         # sin par: queda visible


def hoja(libro, patron: str):
    for ws in libro.worksheets:
        if patron.lower() in ws.title.lower():
            return ws
    raise ValueError(f"No se encontró una hoja que contenga '{patron}'")


def fila_encabezado(ws, etiqueta: str) -> int:
    for r in range(1, min(ws.max_row, 20) + 1):
        for c in range(1, ws.max_column + 1):
            if etiqueta.lower() in str(ws.cell(r, c).value or "").lower():
                return r
    raise ValueError(f"No se encontró el encabezado '{etiqueta}' en la hoja '{ws.title}'")


def buscar_columna(ws, fila: int, spec) -> int | None:
    incluye, excluye = spec
    for c in range(1, ws.max_column + 1):
        t = str(ws.cell(fila, c).value or "").lower()
        if all(k in t for k in incluye) and not any(k in t for k in excluye):
            return c
    return None


# ------------------------------------------------------------------ lectura
def leer_ministerio(ruta) -> tuple[OrderedDict, dict]:
    """{organismo: {concepto: valor}} y {organismo: observación} desde 'Resumen'."""
    ws = hoja(load_workbook(ruta, data_only=True, read_only=False), "Resumen")
    hr = fila_encabezado(ws, "Organismo")
    c_org = buscar_columna(ws, hr, (["organismo"], []))
    c_obs = buscar_columna(ws, hr, (["observ"], []))
    cols = {k: buscar_columna(ws, hr, spec) for k, spec in MINISTERIO_COLS.items()}
    faltan = [k for k, c in cols.items() if c is None]
    if faltan:
        raise ValueError(f"Reporte del Ministerio sin columnas: {', '.join(faltan)}")
    datos, obs = OrderedDict(), {}
    for r in range(hr + 1, ws.max_row + 1):
        org = normaliza(ws.cell(r, c_org).value)
        if not org or org.startswith("TOTAL"):
            continue
        datos[org] = {k: num(ws.cell(r, c).value) for k, c in cols.items()}
        if c_obs and ws.cell(r, c_obs).value:
            obs[acreedor(org)] = str(ws.cell(r, c_obs).value).strip()
    return datos, obs


def leer_banco(ruta) -> OrderedDict:
    """{organismo: {concepto: valor}} sumando las dos hojas de giros."""
    libro = load_workbook(ruta, data_only=True)
    total = OrderedDict()

    def destino(nombre):
        return total.setdefault(acreedor(nombre), {k: 0.0 for k in CONCEPTOS})

    def acumular(nombre_hoja, specs: dict):
        ws = hoja(libro, nombre_hoja)
        hr = fila_encabezado(ws, "Agrupaci")
        cols = {k: buscar_columna(ws, hr, spec) for k, spec in specs.items()}
        cols = {k: c for k, c in cols.items() if c is not None}
        # 1) Camino principal: filas "TOTAL <grupo>" (clasificación oficial del Banco)
        subtotales = 0
        for r in range(hr + 1, ws.max_row + 1):
            etiqueta = str(ws.cell(r, 1).value or "").strip()
            if not etiqueta.upper().startswith("TOTAL"):
                continue
            grupo = etiqueta[5:].strip(" -:")
            if not grupo:                      # gran total: se ignora
                continue
            fila = destino(grupo)
            for k, c in cols.items():
                fila[k] += num(ws.cell(r, c).value)
            subtotales += 1
        if subtotales:
            return
        # 2) Respaldo: sumar el detalle arrastrando la agrupación
        c_grupo = buscar_columna(ws, hr, (["agrupaci"], []))
        c_ref = buscar_columna(ws, hr, (["préstamo"], [])) or buscar_columna(ws, hr, (["prestamo"], []))
        grupo = None
        for r in range(hr + 1, ws.max_row + 1):
            grupo = str(ws.cell(r, c_grupo).value or "").strip() or grupo
            if not grupo or not ws.cell(r, c_ref).value:
                continue
            fila = destino(grupo)
            for k, c in cols.items():
                fila[k] += num(ws.cell(r, c).value)

    acumular(HOJA_DESEMBOLSOS, {"Desembolsos": BANCO_DESEMBOLSO_COL})
    acumular(HOJA_PAGOS, BANCO_PAGOS_COLS)
    return total


def tipo_reporte(ruta) -> str:
    """'banco' o 'ministerio', según las hojas del libro."""
    libro = load_workbook(ruta, read_only=True)
    nombres = [ws.title.lower() for ws in libro.worksheets]
    libro.close()
    if any("resumen" in n for n in nombres):
        return "ministerio"
    if any("giros" in n for n in nombres):
        return "banco"
    raise ValueError("No se reconoce el archivo: se esperan las hojas 'Resumen' o 'Giros ...'")


def detectar_periodo(ruta_ministerio) -> str:
    """'AAAA-MM' a partir del título del reporte del Ministerio."""
    libro = load_workbook(ruta_ministerio, read_only=True)
    try:
        for fila in hoja(libro, "Resumen").iter_rows(min_row=1, max_row=4, values_only=True):
            texto = " ".join(str(v).lower() for v in fila if v)
            anio = re.search(r"(20\d{2})", texto)
            for i, mes in enumerate(MESES, start=1):
                if mes in texto and anio:
                    return f"{anio.group(1)}-{i:02d}"
    finally:
        libro.close()
    raise ValueError("No se pudo detectar el periodo en el título del reporte del Ministerio")


# ------------------------------------------------------------ conciliación
def conciliar(ministerio: dict, banco: dict) -> list[Fila]:
    filas = []
    for ent in ENTIDADES:
        vm_ent = ministerio.get(ent, {})
        vb_ent = banco.get(ent, {})
        for concepto in CONCEPTOS:
            vm = round(vm_ent.get(concepto, 0.0), 2)
            vb = round(vb_ent.get(concepto, 0.0), 2)
            if vm == 0 and vb == 0:
                continue
            dif = round(vm - vb, 2) or 0.0
            estado = "CONCILIADO" if abs(dif) <= TOLERANCIA else "DIFERENCIA"
            filas.append(Fila(ent, concepto, vm, vb, dif, estado))
    sin_par = sorted(set(banco) - set(ENTIDADES))
    for ent in sin_par:                                      # agrupaciones sin mapeo
        for concepto, vb in banco[ent].items():
            if round(vb, 2):
                filas.append(Fila(ent, concepto, 0.0, round(vb, 2), round(-vb, 2), "DIFERENCIA"))
    return filas


def clasificar(observacion: str) -> tuple[str, str, str]:
    """(tipo, por qué, acción sugerida) a partir de la observación del Ministerio."""
    t = (observacion or "").lower()
    if "directo" in t or "directa" in t:
        return ("Pago directo",
                "El Ministerio pagó directamente al proveedor; el dinero no pasó por el Banco Central.",
                "Registrar el pago directo del lado del Banco con su respaldo documental.")
    if "cambiario" in t or "moneda original" in t:
        return ("Diferencial cambiario",
                "El préstamo está en otra moneda y la conversión a USD difiere entre reportes.",
                "Documentar como diferencia de tipo de cambio; no requiere ajuste.")
    return ("Por revisar",
            "No hay una observación que explique la diferencia (posible desfase de fecha valor).",
            "Revisar fechas valor y respaldos con el Ministerio.")


def diagnostico(filas: list[Fila], observaciones: dict) -> list[dict]:
    por_acreedor = OrderedDict()
    for f in filas:
        if f.estado == "DIFERENCIA":
            por_acreedor.setdefault(f.acreedor, {})[f.concepto] = f.diferencia
    items = []
    for ent, rubros in por_acreedor.items():
        obs = observaciones.get(ent, "")
        tipo, por_que, accion = clasificar(obs)
        items.append({"acreedor": ent, "rubros": rubros, "observacion": obs,
                      "tipo": tipo, "por_que": por_que, "accion": accion})
    return items


def conciliar_archivos(ruta_a, ruta_b) -> dict:
    """Recibe los dos reportes en cualquier orden y devuelve el resultado completo."""
    tipos = {tipo_reporte(ruta_a): ruta_a, tipo_reporte(ruta_b): ruta_b}
    if set(tipos) != {"banco", "ministerio"}:
        raise ValueError("Sube un reporte del Banco Central y uno del Ministerio")
    ministerio, observaciones = leer_ministerio(tipos["ministerio"])
    banco = leer_banco(tipos["banco"])
    filas = conciliar(ministerio, banco)
    total_m = round(sum(f.ministerio for f in filas), 2)
    total_b = round(sum(f.banco for f in filas), 2)
    return {
        "periodo": detectar_periodo(tipos["ministerio"]),
        "filas": [asdict(f) for f in filas],
        "diagnostico": diagnostico(filas, observaciones),
        "resumen": {
            "conciliados": sum(f.estado == "CONCILIADO" for f in filas),
            "diferencias": sum(f.estado == "DIFERENCIA" for f in filas),
            "total_ministerio": total_m,
            "total_banco": total_b,
            "diferencia_neta": round(total_m - total_b, 2),
        },
    }


# --------------------------------------------------------------- exportar
def exportar_excel(resultado: dict, ruta):
    verde, rojo = PatternFill("solid", fgColor="C8E6C9"), PatternFill("solid", fgColor="FFCDD2")
    cab_fill, cab_font = PatternFill("solid", fgColor="1F3A5F"), Font(bold=True, color="FFFFFF")
    wb = Workbook()
    ws = wb.active
    ws.title = "Conciliación"
    ws["A1"] = f"Conciliación de deuda externa - periodo {resultado['periodo']}"
    ws["A1"].font = Font(bold=True, size=13)
    titulos = ["Acreedor", "Concepto", "Ministerio (USD)", "Banco (USD)", "Diferencia (USD)", "Estado"]
    for c, t in enumerate(titulos, start=1):
        cell = ws.cell(3, c, t)
        cell.fill, cell.font, cell.alignment = cab_fill, cab_font, Alignment(horizontal="center")
    for r, f in enumerate(resultado["filas"], start=4):
        valores = [f["acreedor"], f["concepto"], f["ministerio"], f["banco"], f["diferencia"], f["estado"]]
        for c, v in enumerate(valores, start=1):
            cell = ws.cell(r, c, v)
            if c in (3, 4, 5):
                cell.number_format = "#,##0.00"
        ws.cell(r, 6).fill = verde if f["estado"] == "CONCILIADO" else rojo
    for letra, ancho in zip("ABCDEF", (14, 22, 18, 18, 18, 14)):
        ws.column_dimensions[letra].width = ancho

    wd = wb.create_sheet("Diagnóstico")
    for c, t in enumerate(["Acreedor", "Tipo", "Rubros con diferencia", "Observación del Ministerio",
                           "Por qué", "Acción sugerida"], start=1):
        cell = wd.cell(1, c, t)
        cell.fill, cell.font = cab_fill, cab_font
    for r, d in enumerate(resultado["diagnostico"], start=2):
        rubros = "; ".join(f"{k}: {v:,.2f}" for k, v in d["rubros"].items())
        for c, v in enumerate([d["acreedor"], d["tipo"], rubros, d["observacion"], d["por_que"], d["accion"]], 1):
            wd.cell(r, c, v).alignment = Alignment(wrap_text=True, vertical="top")
    for letra, ancho in zip("ABCDEF", (12, 20, 30, 45, 45, 45)):
        wd.column_dimensions[letra].width = ancho
    wb.save(ruta)
    return ruta


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1])
        return 1
    res = conciliar_archivos(*argv)
    print(f"Periodo {res['periodo']}: {res['resumen']['conciliados']} conciliados, "
          f"{res['resumen']['diferencias']} con diferencia")
    for f in res["filas"]:
        if f["estado"] == "DIFERENCIA":
            print(f"  {f['acreedor']:<10} {f['concepto']:<22} {f['diferencia']:>15,.2f}")
    salida = Path(f"Conciliacion_{res['periodo']}.xlsx")
    exportar_excel(res, salida)
    print(f"Reporte: {salida.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
