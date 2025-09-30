from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.views.generic import CreateView, DeleteView
from .forms import SignatureForm
from flights.views import LoginRequiredMixin
from .models import Signature


class SignatureCreateView(LoginRequiredMixin, CreateView):
    model = Signature
    form_class = SignatureForm
    success_url = '/accounts/profile'

    def form_valid(self, form):
        object = form.save(commit=False)
        object.user = self.request.user
        object.save()
        return super(SignatureCreateView, self).form_valid(form)

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
    template = '/pdf_output/signature_delete.html'
    success_url = '/accounts/profile/'

    def get_context_data(self, **kwargs):

        context = super(SignatureDeleteView, self).get_context_data(**kwargs)
        context['title'] = "D-> | New Aircraft"

        context['home_link'] = reverse('home')
        context['page_title'] = "Upload Signature"
        context['parent_link'] = reverse('profile')
        context['parent_name'] = 'Profile'
        return context
