# Semillitas CECyTEM en Flask

La nueva interfaz del navegador se inicia con `app.py` y reutiliza las ilustraciones y los sonidos del proyecto.

## Preparación en Windows

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Abre `http://127.0.0.1:5000`. También puedes activar el entorno virtual y ejecutar `python app.py`.

## Migración y seguridad

- En el primer inicio se importan las cuentas y el progreso de `usuarios_kinder.json` a `semillitas_web.sqlite3`; las contraseñas anteriores se convierten a hashes. El archivo JSON original no se borra ni se modifica.
- El JSON antiguo conserva contraseñas en texto claro para que la aplicación de escritorio siga funcionando. No lo publiques ni lo agregues al control de versiones; el `.gitignore` lo excluye.
- Las cuentas nuevas se guardan en SQLite. El rol docente requiere configurar `KINDER_TEACHER_CODE`.
- Antes de publicar el sitio, configura una clave privada y estable para sesiones (`KINDER_SECRET_KEY`), una clave de registro docente y un servidor WSGI de producción. No publiques la aplicación de desarrollo de Flask en Internet.
- Los reportes del panel docente se descargan como CSV desde la aplicación.
- El avance del navegador, la autenticación, los niveles, las medallas, las estampas, los temas y los minijuegos usan la nueva base SQLite; la versión Tkinter y su archivo de progreso permanecen separados.
