import os
from os.path import abspath, dirname
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from decouple import config, Csv
from botocore.client import Config

DEBUG = config('DEBUG', default=False, cast=bool)

print('Dev settings = ', config('DEBUG'))


if DEBUG is False:
    sentry_sdk.init(
        dsn="https://65a9a45f86104c29873f4bdbfa6846b9@sentry.io/5178641",
        integrations=[DjangoIntegration(), CeleryIntegration()],
        send_default_pii=True
    )
else:
    print('Sentry Not Active')


if DEBUG is False:
    STRIPE_SECRET_KEY = config('STRIPE_LIVE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = config('STRIPE_LIVE_PUBLISHABLE_KEY')
    ENDPOINT_SECRET_KEY = config('ENDPOINT_LIVE_SECRET')
    PLAN_MONTHLY = config('PLAN_MONTHLY_LIVE')
    PLAN_YEARLY = config('PLAN_YEARLY_LIVE')
else:
    STRIPE_SECRET_KEY = config('STRIPE_TEST_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = config('STRIPE_TEST_PUBLISHABLE_KEY')
    ENDPOINT_SECRET_KEY = config('ENDPOINT_TEST_SECRET')
    PLAN_MONTHLY = config('PLAN_MONTHLY_TEST')
    PLAN_YEARLY = config('PLAN_YEARLY_TEST')

    print('Stripe Test Keys')

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DJANGO_ROOT = dirname(dirname(abspath(__file__)))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!


SECRET_KEY = config('SECRET_KEY')

SITE_ID = 8

# SECURITY WARNING: don't run with debug turned on in production!

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', cast=Csv())
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
CSRF_USE_SESSIONS = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
CSRF_COOKIE_DOMAIN = config('CSRF_COOKIE_DOMAIN')

APPEND_SLASH = True

# Application definition

INSTALLED_APPS = [
    # autocomplete
    'dal',
    'dal_select2',

    'django.contrib.contenttypes',
    'django.contrib.auth',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.facebook',
    'allauth.socialaccount.providers.google',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.admin',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # apps
    'api',
    'errors',
    'profile',
    'accounts',
    'flights',
    'pdf_output',
    'csv_app',
    'signature',

    'signature_pad',
    'rest_framework',
    'rest_framework.authtoken',
    'django_recaptcha',
    'django_extensions',

    'picklefield',
    'widget_tweaks',
    'columns',
    'extra_views',
    'anymail',
    'storages',
    'django_celery_results',
    'django_celery_beat',
]

AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
    # needed for all_auth
    'allauth.account.auth_backends.AuthenticationBackend',
)


ACCOUNT_SIGNUP_FIELDS = ['email*', 'email2*', 'password1*', 'password2*']
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_SIGNUP_FIELDS = ['email*', 'password1*']
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_SIGNUP_FIELDS = ['email*', 'email2*', 'password1*', 'password2*']
ACCOUNT_USER_DISPLAY = 'utils.allauth.user_display'

ACCOUNT_RATE_LIMITS = {
    "login_user": "5/m",      # 5 logins per minute per user
    "login_ip": "20/m",       # 20 logins per minute per IP
    "signup_ip": "5/h",       # 5 signups per hour per IP
}

ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_ADAPTER = 'allauth.account.adapter.DefaultAccountAdapter'
ACCOUNT_USERNAME_BLACKLIST = ['admin', 'pigarkle', 'test']

ACCOUNT_FORMS = {
    'signup': 'accounts.forms.CustomSignupForm',
}


# SOCIALACCOUNT_EMAIL_VERIFICATION = ACCOUNT_EMAIL_VERIFICATION
# SOCIALACCOUNT_EMAIL_REQUIRED = ACCOUNT_SIGNUP_FIELDS

LOGIN_REDIRECT_URL = '/home/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = ACCOUNT_LOGOUT_REDIRECT_URL
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = LOGIN_REDIRECT_URL

# SOCIALACCOUNT_EMAIL_VERIFICATION = ACCOUNT_EMAIL_VERIFICATION
# SOCIALACCOUNT_EMAIL_REQUIRED = ACCOUNT_EMAIL_REQUIRED


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    # 'debug_toolbar.middleware.DebugToolbarMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


ROOT_URLCONF = 'logbook.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],

        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # needed for {% media url %}
                'django.template.context_processors.media',
                # needed for allauth
                'django.template.context_processors.request',
            ],
        },
    },
]

