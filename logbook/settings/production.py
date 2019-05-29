from .base import *

SECURE_SSL_REDIRECT = True

DEBUG = False

INSTALLED_APPS += [
    'whitenoise.runserver_nostatic',
]

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

print('production settings')
