"""Pruebas del motor de conciliación con los reportes ficticios de data/sample.

    python scripts/generate_sample_data.py
    python -m unittest discover -s tests -v
"""
import unittest
from pathlib import Path

from openpyxl import load_workbook

from conciliacion import engine

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"
BANCO_MAR = SAMPLE / "Reporte_Banco_Central_2026-03.xlsx"
MIN_MAR = SAMPLE / "Reporte_Ministerio_2026-03.xlsx"
BANCO_FEB = SAMPLE / "Reporte_Banco_Central_2026-02.xlsx"
MIN_FEB = SAMPLE / "Reporte_Ministerio_2026-02.xlsx"


class AliasTest(unittest.TestCase):
    def test_nombre_largo_con_sigla(self):
        self.assertEqual(engine.acreedor("CORPORACIÓN ANDINA DE FOMENTO - CAF"), "CAF")

    def test_sub_prestamista_se_agrupa(self):
        self.assertEqual(engine.acreedor("EXIMBANK ORIENTE - EXIM"), "GOBIERNOS")
        self.assertEqual(engine.acreedor("OTROS"), "BANCOS")

    def test_palabra_clave(self):
        self.assertEqual(engine.acreedor("BONOS SOBERANOS 2030"), "BONOS")


class ConciliacionTest(unittest.TestCase):
    def test_febrero_cuadra_con_redondeos_dentro_de_tolerancia(self):
        res = engine.conciliar_archivos(BANCO_FEB, MIN_FEB)
        self.assertEqual(res["periodo"], "2026-02")
        self.assertEqual(res["resumen"]["diferencias"], 0)

    def test_marzo_detecta_las_tres_diferencias_sembradas(self):
        res = engine.conciliar_archivos(MIN_MAR, BANCO_MAR)        # orden inverso a propósito
        difs = {(f["acreedor"], f["concepto"]): f["diferencia"]
                for f in res["filas"] if f["estado"] == "DIFERENCIA"}
        self.assertEqual(difs, {("CAF", "Desembolsos"): 1_250_000.00,
                                ("FIDA", "Intereses"): 1_843.27,
                                ("BANCOS", "Amortizaciones"): -15_000.00})

    def test_diagnostico_clasifica_por_observacion(self):
        res = engine.conciliar_archivos(BANCO_MAR, MIN_MAR)
        tipos = {d["acreedor"]: d["tipo"] for d in res["diagnostico"]}
        self.assertEqual(tipos, {"CAF": "Pago directo", "FIDA": "Diferencial cambiario",
                                 "BANCOS": "Por revisar"})

    def test_no_se_usa_el_subtotal_padre(self):
        ministerio, _ = engine.leer_ministerio(MIN_MAR)
        self.assertIn("MULTILATERAL", ministerio)                  # existe en el reporte...
        res = engine.conciliar_archivos(BANCO_MAR, MIN_MAR)
        self.assertNotIn("MULTILATERAL", {f["acreedor"] for f in res["filas"]})   # ...pero no se concilia

    def test_columnas_se_ubican_por_titulo(self):
        """Marzo trae 'Condonado' antes que 'Mora' (en febrero va después) y aun así cuadra."""
        ws = load_workbook(BANCO_MAR)["Giros al Exterior"]
        titulos = [c.value for c in ws[4]]
        self.assertLess(titulos.index("Condonado (USD)"), titulos.index("Interés Mora (USD)"))
        res = engine.conciliar_archivos(BANCO_MAR, MIN_MAR)
        condonados = [f for f in res["filas"] if f["concepto"] == "Intereses Condonados"]
        self.assertTrue(condonados and all(f["estado"] == "CONCILIADO" for f in condonados))


if __name__ == "__main__":
    unittest.main()
