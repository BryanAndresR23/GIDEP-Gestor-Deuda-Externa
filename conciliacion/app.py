"""
Aplicación web local para la conciliación de deuda externa.

    python -m conciliacion.app        ->  http://127.0.0.1:5001
    (otro puerto: variable de entorno CONCILIACION_PORT)

Endpoints
    GET  /                       panel de una sola página
    POST /api/conciliar          recibe los dos reportes (en cualquier orden), concilia y guarda el periodo
    GET  /api/historial          periodos conciliados y su resumen
    GET  /api/periodo/<periodo>  detalle guardado de un periodo
    GET  /api/exportar/<periodo> descarga el Excel con semáforo

Los reportes originales solo se leen: nunca se modifican. El historial vive en
una base SQLite local (conciliacion.db) y la app solo escucha en 127.0.0.1.
"""
from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file

from . import engine

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "conciliacion.db"
EXPORTS = BASE / "reportes"

app = Flask(__name__)


def db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS periodos (
                       periodo TEXT PRIMARY KEY,
                       conciliado_en TEXT NOT NULL,
                       resultado TEXT NOT NULL)""")
    return con


def guardar(resultado: dict):
    with db() as con:
        con.execute("INSERT OR REPLACE INTO periodos VALUES (?, ?, ?)",
                    (resultado["periodo"], datetime.now().isoformat(timespec="seconds"),
                     json.dumps(resultado, ensure_ascii=False)))


def cargar(periodo: str) -> dict | None:
    with db() as con:
        fila = con.execute("SELECT resultado FROM periodos WHERE periodo = ?", (periodo,)).fetchone()
    return json.loads(fila[0]) if fila else None


@app.get("/")
def index():
    return render_template("index.html", tolerancia=engine.TOLERANCIA)


@app.post("/api/conciliar")
def api_conciliar():
    archivos = request.files.getlist("archivos")
    if len(archivos) != 2:
        return jsonify(error="Sube exactamente dos archivos: el del Banco Central y el del Ministerio."), 400
    with tempfile.TemporaryDirectory() as tmp:
        rutas = []
        for i, f in enumerate(archivos):
            ruta = Path(tmp) / f"reporte_{i}.xlsx"
            f.save(ruta)
            rutas.append(ruta)
        try:
            resultado = engine.conciliar_archivos(*rutas)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
    guardar(resultado)
    return jsonify(resultado)


@app.get("/api/historial")
def api_historial():
    with db() as con:
        filas = con.execute("SELECT periodo, conciliado_en, resultado FROM periodos ORDER BY periodo DESC").fetchall()
    return jsonify([{"periodo": p, "conciliado_en": c, **json.loads(r)["resumen"]} for p, c, r in filas])


@app.get("/api/periodo/<periodo>")
def api_periodo(periodo):
    resultado = cargar(periodo)
    return (jsonify(resultado), 200) if resultado else (jsonify(error="Periodo no encontrado"), 404)


@app.get("/api/exportar/<periodo>")
def api_exportar(periodo):
    resultado = cargar(periodo)
    if not resultado:
        return jsonify(error="Periodo no encontrado"), 404
    EXPORTS.mkdir(exist_ok=True)
    ruta = engine.exportar_excel(resultado, EXPORTS / f"Conciliacion_{periodo}.xlsx")
    return send_file(ruta, as_attachment=True)


if __name__ == "__main__":
    import os
    app.run(host="127.0.0.1", port=int(os.environ.get("CONCILIACION_PORT", "5001")), debug=False)
