# Backend — Multisistemas Barberías

Django + DRF que reemplaza el `localStorage` del frontend. Un despliegue de
este backend sirve a **una sola barbería** (ver `BARBERIA_*` en `.env`) — no
hay modelo de tenant ni filtrado por barbería en la base de datos.

## Levantar el proyecto local

Requisitos: Python 3.10+. No hace falta Docker ni Postgres para desarrollo —
si no defines `DATABASE_URL` en `.env`, el proyecto usa SQLite automáticamente.

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Editar .env con tus valores (para desarrollo local los defaults ya sirven)

python manage.py migrate
python manage.py createsuperuser   # para entrar a /admin
python manage.py seed_demo_data    # opcional: barberos/servicios PLACEHOLDER
                                    # para probar el flujo sin datos reales

python manage.py runserver
```

Servidor en `http://127.0.0.1:8000`. Panel admin en `http://127.0.0.1:8000/admin/`.

## Migrar a Postgres (Docker o Railway)

El código no cambia, solo `.env`:

```
DATABASE_URL=postgres://usuario:password@host:5432/nombre_bd
```

## Endpoints

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/barberos/` | Lista barberos activos |
| GET | `/api/servicios/` | Lista servicios activos |
| GET | `/api/reservas/` | Lista todas las reservas |
| POST | `/api/reservas/` | Crea una reserva (queda en estado `pendiente`) |
| PATCH | `/api/reservas/<id>/` | Actualiza estado (`pendiente`/`confirmada`/`completada`/`cancelada`) |

Ejemplos:

```bash
curl http://127.0.0.1:8000/api/barberos/

curl -X POST http://127.0.0.1:8000/api/reservas/ \
  -H "Content-Type: application/json" \
  -d '{"barbero":1,"servicio":1,"cliente_nombre":"Juan Pérez","cliente_telefono":"987654321","cliente_email":"juan@example.com","fecha":"2026-08-01","hora":"10:00"}'

curl -X PATCH http://127.0.0.1:8000/api/reservas/1/ \
  -H "Content-Type: application/json" \
  -d '{"estado":"confirmada"}'
```

Si dos reservas intentan tomar el mismo `barbero` + `fecha` + `hora` a la vez,
la segunda recibe **409 Conflict** con `{"detail": "Ese horario ya fue
reservado..."}`. Esta garantía vive en un constraint de base de datos
(`unique_barbero_fecha_hora_activa`), no solo en validación de Python, para
que sea segura ante requests concurrentes.

## Email de confirmación

Al crear una reserva se dispara un email de confirmación en un hilo aparte
(no bloquea la respuesta al cliente). En local, sin `RESEND_API_KEY`
configurada, el email se imprime en la consola del `runserver` en vez de
enviarse de verdad. Para enviar emails reales, configura `RESEND_API_KEY` y
`DEFAULT_FROM_EMAIL` en `.env`.

## Datos placeholder

`python manage.py seed_demo_data` crea barberos y servicios marcados como
`[PLACEHOLDER]` — a propósito distintos del mock de `frontend/js/api.js`,
para no confundirlos con datos reales. Reemplázalos vía `/admin` con la
información real de cada barbería antes de considerar el ambiente listo
para clientes reales.

## Estrategia de ramas (para el deploy en Railway — Paso 3, todavía no)

```
main                    ← desarrollo (esta rama)
deploy/legendaria       ← Railway Service "backend-legendaria"
deploy/otra-barberia    ← Railway Service "backend-otra"
```

Cada rama `deploy/*` se despliega en su propio servicio de Railway con
autodeploy escuchando solo esa rama, y su propio `.env` (identidad de
barbería + `DATABASE_URL` apuntando a su propia base lógica dentro de la
misma instancia de Postgres). Para llevar un cambio de `main` a producción:

```bash
git checkout deploy/legendaria
git merge main
git push
```
