import os
from os.path import abspath, dirname
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from decouple import config

DEBUG = config('DEBUG', default=False, cast=bool)

print('Dev settings = ', config('DEBUG'))

print(DEBUG)

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

SECURE_SSL_REDIRECT = False


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!


SECRET_KEY = config('SECRET_KEY')

SITE_ID = 8

# SECURITY WARNING: don't run with debug turned on in production!

ALLOWED_HOSTS = config('ALLOWED_HOSTS').split(' ')

# APPEND_SLASH = False

# Application definition

INSTALLED_APPS = [
    'whitenoise.runserver_nostatic',
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
    'profile',
    'accounts',
    'flights',
    'pdf_output',
    'csv_app',

    # 'api',
    'django_extensions',
    'corsheaders',
    # 'debug_toolbar',
    'picklefield',
    'widget_tweaks',
    'columns',
    'extra_views',
    'anymail',
    'storages',
    'django_celery_results',
    'django_celery_beat'
]

AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
    # needed for all_auth
    'allauth.account.auth_backends.AuthenticationBackend',
)

ACCOUNT_USERNAME_REQUIRED = False

ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 1
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_SIGNUP_EMAIL_ENTER_TWICE = True
ACCOUNT_USER_DISPLAY = 'utils.allauth.user_display'

ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT = 216000  # 1 hour
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_ADAPTER = 'allauth.account.adapter.DefaultAccountAdapter'
ACCOUNT_USERNAME_BLACKLIST = ['admin', 'pigarkle', 'test']

ACCOUNT_FORMS = {
    'signup': 'accounts.forms.CustomSignupForm',
}

SOCIALACCOUNT_EMAIL_VERIFICATION = ACCOUNT_EMAIL_VERIFICATION
SOCIALACCOUNT_EMAIL_REQUIRED = ACCOUNT_EMAIL_REQUIRED

LOGIN_REDIRECT_URL = '/home'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = ACCOUNT_LOGOUT_REDIRECT_URL
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = LOGIN_REDIRECT_URL


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
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

DATE_INPUT_FORMATS = ['%m-%d-%Y', '%m/%d/%Y', '%Y-%m-%d']

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
AWS_DEFAULT_ACL = None
AWS_S3_FILE_OVERWRITE = False
MEDIA_URL = config('MEDIA_URL')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}

if DEBUG is False:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'handlers': {
            'file': {
                'level': 'WARNING',
                'class': 'logging.FileHandler',
                'filename': config('LOG_DIR'),
            },
        },
        'loggers': {
            'django': {
                'handlers': ['file'],
                'level': 'INFO',
                'propagate': True,
            },
        },
    }


ANYMAIL = {
    # (exact settings here depend on your ESP...)
    "MAILGUN_API_KEY": config('MAILGUN_API_KEY'),
    "MAILGUN_SENDER_DOMAIN": 'mg.direct2logbook.com',  # your Mailgun domain, if needed
}

# or sendgrid.EmailBackend, or...
if DEBUG is True:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"

DEFAULT_FROM_EMAIL = "no-reply@direct2logbook.com"

CSRF_USE_SESSIONS = True
