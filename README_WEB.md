# Semillitas CECyTEM en Flask

La nueva interfaz del navegador se inicia con `app.py` y reutiliza las ilustraciones y los sonidos del proyecto.

## Ejecución local en Windows

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

Abre `http://127.0.0.1:5000`. En local, la aplicación usa SQLite (`semillitas_web.sqlite3`).

## Publicar en Render con Neon

1. Crea una base de datos en Neon y copia la cadena de conexión PostgreSQL (incluye `sslmode=require`; usa la cadena pooled si está disponible).
2. En Render, crea un **Blueprint** desde este repositorio y la rama `main`; Render leerá `render.yaml`.
3. Cuando Render lo solicite, configura `DATABASE_URL` con la cadena de Neon y `KINDER_TEACHER_CODE` con una clave privada para registrar docentes. `KINDER_SECRET_KEY` se genera automáticamente.
4. Confirma el despliegue. Render instalará `requirements.txt` y ejecutará Gunicorn. La aplicación crea las tablas de Neon al iniciar.

La app usa PostgreSQL cuando existe `DATABASE_URL` y SQLite cuando no existe. La base SQLite y el archivo `usuarios_kinder.json` locales no se publican ni se copian automáticamente a Neon; si ya contienen cuentas o progreso que necesitas conservar, hay que migrarlos por separado antes de usar la instancia pública.

## Seguridad y datos

- En local, el primer inicio puede importar las cuentas y el progreso de `usuarios_kinder.json` a SQLite; las contraseñas se convierten a hashes. El archivo JSON original no se borra ni se modifica. Ese archivo no se incluye en el despliegue, por lo que las cuentas antiguas no aparecen automáticamente en Neon.
- El JSON antiguo conserva contraseñas en texto claro para que la aplicación de escritorio siga funcionando. No lo publiques ni lo agregues al control de versiones; el `.gitignore` lo excluye.
- Las cuentas nuevas se guardan en la base configurada. El rol docente requiere `KINDER_TEACHER_CODE`.
- En Render, `KINDER_SECRET_KEY` debe mantenerse estable para conservar las sesiones; el Blueprint la genera y guarda como secreto.
- Los reportes del panel docente se descargan como CSV desde la aplicación.
- El avance del navegador, la autenticación, los niveles, las medallas, las estampas, los temas y los minijuegos usan la base configurada; la versión Tkinter y su archivo de progreso permanecen separados.
