from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, DeleteView, UpdateView
from django.shortcuts import get_object_or_404
from .forms import SignatureForm
from flights.views import LoginRequiredMixin
from .models import Signature


class SignatureCreateView(LoginRequiredMixin, CreateView):
    model = Signature
    form_class = SignatureForm
    success_url = reverse_lazy('profile')

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
    success_url = reverse_lazy('profile')

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


class SignatureUpdateView(LoginRequiredMixin, UpdateView):
    model = Signature
    form_class = SignatureForm
    template_name = 'signature/signature_form.html'
    success_url = reverse_lazy('profile')

    def get_object(self, queryset=None):
        signature = get_object_or_404(Signature, user=self.request.user)
        # Keep a saved snapshot for comparison even if POST validation mutates the form instance.
        self.current_signature = str(signature.signature or '')
        return signature

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(title='D-> | Update Signature', page_title='Update Signature',
                       parent_link=reverse('profile'), parent_name='Profile', submit_action='update',
                       current_signature=self.current_signature)
        return context
