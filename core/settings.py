from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    raw_value = os.getenv(name, default) or ""
    return [item.strip() for item in raw_value.split(",") if item.strip()]


DEBUG = env_bool("DEBUG", default=False)

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-secret-key"
    else:
        raise ValueError("SECRET_KEY .env içinde tanımlı olmalı.")

ALLOWED_HOSTS = env_list(
    "ALLOWED_HOSTS",
    default="localhost,127.0.0.1",
)

if not DEBUG and not ALLOWED_HOSTS:
    raise ValueError("DEBUG=False iken ALLOWED_HOSTS boş olamaz.")


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "corsheaders",

    "chat",
    "accounts",
]


MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


ROOT_URLCONF = "core.urls"


TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]


WSGI_APPLICATION = "core.wsgi.application"


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


LANGUAGE_CODE = "tr-tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# -----------------------------------------------------------------------------
# CORS / CSRF
# -----------------------------------------------------------------------------
# Development default:
#   CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
#
# Production:
#   CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
#   CSRF_TRUSTED_ORIGINS=https://your-frontend-domain.com
#   CORS_ALLOW_ALL_ORIGINS=False
# -----------------------------------------------------------------------------

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://localhost:3000",
)

CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS",
    default="http://localhost:5173,http://localhost:3000",
)

CORS_ALLOW_CREDENTIALS = env_bool("CORS_ALLOW_CREDENTIALS", default=True)

# Production'da asla True olmamalı.
# DEBUG=True iken local geliştirme için açılabilir; default yine False.
CORS_ALLOW_ALL_ORIGINS = env_bool("CORS_ALLOW_ALL_ORIGINS", default=False)

if not DEBUG and CORS_ALLOW_ALL_ORIGINS:
    raise ValueError("DEBUG=False iken CORS_ALLOW_ALL_ORIGINS=True olamaz.")


# -----------------------------------------------------------------------------
# Django REST Framework / JWT
# -----------------------------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
}


# -----------------------------------------------------------------------------
# Security headers
# -----------------------------------------------------------------------------
# Local development HTTP çalıştığı için SSL ayarlarını DEBUG=False iken açıyoruz.
# Deploy ortamında reverse proxy HTTPS kullanıyorsa SECURE_PROXY_SSL_HEADER gerekir.
# -----------------------------------------------------------------------------

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", default=True)
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
REFERRER_POLICY = "same-origin"

# Render / Railway / Nginx / proxy arkasında HTTPS terminate ediliyorsa gerekebilir.
if env_bool("USE_X_FORWARDED_PROTO", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")