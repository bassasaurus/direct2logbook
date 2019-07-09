
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, reverse

from django.contrib.auth import login, authenticate



from django.views.generic import TemplateView, UpdateView

from accounts.models import Profile
from accounts.forms import ProfileForm



class ProfileView(TemplateView):
    model = Profile
    template_name='profile/profile.html'

    def get_context_data(self, **kwargs):
        context = super(ProfileView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Profile"
        context['parent_name'] = 'Home'
        context['parent_link'] = reverse('home')
        context['page_title'] = 'Profile'
        return context


class ProfileUpdateView(UpdateView):

    def get_context_data(self, **kwargs):
        context = super(ProfileUpdateView, self).get_context_data(**kwargs)

        user = self.request.user
        pk = str(user.profile.pk)

        context['title'] = "D-> | Update Profile"
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Profile'
        return context

    model = Profile
    form_class = ProfileForm
    template_name = 'profile/profile_update.html'
    success_url = '/accounts/profile/'

# class ProfileUpdateView(LoginRequiredMixin, UserObjectsMixin, UpdateView):
#     model = Profile
#     fields = ()
#     template_name = 'profile/profile_update.html'
#     success_url = '/profile/'
#
#     def get_context_data(self, **kwargs):
#         context = super(ProfileUpdateView, self).get_context_data(**kwargs)
#
#         profile_form = ProfileForm()
#
#         context['profile_form'] = profile_form
#         context['title'] = "D-> | Update Profile"
#         context['parent_name'] = 'Profile'
#         context['parent_link'] = reverse('profile')
#         context['page_title'] = 'Update Profile'
#         return context
