#!/usr/bin/env python3
"""
Genera los datos FICTICIOS de todos los módulos de la demo del gestor GIDEP.

Todo es inventado: préstamos, oficios, mensajes Swift, cuentas, municipios y
personas. La "fecha de hoy" de la demo es fija (16-mar-2026) para que los
estados (para hoy, vencido, programado...) siempre se vean igual.

Uso:
    python scripts/generate_sample_data.py   # reportes Excel de conciliación (requisito)
    python scripts/generate_demo_data.py     # JSON de los demás módulos -> data/demo
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from conciliacion import engine  # noqa: E402

OUT = ROOT / "data" / "demo"
HOY = date(2026, 3, 16)
rng = random.Random(2026)

PRESTAMOS = [
    {"prestamo": "PR-4417", "id_deuda": "DX-100417", "acreedor": "CAF", "moneda": "USD"},
    {"prestamo": "PR-4460", "id_deuda": "DX-100446", "acreedor": "CAF", "moneda": "USD"},
    {"prestamo": "PR-4482", "id_deuda": "DX-100448", "acreedor": "CAF", "moneda": "USD"},
    {"prestamo": "PR-5120", "id_deuda": "DX-100512", "acreedor": "BID", "moneda": "USD"},
    {"prestamo": "PR-1045", "id_deuda": "DX-100104", "acreedor": "BID", "moneda": "USD"},
    {"prestamo": "PR-3308", "id_deuda": "DX-100330", "acreedor": "BIRF", "moneda": "USD"},
    {"prestamo": "PR-3377", "id_deuda": "DX-100337", "acreedor": "BIRF", "moneda": "USD"},
    {"prestamo": "PR-2291", "id_deuda": "DX-100229", "acreedor": "FIDA", "moneda": "EUR"},
    {"prestamo": "PR-9001", "id_deuda": "DX-100900", "acreedor": "FLAR", "moneda": "USD"},
    {"prestamo": "PR-7004", "id_deuda": "DX-100700", "acreedor": "GOBIERNOS", "moneda": "JPY"},
    {"prestamo": "PR-6612", "id_deuda": "DX-100661", "acreedor": "GOBIERNOS", "moneda": "EUR"},
    {"prestamo": "PR-8150", "id_deuda": "DX-100815", "acreedor": "BANCOS", "moneda": "EUR"},
    {"prestamo": "BONO-2030", "id_deuda": "DX-102030", "acreedor": "BONOS", "moneda": "USD"},
]
CORRESPONSAL = {"USD": "Atlantic Clearing Bank", "EUR": "Euro Meridian Bank", "JPY": "Pacific Rim Banking Corp"}
MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto",
         "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def d(dias: int) -> str:
    return (HOY + timedelta(days=dias)).isoformat()


def oficio(n: int) -> str:
    return f"MF-SFP-2026-{n:04d}-O"


def guardar(nombre: str, datos):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{nombre}.json").write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {nombre + '.json':<28} {len(datos) if hasattr(datos, '__len__') else ''}")


def prestamo(ref):
    return next(p for p in PRESTAMOS if p["prestamo"] == ref)


# ----------------------------------------------------------------- Agenda
def agenda():
    filas = [
        ("PR-5120", 0, None, 1_250_000.00, True, False, True),     # para hoy, ya en SGI -> en proceso
        ("PR-3308", 0, None, 845_300.50, False, False, True),       # para hoy
        ("PR-2291", 2, 0, 310_480.00, False, False, True),          # débito hoy (prioridad)
        ("PR-9001", 3, None, 5_000_000.00, False, False, True),     # programado
        ("PR-7004", 5, 2, 182_500_000, False, False, True),         # programado (JPY)
        ("PR-4417", -2, None, 2_140_775.25, False, False, True),    # vencido
        ("PR-1045", -1, None, 640_210.00, True, True, True),        # procesado
        ("PR-8150", 9, None, 1_005_000.00, False, False, True),     # fuera de la semana
        ("PR-4460", 6, None, 920_000.00, False, False, True),       # programado
        (None, 4, None, 75_000.00, False, False, False),            # sin préstamo -> revisar
    ]
    datos = []
    for i, (ref, fv, fd, monto, sgi, proc, ok) in enumerate(filas, start=101):
        p = prestamo(ref) if ref else {"acreedor": "Sin identificar", "moneda": "USD"}
        datos.append({
            "oficio": oficio(i), "prestamo": ref, "acreedor": p["acreedor"], "moneda": p["moneda"],
            "monto": monto, "fecha_valor": d(fv), "fecha_debito": d(fd) if fd is not None else None,
            "vencimiento": d(fv + 30), "registrado_sgi": sgi, "procesado": proc,
            "comprobante": f"CC-2026-{i:05d}" if proc else None, "evidencia_suficiente": ok,
        })
    return datos


# ------------------------------------------------------------- Validación
def validacion():
    casos = [  # (ref, etapa, cambios)
        ("PR-5120", "En curso", {}),
        ("PR-2291", "En curso", {"fecha_comprobante": -1}),                  # EUR debe ir 2 días hábiles antes
        ("PR-7004", "Antes del pago", {}),
        ("PR-3308", "Después del pago", {"swift_monto": 845_300.05}),        # monto Swift distinto
        ("PR-1045", "Después del pago", {}),
        ("PR-8150", "En curso", {"corresponsal": "Atlantic Clearing Bank"}),  # corresponsal incorrecto
        ("PR-9001", "Antes del pago", {"fecha_valor_cambio": True}),         # cambió la fecha sin correo
    ]
    montos = {"PR-5120": 1_250_000.00, "PR-2291": 310_480.00, "PR-7004": 182_500_000,
              "PR-3308": 845_300.50, "PR-1045": 640_210.00, "PR-8150": 1_005_000.00, "PR-9001": 5_000_000.00}
    fechas = {"PR-5120": 0, "PR-2291": 2, "PR-7004": 5, "PR-3308": -3, "PR-1045": -1, "PR-8150": 9, "PR-9001": 3}
    datos = []
    for i, (ref, etapa, cambios) in enumerate(casos, start=1):
        p = prestamo(ref)
        fv = HOY + timedelta(days=fechas[ref])
        dias_antes = 0 if p["moneda"] == "USD" else (3 if p["moneda"] == "JPY" else 2)
        fc = fv
        n = dias_antes
        while n:                                              # días hábiles hacia atrás
            fc -= timedelta(days=1)
            if fc.weekday() < 5:
                n -= 1
        fc += timedelta(days=cambios.get("fecha_comprobante", 0))
        datos.append({
            "pago": f"PG-{i:03d}", "prestamo": ref, "acreedor": p["acreedor"], "etapa": etapa,
            "instruccion": {"monto": montos[ref], "moneda": p["moneda"], "fecha_valor": fv.isoformat(),
                            "beneficiario": p["acreedor"]},
            "swift": {"monto": cambios.get("swift_monto", montos[ref]), "moneda": p["moneda"],
                      "fecha_valor": fv.isoformat(), "beneficiario": p["acreedor"],
                      "corresponsal": cambios.get("corresponsal", CORRESPONSAL[p["moneda"]])},
            "comprobante": {"fecha": fc.isoformat(), "cuenta_debito": "1100-0099",
                            "comision": 50.00, "cuenta_comision": "2190-0450"},
            "fecha_valor_cambio": cambios.get("fecha_valor_cambio", False),
            "correo_respaldo": False,
        })
    return datos


# ------------------------------------------------------------- Desembolsos
def desembolsos():
    msgs = [
        (0, "MT103", "INTER-AMERICAN DEVELOPMENT BANK", "DISBURSEMENT LOAN PR-5120", 3_400_000.00, "USD"),
        (0, "MT910", "CORPORACION ANDINA DE FOMENTO", "DESEMBOLSO PRESTAMO PR-4482", 1_250_000.00, "USD"),
        (0, "MT103", "INTERNATIONAL FUND FOR AGRICULTURAL DEVELOPMENT", "IFAD DISBURSEMENT", 410_000.00, "EUR"),
        (-1, "MT103", "INTERNATIONAL BANK FOR RECONSTRUCTION AND DEVELOPMENT", "LOAN PR-3377 WITHDRAWAL", 2_000_000.00, "USD"),
        (-2, "MT910", "NORDIC COOPERATION AGENCY", "CREDIT PR-6612 TRANCHE 2", 650_000.00, "EUR"),
        (-3, "MT103", "GLOBAL TRADE SUPPLIES LTD", "INVOICE 4471 PAYMENT", 18_200.00, "USD"),
    ]
    datos = []
    for i, (dia, tipo, ordenante, ref, monto, mon) in enumerate(msgs, start=1):
        datos.append({"mensaje": f"SW-IN-{i:04d}", "fecha": d(dia), "tipo": tipo, "ordenante": ordenante,
                      "referencia": ref, "monto": monto, "moneda": mon, "archivado": dia <= -1})
    return datos


# --------------------------------------------------------------------- FMI
def fmi():
    msgs = [
        (0, "MT298", "GRA CHARGES AND INTEREST PERIOD ENDING 31 JAN 2026"),
        (0, "MT202", "REPURCHASE PRINCIPAL EFF ARRANGEMENT"),
        (-1, "MT298", "SDR REMUNERATION QUARTER 4 2025"),
        (-2, "MT298", "COMMITMENT FEE EXTENDED FUND FACILITY"),
        (-4, "MT298", "SDR ALLOCATION CHARGES Q4 2025"),
        (-6, "MT298", "ANNUAL ASSESSMENT FEE SDR DEPARTMENT"),
        (-7, "MT950", "STATEMENT OF ACCOUNT NO REFERENCE"),
        (-9, "MT298", "HOLIDAY NOTICE 03 APR 2026 MARKETS CLOSED"),
    ]
    return [{"mensaje": f"SW-FMI-{i:03d}", "fecha": d(dia), "tipo": tipo, "texto": texto}
            for i, (dia, tipo, texto) in enumerate(msgs, start=1)]


# ----------------------------------------------------------- Matriz y SGI
def matriz():
    filas = []
    for i, ref in enumerate(["PR-1045", "PR-3377", "PR-6612"], start=1):
        p = prestamo(ref)
        filas.append({"referencia": f"TF-{2600 + i:05d}", "prestamo": ref, "acreedor": p["acreedor"],
                      "fecha_valor": d(-10 * i), "moneda": p["moneda"],
                      "monto": round(rng.uniform(2e5, 2e6), 2)})
    return filas


SGI_EJEMPLO = """SISTEMA DE GIROS - GIROS AL EXTERIOR
Referencia: TF-02611
Préstamo: PR-1045
Acreedor: BID
Fecha valor: 2026-03-15
Moneda: USD
Monto: 640210.00
Tipo de cambio: 1.000000
Monto USD: 640210.00
Corresponsal: Atlantic Clearing Bank"""


# ------------------------------------------------------------ Archivo Quipux
def bandeja_quipux():
    docs = [
        ("Oficio_MF-SFP-2026-0131-O.pdf", "lote-1", "OFICIO MF-SFP-2026-0131-O. Asunto: pago de intereses de "
         "deuda externa pública, préstamo PR-5120. Fecha valor 2026-03-16. Monto USD 1,250,000.00.", False),
        ("estado_cuenta_marzo.pdf", "lote-1", "ESTADO DE CUENTA del acreedor al 2026-03-16. Saldo adeudado.", False),
        ("formulario_giro.pdf", "lote-1", "FORMULARIO DE TRANSFERENCIA AL EXTERIOR. Beneficiario BID.", False),
        ("Oficio_MF-SFP-2026-0144-O.pdf", "lote-2", "OFICIO MF-SFP-2026-0144-O. Deuda externa pública: transferencia "
         "de capital, identificador DX-100229. Fecha valor 2026-03-18.", False),
        ("Memorando_capacitacion.pdf", "lote-3", "MEMORANDO. Asunto: capacitación interna de seguridad de la información.", False),
        ("Oficio_MF-SFP-2026-0150-O.pdf", "lote-4", "OFICIO MF-SFP-2026-0150-O. Deuda externa pública: pago de "
         "amortización. Préstamo por confirmar.", False),
        ("estado_cuenta_feb.pdf", "historico", "ESTADO DE CUENTA del acreedor al 2026-02-27.", True),
        ("Oficio_MF-SFP-2026-0131-O (1).pdf", "lote-5", "OFICIO MF-SFP-2026-0131-O. Asunto: pago de intereses de "
         "deuda externa pública, préstamo PR-5120. Fecha valor 2026-03-16. Monto USD 1,250,000.00.", False),
    ]
    return [{"archivo": a, "lote": lote, "texto": t, "historico": h} for a, lote, t, h in docs]


# ------------------------------------------------------- Contratos de agencia
def bandeja_contratos():
    docs = [
        ("BC-OF-2026-0712.pdf", "OFICIO", "Contrato de Agencia Fiscal - Envío Borrador Contrato", True,
         "Ref. contrato CAF-CT-2026-01, préstamo PR-4482."),
        ("BC-OF-2026-0716.pdf", "OFICIO", "Contrato de Agencia Fiscal - Envío Contrato Firmado", True,
         "Ref. contrato BID-CT-2026-03, préstamo PR-5120."),
        ("BC-OF-2026-0721.pdf", "OFICIO", "Contrato de Agencia Fiscal - Correcciones", False,
         "Ref. contrato BIRF-CT-2026-02."),
        ("BC-OF-2026-0725-TEMP.pdf", "OFICIO", "Contrato de Agencia Fiscal - Revisión", True,
         "Ref. contrato CAF-CT-2026-01."),
        ("BC-MEM-2026-0098.pdf", "MEMORANDO", "Contrato de Agencia Fiscal - Revisión", True,
         "Ref. contrato BID-CT-2026-03."),
        ("BC-OF-2026-0730.pdf", "OFICIO", "Contrato de Agencia Fiscal - Suscripción Contrato", True,
         "Acreedor CAF, beneficiario municipio; sin referencia contractual."),
    ]
    return [{"archivo": a, "encabezado": e, "asunto": s, "firma_final": f, "texto": t} for a, e, s, f, t in docs]


CONTRATOS_CONOCIDOS = {"CAF-CT-2026-01": "CAF", "BID-CT-2026-03": "BID", "BIRF-CT-2026-02": "BIRF",
                       "GOB-CT-2025-07": "GOBIERNOS", "BAN-CT-2025-02": "BANCOS"}


# --------------------------------------------------------------- Firma EC
def firmas():
    filas = []
    flujos = {"Firma Deuda Externa": ["MT103_PR-5120", "MT103_PR-3308", "MT202_PR-2291", "MT103_PR-4417"],
              "Firmas Automáticos": ["AUTO_REPORTE_DIARIO", "AUTO_LIQUIDACION_0316"],
              "Firma Bancos": ["BANCOS_MT199_0316", "BANCOS_MT202_0315"]}
    estados = [(1, "none"), (2, "none"), (2, "same"), (1, "none"), (2, "different"), (2, "none"), (1, "none"), (2, "same")]
    k = 0
    for flujo, docs in flujos.items():
        for nombre in docs:
            firmas_n, destino = estados[k % len(estados)]
            filas.append({"flujo": flujo, "archivo": f"{nombre}.pdf", "firmas": firmas_n, "fecha": d(-(k % 2)),
                          "destino": destino})
            k += 1
    return filas


# ---------------------------------------------------------- Comprobantes
def comprobantes():
    comp = [
        ("CC-2026-00141.pdf", "Analista 1", "PR-1045", oficio(107), "TF-02611", d(-1), 640_210.00, "USD", False),
        ("CC-2026-00142.pdf", "Analista 2", "PR-3308", oficio(102), "TF-02612", d(-3), 845_300.50, "USD", False),
        ("CC-2026-00143.pdf", "Analista 1", "PR-2291", oficio(103), "GS-00410", d(0), 310_480.00, "EUR", False),
        ("CC-2026-00144.pdf", "Analista 2", "PR-4460", None, "TF-02615", d(0), 920_000.00, "USD", False),
        ("CC-2026-00145.pdf", "Analista 1", "PR-9001", oficio(104), "NC-00077", d(0), 5_000_000.00, "USD", True),
    ]
    acks = [
        ("ACK_TF-02611.pdf", "TF-02611", d(-1), 640_210.00, "USD", "PR-1045"),
        ("ACK_TF-02612.pdf", "TF-02612", d(-3), 845_300.50, "USD", None),
        ("ACK_GS-00410.pdf", "GS-00410", d(1), 310_480.00, "EUR", "PR-2291"),
        ("ACK_TF-02699.pdf", "TF-02699", d(0), 920_000.00, "USD", None),
    ]
    return ([{"archivo": a, "responsable": r, "prestamo": p, "oficio": o, "ref": ref, "fecha_valor": f,
              "monto": m, "moneda": mon, "transferencia_interna": ti,
              "texto": "DTR100 NC-01 " + p if ti else ""} for a, r, p, o, ref, f, m, mon, ti in comp],
            [{"archivo": a, "ref": ref, "fecha": f, "monto": m, "moneda": mon, "prestamo": p}
             for a, ref, f, m, mon, p in acks])


# ------------------------------------------------------------------ Correos
def correos():
    ejemplos = [
        ("Confirmación de pago de intereses",
         "Solicitamos confirmar si se realizó el pago de intereses del préstamo con fecha valor de hoy.",
         "Estimados: confirmamos que el pago de intereses fue procesado con la fecha valor indicada. "
         "Adjuntamos el mensaje Swift y el comprobante contable como respaldo. Saludos cordiales.", 7),
        ("Cambio de fecha valor",
         "El acreedor informa que la fecha valor del pago cambia al siguiente día hábil.",
         "Estimados: tomamos nota del cambio de fecha valor. Para proceder necesitamos el oficio o correo "
         "oficial que respalde la nueva fecha; con ese documento actualizamos la programación del pago.", 4),
        ("Solicitud de estado de cuenta",
         "Requerimos el estado de cuenta actualizado del préstamo para la conciliación mensual.",
         "Estimados: adjuntamos el estado de cuenta solicitado con corte al último día hábil del mes. "
         "Quedamos atentos a cualquier observación.", 5),
        ("Diferencia en conciliación",
         "Existe una diferencia entre el reporte del Banco Central y el del Ministerio en desembolsos.",
         "Estimados: la diferencia corresponde a un desembolso pagado de forma directa al proveedor, que no "
         "pasó por el Banco Central. Agradeceremos remitir el respaldo para registrar el ajuste.", 3),
        ("Datos de cuenta del beneficiario",
         "Por favor validar los datos de la cuenta del beneficiario antes del giro.",
         "Estimados: validamos la estructura de la cuenta (IBAN y BIC) y es correcta. Procedemos con el "
         "giro en la fecha valor instruida.", 2),
        ("Mensaje pendiente de segunda firma",
         "El mensaje de pago está pendiente de la segunda firma.",
         "Estimados: el mensaje fue enviado a la segunda firma; una vez firmado lo trasladamos a la carpeta "
         "del día y confirmamos su envío.", 1),
    ]
    return [{"id": i, "asunto": a, "correo": c, "respuesta": r, "usos": u}
            for i, (a, c, r, u) in enumerate(ejemplos, start=1)]


# ---------------------------------------------------------- Condonados CAF
def condonados():
    banco = engine.leer_banco(ROOT / "data" / "sample" / "Reporte_Banco_Central_2026-03.xlsx")
    total = round(banco["CAF"]["Intereses Condonados"], 2)
    partes = [round(total * p, 2) for p in (0.45, 0.35)]
    partes.append(round(total - sum(partes), 2))
    return {"periodo": "2026-03", "valor_reporte_banco": total,
            "estados_cuenta": [{"prestamo": ref, "archivo": f"Estado_cuenta_{ref}_Mar2026.pdf",
                                "interes_condonado_usd": v}
                               for ref, v in zip(["PR-4417", "PR-4460", "PR-4482"], partes)]}


# ---------------------------------------------------------- Retenciones CAF
def retenciones():
    return {"periodo": "2026-03", "gad": [
        {"gad": "GAD Municipal de Río Claro", "prestamo": "PR-4417", "fuente": "Tabla del convenio",
         "monto": 48_750.00, "cuenta_gad": "GAD-0001-RC", "oficio_firmado": True, "comprobante_archivado": True},
        {"gad": "GAD Municipal de Puerto Alto", "prestamo": "PR-4460", "fuente": "Oficio del GAD",
         "monto": 112_300.40, "cuenta_gad": "GAD-0002-PA", "oficio_firmado": True, "comprobante_archivado": False},
        {"gad": "GAD Municipal de Valle Verde", "prestamo": "PR-4482", "fuente": "Oficio del GAD",
         "monto": None, "cuenta_gad": "GAD-0003-VV", "oficio_firmado": False, "comprobante_archivado": False},
    ]}


def usuarios():
    """Usuarios de demostración. La contraseña de los tres es 'gidep-demo' (se guarda solo su hash)."""
    from werkzeug.security import generate_password_hash
    return [{"usuario": u, "nombre": n, "perfil": p, "hash": generate_password_hash("gidep-demo")}
            for u, n, p in (("demo", "Usuario Demo", "Analista"), ("supervisor", "Supervisora Demo", "Supervisor"),
                            ("admin", "Administrador Demo", "Administrador"))]


def main():
    print(f"Generando datos ficticios de la demo en {OUT}")
    guardar("usuarios", usuarios())
    c, a = comprobantes()
    guardar("prestamos", PRESTAMOS)
    guardar("agenda", agenda())
    guardar("validacion", validacion())
    guardar("desembolsos", desembolsos())
    guardar("fmi", fmi())
    guardar("matriz", matriz())
    guardar("bandeja_quipux", bandeja_quipux())
    guardar("bandeja_contratos", bandeja_contratos())
    guardar("contratos_conocidos", CONTRATOS_CONOCIDOS)
    guardar("firmas", firmas())
    guardar("comprobantes", c)
    guardar("acks", a)
    guardar("correos", correos())
    guardar("condonados", condonados())
    guardar("retenciones", retenciones())
    (OUT / "sgi_ejemplo.txt").write_text(SGI_EJEMPLO, encoding="utf-8")
    print("Listo.")


if __name__ == "__main__":
    main()
