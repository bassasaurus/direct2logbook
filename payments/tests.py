from django.test import TestCase
from django.contrib.auth.models import User
import stripe
from decouple import config

class NewUserSignUp(TestCase):

    def create_user(self):
        User.objects.create_user(name="Test User")
