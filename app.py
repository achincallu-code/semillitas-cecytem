from __future__ import annotations

import csv
import io
import json
import os
import random
import secrets
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


class _HybridRow(dict[str, Any]):
    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class _PostgresCursor:
    def __init__(self, cursor: Any):
        self._cursor = cursor

    def fetchone(self) -> _HybridRow | None:
        row = self._cursor.fetchone()
        return _HybridRow(row) if row is not None else None

    def fetchall(self) -> list[_HybridRow]:
        return [_HybridRow(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class _PostgresConnection:
    def __init__(self, connection: Any):
        self._connection = connection

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> _PostgresCursor:
        ignore_conflicts = "INSERT OR IGNORE INTO" in query
        query = query.replace("INSERT OR IGNORE INTO", "INSERT INTO")
        query = query.replace(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
            "SELECT * FROM users WHERE LOWER(username) = LOWER(?)",
        )
        query = query.replace("MIN(5, 1 + (? / 3))", "LEAST(5, 1 + (? / 3))")
        query = query.replace("?", "%s")
        if ignore_conflicts:
            query = f"{query.rstrip().rstrip(';')} ON CONFLICT DO NOTHING"
        return _PostgresCursor(self._connection.execute(query, params))

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        self._connection.close()


ROOT = Path(__file__).resolve().parent
LEGACY_USERS_FILE = ROOT / "usuarios_kinder.json"
AVATARS = ["🐾", "🦁", "🐯", "🐵", "🐘", "🦓", "🦒", "🦊", "🦝"]
MEDALS = {"oro": 0, "plata": 0, "bronce": 0, "otros": 0}
STICKERS = [
    {"id": 1, "name": "Jaguar Dorado", "emoji": "🐆", "cost": 10},
    {"id": 2, "name": "Tucán Arcoíris", "emoji": "🦜", "cost": 15},
    {"id": 3, "name": "Mono Araña", "emoji": "🐒", "cost": 20},
    {"id": 4, "name": "Caimán del Río", "emoji": "🐊", "cost": 25},
    {"id": 5, "name": "Danta Valiente", "emoji": "🦣", "cost": 30},
]

THEMES = {
    "selva": {"name": "🌿 Selva Original", "background": "#204333", "background_image": 'linear-gradient(130deg, rgba(5, 28, 23, .42), rgba(7, 42, 30, .32)), url("/media/Selva3.png")', "primary": "#42a85e", "accent": "#ffd166", "bar": "#14583a", "ink": "#f3ffdc", "surface": "rgba(8, 48, 34, .84)", "surface_soft": "rgba(20, 88, 58, .78)", "line": "rgba(204, 244, 163, .32)", "muted": "#d4e5cf", "glass": "rgba(8, 48, 34, .82)", "glass_strong": "rgba(8, 48, 34, .9)", "glass_border": "rgba(204, 244, 163, .32)"},
    "selva_dia": {"name": "🌅 Selva de Día", "background": "#fffaf0", "primary": "#286b43", "accent": "#e9893f", "bar": "#fffdf9", "ink": "#26352c", "surface": "#ffffff", "surface_soft": "#f4f7ef", "line": "#e6ebdf", "muted": "#718078", "glass": "rgba(255, 255, 255, .92)", "glass_strong": "rgba(255, 255, 255, .97)", "glass_border": "rgba(255, 255, 255, .8)"},
    "selva_noche": {"name": "🌙 Selva de Noche", "background": "#171d2b", "primary": "#49bb78", "accent": "#ff8c69", "bar": "#20293a", "ink": "#e8eaf6", "surface": "#242d3e", "surface_soft": "#303a4d", "line": "#414d60", "muted": "#b7c0cc", "glass": "rgba(21, 31, 45, .88)", "glass_strong": "rgba(29, 42, 58, .96)", "glass_border": "rgba(228, 238, 241, .3)"},
    "oceano": {"name": "🌊 Océano Azul", "background": "#edf8fc", "primary": "#0277bd", "accent": "#00a5bd", "bar": "#ffffff", "ink": "#123c52", "surface": "#ffffff", "surface_soft": "#e9f5f8", "line": "#d8e9ee", "muted": "#637e88", "glass": "rgba(246, 253, 255, .92)", "glass_strong": "rgba(255, 255, 255, .97)", "glass_border": "rgba(255, 255, 255, .82)"},
    "bosque_enchantado": {"name": "🧚 Bosque Encantado", "background": "#f5f0fb", "primary": "#7b1fa2", "accent": "#e05c8d", "bar": "#ffffff", "ink": "#3e2451", "surface": "#ffffff", "surface_soft": "#f1eafb", "line": "#e8dff1", "muted": "#776681", "glass": "rgba(253, 249, 255, .92)", "glass_strong": "rgba(255, 255, 255, .97)", "glass_border": "rgba(255, 255, 255, .82)"},
    "desierto": {"name": "🏜️ Desierto Dorado", "background": "#fff8ed", "primary": "#bd6b16", "accent": "#d98a20", "bar": "#ffffff", "ink": "#563b1e", "surface": "#ffffff", "surface_soft": "#fbf0df", "line": "#eee0cb", "muted": "#89755c", "glass": "rgba(255, 251, 243, .93)", "glass_strong": "rgba(255, 255, 255, .97)", "glass_border": "rgba(255, 255, 255, .84)"},
    "montanas": {"name": "⛰️ Montañas Nevadas", "background": "#f0f7fc", "primary": "#0369a1", "accent": "#0284c7", "bar": "#ffffff", "ink": "#164e63", "surface": "#ffffff", "surface_soft": "#eaf4fb", "line": "#dbe8f0", "muted": "#657e8c", "glass": "rgba(247, 252, 255, .93)", "glass_strong": "rgba(255, 255, 255, .97)", "glass_border": "rgba(255, 255, 255, .84)"},
    "arcoiris": {"name": "🌈 Arcoíris Mágico", "background": "#fff3f8", "primary": "#cf277e", "accent": "#d4a000", "bar": "#ffffff", "ink": "#5e2050", "surface": "#ffffff", "surface_soft": "#fbeaf3", "line": "#f1dce8", "muted": "#856777", "glass": "rgba(255, 249, 252, .93)", "glass_strong": "rgba(255, 255, 255, .97)", "glass_border": "rgba(255, 255, 255, .84)"},
}

GAME_CATALOG = [
    {"id": "colores", "title": "Colores", "icon": "🎨", "level": 1, "mode": "quiz", "description": "Identifica los colores."},
    {"id": "numeros", "title": "Números del 1 al 10", "icon": "🔢", "level": 1, "mode": "quiz", "description": "Cuenta estrellas y números."},
    {"id": "formas", "title": "Formas", "icon": "🔺", "level": 1, "mode": "quiz", "description": "Reconoce figuras geométricas."},
    {"id": "letras", "title": "Letras", "icon": "🔤", "level": 1, "mode": "quiz", "description": "Relaciona animales con su letra inicial."},
    {"id": "burbujas_animales", "title": "Animales", "icon": "🐾", "level": 1, "mode": "quiz", "description": "Conoce animales de la selva."},
    {"id": "sonidos_animales", "title": "Sonidos de animales", "icon": "🔊", "level": 1, "mode": "quiz", "description": "Escucha y adivina quién hace ese sonido."},
    {"id": "dibuja_vocales", "title": "Dibuja vocales", "icon": "✏️", "level": 1, "mode": "draw", "description": "Traza las cinco vocales en el lienzo."},
    {"id": "sumas", "title": "Sumas", "icon": "➕", "level": 2, "mode": "quiz", "description": "Resuelve sumas sencillas."},
    {"id": "restas", "title": "Restas", "icon": "➖", "level": 2, "mode": "quiz", "description": "Resuelve restas sencillas."},
    {"id": "vocales", "title": "Vocales", "icon": "🗣️", "level": 2, "mode": "quiz", "description": "Encuentra la vocal inicial."},
    {"id": "formas_avanzadas", "title": "Formas avanzadas", "icon": "💎", "level": 2, "mode": "quiz", "description": "Reconoce figuras y sus propiedades."},
    {"id": "animales_selva", "title": "Animales de la selva", "icon": "🦁", "level": 2, "mode": "quiz", "description": "Aprende sobre animales salvajes."},
    {"id": "lavarse_manos", "title": "Lavarse las manos", "icon": "🧼", "level": 2, "mode": "lesson", "description": "Aprende los pasos para lavarte las manos."},
    {"id": "memorama", "title": "Memorama", "icon": "🧠", "level": 2, "mode": "memory", "description": "Encuentra las parejas de animales."},
    {"id": "ingles_colores", "title": "Colores en inglés", "icon": "🇬🇧", "level": 3, "mode": "quiz", "description": "Relaciona los colores con sus nombres en inglés."},
    {"id": "mayor_menor", "title": "Mayor o menor", "icon": "⚖️", "level": 3, "mode": "quiz", "description": "Compara cantidades y números."},
    {"id": "completar", "title": "Completar palabras", "icon": "🧩", "level": 3, "mode": "quiz", "description": "Completa palabras de animales."},
    {"id": "numeros_20", "title": "Números del 11 al 20", "icon": "🔢", "level": 3, "mode": "quiz", "description": "Cuenta hasta veinte."},
    {"id": "emociones", "title": "Emociones", "icon": "🎭", "level": 3, "mode": "quiz", "description": "Reconoce cómo se sienten los personajes."},
    {"id": "reloj", "title": "El reloj", "icon": "⏰", "level": 3, "mode": "quiz", "description": "Lee la hora en punto."},
    {"id": "lavar_dientes", "title": "Lávate los dientes", "icon": "🦷", "level": 3, "mode": "lesson", "description": "Sigue los pasos para cuidar tu sonrisa."},
    {"id": "rompecabezas", "title": "Rompecabezas", "icon": "🧩", "level": 0, "mode": "puzzle", "description": "Arma imágenes del mundo natural."},
    {"id": "encuentra_jaguar", "title": "Encuentra al jaguar", "icon": "🐆", "level": 0, "mode": "find", "description": "Busca al jaguar y usa las pistas."},
    {"id": "explota_globos", "title": "Explota globos", "icon": "🎈", "level": 0, "mode": "balloons", "description": "Atrapa los globos que aparecen."},
    {"id": "pintura_libre", "title": "Pintura libre", "icon": "🎨", "level": 0, "mode": "paint", "description": "Crea tu propia obra de arte."},
    {"id": "simon", "title": "Simón dice", "icon": "🎵", "level": 0, "mode": "simon", "description": "Memoriza y repite la secuencia."},
    {"id": "whack", "title": "Atrapa al topo", "icon": "🔨", "level": 0, "mode": "whack", "description": "Toca al topo cuando aparezca."},
    {"id": "sombras", "title": "Sombras misteriosas", "icon": "🌑", "level": 0, "mode": "quiz", "description": "Adivina el animal por su sombra."},
    {"id": "cazar_frutas", "title": "Caza de frutas", "icon": "🍎", "level": 0, "mode": "catch", "description": "Atrapa las frutas que caen."},
]

ANIMALS = [
    ("PERRO", "🐶"), ("GATO", "🐱"), ("CONEJO", "🐰"), ("OSO", "🐻"), ("RANA", "🐸"),
    ("LEÓN", "🦁"), ("TIGRE", "🐯"), ("MONO", "🐵"), ("ELEFANTE", "🐘"), ("CEBRA", "🦓"),
]
SOUND_ANIMALS = [
    ("GATO", "🐱", "gato.mp3"), ("PERRO", "🐶", "perro.mp3"), ("VACA", "🐄", "vaca.mp3"),
    ("OVEJA", "🐑", "oveja.mp3"), ("PATO", "🦆", "pato.mp3"), ("AVE", "🐦", "ave.mp3"),
]
COLORS = [("ROJO", "red", "🔴"), ("AZUL", "blue", "#1976d2", "🔵"), ("VERDE", "green", "#2e7d32", "🟢"), ("AMARILLO", "yellow", "#f9a825", "🟡"), ("MORADO", "purple", "#7b1fa2", "🟣")]
SHAPES = [("CÍRCULO", "⚪"), ("CUADRADO", "🟦"), ("TRIÁNGULO", "🔺"), ("RECTÁNGULO", "🟪"), ("ÓVALO", "🥚")]
EMOTIONS = [("FELIZ", "😊"), ("TRISTE", "😢"), ("ENOJADO", "😠"), ("SORPRENDIDO", "😲")]
HAND_STEPS = [
    ("Moja tus manos", "💧", "Abre la llave y moja tus manos con agua tibia."),
    ("Aplica jabón", "🧼", "Pon un poco de jabón en tus manos."),
    ("Frota bien", "🤲", "Frota las palmas, el dorso y entre los dedos."),
    ("Enjuaga", "💦", "Enjuaga hasta quitar todo el jabón."),
    ("Seca tus manos", "🧻", "Usa una toalla limpia o papel."),
]
NESTED_MEDIA = {"cn/arbol.png", "cn/girasol.png", "cn/flores.png"}
TEETH_STEPS = [
    ("Humedece el cepillo", "💧", "Pon el cepillo bajo el agua."),
    ("Aplica pasta dental", "🪥", "Coloca una pequeña cantidad de pasta."),
    ("Cepilla por fuera", "😁", "Cepilla suavemente la parte exterior."),
    ("Cepilla por dentro", "🦷", "No olvides la parte interior y las muelas."),
    ("Enjuaga", "💦", "Enjuaga tu boca y limpia el cepillo."),
]


def _choice_question(prompt: str, answer: str, options: list[str], visual: str = "", **extra: Any) -> dict[str, Any]:
    choices = list(dict.fromkeys([str(answer), *(str(option) for option in options)]))
    random.shuffle(choices)
    return {"prompt": prompt, "answer": str(answer), "options": choices, "visual": visual, **extra}


def build_questions(game_id: str) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for _ in range(5):
        if game_id == "colores":
            label, css_color, *rest = random.choice(COLORS)
            questions.append(_choice_question("¿De qué color es el recuadro?", label, [item[0] for item in COLORS], css_color, visual_type="color"))
        elif game_id in {"numeros", "numeros_20"}:
            low, high = (1, 10) if game_id == "numeros" else (11, 20)
            number = random.randint(low, high)
            options = [str(n) for n in range(low, high + 1) if n != number]
            questions.append(_choice_question("¿Cuántas estrellas ves?", str(number), random.sample(options, min(3, len(options))), "⭐ " * number, visual_type="stars"))
        elif game_id in {"formas", "formas_avanzadas"}:
            shape, emoji = random.choice(SHAPES if game_id == "formas_avanzadas" else SHAPES[:3])
            questions.append(_choice_question("¿Qué figura geométrica es?", shape, [item[0] for item in SHAPES], emoji, visual_type="emoji"))
        elif game_id == "letras":
            letters = [("ABEJA", "🐝"), ("BALLENA", "🐋"), ("CEBRA", "🦓"), ("DELFÍN", "🐬"), ("ELEFANTE", "🐘"), ("FOCA", "🦭")]
            word, emoji = random.choice(letters)
            answer = word[0]
            questions.append(_choice_question(f"¿Con qué letra empieza {word.lower()}?", answer, list("ABCDEF"), emoji, visual_type="emoji"))
        elif game_id in {"burbujas_animales", "animales_selva"}:
            word, emoji = random.choice(ANIMALS)
            questions.append(_choice_question("¿Qué animal aparece?", word, [animal[0] for animal in ANIMALS], emoji, visual_type="emoji"))
        elif game_id == "sonidos_animales":
            animal, emoji, sound = random.choice(SOUND_ANIMALS)
            questions.append(_choice_question("Escucha el sonido y elige el animal.", animal, [item[0] for item in SOUND_ANIMALS], emoji, sound=sound, visual_type="sound"))
        elif game_id == "sumas":
            a, b = random.randint(1, 10), random.randint(1, 10)
            answer = a + b
            questions.append(_choice_question(f"¿Cuánto es {a} + {b}?", str(answer), [str(max(0, answer + delta)) for delta in (-3, -1, 1, 3)], "➕", visual_type="emoji"))
        elif game_id == "restas":
            a = random.randint(5, 20)
            b = random.randint(1, a)
            answer = a - b
            questions.append(_choice_question(f"¿Cuánto es {a} − {b}?", str(answer), [str(max(0, answer + delta)) for delta in (-3, -1, 1, 3)], "➖", visual_type="emoji"))
        elif game_id == "vocales":
            word, emoji = random.choice([("ARDILLA", "🐿️"), ("ELEFANTE", "🐘"), ("IGUANA", "🦎"), ("OSO", "🐻"), ("URRACA", "🐦")])
            questions.append(_choice_question(f"¿Con qué vocal empieza {word.lower()}?", word[0], list("AEIOU"), emoji, visual_type="emoji"))
        elif game_id == "ingles_colores":
            label, color, *_ = random.choice(COLORS)
            english = {"ROJO": "RED", "AZUL": "BLUE", "VERDE": "GREEN", "AMARILLO": "YELLOW", "MORADO": "PURPLE"}[label]
            questions.append(_choice_question(f"¿Cómo se dice {label.lower()} en inglés?", english, ["RED", "BLUE", "GREEN", "YELLOW", "PURPLE"], color, visual_type="color"))
        elif game_id == "mayor_menor":
            a, b = random.sample(range(1, 21), 2)
            answer = str(max(a, b))
            questions.append(_choice_question(f"¿Cuál número es mayor: {a} o {b}?", answer, [str(a), str(b)], "⚖️", visual_type="emoji"))
        elif game_id == "completar":
            word, emoji = random.choice([("JAGUAR", "🐆"), ("TIGRE", "🐯"), ("MONO", "🐵"), ("LEÓN", "🦁"), ("PATO", "🦆")])
            pos = random.randrange(len(word))
            answer = word[pos]
            shown = word[:pos] + "_" + word[pos + 1:]
            questions.append(_choice_question(f"¿Qué letra falta en {shown}?", answer, list(set(word)) + list("AEIOU"), emoji, visual_type="emoji"))
        elif game_id == "emociones":
            emotion, emoji = random.choice(EMOTIONS)
            scenario = {"FELIZ": "recibió una sorpresa bonita", "TRISTE": "perdió su juguete favorito", "ENOJADO": "alguien rompió su dibujo", "SORPRENDIDO": "vio un arcoíris de muchos colores"}[emotion]
            questions.append(_choice_question(f"¿Cómo se siente quien {scenario}?", emotion, [item[0] for item in EMOTIONS], emoji, visual_type="emoji"))
        elif game_id == "reloj":
            hour = random.randint(1, 12)
            questions.append(_choice_question("¿Qué hora marca el reloj?", f"{hour}:00", [f"{n}:00" for n in range(1, 13) if n != hour][:5], str(hour), visual_type="clock"))
        elif game_id == "sombras":
            animal, emoji = random.choice(ANIMALS)
            questions.append(_choice_question("¿Qué animal se esconde en esta sombra?", animal, [item[0] for item in ANIMALS], emoji, visual_type="shadow"))
    return questions


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return default


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _public_question(question: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in question.items() if key != "answer"}


def _record_event(db: Any, username: str, event: str) -> None:
    db.execute(
        "INSERT INTO events (username, event, created_at) VALUES (?, ?, ?)",
        (username, event[:200], _utc_now()),
    )


def _ensure_csrf_token() -> str:
    token = session.get("_csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
    return token


def _user() -> Any | None:
    user_id = session.get("user_id")
    if user_id is None:
        return None
    db = get_db()
    return db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def _require_user() -> Any:
    user = _user()
    if user is None:
        abort(401)
    return user


def _require_teacher() -> Any:
    user = _require_user()
    if user["role"] != "docente":
        abort(403)
    return user


def _award_medal(db: Any, user_id: int, score: int) -> str | None:
    medal = "oro" if score == 5 else "plata" if score == 4 else "bronce" if score == 3 else None
    if medal:
        db.execute(f"UPDATE users SET medal_{medal} = medal_{medal} + 1 WHERE id = ?", (user_id,))
        total_medals = db.execute(
            "SELECT medal_oro + medal_plata + medal_bronce FROM users WHERE id = ?", (user_id,)
        ).fetchone()[0]
        db.execute("UPDATE users SET tree_level = MIN(5, 1 + (? / 3)) WHERE id = ?", (total_medals, user_id))
    return medal


def _legacy_users(db: Any, app: Flask) -> None:
    if not LEGACY_USERS_FILE.is_file():
        return
    try:
        legacy = json.loads(LEGACY_USERS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        app.logger.warning("No se pudieron leer las cuentas existentes; se conservará el archivo original.")
        return
    if not isinstance(legacy, dict):
        app.logger.warning("El archivo de cuentas anterior no tiene el formato esperado; no se modificó.")
        return
    for username, record in legacy.items():
        if not isinstance(username, str) or not username.strip() or not isinstance(record, dict):
            continue
        password = record.get("password")
        if not isinstance(password, str) or not password:
            continue
        medals = record.get("medallas") if isinstance(record.get("medallas"), dict) else {}
        role = "docente" if record.get("tipo") == "docente" else "estudiante"
        theme = record.get("tema_preferido", "selva_dia")
        if theme not in THEMES:
            theme = "selva_dia"
        album = record.get("album", [])
        if not isinstance(album, list):
            album = []
        try:
            total_time = max(0, float(record.get("tiempo_total", 0) or 0))
        except (TypeError, ValueError):
            total_time = 0
        db.execute(
            """INSERT OR IGNORE INTO users
               (username, password_hash, role, points, errors, total_time, attempts,
                avatar, medal_oro, medal_plata, medal_bronce, medal_otros,
                album_json, theme, tree_level, gender, tutorial_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                username.strip()[:40],
                generate_password_hash(password),
                role,
                _safe_int(record.get("puntos")),
                _safe_int(record.get("errores")),
                total_time,
                _safe_int(record.get("intentos_totales")),
                record.get("avatar") if record.get("avatar") in AVATARS else "🐾",
                _safe_int(medals.get("oro")),
                _safe_int(medals.get("plata")),
                _safe_int(medals.get("bronce")),
                _safe_int(medals.get("otros")),
                json.dumps(album, ensure_ascii=False),
                theme,
                min(5, max(1, _safe_int(record.get("arbol_dino_nivel"), 1))),
                str(record.get("genero", "otro"))[:20],
                int(bool(record.get("tutorial_visto", False))),
            ),
        )
    db.commit()


def _integrity_error_types() -> tuple[type[BaseException], ...]:
    if current_app.config.get("DATABASE_URL"):
        import psycopg

        return (psycopg.IntegrityError,)
    return (sqlite3.IntegrityError,)


def _init_database(app: Flask) -> None:
    schema = """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('estudiante', 'docente')),
                points INTEGER NOT NULL DEFAULT 0,
                errors INTEGER NOT NULL DEFAULT 0,
                total_time REAL NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0,
                avatar TEXT NOT NULL DEFAULT '🐾',
                medal_oro INTEGER NOT NULL DEFAULT 0,
                medal_plata INTEGER NOT NULL DEFAULT 0,
                medal_bronce INTEGER NOT NULL DEFAULT 0,
                medal_otros INTEGER NOT NULL DEFAULT 0,
                album_json TEXT NOT NULL DEFAULT '[]',
                theme TEXT NOT NULL DEFAULT 'selva_dia',
                tree_level INTEGER NOT NULL DEFAULT 1,
                gender TEXT NOT NULL DEFAULT 'otro',
                tutorial_seen INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS game_rounds (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id),
                game_id TEXT NOT NULL,
                state_json TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                game_id TEXT NOT NULL,
                score INTEGER NOT NULL,
                total INTEGER NOT NULL,
                medal TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                event TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
    database_url = app.config.get("DATABASE_URL")
    if database_url:
        import psycopg
        from psycopg.rows import dict_row

        schema = schema.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        schema = schema.replace("username TEXT NOT NULL UNIQUE COLLATE NOCASE", "username TEXT NOT NULL UNIQUE")
        db = _PostgresConnection(psycopg.connect(database_url, row_factory=dict_row))
        try:
            for statement in schema.split(";"):
                if statement.strip():
                    db.execute(statement)
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_username_lower_idx ON users (LOWER(username))")
            if app.config["IMPORT_LEGACY_USERS"]:
                _legacy_users(db, app)
            db.commit()
        finally:
            db.close()
        return

    path = Path(app.config["DATABASE"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db:
        db.row_factory = sqlite3.Row
        db.executescript(schema)
        db.commit()
        if app.config["IMPORT_LEGACY_USERS"]:
            _legacy_users(db, app)


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("KINDER_SECRET_KEY") or secrets.token_urlsafe(32),
        DATABASE=os.environ.get("KINDER_DATABASE", str(ROOT / "semillitas_web.sqlite3")),
        DATABASE_URL=os.environ.get("DATABASE_URL", ""),
        IMPORT_LEGACY_USERS=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_ENV") == "production" or os.environ.get("RENDER") == "true",
    )
    if test_config:
        app.config.update(test_config)
    if not os.environ.get("KINDER_SECRET_KEY") and not app.config.get("TESTING"):
        app.logger.warning("Usando clave de sesión temporal; define KINDER_SECRET_KEY para conservar sesiones entre reinicios.")
    _init_database(app)

    @app.before_request
    def protect_posts() -> None:
        _ensure_csrf_token()
        if request.method == "POST":
            supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
            if not supplied or not secrets.compare_digest(supplied, session.get("_csrf_token", "")):
                abort(400, description="La sesión del formulario venció. Actualiza la página e inténtalo otra vez.")

    @app.context_processor
    def common_template_values() -> dict[str, Any]:
        user = _user()
        theme = THEMES.get(user["theme"], THEMES["selva_dia"]) if user else THEMES["selva_dia"]
        return {
            "current_user": user,
            "theme": theme,
            "themes": THEMES,
            "csrf_token": _ensure_csrf_token(),
        }

    @app.get("/")
    def index():
        if _user():
            return redirect(url_for("dashboard"))
        return render_template("landing.html")

    @app.get("/iniciar-sesion")
    def login_page():
        if _user():
            return redirect(url_for("dashboard"))
        return render_template("login.html")

    @app.route("/registro", methods=["GET", "POST"])
    def register():
        if _user():
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "estudiante")
            teacher_code = request.form.get("teacher_code", "")
            avatar = request.form.get("avatar", "🐾")
            gender = request.form.get("gender", "otro")
            if not 3 <= len(username) <= 40 or not username.replace("_", "").replace("-", "").isalnum():
                flash("El usuario debe tener entre 3 y 40 letras, números, guiones o guiones bajos.", "error")
            elif len(password) < 6:
                flash("La contraseña debe tener al menos 6 caracteres.", "error")
            elif role not in {"estudiante", "docente"}:
                flash("Selecciona un tipo de cuenta válido.", "error")
            elif avatar not in AVATARS:
                flash("Selecciona un avatar válido.", "error")
            elif role == "docente" and (
                not os.environ.get("KINDER_TEACHER_CODE")
                or not secrets.compare_digest(teacher_code, os.environ.get("KINDER_TEACHER_CODE", ""))
            ):
                flash("No se pudo validar la clave de docente. Pide la clave configurada a tu escuela.", "error")
            else:
                db = get_db()
                try:
                    db.execute(
                        "INSERT INTO users (username, password_hash, role, avatar, gender) VALUES (?, ?, ?, ?, ?)",
                        (username, generate_password_hash(password), role, avatar, gender if gender in {"femenino", "masculino", "otro"} else "otro"),
                    )
                    db.commit()
                except _integrity_error_types():
                    db.rollback()
                    flash("Ese nombre de usuario ya está registrado.", "error")
                else:
                    _record_event(db, username, "Creó una cuenta")
                    db.commit()
                    flash("Cuenta creada. Ya puedes iniciar sesión.", "success")
                    return redirect(url_for("login_page"))
        return render_template("register.html", avatars=AVATARS)

    @app.post("/iniciar-sesion")
    def login():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Usuario o contraseña incorrectos.", "error")
            return redirect(url_for("login_page"))
        session.clear()
        session["user_id"] = user["id"]
        _ensure_csrf_token()
        _record_event(db, user["username"], "Inició sesión")
        db.commit()
        if user["role"] == "estudiante" and not user["tutorial_seen"]:
            return redirect(url_for("guide"))
        return redirect(url_for("dashboard"))

    @app.post("/cerrar-sesion")
    def logout():
        user = _user()
        if user:
            _record_event(get_db(), user["username"], "Cerró sesión")
            get_db().commit()
        session.clear()
        flash("Sesión cerrada.", "success")
        return redirect(url_for("index"))

    @app.get("/juego/<game_id>")
    def game(game_id: str):
        user = _require_user()
        definition = next((game for game in GAME_CATALOG if game["id"] == game_id), None)
        if definition is None:
            abort(404)
        questions = build_questions(game_id)
        state = {"questions": questions, "question_index": 0, "question_attempts": 0, "target": random.randrange(9)}
        if definition["mode"] == "memory":
            deck = ["🦁", "🐯", "🐵", "🐘", "🦓", "🐍"] * 2
            random.shuffle(deck)
            state["deck"] = deck
        if definition["mode"] == "find":
            state["target"] = random.randrange(9)
        round_id = str(uuid.uuid4())
        db = get_db()
        db.execute(
            "INSERT INTO game_rounds (id, user_id, game_id, state_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (round_id, user["id"], game_id, json.dumps(state, ensure_ascii=False), _utc_now()),
        )
        _record_event(db, user["username"], f"Inició el juego: {definition['title']}")
        db.commit()
        return render_template(
            "game.html",
            game=definition,
            round_id=round_id,
            question=_public_question(questions[0]) if questions else None,
            activity_data=_activity_data(game_id, state),
        )

    @app.post("/api/responder")
    def answer():
        user = _require_user()
        payload = request.get_json(silent=True) or {}
        round_id = payload.get("round_id")
        answer_value = payload.get("answer")
        if not isinstance(round_id, str) or not isinstance(answer_value, str) or len(answer_value) > 80:
            return jsonify(ok=False, message="Respuesta no válida."), 400
        db = get_db()
        round_row = db.execute(
            "SELECT * FROM game_rounds WHERE id = ? AND user_id = ?", (round_id, user["id"])
        ).fetchone()
        if not round_row or round_row["completed"]:
            return jsonify(ok=False, message="Esta ronda ya terminó. Inicia una nueva."), 409
        state = json.loads(round_row["state_json"])
        index = state["question_index"]
        questions = state["questions"]
        if index >= len(questions):
            return jsonify(ok=False, message="No quedan preguntas en esta ronda."), 409
        expected = questions[index]["answer"].strip().casefold()
        correct = answer_value.strip().casefold() == expected
        db.execute("UPDATE users SET attempts = attempts + 1 WHERE id = ?", (user["id"],))
        if correct:
            state["question_attempts"] = 0
            state["question_index"] += 1
            state["score"] = state.get("score", 0) + 1
            db.execute("UPDATE users SET points = points + 1 WHERE id = ?", (user["id"],))
        else:
            state["question_attempts"] += 1
            db.execute("UPDATE users SET errors = errors + 1 WHERE id = ?", (user["id"],))
        resolved = correct or state["question_attempts"] >= 3
        if not correct and resolved:
            state["question_index"] += 1
            state["question_attempts"] = 0
        complete = state["question_index"] >= len(questions)
        medal = None
        if complete:
            score = state.get("score", 0)
            medal = _award_medal(db, user["id"], score)
            elapsed = max(
                0,
                (datetime.fromisoformat(_utc_now()) - datetime.fromisoformat(round_row["created_at"])).total_seconds(),
            )
            db.execute("UPDATE users SET total_time = total_time + ? WHERE id = ?", (elapsed, user["id"]))
            db.execute(
                "UPDATE game_rounds SET state_json = ?, score = ?, completed = 1, completed_at = ? WHERE id = ?",
                (json.dumps(state, ensure_ascii=False), score, _utc_now(), round_id),
            )
            db.execute(
                "INSERT INTO attempts (user_id, game_id, score, total, medal, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user["id"], round_row["game_id"], score, len(questions), medal, _utc_now()),
            )
            _record_event(db, user["username"], f"Terminó {round_row['game_id']} con {score}/{len(questions)} aciertos")
        else:
            db.execute(
                "UPDATE game_rounds SET state_json = ?, score = ? WHERE id = ?",
                (json.dumps(state, ensure_ascii=False), state.get("score", 0), round_id),
            )
        db.commit()
        next_question = None
        if not complete:
            next_question = _public_question(questions[state["question_index"]])
        return jsonify(
            ok=True,
            correct=correct,
            resolved=resolved,
            reveal=questions[index]["answer"] if resolved and not correct else None,
            question=next_question,
            question_number=min(state["question_index"] + 1, len(questions)),
            total=len(questions),
            score=state.get("score", 0),
            completed=complete,
            medal=medal,
            points_awarded=int(correct),
        )

    @app.post("/api/completar-actividad")
    def complete_activity():
        user = _require_user()
        payload = request.get_json(silent=True) or {}
        round_id = payload.get("round_id")
        if not isinstance(round_id, str):
            return jsonify(ok=False, message="Actividad no válida."), 400
        db = get_db()
        round_row = db.execute(
            "SELECT * FROM game_rounds WHERE id = ? AND user_id = ?", (round_id, user["id"])
        ).fetchone()
        if not round_row or round_row["completed"]:
            return jsonify(ok=False, message="La actividad ya fue completada o no existe."), 409
        definition = next((item for item in GAME_CATALOG if item["id"] == round_row["game_id"]), None)
        if definition is None:
            abort(404)
        reward = 10 if definition["mode"] == "lesson" else 5 if definition["mode"] == "draw" else 1
        state = json.loads(round_row["state_json"])
        medal = _award_medal(db, user["id"], 5) if definition["mode"] == "draw" else None
        db.execute("UPDATE users SET points = points + ? WHERE id = ?", (reward, user["id"]))
        elapsed = max(
            0,
            (datetime.fromisoformat(_utc_now()) - datetime.fromisoformat(round_row["created_at"])).total_seconds(),
        )
        db.execute("UPDATE users SET total_time = total_time + ? WHERE id = ?", (elapsed, user["id"]))
        db.execute(
            "UPDATE game_rounds SET score = ?, completed = 1, completed_at = ? WHERE id = ?",
            (reward, _utc_now(), round_id),
        )
        db.execute(
            "INSERT INTO attempts (user_id, game_id, score, total, medal, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (user["id"], round_row["game_id"], reward, reward, medal, _utc_now()),
        )
        _record_event(db, user["username"], f"Completó la actividad: {definition['title']}")
        db.commit()
        return jsonify(ok=True, points=reward, medal=medal, message="¡Muy bien! Actividad completada.")

    @app.get("/inicio")
    def dashboard():
        user = _require_user()
        if user["role"] == "docente":
            return redirect(url_for("teacher_panel"))
        db = get_db()
        ranking = db.execute(
            "SELECT username, avatar, points FROM users WHERE role = 'estudiante' ORDER BY points DESC, username LIMIT 10"
        ).fetchall()
        album = json.loads(user["album_json"])
        owned_ids = {item.get("id") for item in album if isinstance(item, dict)}
        tree_level = min(5, max(1, user["tree_level"]))
        return render_template(
            "dashboard.html",
            games=GAME_CATALOG,
            levels=(1, 2, 3),
            ranking=ranking,
            album_count=len(owned_ids),
            total_stickers=len(STICKERS),
            tree_level=tree_level,
            tree_image=f"arbol_dino{tree_level}.png",
        )

    @app.get("/album")
    def album_page():
        user = _require_user()
        album = json.loads(user["album_json"])
        owned_ids = {item.get("id") for item in album if isinstance(item, dict)}
        return render_template(
            "album.html",
            stickers=STICKERS,
            owned_ids=owned_ids,
            album_count=len(owned_ids),
            total_stickers=len(STICKERS),
        )

    @app.get("/ajustes")
    def settings_page():
        _require_user()
        return render_template("settings.html", avatars=AVATARS, themes=THEMES)

    @app.get("/guia")
    def guide():
        _require_user()
        return render_template("guide.html")

    @app.post("/guia/completar")
    def complete_guide():
        user = _require_user()
        db = get_db()
        db.execute("UPDATE users SET tutorial_seen = 1 WHERE id = ?", (user["id"],))
        db.commit()
        return redirect(url_for("dashboard"))

    @app.post("/configuracion")
    def settings():
        user = _require_user()
        avatar = request.form.get("avatar", user["avatar"])
        theme = request.form.get("theme", user["theme"])
        if avatar not in AVATARS or theme not in THEMES:
            abort(400)
        db = get_db()
        db.execute("UPDATE users SET avatar = ?, theme = ? WHERE id = ?", (avatar, theme, user["id"]))
        db.commit()
        flash("Tu perfil se actualizó.", "success")
        return redirect(url_for("settings_page"))

    @app.post("/album/comprar/<int:sticker_id>")
    def buy_sticker(sticker_id: int):
        user = _require_user()
        sticker = next((item for item in STICKERS if item["id"] == sticker_id), None)
        if sticker is None:
            abort(404)
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        album = json.loads(user["album_json"])
        if any(item.get("id") == sticker_id for item in album if isinstance(item, dict)):
            flash("Esa estampa ya está en tu álbum.", "error")
        elif user["points"] < sticker["cost"]:
            flash("Todavía necesitas más estrellas para comprarla.", "error")
        else:
            album.append(sticker)
            db.execute(
                "UPDATE users SET points = points - ?, album_json = ? WHERE id = ?",
                (sticker["cost"], json.dumps(album, ensure_ascii=False), user["id"]),
            )
            db.commit()
            flash(f"¡Conseguiste {sticker['name']}!", "success")
        return redirect(url_for("album_page"))

    @app.get("/docente")
    def teacher_panel():
        _require_teacher()
        db = get_db()
        students = [
            dict(row)
            for row in db.execute(
                """SELECT id, username, avatar, points, errors, attempts, total_time,
                          medal_oro, medal_plata, medal_bronce, tree_level
                   FROM users WHERE role = 'estudiante'
                   ORDER BY points DESC, username"""
            ).fetchall()
        ]
        completed_counts = {
            row["user_id"]: row["completed_activities"]
            for row in db.execute(
                """SELECT a.user_id, COUNT(*) AS completed_activities
                   FROM attempts AS a
                   JOIN users AS u ON u.id = a.user_id
                   WHERE u.role = 'estudiante'
                   GROUP BY a.user_id"""
            ).fetchall()
        }
        recent_activities: dict[int, list[dict[str, Any]]] = {
            student["id"]: [] for student in students
        }
        game_titles = {game["id"]: game["title"] for game in GAME_CATALOG}
        for row in db.execute(
            """WITH ranked_attempts AS (
                   SELECT a.user_id, a.game_id, a.score, a.total, a.medal, a.created_at,
                          ROW_NUMBER() OVER (
                              PARTITION BY a.user_id ORDER BY a.created_at DESC, a.id DESC
                          ) AS position
                   FROM attempts AS a
                   JOIN users AS u ON u.id = a.user_id
                   WHERE u.role = 'estudiante'
               )
               SELECT user_id, game_id, score, total, medal, created_at, position
               FROM ranked_attempts
               WHERE position <= 8
               ORDER BY user_id, position"""
        ).fetchall():
            recent_activities[row["user_id"]].append(
                {
                    "title": game_titles.get(row["game_id"], row["game_id"]),
                    "score": row["score"],
                    "total": row["total"],
                    "medal": row["medal"],
                    "created_at": row["created_at"],
                }
            )

        for student in students:
            completed = completed_counts.get(student["id"], 0)
            student["completed_activities"] = completed
            student["average_activity_time"] = student["total_time"] / completed if completed else 0

        events = db.execute(
            """SELECT e.username, e.event, e.created_at
               FROM events AS e
               JOIN users AS u ON u.username = e.username
               WHERE u.role = 'estudiante'
               ORDER BY e.id DESC LIMIT 50"""
        ).fetchall()
        group_stats = {
            "students": len(students),
            "points": sum(student["points"] for student in students),
            "activities": sum(student["completed_activities"] for student in students),
            "medals": sum(
                student["medal_oro"] + student["medal_plata"] + student["medal_bronce"]
                for student in students
            ),
        }
        return render_template(
            "teacher.html",
            students=students,
            recent_activities=recent_activities,
            events=events,
            group_stats=group_stats,
        )

    @app.get("/docente/reporte.csv")
    def teacher_report():
        _require_teacher()
        rows = get_db().execute(
            """SELECT username, points, errors, attempts, total_time, medal_oro, medal_plata, medal_bronce
               FROM users WHERE role = 'estudiante' ORDER BY username"""
        ).fetchall()
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Alumno", "Puntos", "Errores", "Intentos", "Promedio de respuesta (s)", "Oro", "Plata", "Bronce"])
        for row in rows:
            average = round(row["total_time"] / row["attempts"], 2) if row["attempts"] else 0
            writer.writerow([row["username"], row["points"], row["errors"], row["attempts"], average, row["medal_oro"], row["medal_plata"], row["medal_bronce"]])
        response = make_response("\ufeff" + output.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = 'attachment; filename="reporte_semillitas.csv"'
        return response

    @app.get("/docente/bitacora.csv")
    def teacher_event_report():
        _require_teacher()
        rows = get_db().execute(
            "SELECT created_at, username, event FROM events ORDER BY id"
        ).fetchall()
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["Fecha UTC", "Usuario", "Evento"])
        writer.writerows((row["created_at"], row["username"], row["event"]) for row in rows)
        response = make_response("\ufeff" + output.getvalue())
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        response.headers["Content-Disposition"] = 'attachment; filename="bitacora_semillitas.csv"'
        return response

    @app.get("/media/<path:filename>")
    def media(filename: str):
        media_path = Path(filename)
        if filename not in NESTED_MEDIA and (
            media_path.name != filename or media_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".mp3"}
        ):
            abort(404)
        target = (ROOT / filename).resolve()
        if not target.is_relative_to(ROOT):
            abort(404)
        if not target.is_file():
            abort(404)
        response = send_from_directory(ROOT, filename)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.errorhandler(401)
    def unauthorized(_error):
        flash("Inicia sesión para continuar.", "error")
        return redirect(url_for("index"))

    @app.teardown_appcontext
    def close_db(_error: BaseException | None = None) -> None:
        db = g.pop("db", None)
        if db is not None:
            db.close()

    return app


def _activity_data(game_id: str, state: dict[str, Any]) -> dict[str, Any]:
    if game_id == "lavarse_manos":
        steps = HAND_STEPS
    elif game_id == "lavar_dientes":
        steps = TEETH_STEPS
    else:
        steps = []
    result: dict[str, Any] = {"steps": steps}
    if game_id == "memorama":
        result["deck"] = state["deck"]
    if game_id == "dibuja_vocales":
        result["vowels"] = random.sample(list("AEIOU"), 5)
    if game_id == "rompecabezas":
        result["puzzles"] = [
            {"name": "Árbol", "image": "cn/arbol.png"},
            {"name": "Girasol", "image": "cn/girasol.png"},
            {"name": "Flores", "image": "cn/flores.png"},
        ]
    return result


def get_db() -> Any:
    if "db" not in g:
        database_url = current_app.config.get("DATABASE_URL")
        if database_url:
            import psycopg
            from psycopg.rows import dict_row

            db = _PostgresConnection(psycopg.connect(database_url, row_factory=dict_row))
        else:
            db = sqlite3.connect(current_app.config["DATABASE"])
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
        g.db = db
    return g.db


app = create_app()


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1",
        host="127.0.0.1",
        port=int(os.environ.get("KINDER_PORT", "5000")),
    )
