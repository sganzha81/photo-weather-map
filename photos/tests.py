from datetime import datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import Photo


class UserPhotosPublicFilterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sam", password="password")
        self.other_user = User.objects.create_user(username="alex", password="password")

    def create_photo(self, user, filename, is_public=False):
        photo = Photo(
            user=user,
            image=f"photos/tests/{filename}",
            is_public=is_public,
            file_size=18,
        )
        Photo.objects.bulk_create([photo])
        return photo

    def test_public_filter_counts_and_limits_photos_to_current_user(self):
        public_photo = self.create_photo(self.user, "public.jpg", is_public=True)
        private_photo = self.create_photo(self.user, "private.jpg", is_public=False)
        self.create_photo(self.other_user, "other-public.jpg", is_public=True)

        self.client.force_login(self.user)

        response = self.client.get(reverse("user_photos"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["filter_counts"]["public"], 1)
        self.assertEqual(response.context["public_photo_count"], 1)
        self.assertContains(response, "Публичные:")
        self.assertContains(response, '<span data-public-count>1</span>', html=True)
        self.assertContains(response, "🌍 Публичное")
        self.assertContains(response, "🔒 Приватное")

        response = self.client.get(f"{reverse('user_photos')}?status=public")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_status"], "public")
        self.assertEqual(list(response.context["photos"]), [public_photo])
        self.assertNotIn(private_photo, response.context["photos"])

    def test_public_filter_empty_state(self):
        self.create_photo(self.user, "private.jpg", is_public=False)

        self.client.force_login(self.user)
        response = self.client.get(f"{reverse('user_photos')}?status=public")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "У вас пока нет публичных фото.")
        self.assertContains(
            response,
            "Отметьте фото как публичные, чтобы они появились на публичной карте.",
        )


class TogglePhotoPublicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sam", password="password")
        self.other_user = User.objects.create_user(username="alex", password="password")

    def create_photo(self, user, filename, is_public=False):
        photo = Photo(
            user=user,
            image=f"photos/tests/{filename}",
            is_public=is_public,
            file_size=18,
        )
        Photo.objects.bulk_create([photo])
        return photo

    def test_authenticated_user_can_make_own_photo_public(self):
        photo = self.create_photo(self.user, "private.jpg", is_public=False)
        self.client.force_login(self.user)

        response = self.client.post(reverse("toggle_photo_public", args=[photo.pk]))

        photo.refresh_from_db()
        self.assertRedirects(response, reverse("user_photos"))
        self.assertTrue(photo.is_public)

    def test_repeated_post_makes_photo_private_again(self):
        photo = self.create_photo(self.user, "public.jpg", is_public=True)
        self.client.force_login(self.user)

        response = self.client.post(reverse("toggle_photo_public", args=[photo.pk]))

        photo.refresh_from_db()
        self.assertRedirects(response, reverse("user_photos"))
        self.assertFalse(photo.is_public)

    def test_ajax_post_returns_public_toggle_json(self):
        photo = self.create_photo(self.user, "private.jpg", is_public=False)
        self.create_photo(self.user, "already-public.jpg", is_public=True)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("toggle_photo_public", args=[photo.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        photo.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertTrue(photo.is_public)

        data = response.json()
        self.assertEqual(
            data,
            {
                "success": True,
                "photo_id": photo.id,
                "is_public": True,
                "public_count": 2,
                "message": "Фото теперь отображается на публичной карте.",
            },
        )

    def test_ajax_post_returns_private_toggle_json(self):
        photo = self.create_photo(self.user, "public.jpg", is_public=True)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("toggle_photo_public", args=[photo.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        photo.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertFalse(photo.is_public)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["photo_id"], photo.id)
        self.assertFalse(data["is_public"])
        self.assertEqual(data["public_count"], 0)
        self.assertEqual(data["message"], "Фото скрыто с публичной карты.")

    def test_user_cannot_toggle_another_users_photo(self):
        photo = self.create_photo(self.other_user, "other-public.jpg", is_public=True)
        self.client.force_login(self.user)

        response = self.client.post(reverse("toggle_photo_public", args=[photo.pk]))

        photo.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertTrue(photo.is_public)

    def test_safe_next_redirect_is_preserved(self):
        photo = self.create_photo(self.user, "private.jpg", is_public=False)
        self.client.force_login(self.user)
        next_url = "/photos/my/?status=public"

        response = self.client.post(
            reverse("toggle_photo_public", args=[photo.pk]),
            {"next": next_url},
        )

        self.assertRedirects(response, next_url)

    def test_unsafe_next_redirect_is_ignored(self):
        photo = self.create_photo(self.user, "private.jpg", is_public=False)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("toggle_photo_public", args=[photo.pk]),
            {"next": "https://evil.com/"},
        )

        self.assertRedirects(response, reverse("user_photos"))

    def test_user_photos_page_shows_public_toggle_switches_in_status_row(self):
        self.create_photo(self.user, "private.jpg", is_public=False)
        self.create_photo(self.user, "public.jpg", is_public=True)
        self.client.force_login(self.user)

        response = self.client.get(reverse("user_photos"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "status-row")
        self.assertContains(response, 'class="public-toggle-form"', count=2)
        self.assertContains(response, "data-public-toggle-form")
        self.assertContains(response, "data-visibility-badge")
        self.assertContains(response, "data-public-switch")
        self.assertContains(response, "data-public-count")
        self.assertContains(response, "active-status")
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, "На публичной карте", count=2)
        self.assertContains(response, "Фото отображается на вашей публичной карте")
        self.assertContains(response, "Фото скрыто с вашей публичной карты")
        self.assertContains(response, "Показывать фото на публичной карте")
        self.assertContains(response, "Скрыть фото с публичной карты")
        self.assertContains(response, "public-switch-on")
        self.assertContains(response, "public-switch-off")
        self.assertNotContains(response, "Сделать публичным")
        self.assertNotContains(response, "Скрыть с публичной карты")


class CalculateClimateNormAjaxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sam", password="password")
        self.other_user = User.objects.create_user(username="alex", password="password")

    def create_photo(self, user, filename, **overrides):
        defaults = {
            "user": user,
            "image": f"photos/tests/{filename}",
            "file_size": 18,
            "latitude": 53.1959,
            "longitude": 50.1002,
            "taken_at": timezone.make_aware(datetime(2024, 5, 10, 12, 0)),
            "weather_data": {"source": "hourly", "temperature": 18.0},
        }
        defaults.update(overrides)
        photo = Photo(**defaults)
        Photo.objects.bulk_create([photo])
        return photo

    @patch("photos.views.fetch_climate_comparison_for_photo")
    def test_ajax_post_returns_climate_json(self, fetch_climate):
        photo = self.create_photo(self.user, "with-weather.jpg")
        fetch_climate.return_value = {
            "normal_temperature": 12.345,
            "temperature_anomaly": 5.655,
            "comparison_text": "Теплее обычного.",
            "years_used": [2021, 2022, 2023],
        }
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("calculate_climate_norm", args=[photo.pk]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        photo.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(photo.climate_data, fetch_climate.return_value)

        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["photo_id"], photo.id)
        self.assertEqual(data["climate_data"], fetch_climate.return_value)
        self.assertEqual(data["climate_display"]["normal_temperature"], "+12.3 °C")
        self.assertEqual(data["climate_display"]["comparison_text"], "Теплее обычного.")
        self.assertEqual(data["climate_display"]["years_used"], [2021, 2022, 2023])
        self.assertEqual(data["message"], "Климатическая норма рассчитана.")

    @patch("photos.views.fetch_climate_comparison_for_photo")
    def test_regular_post_still_redirects(self, fetch_climate):
        photo = self.create_photo(self.user, "with-weather.jpg")
        fetch_climate.return_value = {
            "normal_temperature": 12.0,
            "comparison_text": "Обычная погода.",
        }
        self.client.force_login(self.user)

        response = self.client.post(reverse("calculate_climate_norm", args=[photo.pk]))

        self.assertRedirects(response, reverse("user_photos"))

    def test_user_cannot_calculate_climate_for_another_users_photo(self):
        photo = self.create_photo(self.other_user, "other.jpg")
        self.client.force_login(self.user)

        response = self.client.post(reverse("calculate_climate_norm", args=[photo.pk]))

        self.assertEqual(response.status_code, 404)

    def test_user_photos_page_has_climate_ajax_hooks(self):
        self.create_photo(self.user, "with-weather.jpg", climate_data=None)
        self.client.force_login(self.user)

        response = self.client.get(reverse("user_photos"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="climate-form"')
        self.assertContains(response, "data-climate-form")
        self.assertContains(response, "data-climate-feedback")
        self.assertContains(response, "data-photo-meta")
        self.assertContains(response, "csrfmiddlewaretoken")


class EditPhotoNextTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="sam", password="password")

    def create_photo(self, filename, **overrides):
        defaults = {
            "user": self.user,
            "image": f"photos/tests/{filename}",
            "file_size": 18,
            "latitude": 53.1959,
            "longitude": 50.1002,
            "taken_at": timezone.make_aware(datetime(2024, 5, 10, 12, 0)),
            "weather_data": {"source": "hourly", "temperature": 18.0},
        }
        defaults.update(overrides)
        photo = Photo(**defaults)
        Photo.objects.bulk_create([photo])
        return photo

    def edit_payload(self, next_url=None):
        payload = {
            "taken_at": "2024-05-10T12:00",
            "latitude": "53.1959",
            "longitude": "50.1002",
            "is_public": "on",
        }
        if next_url is not None:
            payload["next"] = next_url
        return payload

    def test_user_photos_cards_have_anchor_and_edit_next(self):
        photo = self.create_photo("public.jpg", is_public=True)
        self.client.force_login(self.user)

        response = self.client.get(f"{reverse('user_photos')}?status=public")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'id="photo-{photo.id}"')
        self.assertContains(response, f"data-photo-id=\"{photo.id}\"")
        self.assertContains(
            response,
            f"{reverse('edit_photo', args=[photo.id])}?next=/photos/my/%3Fstatus%3Dpublic%23photo-{photo.id}",
        )

    @patch("photos.views.fetch_weather_for_photo")
    def test_edit_photo_post_redirects_to_safe_next(self, fetch_weather):
        photo = self.create_photo("photo.jpg")
        fetch_weather.return_value = {"source": "hourly", "temperature": 19.0}
        self.client.force_login(self.user)
        next_url = f"/photos/my/?status=public#photo-{photo.id}"

        response = self.client.post(
            reverse("edit_photo", args=[photo.id]),
            self.edit_payload(next_url),
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    @patch("photos.views.fetch_weather_for_photo")
    def test_edit_photo_post_ignores_unsafe_next(self, fetch_weather):
        photo = self.create_photo("photo.jpg")
        fetch_weather.return_value = {"source": "hourly", "temperature": 19.0}
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("edit_photo", args=[photo.id]),
            self.edit_payload("https://evil.com/"),
        )

        self.assertRedirects(response, reverse("user_photos"))

    def test_edit_page_contains_hidden_next_and_cancel_link(self):
        photo = self.create_photo("photo.jpg")
        self.client.force_login(self.user)
        next_url = f"/photos/my/#photo-{photo.id}"

        response = self.client.get(
            f"{reverse('edit_photo', args=[photo.id])}?next=%2Fphotos%2Fmy%2F%23photo-{photo.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<input type="hidden" name="next" value="{next_url}">',
            html=True,
        )
        self.assertContains(response, f'href="{next_url}"')
