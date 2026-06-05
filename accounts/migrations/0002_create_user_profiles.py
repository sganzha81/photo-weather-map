from django.conf import settings
from django.db import migrations


def create_user_profiles(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    UserProfile = apps.get_model("accounts", "UserProfile")

    existing_profile_user_ids = set(
        UserProfile.objects.values_list("user_id", flat=True)
    )
    profiles = [
        UserProfile(user_id=user_id)
        for user_id in User.objects.values_list("id", flat=True)
        if user_id not in existing_profile_user_ids
    ]
    UserProfile.objects.bulk_create(profiles, ignore_conflicts=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_user_profiles, noop_reverse),
    ]
