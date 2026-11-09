"""Activaciones de Cuentas: valida la estructura de una cuenta antes de usarla en un pago.

Validadores (algoritmos públicos):
  * IBAN: longitud por país + dígito de control ISO 7064 (mod 97).
  * ABA Routing (EE. UU.): 9 dígitos, suma ponderada 3-7-1 múltiplo de 10.
  * CLABE (México): 18 dígitos, pesos 3-7-1 módulo 10.
  * Transit (Canadá): tránsito de 5 dígitos + institución de 3, o formato electrónico 0YYYXXXXX.
  * BSB (Australia): 6 dígitos (XXX-XXX).
Muestra además dónde va el dato en un mensaje ISO 20022 (pacs.008).
"""
from __future__ import annotations

import re

IBAN_LONGITUD = {
    "AD": 24, "AE": 23, "AT": 20, "BE": 16, "BG": 22, "BR": 29, "CH": 21, "CY": 28, "CZ": 24, "DE": 22,
    "DK": 18, "DO": 28, "EE": 20, "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27, "HR": 21, "HU": 28,
    "IE": 22, "IL": 23, "IT": 27, "LU": 20, "MT": 31, "NL": 18, "NO": 15, "PL": 28, "PT": 25, "RO": 24,
    "SA": 24, "SE": 24, "SI": 19, "SK": 24, "TR": 26, "CR": 22, "GT": 28, "SV": 28,
}
TIPOS = {
    "IBAN": "Cuenta internacional (Europa y otros)",
    "ABA": "ABA Routing de Estados Unidos",
    "CLABE": "CLABE de México",
    "TRANSIT": "Transit de Canadá",
    "BSB": "BSB de Australia",
}
ISO20022 = {
    "IBAN": "CdtrAcct/Id/IBAN",
    "ABA": "CdtrAgt/FinInstnId/ClrSysMmbId · ClrSysId/Cd = USABA",
    "CLABE": "CdtrAcct/Id/Othr/Id · SchmeNm/Prtry = CLABE",
    "TRANSIT": "CdtrAgt/FinInstnId/ClrSysMmbId · ClrSysId/Cd = CACPA",
    "BSB": "CdtrAgt/FinInstnId/ClrSysMmbId · ClrSysId/Cd = AUBSB",
}
EJEMPLOS = {"IBAN": ["DE89 3704 0044 0532 0130 00", "GB82 WEST 1234 5698 7654 31"],
            "ABA": ["011000015", "011000016"], "CLABE": ["032180000118359719", "032180000118359718"],
            "TRANSIT": ["12345-003", "1234-03"], "BSB": ["062-000", "06200"]}


def _limpio(valor: str) -> str:
    return re.sub(r"[\s-]", "", valor or "").upper()


def validar_iban(valor: str) -> list[tuple[str, bool]]:
    v = _limpio(valor)
    pais = v[:2]
    checks = [("Solo letras y números", v.isalnum()),
              ("País reconocido", pais in IBAN_LONGITUD)]
    checks.append((f"Longitud {IBAN_LONGITUD.get(pais, '?')} para {pais}", len(v) == IBAN_LONGITUD.get(pais)))
    try:
        numero = int("".join(str(int(c, 36)) for c in v[4:] + v[:4]))
        ok = numero % 97 == 1
    except ValueError:
        ok = False
    checks.append(("Dígito de control (mod 97)", ok))
    return checks


def validar_aba(valor: str) -> list[tuple[str, bool]]:
    v = _limpio(valor)
    ok_formato = v.isdigit() and len(v) == 9
    suma = sum(int(d) * p for d, p in zip(v, [3, 7, 1] * 3)) if ok_formato else 1
    return [("9 dígitos", ok_formato), ("Suma ponderada 3-7-1 múltiplo de 10", ok_formato and suma % 10 == 0)]


def validar_clabe(valor: str) -> list[tuple[str, bool]]:
    v = _limpio(valor)
    ok_formato = v.isdigit() and len(v) == 18
    ok_control = False
    if ok_formato:
        suma = sum((int(d) * p) % 10 for d, p in zip(v[:17], [3, 7, 1] * 6))
        ok_control = (10 - suma % 10) % 10 == int(v[17])
    return [("18 dígitos", ok_formato), ("Dígito de control (pesos 3-7-1)", ok_control)]


def validar_transit(valor: str) -> list[tuple[str, bool]]:
    v = (valor or "").strip()
    papel = re.fullmatch(r"\d{5}-\d{3}", v) is not None
    electronico = re.fullmatch(r"0\d{8}", v) is not None
    return [("Formato 12345-678 (tránsito-institución) o 0YYYXXXXX", papel or electronico)]


def validar_bsb(valor: str) -> list[tuple[str, bool]]:
    v = _limpio(valor)
    return [("6 dígitos (XXX-XXX)", v.isdigit() and len(v) == 6)]


VALIDADORES = {"IBAN": validar_iban, "ABA": validar_aba, "CLABE": validar_clabe,
               "TRANSIT": validar_transit, "BSB": validar_bsb}


def validar(tipo: str, valor: str) -> dict:
    checks = VALIDADORES[tipo](valor)
    return {"tipo": tipo, "valor": valor, "valida": all(ok for _, ok in checks),
            "checks": checks, "iso20022": ISO20022[tipo]}
