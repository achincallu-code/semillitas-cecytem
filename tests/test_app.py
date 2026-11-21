import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import app as semillitas_app
from app import GAME_CATALOG, _PostgresConnection, build_questions, create_app


class SemillitasWebTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-key",
                "DATABASE": str(Path(self.temp_dir.name) / "test.sqlite3"),
                "IMPORT_LEGACY_USERS": False,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_postgres_adapter_translates_sql_and_supports_named_and_indexed_rows(self):
        class FakeCursor:
            def fetchone(self):
                return {"username": "Ana", "points": 12}

            def fetchall(self):
                return [{"username": "Ana", "points": 12}]

        class FakeConnection:
            def __init__(self):
                self.query = None
                self.params = None

            def execute(self, query, params):
                self.query = query
                self.params = params
                return FakeCursor()

        raw_connection = FakeConnection()
        db = _PostgresConnection(raw_connection)

        row = db.execute(
            "SELECT * FROM users WHERE username = ? COLLATE NOCASE",
            ("ana",),
        ).fetchone()
        self.assertEqual(raw_connection.query, "SELECT * FROM users WHERE LOWER(username) = LOWER(%s)")
        self.assertEqual(raw_connection.params, ("ana",))
        self.assertEqual((row["username"], row[1]), ("Ana", 12))

        db.execute("INSERT OR IGNORE INTO users (username) VALUES (?)", ("Ana",))
        self.assertEqual(
            raw_connection.query,
            "INSERT INTO users (username) VALUES (%s) ON CONFLICT DO NOTHING",
        )

    def csrf_token(self):
        response = self.client.get("/")
        self.assertIn(response.status_code, (200, 302))
        with self.client.session_transaction() as session:
            return session["_csrf_token"]

    def register(self, username="explorador", password="semilla123"):
        token = self.csrf_token()
        return self.client.post(
            "/registro",
            data={
                "csrf_token": token,
                "username": username,
                "password": password,
                "role": "estudiante",
                "avatar": "🦁",
                "gender": "otro",
            },
            follow_redirects=True,
        )

    def login(self, username="explorador", password="semilla123"):
        return self.client.post(
            "/iniciar-sesion",
            data={"csrf_token": self.csrf_token(), "username": username, "password": password},
            follow_redirects=True,
        )

    def test_welcome_screen_precedes_login_and_serves_its_artwork(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'class="landing-view"', response.data)
        self.assertIn(b'href="/iniciar-sesion" data-start-login', response.data)
        self.assertIn(b'/static/images/semillitas-bienvenidos.png', response.data)

        login_page = self.client.get("/iniciar-sesion")
        self.assertEqual(login_page.status_code, 200)
        self.assertIn("Nombre de usuario".encode(), login_page.data)
        self.assertIn('action="/iniciar-sesion"'.encode(), login_page.data)
        self.assertIn('class="back-link auth-back-link" href="/"'.encode(), login_page.data)

        artwork = self.client.head("/static/images/semillitas-bienvenidos.png")
        self.assertEqual(artwork.status_code, 200)
        self.assertEqual(artwork.mimetype, "image/png")
        artwork.close()

    def test_password_visibility_controls_are_available_on_auth_forms(self):
        login_page = self.client.get("/iniciar-sesion")
        self.assertIn(b'data-password-toggle aria-label="Mostrar contrase\xc3\xb1a"', login_page.data)
        self.assertIn(b'class="password-field"', login_page.data)

        register_page = self.client.get("/registro")
        self.assertEqual(register_page.status_code, 200)
        self.assertEqual(register_page.data.count(b"data-password-toggle"), 2)
        self.assertIn(b"Mostrar clave de docente", register_page.data)

        script = self.client.get("/static/js/site.js")
        self.assertIn(b'input.type = visible ? "text" : "password"', script.data)
        script.close()

    def test_register_login_and_dashboard(self):
        response = self.register()
        self.assertIn("Cuenta creada".encode(), response.data)
        response = self.login()
        self.assertIn("¡Estoy listo para jugar!".encode(), response.data)
        response = self.client.post(
            "/guia/completar",
            data={"csrf_token": self.csrf_token()},
            follow_redirects=True,
        )
        self.assertIn("¡Hola, explorador!".encode(), response.data)
        self.assertIn("Mi álbum de estampas".encode(), response.data)

    def test_album_and_settings_are_separate_pages_linked_from_the_top_navigation(self):
        self.register()
        self.login()
        with self.client.session_transaction() as session:
            user_id = session["user_id"]
        with self.app.app_context():
            from app import get_db

            get_db().execute("UPDATE users SET points = 24 WHERE id = ?", (user_id,))
            get_db().commit()

        dashboard = self.client.get("/inicio")
        self.assertIn(b'href="/album"', dashboard.data)
        self.assertIn(b'href="/ajustes"', dashboard.data)
        self.assertIn("24".encode(), dashboard.data)
        self.assertNotIn("Jaguar Dorado".encode(), dashboard.data)

        album = self.client.get("/album")
        self.assertEqual(album.status_code, 200)
        self.assertIn("Mi álbum de estampas".encode(), album.data)
        self.assertIn("Jaguar Dorado".encode(), album.data)
        self.assertIn(b'action="/album/comprar/1"', album.data)
        purchased = self.client.post(
            "/album/comprar/1",
            data={"csrf_token": self.csrf_token()},
            follow_redirects=True,
        )
        self.assertIn("¡Conseguiste Jaguar Dorado!".encode(), purchased.data)
        self.assertIn("¡Ya está en tu álbum!".encode(), purchased.data)

        settings = self.client.get("/ajustes")
        self.assertEqual(settings.status_code, 200)
        self.assertIn("Ajustes de aventura".encode(), settings.data)
        self.assertIn('name="avatar" value="🦁" checked'.encode(), settings.data)
        self.assertIn(b'data-preserve-scroll', settings.data)
        self.assertIn(b'data-theme-background-image="none, none"', settings.data)
        self.assertIn(b'data-theme-background-image="linear-gradient(130deg,', settings.data)
        saved = self.client.post(
            "/configuracion",
            data={"csrf_token": self.csrf_token(), "avatar": "🐯", "theme": "oceano"},
            follow_redirects=True,
        )
        self.assertIn("Tu perfil se actualizó.".encode(), saved.data)
        self.assertIn('name="avatar" value="🐯" checked'.encode(), saved.data)
        self.assertIn('name="theme" value="oceano"'.encode(), saved.data)
        self.assertIn('data-theme-primary="#0277bd"'.encode(), saved.data)
        self.assertIn("--primary: #0277bd".encode(), saved.data)
        self.assertIn('data-theme-background="#edf8fc"'.encode(), saved.data)
        self.assertIn('data-theme-surface-soft="#e9f5f8"'.encode(), saved.data)

        dashboard = self.client.get("/inicio")
        self.assertIn("--page-bg: #edf8fc".encode(), dashboard.data)
        self.assertIn("--primary: #0277bd".encode(), dashboard.data)
        css = self.client.get("/static/css/app.css")
        self.assertIn(".button.primary, .button.tiny", css.data.decode())
        self.assertIn("background: var(--primary)", css.data.decode())
        css.close()
        script = self.client.get("/static/js/site.js")
        self.assertIn("input.addEventListener(\"change\"", script.data.decode())
        self.assertIn('backgroundImage: "--page-bg-image"', script.data.decode())
        self.assertIn('data-preserve-scroll', script.data.decode())
        script.close()

    def test_dashboard_separates_years_into_accessible_tabs_and_loads_background_asset(self):
        self.register()
        self.login()
        response = self.client.get("/inicio")
        self.assertIn(b'role="tablist"', response.data)
        self.assertIn(b'data-year-tab="1"', response.data)
        self.assertIn(b'data-year-tab="2"', response.data)
        self.assertIn(b'data-year-tab="3"', response.data)
        self.assertIn(b'data-year-tab="minigames"', response.data)
        self.assertIn(b'data-year-panel="2" hidden', response.data)
        self.assertIn(b'data-year-panel="3" hidden', response.data)
        self.assertIn(b'id="tree-open"', response.data)
        self.assertIn(b'<dialog class="tree-dialog"', response.data)
        self.assertIn(b'id="tree-current-image" src="/media/arbol_dino1.png"', response.data)
        self.assertNotIn(b'tree-stages', response.data)
        css = self.client.get("/static/css/app.css")
        self.assertIn(b'url("/media/Selva3.png")', css.data)
        self.assertIn(b".tree-dialog", css.data)
        css.close()
        dashboard_js = self.client.get("/static/js/dashboard.js")
        self.assertIn(b"ArrowRight", dashboard_js.data)
        self.assertIn(b"showModal", dashboard_js.data)
        dashboard_js.close()
        image = self.client.head("/media/Selva3.png")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.mimetype, "image/png")
        image.close()
        for level in range(1, 6):
            with self.subTest(tree_level=level):
                image = self.client.head(f"/media/arbol_dino{level}.png")
                self.assertEqual(image.status_code, 200)
                image.close()

    def test_tree_dialog_uses_the_current_level_image(self):
        self.register()
        self.login()
        with self.client.session_transaction() as session:
            user_id = session["user_id"]
        with self.app.app_context():
            from app import get_db

            get_db().execute(
                "UPDATE users SET medal_oro = 3, medal_plata = 1, tree_level = 2 WHERE id = ?",
                (user_id,),
            )
            get_db().commit()

        response = self.client.get("/inicio")
        self.assertIn(b"Nivel 2 de 5", response.data)
        self.assertIn(b'id="tree-current-image" src="/media/arbol_dino2.png"', response.data)
        self.assertIn(b'class="tree-level-bar" max="5" value="2"', response.data)
        self.assertIn("Cada 3 medallas, tu árbol sube de nivel.".encode(), response.data)
        self.assertNotIn(b'arbol_dino1.png', response.data)

    def test_quiz_round_awards_score_and_medal(self):
        self.register()
        self.login()
        page = self.client.get("/juego/colores")
        self.assertEqual(page.status_code, 200)
        with self.client.session_transaction() as session:
            user_id = session["user_id"]
        with self.app.app_context():
            from app import get_db

            round_row = get_db().execute(
                "SELECT id, state_json FROM game_rounds WHERE user_id = ?", (user_id,)
            ).fetchone()
            import json

            state = json.loads(round_row["state_json"])
            round_id = round_row["id"]
        token = self.csrf_token()
        for question in state["questions"]:
            response = self.client.post(
                "/api/responder",
                json={"round_id": round_id, "answer": question["answer"]},
                headers={"X-CSRF-Token": token},
            )
            self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["completed"])
        self.assertEqual(response.json["score"], 5)
        self.assertEqual(response.json["medal"], "oro")

    def test_every_catalog_game_opens_and_static_media_is_allowlisted(self):
        self.register()
        self.login()
        for game in GAME_CATALOG:
            with self.subTest(game=game["id"]):
                response = self.client.get(f"/juego/{game['id']}")
                self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/media/usuarios_kinder.json").status_code, 404)
        media_response = self.client.head("/media/cn/arbol.png")
        self.assertEqual(media_response.status_code, 200)
        media_response.close()

    def test_existing_music_animal_and_feedback_audio_are_available(self):
        for filename in ("selva.mp3", "perro.mp3", "correcto.mp3", "error.mp3", "muy_bien.mp3"):
            with self.subTest(filename=filename):
                response = self.client.head(f"/media/{filename}")
                self.assertEqual(response.status_code, 200)
                self.assertIn("audio", response.headers["Content-Type"])
                response.close()

    def test_quiz_catalog_has_five_answerable_questions_per_round(self):
        for game in GAME_CATALOG:
            if game["mode"] != "quiz":
                continue
            with self.subTest(game=game["id"]):
                questions = build_questions(game["id"])
                self.assertEqual(len(questions), 5)
                for question in questions:
                    self.assertIn(question["answer"], question["options"])

    def test_lesson_rewards_once(self):
        self.register()
        self.login()
        self.client.get("/juego/lavarse_manos")
        with self.client.session_transaction() as session:
            user_id = session["user_id"]
        with self.app.app_context():
            from app import get_db

            round_id = get_db().execute(
                "SELECT id FROM game_rounds WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                (user_id,),
            ).fetchone()[0]
        token = self.csrf_token()
        response = self.client.post(
            "/api/completar-actividad",
            json={"round_id": round_id},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["points"], 10)
        duplicate = self.client.post(
            "/api/completar-actividad",
            json={"round_id": round_id},
            headers={"X-CSRF-Token": token},
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_teacher_panel_is_forbidden_to_students_and_bad_answers_do_not_award_points(self):
        self.register()
        self.login()
        self.assertEqual(self.client.get("/docente").status_code, 403)
        self.client.get("/juego/colores")
        with self.client.session_transaction() as session:
            user_id = session["user_id"]
        with self.app.app_context():
            from app import get_db

            round_id = get_db().execute(
                "SELECT id FROM game_rounds WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)
            ).fetchone()[0]
        response = self.client.post(
            "/api/responder",
            json={"round_id": round_id, "answer": "no es la respuesta"},
            headers={"X-CSRF-Token": self.csrf_token()},
        )
        self.assertFalse(response.json["correct"])
        self.assertEqual(response.json["points_awarded"], 0)

    def test_teacher_panel_focuses_on_student_progress_without_game_navigation(self):
        self.register(username="alumna_prueba")
        with self.app.app_context():
            from app import get_db

            db = get_db()
            student_id = db.execute(
                "SELECT id FROM users WHERE username = ?", ("alumna_prueba",)
            ).fetchone()["id"]
            db.execute(
                """UPDATE users SET points = 17, errors = 2, attempts = 8,
                          total_time = 120, medal_plata = 1, tree_level = 2
                   WHERE id = ?""",
                (student_id,),
            )
            db.execute(
                """INSERT INTO attempts (user_id, game_id, score, total, medal, created_at)
                   VALUES (?, 'memorama', 4, 5, 'plata', '2026-11-20T01:00:00+00:00')""",
                (student_id,),
            )
            db.execute(
                """INSERT INTO users (username, password_hash, role)
                   VALUES ('docente_prueba', ?, 'docente')""",
                (semillitas_app.generate_password_hash("docente123"),),
            )
            db.commit()

        login_response = self.client.post(
            "/iniciar-sesion",
            data={
                "csrf_token": self.csrf_token(),
                "username": "docente_prueba",
                "password": "docente123",
            },
            follow_redirects=True,
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertIn(b"Panel docente", login_response.data)

        response = self.client.get("/docente")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"alumna_prueba", response.data)
        self.assertIn("Memorama".encode(), response.data)
        self.assertIn(b"Actividades completadas", response.data)
        self.assertIn(b"Buscar estudiante", response.data)
        self.assertNotIn(b'class="game-card"', response.data)
        self.assertNotIn(b'href="/juego/', response.data)
        self.assertNotIn(b"Mi aventura", response.data)

        dashboard_response = self.client.get("/inicio")
        self.assertEqual(dashboard_response.status_code, 302)
        self.assertEqual(dashboard_response.headers["Location"], "/docente")
        self.assertEqual(self.client.get("/docente/reporte.csv").status_code, 200)
        self.assertEqual(self.client.get("/docente/bitacora.csv").status_code, 200)

    def test_legacy_accounts_are_hashed_and_the_source_file_is_unchanged(self):
        source = Path(self.temp_dir.name) / "legacy.json"
        original = json.dumps(
            {
                "estudiante_demo": {
                    "password": "clave-anterior",
                    "tipo": "estudiante",
                    "puntos": 12,
                    "medallas": {"oro": 1, "plata": 0, "bronce": 0},
                    "album": [],
                    "tema_preferido": "selva_dia",
                }
            },
            ensure_ascii=False,
        )
        source.write_text(original, encoding="utf-8")
        with patch.object(semillitas_app, "LEGACY_USERS_FILE", source):
            migrated_app = create_app(
                {
                    "TESTING": True,
                    "SECRET_KEY": "test-key",
                    "DATABASE": str(Path(self.temp_dir.name) / "migration.sqlite3"),
                    "IMPORT_LEGACY_USERS": True,
                }
            )
        with migrated_app.app_context():
            from app import get_db

            user = get_db().execute(
                "SELECT password_hash, points, medal_oro FROM users WHERE username = ?",
                ("estudiante_demo",),
            ).fetchone()
            self.assertTrue(semillitas_app.check_password_hash(user["password_hash"], "clave-anterior"))
            self.assertEqual((user["points"], user["medal_oro"]), (12, 1))
        self.assertEqual(source.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
