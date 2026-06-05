from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import RegisterForm, USERNAME_ERROR_MESSAGE, UserProfileForm


class RegisterFormTests(TestCase):
    def form(self, username):
        return RegisterForm(
            data={
                "username": username,
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            }
        )

    def test_accepts_url_safe_username(self):
        form = self.form("olga-k16")

        self.assertTrue(form.is_valid(), form.errors)

    def test_normalizes_username_to_lowercase(self):
        form = self.form("Olga-K16")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["username"], "olga-k16")

    def test_strips_username_edge_spaces(self):
        form = self.form("  Olga-K16  ")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["username"], "olga-k16")

    def test_rejects_invalid_usernames(self):
        for username in ("Ольга@К16", "@olga", "olga k16", "olga/k16"):
            with self.subTest(username=username):
                form = self.form(username)

                self.assertFalse(form.is_valid())
                self.assertIn(USERNAME_ERROR_MESSAGE, form.errors["username"])

    def test_username_must_be_unique_after_normalization(self):
        User.objects.create_user(
            username="olga-k16",
            email="olga@example.com",
            password="password123",
        )

        form = self.form("Olga-K16")

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Пользователь с таким username уже существует.",
            form.errors["username"],
        )


class RegisterViewTests(TestCase):
    def test_post_creates_user_with_normalized_username(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "  Olga-K16  ",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(response, reverse("photo_list"))
        self.assertTrue(User.objects.filter(username="olga-k16").exists())


class UserProfileFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="olga",
            email="olga@example.com",
            password="password123",
        )

    def form_for_user(self, user, **overrides):
        data = {
            "username": user.username,
            "email": user.email,
            "first_name": "Ольга",
            "last_name": "Климова",
        }
        data.update(overrides)
        return UserProfileForm(data=data, instance=user)

    def test_accepts_url_safe_username(self):
        form = self.form_for_user(self.user, username="olga-k16")

        self.assertTrue(form.is_valid(), form.errors)

    def test_normalizes_username_to_lowercase(self):
        form = self.form_for_user(self.user, username="Olga-K16")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["username"], "olga-k16")

    def test_strips_username_edge_spaces(self):
        form = self.form_for_user(self.user, username="  olga-k16  ")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["username"], "olga-k16")

    def test_rejects_username_with_cyrillic_at_space_or_slash(self):
        for username in ("Ольга@К16", "olga k16", "olga/k16"):
            with self.subTest(username=username):
                form = self.form_for_user(self.user, username=username)

                self.assertFalse(form.is_valid())
                self.assertIn(USERNAME_ERROR_MESSAGE, form.errors["username"])

    def test_username_uniqueness_excludes_current_user(self):
        form = self.form_for_user(self.user, username="olga")

        self.assertTrue(form.is_valid(), form.errors)

    def test_username_must_be_unique_for_other_users(self):
        User.objects.create_user(
            username="taken",
            email="taken@example.com",
            password="password123",
        )

        form = self.form_for_user(self.user, username="taken")

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Пользователь с таким username уже существует.",
            form.errors["username"],
        )

    def test_email_is_required(self):
        form = self.form_for_user(self.user, email="")

        self.assertFalse(form.is_valid())
        self.assertIn("Обязательное поле.", form.errors["email"])

    def test_normalizes_email_to_lowercase(self):
        form = self.form_for_user(self.user, email="Test@Email.COM")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["email"], "test@email.com")

    def test_strips_email_edge_spaces(self):
        form = self.form_for_user(self.user, email="  test@email.com  ")

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["email"], "test@email.com")

    def test_email_must_be_unique_for_other_users(self):
        User.objects.create_user(
            username="another",
            email="taken@example.com",
            password="password123",
        )

        form = self.form_for_user(self.user, email="taken@example.com")

        self.assertFalse(form.is_valid())
        self.assertIn(
            "Пользователь с таким email уже существует.",
            form.errors["email"],
        )


class ProfileEditViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="olga",
            email="olga@example.com",
            password="password123",
        )

    def test_updates_profile_and_redirects_to_profile(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("profile_edit"),
            {
                "username": "  Olga-K16  ",
                "email": "  New@Example.COM  ",
                "first_name": "Ольга",
                "last_name": "Климова",
            },
        )

        self.assertRedirects(response, reverse("profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "olga-k16")
        self.assertEqual(self.user.email, "new@example.com")
        self.assertEqual(self.user.first_name, "Ольга")
        self.assertEqual(self.user.last_name, "Климова")
