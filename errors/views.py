from django.shortcuts import reverse, render


def error_400(request, exception):
    context = {
        'title': '400',
        'home_link': reverse('home')
    }
    return render(request, '400.html', context)


def error_404(request, exception):
    context = {
        'title': '404',
        'home_link': reverse('home')
    }
    return render(request, '404.html', context)


def error_500(request):
    context = {
        'title': '500',
        'home_link': reverse('home')
    }
    return render(request, '500.html', context)


def error_403(request, exception):
    context = {
        'title': '403',
        'home_link': reverse('home'),
    }
    return render(request, '403.html', context)
