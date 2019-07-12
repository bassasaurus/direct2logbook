
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect, reverse

from django.contrib.auth import login, authenticate

from accounts.forms import SignUpForm

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, UpdateView

from accounts.models import Profile
from accounts.forms import ProfileForm

from allauth.account.views import EmailView
from allauth.socialaccount.views import ConnectionsView

class LoginRequiredMixin(LoginRequiredMixin):
    login_url = '/accounts/login'
    # redirect_field_name = None

class UserObjectsMixin():

    def get_queryset(self):
        user = self.request.user
        return super(UserObjectsMixin, self).get_queryset().filter(user=user)

def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('home')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})

class ProfileView(LoginRequiredMixin, UserObjectsMixin, TemplateView):
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


# Views from allauth
class EmailView(EmailView):

    def get_context_data(self, **kwargs):
        context = super(EmailView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Update Email"
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Email'
        return context

class ConnectionsView(ConnectionsView):

    def get_context_data(self, **kwargs):
        context = super(ConnectionsView, self).get_context_data(**kwargs)

        context['title'] = "D-> | Update Social Accounts"
        context['parent_name'] = 'Profile'
        context['parent_link'] = reverse('profile')
        context['page_title'] = 'Update Social Accounts'
        return context
