from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth import login, update_session_auth_hash
from django.contrib import messages
from django.db.models import Q, Sum

from photos.file_utils import format_file_size
from photos.models import Photo
from photos.site_settings import get_user_storage_limit_bytes

from .forms import UserProfileForm


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()  # создаёт пользователя в базе
            login(request, user)  # сразу авторизуем (создаём сессию)
            messages.success(request, "Регистрация прошла успешно!")
            return redirect("photo_list")
        else:
            messages.error(request, "Пожалуйста, исправьте ошибки.")
    else:
        form = UserCreationForm()
    return render(request, "registration/register.html", {"form": form})


@login_required
def profile(request):
    photos = Photo.objects.filter(user=request.user)
    storage_used = photos.aggregate(total=Sum("file_size"))["total"] or 0
    storage_limit = get_user_storage_limit_bytes()
    storage_usage_percent = (
        round(storage_used / storage_limit * 100, 1) if storage_limit else 0
    )
    storage_usage_bar_percent = min(storage_usage_percent, 100)
    storage_usage_bar_percent_css = f"{storage_usage_bar_percent:.1f}".rstrip(
        "0"
    ).rstrip(".")

    stats = {
        "total_photos": photos.count(),
        "public_photos": photos.filter(is_public=True).count(),
        "with_geo": photos.filter(
            latitude__isnull=False,
            longitude__isnull=False,
        ).count(),
        "without_geo": photos.filter(
            Q(latitude__isnull=True) | Q(longitude__isnull=True)
        ).count(),
        "with_weather": photos.filter(weather_data__isnull=False)
        .exclude(weather_data={})
        .count(),
        "with_climate": photos.filter(climate_data__isnull=False)
        .exclude(climate_data={})
        .count(),
    }

    context = {
        "stats": stats,
        "storage_used_display": format_file_size(storage_used),
        "storage_limit_display": format_file_size(storage_limit),
        "storage_usage_percent": storage_usage_percent,
        "storage_usage_bar_percent_css": storage_usage_bar_percent_css,
    }
    return render(request, "registration/profile.html", context)


@login_required
def profile_edit(request):
    if request.method == "POST":
        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль обновлён.")
            return redirect("profile")
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, "registration/profile_edit.html", {"form": form})


@login_required
def password_change(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Пароль успешно изменён.")
            return redirect("profile")
    else:
        form = PasswordChangeForm(request.user)

    return render(request, "registration/password_change.html", {"form": form})
