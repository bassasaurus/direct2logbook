from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache


@never_cache
def csrf_failure(request, reason=''):
    """Offer recovery without replaying a rejected POST or exposing its contents."""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'message': 'This form has expired. Refresh the page and try again.'}, status=403)
    login = request.path == reverse('account_login')
    retry_url = reverse('account_login') if login else request.get_full_path()
    if not url_has_allowed_host_and_scheme(retry_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        retry_url = reverse('home')
    return render(request, 'account/session_expired.html', {
        'sign_in_expired': login, 'retry_url': retry_url,
    }, status=403)
