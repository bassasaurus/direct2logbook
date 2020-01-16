from decouple import config
from os.path import abspath, dirname
import os

print('development settings')
# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

POSTGRES_DB_NAME = config('POSTGRES_DB_NAME')
POSTGRES_UN = config('POSTGRES_UN')
POSTGRES_PW = config('POSTGRES_PW')
DB_HOST = config('DB_HOST')

SECURE_SSL_REDIRECT = False

DEBUG = True

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
    }
}

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DJANGO_ROOT = dirname(dirname(abspath(__file__)))

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' #disable/setup for production
