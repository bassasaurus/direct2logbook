import os
from os.path import abspath, basename, dirname, join, normpath
from sys import path
from decouple import config

"""
Django settings for logbook project.

Generated by 'django-admin startproject' using Django 1.10.2.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DJANGO_ROOT = dirname(dirname(abspath(__file__)))

SECURE_SSL_REDIRECT = False


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.10/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!


SECRET_KEY = config('SECRET_KEY')

SITE_ID = 4

# SECURITY WARNING: don't run with debug turned on in production!

DEBUG = False
ALLOWED_HOSTS = ["*"]

# APPEND_SLASH = False

# Application definition

INSTALLED_APPS = [
    'whitenoise.runserver_nostatic',
    #autocomplete
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

    #apps
    'accounts',
    'flights',
    'pdf_output',

    #installed
    'rest_framework',
    'rest_framework_docs',
    'api',
    'django_extensions',
    'corsheaders',
    'debug_toolbar',
    'picklefield',
    'widget_tweaks',
    'columns',
    'extra_views',
    'anymail',
]

AUTHENTICATION_BACKENDS = (
    # Needed to login by username in Django admin, regardless of `allauth`
    'django.contrib.auth.backends.ModelBackend',
    # needed for all_auth
    'allauth.account.auth_backends.AuthenticationBackend',
)
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS=3
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5
ACCOUNT_LOGIN_ATTEMPTS_TIMEOUT = 43200 # .5 day in seconds
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_ADAPTER='allauth.account.adapter.DefaultAccountAdapter'

ACCOUNT_SIGNUP_EMAIL_ENTER_TWICE=True
ACCOUNT_USERNAME_BLACKLIST=['admin', 'pigarkle', 'test']
ACCOUNT_UNIQUE_EMAIL=True
ACCOUNT_CONFIRM_EMAIL_ON_GET=True


SOCIALACCOUNT_EMAIL_VERIFICATION=ACCOUNT_EMAIL_VERIFICATION
SOCIALACCOUNT_EMAIL_REQUIRED=ACCOUNT_EMAIL_REQUIRED


LOGIN_REDIRECT_URL = '/home'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

ACCOUNT_EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL=ACCOUNT_LOGOUT_REDIRECT_URL
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL=LOGIN_REDIRECT_URL



MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'debug_toolbar.middleware.DebugToolbarMiddleware',
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

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.10/howto/static-files/

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

STATIC_ROOT = os.path.join(BASE_DIR, 'static')
STATIC_URL = '/static/'

MEDIA_ROOT = os.path.join(BASE_DIR, '/media/')
MEDIA_URL = '/media/'


REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAdminUser',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.LimitOffsetPagination',
    'PAGE_SIZE': 20
}

# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' #disable/setup for production


CACHES = {'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'logbook/debug.log',
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
EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"  # or sendgrid.EmailBackend, or...
DEFAULT_FROM_EMAIL = "no-reply@direct2logbook.com"  # if you don't already have this in settings

CSRF_USE_SESSIONS = True

if os.environ.get('DJANGO_DEVELOPMENT_SETTINGS') is not None:
    from .development import *
