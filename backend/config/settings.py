"""
Django settings for config project.

Un despliegue de este proyecto = una sola barberia. La identidad de la
barberia (nombre, slug, colores, si permite elegir barbero) vive en
variables de entorno, no en la base de datos -- ver BARBERIA_* mas abajo.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env("SECRET_KEY", default="django-insecure-only-for-local-dev-change-me")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "reservas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Database
# Local dev: si no hay DATABASE_URL en .env, cae a SQLite (cero instalacion).
# Railway / Docker: DATABASE_URL apunta a Postgres -- no se toca codigo, solo .env.
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internationalization

LANGUAGE_CODE = "es-cl"

TIME_ZONE = "America/Santiago"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Django 6.0 no tiene STATICFILES_STORAGE (removido de global_settings.py) --
# el reemplazo desde Django 4.2+ es STORAGES. Whitenoise sirve /static/ desde
# el propio proceso de Django, sin depender de Nginx/Cloudflare para eso.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Django REST Framework
# Sin autenticacion todavia: el flujo de reserva es publico (cliente sin login)
# y el panel admin.js tampoco tiene login aun (ver nota de seguridad en admin.js).
# Antes de desplegar a produccion real hay que restringir el PATCH de reservas.
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_PAGINATION_CLASS": None,
}


# CORS -- el frontend (Cloudflare Pages) es un origen distinto al backend (Railway)
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
# Utilisimo en desarrollo local para no pelear con el puerto del Live Server / http.server
CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS_DEV", default=DEBUG)


# Email (Resend via django-anymail) -- confirmacion de reserva
# En local sin RESEND_API_KEY configurada, los emails se imprimen en consola
# en vez de fallar (ver EMAIL_BACKEND condicional abajo).
RESEND_API_KEY = env("RESEND_API_KEY", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="reservas@example.com")

if RESEND_API_KEY:
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    ANYMAIL = {
        "RESEND_API_KEY": RESEND_API_KEY,
    }
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


# Identidad de la barberia servida por ESTE despliegue (no vive en la BD).
# Un despliegue = una barberia; estas variables cambian por servicio de Railway.
BARBERIA_NOMBRE = env("BARBERIA_NOMBRE", default="Barberia Demo")
BARBERIA_SLUG = env("BARBERIA_SLUG", default="demo")
BARBERIA_PERMITE_ELEGIR_BARBERO = env.bool("BARBERIA_PERMITE_ELEGIR_BARBERO", default=True)
BARBERIA_COLOR_PRIMARIO = env("BARBERIA_COLOR_PRIMARIO", default="#C9A961")
