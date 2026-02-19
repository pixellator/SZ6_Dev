"""
wsz6_portal/settings/production.py

Production settings. All secrets must be provided via environment
variables or a secure .env file (never committed to version control).
"""

from .base import *
from decouple import config

DEBUG = False

ALLOWED_HOSTS = config('DJANGO_ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])

# ---------------------------------------------------------------------------
# Databases (PostgreSQL required in production)
# ---------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     config('UARD_DB_NAME'),
        'USER':     config('UARD_DB_USER'),
        'PASSWORD': config('UARD_DB_PASSWORD'),
        'HOST':     config('UARD_DB_HOST', default='localhost'),
        'PORT':     config('UARD_DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
    },
    'gdm': {
        'ENGINE':   'django.db.backends.postgresql',
        'NAME':     config('GDM_DB_NAME'),
        'USER':     config('GDM_DB_USER'),
        'PASSWORD': config('GDM_DB_PASSWORD'),
        'HOST':     config('GDM_DB_HOST', default='localhost'),
        'PORT':     config('GDM_DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
    },
}

# ---------------------------------------------------------------------------
# Channel Layer (Redis required in production)
# ---------------------------------------------------------------------------

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', default='redis://127.0.0.1:6379')],
            'capacity': 1500,
        },
    },
}

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ---------------------------------------------------------------------------
# Email (use a real backend in production)
# ---------------------------------------------------------------------------

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = True
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@wsz6portal.example.com')

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
