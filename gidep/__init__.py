"""GIDEP (demo) — Gestor Integral de Deuda Externa Pública.

Versión pública reconstruida con datos ficticios del gestor que uso a diario. Reúne en
una sola app local los procesos de conciliación, pagos, documentos y herramientas.

    python -m gidep          ->  http://127.0.0.1:5001   (usuario demo / contraseña gidep-demo)
"""
from __future__ import annotations

import os
import secrets
import tempfile
from functools import wraps
from pathlib import Path

from flask import (Flask, flash, redirect, render_template, request, send_file, session, url_for)
from werkzeug.security import check_password_hash

from conciliacion import engine

from . import demo
from .modulos import (activaciones, agenda, archivo_quipux, centro, comprobantes, conciliacion, condonados,
                      contratos, correos, desembolsos, firma, fmi, matriz, retenciones, validacion)

MODULOS = {  # apartados que usan la plantilla genérica
    "agenda": agenda, "validacion": validacion, "desembolsos": desembolsos, "fmi": fmi,
    "archivo-quipux": archivo_quipux, "contratos": contratos, "firma": firma,
    "comprobantes": comprobantes, "condonados": condonados, "retenciones": retenciones,
}

NAV = [
    ("Inicio", [("centro", "Centro de Control", "/centro")]),
    ("Conciliación", [("conciliacion", "Conciliación de Deuda", "/conciliacion"),
                      ("condonados", "Condonados CAF", "/modulo/condonados"),
                      ("retenciones", "Retenciones CAF", "/modulo/retenciones")]),
    ("Pagos", [("agenda", "Agenda Diaria", "/modulo/agenda"),
               ("validacion", "Validación de Pagos", "/modulo/validacion"),
               ("matriz", "Matriz de Préstamos", "/matriz"),
               ("desembolsos", "Desembolsos", "/modulo/desembolsos"),
               ("fmi", "FMI · Mensajes Swift", "/modulo/fmi")]),
    ("Documentos", [("archivo-quipux", "Archivo Quipux", "/modulo/archivo-quipux"),
                    ("contratos", "Contratos Agencia Fiscal", "/modulo/contratos"),
                    ("comprobantes", "Comprobantes y ACK", "/modulo/comprobantes"),
                    ("firma", "Firma EC", "/modulo/firma")]),
    ("Herramientas", [("activaciones", "Activaciones de Cuentas", "/activaciones"),
                      ("correos", "Análisis de Correos", "/correos")]),
]


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("GIDEP_SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    )

    @app.before_request
    def acceso_automatico():
        """Solo para demos y capturas: GIDEP_AUTOLOGIN=1 entra como el usuario demo."""
        if os.environ.get("GIDEP_AUTOLOGIN") == "1" and not session.get("usuario"):
            session["usuario"] = {"usuario": "demo", "nombre": "Usuario Demo", "perfil": "Analista"}

    @app.context_processor
    def contexto():
        return {"nav": NAV, "usuario": session.get("usuario"), "hoy": demo.fmt_fecha(demo.HOY.isoformat())}

    def requiere_sesion(vista):
        @wraps(vista)
        def envoltura(*args, **kwargs):
            if not session.get("usuario"):
                return redirect(url_for("login", siguiente=request.path))
            return vista(*args, **kwargs)
        return envoltura

    # ---------------------------------------------------------------- acceso
    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            nombre = request.form.get("usuario", "").strip().lower()
            u = next((x for x in demo.cargar("usuarios") if x["usuario"] == nombre), None)
            if u and check_password_hash(u["hash"], request.form.get("clave", "")):
                session.clear()
                session["usuario"] = {"usuario": u["usuario"], "nombre": u["nombre"], "perfil": u["perfil"]}
                destino = request.args.get("siguiente", "")
                return redirect(destino if destino.startswith("/") and not destino.startswith("//") else "/centro")
            error = "Usuario o contraseña incorrectos."
        return render_template("login.html", error=error)

    @app.get("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    def inicio():
        return redirect("/centro")

    # -------------------------------------------------------------- módulos
    @app.get("/centro")
    @requiere_sesion
    def vista_centro():
        return render_template("centro.html", activo="centro", alertas=centro.alertas(),
                               agenda=agenda.pagos(), lectura=demo.ultima_lectura())

    @app.get("/modulo/<nombre>")
    @requiere_sesion
    def vista_modulo(nombre):
        if nombre not in MODULOS:
            return redirect("/centro")
        return render_template("modulo.html", activo=nombre, m=MODULOS[nombre].vista())

    @app.get("/modulo/retenciones/excel")
    @requiere_sesion
    def retenciones_excel():
        return send_file(retenciones.excel(), as_attachment=True, download_name="Retenciones_CAF_2026-03.xlsx")

    # ---------------------------------------------------------- conciliación
    @app.route("/conciliacion", methods=["GET", "POST"])
    @requiere_sesion
    def vista_conciliacion():
        if request.method == "GET" and request.args.get("ejemplo"):
            rutas = [demo.ROOT / "data" / "sample" / f"Reporte_{n}_2026-03.xlsx" for n in ("Banco_Central", "Ministerio")]
            conciliacion.guardar(session, engine.conciliar_archivos(*rutas))
        if request.method == "POST":
            archivos = request.files.getlist("archivos")
            if request.form.get("ejemplo"):
                rutas = [demo.ROOT / "data" / "sample" / f"Reporte_{n}_2026-03.xlsx" for n in ("Banco_Central", "Ministerio")]
                conciliacion.guardar(session, engine.conciliar_archivos(*rutas))
            elif len(archivos) != 2:
                flash("Sube exactamente dos reportes: el del Banco Central y el del Ministerio.")
            else:
                with tempfile.TemporaryDirectory() as tmp:
                    rutas = []
                    for i, f in enumerate(archivos):
                        ruta = Path(tmp) / f"reporte_{i}.xlsx"
                        f.save(ruta)
                        rutas.append(ruta)
                    try:
                        conciliacion.guardar(session, engine.conciliar_archivos(*rutas))
                    except ValueError as exc:
                        flash(str(exc))
                        return redirect("/conciliacion")
            return redirect("/conciliacion?tab=carteras")
        res = conciliacion.actual(session)
        tab = request.args.get("tab", "carteras" if res else "recepcion")
        oficio = conciliacion.oficio_respuesta(res, session["usuario"]["nombre"]) if res else ""
        return render_template("conciliacion.html", activo="conciliacion", res=res, tab=tab, oficio=oficio,
                               solo=request.args.get("solo") == "1", tolerancia=engine.TOLERANCIA)

    @app.get("/conciliacion/exportar")
    @requiere_sesion
    def conciliacion_exportar():
        res = conciliacion.actual(session)
        if not res:
            return redirect("/conciliacion")
        salida = demo.runtime(f"Conciliacion_{res['periodo']}.xlsx")
        engine.exportar_excel(res, salida)
        return send_file(salida, as_attachment=True)

    # -------------------------------------------------------- herramientas
    @app.route("/matriz", methods=["GET", "POST"])
    @requiere_sesion
    def vista_matriz():
        texto = request.form.get("texto", "")
        if request.method == "GET" and request.args.get("ejemplo"):
            texto = demo.texto("sgi_ejemplo.txt")
        checks, agregado = None, None
        if texto:
            datos = matriz.leer_texto(texto)
            if request.form.get("accion") == "agregar":
                agregado = matriz.agregar(datos)
            checks = matriz.chips_verificacion(matriz.verificar(datos))
        return render_template("matriz.html", activo="matriz", texto=texto, checks=checks, agregado=agregado,
                               tabla_matriz=matriz.tabla_matriz())

    @app.route("/activaciones", methods=["GET", "POST"])
    @requiere_sesion
    def vista_activaciones():
        tipo = request.values.get("tipo", "IBAN")
        valor = request.values.get("valor", "")
        resultado = activaciones.validar(tipo, valor) if valor and tipo in activaciones.VALIDADORES else None
        return render_template("activaciones.html", activo="activaciones", tipos=activaciones.TIPOS,
                               ejemplos=activaciones.EJEMPLOS, tipo=tipo, valor=valor, r=resultado)

    @app.route("/correos", methods=["GET", "POST"])
    @requiere_sesion
    def vista_correos():
        correo = request.values.get("correo", "")
        sugerencia = None
        if request.form.get("accion") == "aprobar":
            correos.aprobar(request.form.get("asunto", ""), correo, request.form.get("respuesta", ""),
                            int(request.form["ejemplo_id"]) if request.form.get("ejemplo_id") else None)
            flash("Respuesta guardada como nuevo ejemplo aprobado.")
            return redirect("/correos")
        if correo:
            sugerencia = correos.sugerir(correo)
        return render_template("correos.html", activo="correos", correo=correo, s=sugerencia, base=correos.base())

    return app
