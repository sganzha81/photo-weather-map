from django.contrib.auth.models import User
from django.test import TestCase
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
        self.assertContains(response, "Публичные: 1")
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
