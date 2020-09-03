from django.test import TestCase
from django.contrib.auth.models import User
import stripe
from decouple import config

# class NewUserSignUp(TestCase):
#
#     def create_user(self):
#         User.objects.create_user(name="Test User")
#
#     stripe.api_key = 'sk_test_BiWcuDHJRWpGoj35FSL0Rped009H2t2bFq'
#
#     session = stripe.checkout.Session.create(
#         customer='cus_123',
#         payment_method_types=['card'],
#         line_items=[{
#             'name': 'T-shirt',
#             'description': 'Comfortable cotton t-shirt',
#             'images': ['https://example.com/t-shirt.png'],
#             'amount': 500,
#             'currency': 'usd',
#             'quantity': 1,
#             }],
#         success_url='https://example.com/success',
#         cancel_url='https://example.com/cancel',
#     )
