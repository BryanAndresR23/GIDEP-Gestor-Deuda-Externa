"""Análisis de respuestas de correos: sugiere una respuesta a partir de ejemplos aprobados.

Trabaja solo con una base local de respuestas revisadas: no inventa criterios y no envía
el contenido a servicios externos. La similitud es un coseno sobre las palabras del
correo (sin tildes ni palabras vacías). Cada respuesta final aprobada se guarda como
nuevo ejemplo y se cuenta cuántas veces se usó cada uno.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter

from ..demo import cargar, runtime

VACIAS = set("""a al algo como con de del el en es esta este ha la las le lo los mas me mi no o para pero por
que se si sin su sus un una unos y ya favor solicitamos solicito estimados saludos gracias hoy""".split())


def palabras(texto: str) -> Counter:
    t = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return Counter(w for w in re.findall(r"[a-z0-9]+", t) if w not in VACIAS and len(w) > 2)


def similitud(a: Counter, b: Counter) -> float:
    comunes = set(a) & set(b)
    num = sum(a[w] * b[w] for w in comunes)
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return num / den if den else 0.0


def base() -> list[dict]:
    ruta = runtime("correos.json")
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return [dict(e) for e in cargar("correos")]


def _guardar(ejemplos):
    runtime("correos.json").write_text(json.dumps(ejemplos, ensure_ascii=False, indent=2), encoding="utf-8")


def sugerir(correo: str, ejemplos: list[dict] | None = None) -> dict | None:
    ejemplos = base() if ejemplos is None else ejemplos
    consulta = palabras(correo)
    puntajes = sorted(((similitud(consulta, palabras(e["asunto"] + " " + e["correo"])), e) for e in ejemplos),
                      key=lambda x: x[0], reverse=True)
    if not puntajes or puntajes[0][0] < 0.15:
        return None
    score, mejor = puntajes[0]
    return {"ejemplo": mejor, "similitud": round(score * 100), "alternativas": [
        {"asunto": e["asunto"], "similitud": round(s * 100)} for s, e in puntajes[1:3] if s >= 0.1]}


def aprobar(asunto: str, correo: str, respuesta: str, ejemplo_usado: int | None = None):
    ejemplos = base()
    if ejemplo_usado:
        for e in ejemplos:
            if e["id"] == ejemplo_usado:
                e["usos"] += 1
    ejemplos.append({"id": max(e["id"] for e in ejemplos) + 1, "asunto": asunto or "Respuesta aprobada",
                     "correo": correo, "respuesta": respuesta, "usos": 0})
    _guardar(ejemplos)
