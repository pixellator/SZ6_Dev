"""
wsz6_portal/settings/development.py

Development-environment settings.
Uses SQLite (no PostgreSQL needed to get started) and the
in-memory channel layer so the only hard dependency is Python itself.
Switch to Redis/PostgreSQL by setting USE_REDIS=true in .env.dev.
"""

from .base import *
from decouple import config

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']

# ---------------------------------------------------------------------------
# Databases
# ---------------------------------------------------------------------------

_use_postgres = config('USE_POSTGRES', default=False, cast=bool)

if _use_postgres:
    DATABASES = {
        'default': {
            'ENGINE':   'django.db.backends.postgresql',
            'NAME':     config('UARD_DB_NAME',     default='wsz6_uard'),
            'USER':     config('UARD_DB_USER',     default='wsz6'),
            'PASSWORD': config('UARD_DB_PASSWORD', default='wsz6dev'),
            'HOST':     config('UARD_DB_HOST',     default='localhost'),
            'PORT':     config('UARD_DB_PORT',     default='5432'),
        },
        'gdm': {
            'ENGINE':   'django.db.backends.postgresql',
            'NAME':     config('GDM_DB_NAME',     default='wsz6_gdm'),
            'USER':     config('GDM_DB_USER',     default='wsz6'),
            'PASSWORD': config('GDM_DB_PASSWORD', default='wsz6dev'),
            'HOST':     config('GDM_DB_HOST',     default='localhost'),
            'PORT':     config('GDM_DB_PORT',     default='5432'),
        },
    }
else:
    # Zero-dependency fallback for the earliest stage of development.
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db_uard.sqlite3',
        },
        'gdm': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db_gdm.sqlite3',
        },
    }

# ---------------------------------------------------------------------------
# Channel Layer
# ---------------------------------------------------------------------------

_use_redis = config('USE_REDIS', default=False, cast=bool)

if _use_redis:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': [config('REDIS_URL', default='redis://127.0.0.1:6379')],
            },
        },
    }
else:
    # In-memory channel layer: works without Redis, single-process only.
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }

# ---------------------------------------------------------------------------
# Email: print to console in development
# ---------------------------------------------------------------------------

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ---------------------------------------------------------------------------
# Logging: show SQL queries and debug info
# ---------------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',   # Set to DEBUG to log all SQL
            'propagate': False,
        },
    },
}
