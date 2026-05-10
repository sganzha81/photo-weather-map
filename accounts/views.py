from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages


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
