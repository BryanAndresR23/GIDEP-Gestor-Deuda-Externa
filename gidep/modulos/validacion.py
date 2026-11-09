"""Validación de Pagos: revisa cada pago antes, durante y después del envío.

Controles:
  * El mensaje Swift dice lo mismo que la instrucción del oficio (monto, moneda,
    fecha valor y beneficiario).
  * El pago sale por el banco corresponsal que corresponde a la moneda.
  * El comprobante contable usa las cuentas correctas y la comisión fija.
  * Fechas: en USD el comprobante va con la fecha valor; en otras monedas, 2 días
    hábiles antes (JPY, 3).
  * Si la fecha valor cambió, debe existir el correo de respaldo.
Las cuentas contables y la comisión de esta demo son ficticias.
"""
from __future__ import annotations

from datetime import date, timedelta

from ..demo import cargar, chip, fecha, fmt_fecha, fmt_monto

CORRESPONSAL = {"USD": "Atlantic Clearing Bank", "EUR": "Euro Meridian Bank", "JPY": "Pacific Rim Banking Corp"}
CUENTA_DEBITO = "1100-0099"
CUENTA_COMISION = "2190-0450"
COMISION_USD = 50.00
TOLERANCIA_MENOR = 1.00


def dias_habiles_antes(dia: date, n: int) -> date:
    while n:
        dia -= timedelta(days=1)
        if dia.weekday() < 5:
            n -= 1
    return dia


def fecha_comprobante_esperada(fecha_valor: date, moneda: str) -> date:
    return dias_habiles_antes(fecha_valor, 0 if moneda == "USD" else 3 if moneda == "JPY" else 2)


def validar(pago: dict) -> tuple[str, list[str]]:
    """Devuelve (estado, hallazgos). Estado: Correcto | Revisar | Con errores."""
    ins, sw, comp = pago["instruccion"], pago["swift"], pago["comprobante"]
    errores, menores = [], []
    dif = round(abs(sw["monto"] - ins["monto"]), 2)
    if dif > TOLERANCIA_MENOR:
        errores.append(f"El Swift tiene {fmt_monto(sw['monto'], sw['moneda'])} y la instrucción "
                       f"{fmt_monto(ins['monto'], ins['moneda'])}.")
    elif dif > 0:
        menores.append(f"Diferencia menor de {fmt_monto(dif, sw['moneda'])} entre Swift e instrucción.")
    if sw["moneda"] != ins["moneda"]:
        errores.append(f"Moneda del Swift ({sw['moneda']}) distinta a la instruida ({ins['moneda']}).")
    if sw["fecha_valor"] != ins["fecha_valor"]:
        errores.append("La fecha valor del Swift no coincide con la instrucción.")
    if sw["beneficiario"] != ins["beneficiario"]:
        errores.append("El beneficiario del Swift no coincide con la instrucción.")
    esperado = CORRESPONSAL.get(ins["moneda"])
    if sw["corresponsal"] != esperado:
        errores.append(f"Sale por {sw['corresponsal']}; para {ins['moneda']} corresponde {esperado}.")
    if comp["cuenta_debito"] != CUENTA_DEBITO:
        errores.append(f"Cuenta de débito {comp['cuenta_debito']}; debe ser {CUENTA_DEBITO}.")
    if comp["comision"] != COMISION_USD or comp["cuenta_comision"] != CUENTA_COMISION:
        errores.append(f"La comisión debe ser USD {COMISION_USD:.2f} a la cuenta {CUENTA_COMISION}.")
    debida = fecha_comprobante_esperada(fecha(ins["fecha_valor"]), ins["moneda"])
    if fecha(comp["fecha"]) != debida:
        regla = "con la fecha valor" if ins["moneda"] == "USD" else \
            f"{3 if ins['moneda'] == 'JPY' else 2} días hábiles antes de la fecha valor"
        errores.append(f"Comprobante con fecha {fmt_fecha(comp['fecha'])}; debía ser {fmt_fecha(debida.isoformat())} "
                       f"(en {ins['moneda']} va {regla}).")
    if pago.get("fecha_valor_cambio") and not pago.get("correo_respaldo"):
        errores.append("La fecha valor cambió y no está el correo de respaldo en la carpeta.")
    if errores:
        return "Con errores", errores + menores
    if menores:
        return "Revisar", menores
    return "Correcto", ["Swift, comprobante, corresponsal y fechas coinciden."]


TONOS = {"Correcto": "ok", "Revisar": "warn", "Con errores": "bad"}


def resultados() -> list[dict]:
    return [{**p, "estado": e, "hallazgos": h} for p in cargar("validacion") for e, h in [validar(p)]]


def vista() -> dict:
    res = resultados()
    cuenta = {k: sum(r["estado"] == k for r in res) for k in TONOS}
    etapas = {k: sum(r["etapa"] == k for r in res) for k in ("Antes del pago", "En curso", "Después del pago")}
    return {
        "titulo": "Validación de Pagos",
        "subtitulo": "Valida cada pago de deuda antes (pendientes de la Agenda), en curso (carpetas de los analistas) "
                     "y después del envío (confirmación del Swift).",
        "kpis": [
            {"valor": etapas["Antes del pago"], "etiqueta": "Antes del pago", "tono": "info"},
            {"valor": etapas["En curso"], "etiqueta": "En curso", "tono": "info"},
            {"valor": etapas["Después del pago"], "etiqueta": "Después del pago", "tono": "info"},
            {"valor": cuenta["Correcto"], "etiqueta": "Correctos", "tono": "ok"},
            {"valor": cuenta["Revisar"], "etiqueta": "Revisar (diferencias menores)", "tono": "warn"},
            {"valor": cuenta["Con errores"], "etiqueta": "Con errores", "tono": "bad"},
        ],
        "secciones": [{
            "titulo": "Resultado de la validación",
            "columnas": ["Pago", "Etapa", "Préstamo", "Monto instruido", "Fecha valor", "Hallazgos", "Estado"],
            "filas": [[r["pago"].replace("-", "‑"), r["etapa"], f"{r['prestamo']} · {r['acreedor']}",
                       fmt_monto(r["instruccion"]["monto"], r["instruccion"]["moneda"]),
                       fmt_fecha(r["instruccion"]["fecha_valor"]), " ".join(r["hallazgos"]),
                       chip(r["estado"], TONOS[r["estado"]])] for r in res],
        }],
        "reglas": [
            "USD: el comprobante va con la fecha valor. Otras monedas: 2 días hábiles antes; JPY: 3.",
            "Cada moneda sale por su corresponsal: USD Atlantic Clearing Bank, EUR Euro Meridian Bank, "
            "JPY Pacific Rim Banking Corp (bancos ficticios).",
            f"Comprobante: débito a {CUENTA_DEBITO} y comisión USD {COMISION_USD:.2f} a {CUENTA_COMISION} "
            "(cuentas ficticias).",
            "Si la fecha valor cambió, el correo de respaldo debe estar en la carpeta del pago.",
        ],
    }
