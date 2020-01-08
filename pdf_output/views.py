
from pdf_output.models import Signature
from django.contrib.auth.decorators import login_required
import datetime

from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import reverse
from django.views.generic import CreateView, UpdateView, DetailView, DeleteView

from .forms import SignatureForm
from django.contrib.auth.mixins import UserPassesTestMixin
from flights.views import LoginRequiredMixin

from .pdf_generate_task import pdf_generate

from celery import Celery


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


class SignatureUpdateView(LoginRequiredMixin, UpdateView):
    model = Signature
    form_class = SignatureForm
    template_name = 'pdf_output/signature_update.html'
    success_url = '/accounts/profile/'

    def get_context_data(self, **kwargs):

        context = super(SignatureUpdateView, self).get_context_data(**kwargs)
        context['title'] = "D-> | Update Signature"

        context['home_link'] = reverse('profile')
        context['page_title'] = "Update Signature"
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


@login_required
def PDFView(request, user_id):

    user_pk = request.user.pk

    pdf_generate.delay(user_pk)

    response = HttpResponse('Check your email')
    # response.write(pdf)

    return response