MESSAGE_STORAGE = 'django.contrib.messages.storage.cookie.CookieStorage'


INTERNAL_IPS = '127.0.0.1:8000'

WSGI_APPLICATION = 'logbook.wsgi.application'

# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

POSTGRES_DB_NAME = config('POSTGRES_DB_NAME')
POSTGRES_UN = config('POSTGRES_UN')
POSTGRES_PW = config('POSTGRES_PW')
DB_HOST = config('DB_HOST')

DATABASES = {
    # 'default': {
    #     'ENGINE': 'django.db.backends.sqlite3',
    #     'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    # }
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': POSTGRES_DB_NAME,
        'USER': POSTGRES_UN,
        'PASSWORD': POSTGRES_PW,
        'HOST': DB_HOST,
        'PORT': '5432',
    }
}

CONN_MAX_AGE = None


# Password validation
# https://docs.djangoproject.com/en/1.10/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.10/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = False

USE_TZ = True

DATE_FORMAT = 'm/d/Y, m-d-Y'

DATE_INPUT_FORMATS = ['%m/%d/%Y']

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

STATIC_ROOT = "/home/blakepowell/static"
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]


MEDIA_URL = config('MEDIA_URL')

# --- credentials & bucket (env is best; shown here for clarity) ---
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY")
# e.g., "direct2logbook-media"
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME")
# <- MUST MATCH BUCKET'S REAL REGION
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="us-east-1")
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_S3_ADDRESSING_STYLE = "virtual"   # virtual-hosted-style URLs

# DO NOT set AWS_S3_CUSTOM_DOMAIN when using presigned S3 URLs.
# Leave querystring_auth at default (True) for private objects.

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "region_name": AWS_S3_REGION_NAME,
            # Pin the endpoint to the region so the host & signature match:
            "endpoint_url": f"https://s3.{AWS_S3_REGION_NAME}.amazonaws.com",
            # No access_key/secret_key here; django-storages reads globals above.
            "file_overwrite": False,
            "default_acl": None,
        },
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}


if not config('DEBUG', default=False, cast=bool):
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '[{asctime}] {levelname} {name}: {message}',
                'style': '{',
            },
            'simple': {
                'format': '{levelname}: {message}',
                'style': '{',
            },
        },
        'handlers': {
            'file': {
                'level': 'WARNING',
                'class': 'logging.FileHandler',
                'filename': '/home/blakepowell/logs/django.log',
                'formatter': 'verbose',
            },
        },
        'loggers': {
            'django': {
                'handlers': ['file'],
                'level': 'WARNING',
                'propagate': True,
            },
            'django.request': {
                'handlers': ['file'],
                'level': 'WARNING',
                'propagate': False,
            },
            'django.security.csrf': {
                'handlers': ['file'],
                'level': 'ERROR',
                'propagate': False,
            },
        },
    }


ANYMAIL = {
    "MAILGUN_API_KEY": config('MAILGUN_API_KEY'),
    "MAILGUN_SENDER_DOMAIN": 'mg.direct2logbook.com',
    "MAILGUN_API_URL": config('MAILGUN_API_URL')
}

# if DEBUG is True:
#     EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
# else:
#     EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"

EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"

DEFAULT_FROM_EMAIL = "no-reply@direct2logbook.com"

CSP_IMG_SRC = ("'self'", "data:", "https:", "blob:")

SILENCED_SYSTEM_CHECKS = ['django_recaptcha.recaptcha_test_key_error']

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 100,
    'DATE_FORMAT': '%m/%d/%Y',
    'DATE_INPUT_FORMATS': ['%m/%d/%Y']
}

# fix 3.2 upgrade error
DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

# --- Local development overrides ---
if config('DEBUG', default=False, cast=bool):
    # Don't force HTTPS locally
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

    # Allow cookies and CSRF over plain HTTP
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False

    # Optional: allow local HTTP origins for CSRF
    CSRF_TRUSTED_ORIGINS = [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]

    # Don’t require secure proxy headers in dev
    SECURE_PROXY_SSL_HEADER = None
