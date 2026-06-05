from django.contrib.auth.models import User
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    show_full_name_on_public_map = models.BooleanField(default=False)

    def __str__(self):
        return f"Profile for {self.user.username}"
