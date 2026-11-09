"""Pruebas del gestor GIDEP (demo): acceso, pantallas y reglas de cada apartado.

    python scripts/generate_sample_data.py && python scripts/generate_demo_data.py
    python -m unittest discover -s tests -v
"""
import tempfile
import unittest
from datetime import date
from pathlib import Path

from gidep import NAV, create_app, demo
from gidep.modulos import (activaciones, agenda, archivo_quipux, comprobantes, contratos, correos, desembolsos,
                           firma, fmi, matriz, validacion)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        demo.RUNTIME = Path(self.tmp.name)              # lo que escribe la demo va a una carpeta temporal
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def entrar(self, usuario="demo", clave="gidep-demo"):
        return self.client.post("/login", data={"usuario": usuario, "clave": clave})


class AccesoTest(Base):
    def test_sin_sesion_redirige_al_login(self):
        r = self.client.get("/modulo/agenda")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_clave_incorrecta(self):
        self.assertIn("incorrectos", self.entrar(clave="mala").get_data(as_text=True))

    def test_todas_las_pantallas_responden(self):
        self.entrar()
        for _, items in NAV:
            for clave, nombre, url in items:
                with self.subTest(apartado=nombre):
                    r = self.client.get(url)
                    self.assertEqual(r.status_code, 200)
                    self.assertIn(nombre.split(" ")[0], r.get_data(as_text=True))

    def test_cookie_de_sesion_protegida(self):
        self.assertTrue(self.app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertEqual(self.app.config["SESSION_COOKIE_SAMESITE"], "Lax")


class ConciliacionTest(Base):
    def test_regla_de_sesion_y_flujo_completo(self):
        self.entrar()
        vacio = self.client.get("/conciliacion?tab=carteras").get_data(as_text=True)
        self.assertIn("Regla de sesión", vacio)
        self.client.post("/conciliacion", data={"ejemplo": "1"})
        carteras = self.client.get("/conciliacion?tab=carteras").get_data(as_text=True)
        self.assertIn("Periodo 2026-03", carteras)
        oficio = self.client.get("/conciliacion?tab=oficio").get_data(as_text=True)
        self.assertIn("Pago directo", oficio)
        with self.client.get("/conciliacion/exportar") as r:
            self.assertEqual(r.status_code, 200)


class ReglasTest(Base):
    def test_agenda_prioriza_fecha_de_debito_y_no_adivina(self):
        estados = {o["oficio"]: o["estado"] for o in agenda.pagos()}
        self.assertEqual(estados["MF-SFP-2026-0103-O"], "Para hoy")      # fecha valor +2, débito hoy
        self.assertEqual(estados["MF-SFP-2026-0101-O"], "En proceso")    # hoy y ya registrado
        self.assertEqual(estados["MF-SFP-2026-0106-O"], "Vencido")
        self.assertEqual(estados["MF-SFP-2026-0110-O"], "Por revisar")   # sin préstamo identificado

    def test_validacion_de_pagos(self):
        res = {r["prestamo"]: r["estado"] for r in validacion.resultados()}
        self.assertEqual(res["PR-5120"], "Correcto")
        self.assertEqual(res["PR-3308"], "Revisar")          # diferencia menor
        self.assertEqual(res["PR-2291"], "Con errores")      # fecha del comprobante en EUR
        self.assertEqual(res["PR-8150"], "Con errores")      # corresponsal equivocado
        self.assertEqual(res["PR-9001"], "Con errores")      # cambio de fecha sin correo

    def test_regla_de_fechas_por_moneda(self):
        viernes, lunes = date(2026, 3, 13), date(2026, 3, 16)
        self.assertEqual(validacion.fecha_comprobante_esperada(lunes, "USD"), lunes)
        self.assertEqual(validacion.fecha_comprobante_esperada(lunes, "EUR"), date(2026, 3, 12))
        self.assertEqual(validacion.fecha_comprobante_esperada(lunes, "JPY"), date(2026, 3, 11))
        self.assertEqual(validacion.dias_habiles_antes(viernes, 1), date(2026, 3, 12))

    def test_desembolsos(self):
        res = {r["mensaje"]: r["estado"] for r in desembolsos.resultados()}
        self.assertEqual(res["SW-IN-0001"], "Por archivar")
        self.assertEqual(res["SW-IN-0003"], "Revisar")       # FIDA sin préstamo en el mensaje
        self.assertEqual(res["SW-IN-0006"], "Descartado")    # pago comercial

    def test_fmi(self):
        res = {r["texto"][:20]: (r["proceso"], r["estado"]) for r in fmi.resultados()}
        self.assertEqual(res["GRA CHARGES AND INTE"], ("Intereses y comisiones", "Archivado"))
        self.assertEqual(res["REPURCHASE PRINCIPAL"], ("Recompras", "Por archivar"))
        self.assertEqual(res["STATEMENT OF ACCOUNT"][1], "Revisar")

    def test_archivo_quipux(self):
        res = {r["archivo"]: r["estado"] for r in archivo_quipux.procesar()}
        self.assertEqual(res["Oficio_MF-SFP-2026-0131-O.pdf"], "Archivado")
        self.assertEqual(res["estado_cuenta_marzo.pdf"], "Archivado")         # vinculado al único oficio del lote
        self.assertEqual(res["Memorando_capacitacion.pdf"], "Ignorado")
        self.assertEqual(res["Oficio_MF-SFP-2026-0150-O.pdf"], "Por revisar")
        self.assertEqual(res["estado_cuenta_feb.pdf"], "Histórico protegido")
        self.assertEqual(res["Oficio_MF-SFP-2026-0131-O (1).pdf"], "Duplicado")

    def test_contratos(self):
        res = {r["archivo"]: r for r in contratos.resultados()}
        self.assertEqual(res["BC-OF-2026-0712.pdf"]["estado"], "Archivado")
        self.assertTrue(res["BC-OF-2026-0712.pdf"]["ruta"].endswith("BC-OF-2026-0712 (Envío Borrador Contrato).pdf"))
        self.assertEqual(res["BC-OF-2026-0725-TEMP.pdf"]["estado"], "Excluido")
        self.assertEqual(res["BC-MEM-2026-0098.pdf"]["estado"], "Excluido")
        self.assertEqual(res["BC-OF-2026-0730.pdf"]["estado"], "Por revisar")

    def test_firma(self):
        estados = [r["estado"] for r in firma.resultados()]
        for e in ("Por firmar", "Listo para copiar", "Ya archivado", "Conflicto"):
            self.assertIn(e, estados)

    def test_comprobantes(self):
        res = {r["archivo"]: r["estado"] for r in comprobantes.resultados()}
        self.assertEqual(res["CC-2026-00141.pdf"], "Listo para archivar")
        self.assertEqual(res["CC-2026-00142.pdf"], "Revisar")
        self.assertEqual(res["CC-2026-00144.pdf"], "Esperando ACK")       # no se archiva por suposición
        self.assertEqual(res["CC-2026-00145.pdf"], "Transferencia interna")

    def test_validadores_de_cuentas(self):
        for tipo, (valido, invalido) in activaciones.EJEMPLOS.items():
            with self.subTest(tipo=tipo):
                self.assertTrue(activaciones.validar(tipo, valido)["valida"])
                self.assertFalse(activaciones.validar(tipo, invalido)["valida"])

    def test_matriz_agrega_y_evita_duplicados(self):
        datos = matriz.leer_texto(demo.texto("sgi_ejemplo.txt"))
        self.assertTrue(all(ok for _, ok, _ in matriz.verificar(datos)))
        self.assertTrue(matriz.agregar(datos))
        self.assertFalse(matriz.agregar(datos))            # segunda vez: referencia duplicada

    def test_correos_sugiere_y_aprende(self):
        s = correos.sugerir("El acreedor cambia la fecha valor del pago al siguiente día hábil")
        self.assertEqual(s["ejemplo"]["asunto"], "Cambio de fecha valor")
        antes = len(correos.base())
        correos.aprobar("Nuevo caso", "texto", "respuesta", s["ejemplo"]["id"])
        self.assertEqual(len(correos.base()), antes + 1)


if __name__ == "__main__":
    unittest.main()
