"""
Django settings for medication_backend project.
"""

from pathlib import Path
from datetime import timedelta
import os
import sys

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY    = 'django-insecure-your-secret-key-change-in-production'
DEBUG         = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_celery_beat',
    'django_celery_results',

    # Our apps
    'accounts',
    'prescriptions',
    'predictions',
    'notifications',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'medication_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'medication_backend.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
# FIX: Keep TIME_ZONE as IST for display. USE_TZ=True means Django stores UTC
# internally but converts to IST for display. Celery is also set to IST below.
TIME_ZONE = 'Asia/Kolkata'
USE_I18N  = True
USE_TZ    = True

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# FIX: MEDIA_URL must have a leading slash so image URLs resolve correctly
MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':    timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME':   timedelta(days=30),
    'ROTATE_REFRESH_TOKENS':    False,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM':                'HS256',
    'SIGNING_KEY':              SECRET_KEY,
    'AUTH_HEADER_TYPES':        ('Bearer',),
    # FIX: Update patient.last_login on every token issue
    'UPDATE_LAST_LOGIN':        True,
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_ALL_ORIGINS = True

# ── Tesseract OCR (local fallback) ─────────────────────────────────────────
# FIX: Auto-detect platform instead of hardcoding Windows path.
# On Linux/Mac, tesseract is on $PATH so no explicit cmd is needed.
# On Windows, fall back to the default installation path.
if sys.platform == 'win32':
    TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
else:
    # On Linux/Mac tesseract is on PATH — pytesseract finds it automatically.
    # Set to 'tesseract' so ocr_service.py can assign it without crashing.
    TESSERACT_CMD = 'tesseract'

# ── Twilio SMS ─────────────────────────────────────────────────────────────
USE_TWILIO          = True
TWILIO_ACCOUNT_SID  = 'AC9edaf1133030283210aac23d6169d970'
TWILIO_AUTH_TOKEN   = '1617f9c4f131419182e6f99aeb11987d'
TWILIO_PHONE_NUMBER = '+14137281674'

# ── Celery + Redis ─────────────────────────────────────────────────────────
CELERY_BROKER_URL        = 'redis://127.0.0.1:6379/0'
CELERY_RESULT_BACKEND    = 'django-db'
CELERY_ACCEPT_CONTENT    = ['json']
CELERY_TASK_SERIALIZER   = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# FIX: CELERY_ENABLE_UTC=True with CELERY_TIMEZONE='Asia/Kolkata' caused a
# 5.5-hour offset — Celery stored scheduled_time in UTC but compared using IST,
# so reminders fired 5.5 hours late (or never within the 2-minute window).
# Solution: disable UTC mode so Celery works entirely in IST, matching Django's
# USE_TZ=True behaviour where timezone.now() returns UTC-aware datetimes that
# Django automatically converts to IST for display.
CELERY_TIMEZONE   = 'Asia/Kolkata'
CELERY_ENABLE_UTC = False

# FIX: Explicit scheduler backend — prevents Beat from using an incompatible
# in-memory scheduler when django_celery_beat is installed.
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

CELERY_BEAT_SCHEDULE = {
    'send-due-reminders-every-minute': {
        'task':     'notifications.tasks.send_due_reminders',
        'schedule': 60.0,
    },
}

# ── Google Cloud Vision (optional — needs google_credentials.json) ─────────
GOOGLE_CLOUD_VISION_CREDENTIALS = BASE_DIR / 'google_credentials.json'

# ── Gemini Vision API (FREE — primary OCR for handwritten prescriptions) ───
# Get free key at: https://aistudio.google.com (no credit card needed)
# Free tier: 15 requests/minute, 1500/day
GEMINI_API_KEY = "AIzaSyB1YUN6dRm5JrA55Qsie4FE031S99WrniM"

# ── OCR.space (free text OCR fallback — 25k requests/month) ────────────────
OCR_SPACE_API_KEY = "K89361646188957"