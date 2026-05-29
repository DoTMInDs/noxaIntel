"""
Django settings for config project.
"""
import os
from pathlib import Path
import environ


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environ
env = environ.Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, 'django-insecure-ai-soccer-betting-platform-super-secret-key-2026'),
    ALLOWED_HOSTS=(list, ['*']),
    DATABASE_URL=(str, f'sqlite:///{BASE_DIR}/db.sqlite3'),
    REDIS_URL=(str, 'redis://localhost:6379/0'),
    VAPID_PUBLIC_KEY=(str, ''),
    VAPID_PRIVATE_KEY=(str, ''),
    VAPID_ADMIN_EMAIL=(str, 'admin@noxaintel.com'),
)

# ngrok configuration for local development
if env('DEBUG'):
    NGROK_AUTH_TOKEN = env('NGROK_AUTH_TOKEN', default='')
    if NGROK_AUTH_TOKEN:
        os.system(f'ngrok authtoken {NGROK_AUTH_TOKEN}')
        os.system('ngrok http 8000 &')

# Take environment variables from .env file if exists
environ.Env.read_env(BASE_DIR / '.env')
SECRET_KEY = env('SECRET_KEY')

# DEBUG = env('DEBUG')
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = env('ALLOWED_HOSTS')
# ── Trusted origins (required for CSRF when behind reverse-proxies / ngrok) ──
_ngrok = env('NGROK_URL', default='')
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
if _ngrok:
    CSRF_TRUSTED_ORIGINS.append(_ngrok.rstrip('/'))
# Allow ALL ngrok-free.app subdomains automatically when DEBUG is on
if DEBUG:
    CSRF_TRUSTED_ORIGINS += [
        'https://*.ngrok-free.app',
        'https://*.ngrok.io',
    ]

CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://localhost').split(' ')

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

SESSION_COOKIE_AGE = 3600  # 1 hour (reasonable for financial app)
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # Allow persistent sessions
SESSION_SAVE_EVERY_REQUEST = False  # Only save when modified (better performance)


if not DEBUG:
    # SSL Settings (controlled by Render env var)
    enable_ssl = os.getenv('ENABLE_SSL_SECURITY', 'False').lower() == 'true'
    if enable_ssl:
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_SSL_REDIRECT = True
        SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '31536000'))
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    
    # Safe security headers (always enable in production)
    SECURE_BROWSER_XSS_FILTER = os.getenv('SECURE_BROWSER_XSS_FILTER', 'True').lower() == 'true'
    SECURE_CONTENT_TYPE_NOSNIFF = os.getenv('SECURE_CONTENT_TYPE_NOSNIFF', 'True').lower() == 'true'
    X_FRAME_OPTIONS = os.getenv('X_FRAME_OPTIONS', 'DENY')
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'django_htmx',
    
    # Local apps
    'users.apps.UsersConfig',
    'matches.apps.MatchesConfig',
    'predictions.apps.PredictionsConfig',
    'betting.apps.BettingConfig',
    'ai_engine.apps.AiEngineConfig',
    'notifications.apps.NotificationsConfig',
    'analytics.apps.AnalyticsConfig',
    'pwa.apps.PwaConfig',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'config.context_processors.vapid_public_key',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database
DATABASES = {
    'default': env.db('DATABASE_URL')
}

# Cache configuration (Redis for low latency)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
        }
    }
}

# Custom User Model
AUTH_USER_MODEL = 'users.CustomUser'
LOGIN_REDIRECT_URL = 'matches:dashboard'
LOGOUT_REDIRECT_URL = 'users:login'
LOGIN_URL = 'users:login'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# VAPID Keys for Web Push Notifications
VAPID_PUBLIC_KEY = env('VAPID_PUBLIC_KEY')
VAPID_PRIVATE_KEY = env('VAPID_PRIVATE_KEY')
VAPID_ADMIN_EMAIL = env('VAPID_ADMIN_EMAIL')

# Celery Configuration
CELERY_BROKER_URL = env('REDIS_URL')
CELERY_RESULT_BACKEND = env('REDIS_URL')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULE = {
    'sync-live-fixtures-and-odds-every-2m': {
        'task': 'ai_engine.tasks.sync_live_fixtures_and_odds',
        'schedule': 120.0,
    },
    'sync-daily-fixtures-every-12h': {
        'task': 'ai_engine.tasks.sync_daily_fixtures',
        'schedule': 43200.0,
    },
    'precompute-predictions-every-1h': {
        'task': 'ai_engine.tasks.precompute_upcoming_predictions',
        'schedule': 3600.0,
    },
}

# Logging configuration for cache hit/miss and AI engine monitoring
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'analytics': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'ai_engine': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
