from django.db import models
from signature_pad import SignaturePadField
from django.contrib.auth.models import User
from .encryption import encrypt_payload, decrypt_payload
from .strokes import validate_strokes


class Signature(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # Compatibility field for records created before encrypted storage.
    signature = SignaturePadField(blank=True, null=True)
    encrypted_data = models.TextField(blank=True, default='', editable=False)

    def set_strokes(self, strokes, aspect_ratio=3):
        import math
        from django.core.exceptions import ValidationError
        if self.user_id is None:
            raise ValueError('A signature must belong to an account before encryption.')
        validate_strokes(strokes)
        if not math.isfinite(aspect_ratio) or not .5 <= aspect_ratio <= 10:
            raise ValidationError('Invalid signature proportions.')
        self.encrypted_data = encrypt_payload({'strokes': strokes, 'aspect_ratio': aspect_ratio}, self.user_id)
        self.signature = None

    @property
    def rendered_signature(self):
        if self.encrypted_data:
            data = decrypt_payload(self.encrypted_data, self.user_id)
            if 'strokes' in data:
                from .rendering import render_signature
                return render_signature(data['strokes'], data['aspect_ratio'])
            return data['image']
        return str(self.signature) if self.signature else None

    def save(self, *args, **kwargs):
        if hasattr(self, '_pending_strokes'):
            self.set_strokes(*self._pending_strokes)
            del self._pending_strokes
        # Legacy clients/admin can still submit PNG; never persist new plaintext images.
        if self.signature:
            self._meta.get_field('signature').clean(self.signature, self)
            self.encrypted_data = encrypt_payload({'image': str(self.signature)}, self.user_id)
            self.signature = None
            if kwargs.get('update_fields') is not None:
                kwargs['update_fields'] = set(kwargs['update_fields']) | {'signature', 'encrypted_data'}
        if self.encrypted_data and kwargs.get('update_fields') is not None:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'signature', 'encrypted_data'}
        super().save(*args, **kwargs)
