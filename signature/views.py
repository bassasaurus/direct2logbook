from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.generic import CreateView, DeleteView
from django.shortcuts import get_object_or_404
from .forms import SignatureForm
from flights.views import LoginRequiredMixin
from .models import Signature


class SignatureCreateView(LoginRequiredMixin, CreateView):
    model = Signature
    form_class = SignatureForm
    success_url = '/accounts/profile'

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_context_data(self, **kwargs):

        context = super(SignatureCreateView, self).get_context_data(**kwargs)
        context['title'] = "D-> | Upload Signature"
        context['home_link'] = reverse('home')
        context['page_title'] = "Upload Signature"
        context['parent_link'] = reverse('profile')
        context['parent_name'] = 'Profile'
        return context


class SignatureDeleteView(LoginRequiredMixin, DeleteView):
    model = Signature
    template_name = 'signature/signature_confirm_delete.html'
    success_url = '/accounts/profile/'

    def get_queryset(self):
        return Signature.objects.filter(user=self.request.user)

    def get_object(self, queryset=None):
        # Look up the signature by the logged-in user instead of pk
        return get_object_or_404(Signature, user=self.request.user)

    def get_context_data(self, **kwargs):

        context = super(SignatureDeleteView, self).get_context_data(**kwargs)

        signature = Signature.objects.get(user=self.request.user)

        context['signature'] = signature
        context['title'] = "D-> | New Aircraft"
        context['signature'] = Signature.objects.get(user=self.request.user)
        context['home_link'] = reverse('home')
        context['page_title'] = "Delete Signature"
        context['parent_link'] = reverse('profile')
        context['parent_name'] = 'Profile'
        return context
