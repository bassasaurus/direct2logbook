import base64
from io import BytesIO
from PIL import Image
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from signature.models import Signature


def image(color):
    output = BytesIO()
    Image.new('RGB', (2, 2), color=color).save(output, 'PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()


@override_settings(SECURE_SSL_REDIRECT=False)
class SignatureUpdateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('signature-web-owner')
        self.other = get_user_model().objects.create_user('signature-web-other')
        self.user.profile.free_access = True; self.user.profile.save()
        self.signature = Signature.objects.create(user=self.user, signature=image('black'))
        self.foreign = Signature.objects.create(user=self.other, signature=image('white'))
        self.client.force_login(self.user)

    def test_profile_update_link_opens_own_existing_signature_editor(self):
        profile = self.client.get(reverse('profile'))
        self.assertContains(profile, 'Update Signature')
        self.assertContains(profile, reverse('signature_update'))
        self.assertNotContains(profile, 'Delete Signature')
        response = self.client.get(reverse('signature_update'))
        self.assertEqual(response.context['form'].instance.pk, self.signature.pk)
        self.assertContains(response, 'data-submit-feedback="update"')
        self.assertEqual(response.context['current_signature'], image('black'))
        html = response.content.decode()
        self.assertLess(html.index('Current Signature'), html.index('name="signature"'))

    def test_save_updates_same_record_and_cannot_change_owner(self):
        replacement = image('red')
        response = self.client.post(reverse('signature_update'), {'signature': replacement, 'user': self.other.pk})
        self.assertRedirects(response, reverse('profile'))
        self.signature.refresh_from_db(); self.foreign.refresh_from_db()
        self.assertEqual(self.signature.signature, replacement)
        self.assertEqual(self.signature.user_id, self.user.pk)
        self.assertEqual(self.foreign.signature, image('white'))
        self.assertEqual(Signature.objects.filter(user=self.user).count(), 1)

    def test_invalid_or_anonymous_updates_do_not_change_signature(self):
        response = self.client.post(reverse('signature_update'), {'signature': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_signature'], image('black'))
        self.signature.refresh_from_db()
        self.assertEqual(self.signature.signature, image('black'))
        self.client.logout()
        self.assertEqual(self.client.post(reverse('signature_update'), {'signature': image('red')}).status_code, 302)
