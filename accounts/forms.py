import re

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

from .models import UserProfile


USERNAME_ALLOWED_RE = re.compile(r"^[A-Za-z0-9._-]+$")
USERNAME_ERROR_MESSAGE = (
    "Username может содержать только латинские буквы, цифры, точку, дефис и "
    "подчёркивание."
)


def clean_url_safe_username(username):
    username = username.strip().lower()

    if not USERNAME_ALLOWED_RE.fullmatch(username):
        raise forms.ValidationError(USERNAME_ERROR_MESSAGE)

    return username


class RegisterForm(UserCreationForm):
    def clean_username(self):
        username = clean_url_safe_username(self.cleaned_data["username"])

        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Пользователь с таким username уже существует.")

        return username


class UserProfileForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="Email")
    show_full_name_on_public_map = forms.BooleanField(
        required=False,
        label="Показывать имя и фамилию на публичной карте",
        help_text=(
            "Если включено, на публичной карте будут отображаться имя и фамилия "
            "из профиля. Если выключено, будет отображаться только @username."
        ),
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "show_full_name_on_public_map",
        )
        labels = {
            "username": "Username",
            "email": "Email",
            "first_name": "Имя",
            "last_name": "Фамилия",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            profile, _ = UserProfile.objects.get_or_create(user=self.instance)
            self.fields["show_full_name_on_public_map"].initial = (
                profile.show_full_name_on_public_map
            )

    def clean_username(self):
        username = clean_url_safe_username(self.cleaned_data["username"])

        users = User.objects.filter(username=username)
        if self.instance.pk:
            users = users.exclude(pk=self.instance.pk)

        if users.exists():
            raise forms.ValidationError("Пользователь с таким username уже существует.")

        return username

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()

        users = User.objects.filter(email=email)
        if self.instance.pk:
            users = users.exclude(pk=self.instance.pk)

        if users.exists():
            raise forms.ValidationError("Пользователь с таким email уже существует.")

        return email

    def save(self, commit=True):
        user = super().save(commit=commit)

        if commit:
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.show_full_name_on_public_map = self.cleaned_data[
                "show_full_name_on_public_map"
            ]
            profile.save(update_fields=["show_full_name_on_public_map"])

        return user
