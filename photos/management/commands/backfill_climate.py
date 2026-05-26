from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from photos.climate import fetch_climate_comparison_for_photo
from photos.models import Photo


class Command(BaseCommand):
    help = "Mass backfills climate_data for photos with weather_data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            dest="username",
            help="Only process photos owned by this username.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Process no more than this many photos.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show which photos would be processed without saving changes.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Process matching photos even when climate_data is already set.",
        )

    def handle(self, *args, **options):
        username = options.get("username")
        limit = options.get("limit")
        dry_run = options["dry_run"]
        force = options["force"]

        if limit is not None and limit < 0:
            raise CommandError("--limit must be a non-negative integer.")

        queryset = (
            Photo.objects.select_related("user")
            .filter(
                latitude__isnull=False,
                longitude__isnull=False,
                taken_at__isnull=False,
                weather_data__isnull=False,
            )
            .order_by("id")
        )

        if not force:
            queryset = queryset.filter(climate_data__isnull=True)

        if username:
            User = get_user_model()
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist as exc:
                raise CommandError(f'User "{username}" does not exist.') from exc
            queryset = queryset.filter(user=user)

        if limit is not None:
            queryset = queryset[:limit]

        photos = list(queryset)
        total = len(photos)
        self.stdout.write(f"Found {total} photos for climate backfill.")

        updated = 0
        skipped = 0
        failed = 0

        for index, photo in enumerate(photos, start=1):
            prefix = self._format_prefix(index, total, photo)

            if dry_run:
                self.stdout.write(f"{prefix} dry-run")
                continue

            try:
                climate_data = fetch_climate_comparison_for_photo(photo)
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"{prefix} failed ({type(exc).__name__}: {exc})"
                    )
                )
                continue

            if not climate_data:
                skipped += 1
                self.stderr.write(self.style.WARNING(f"{prefix} skipped"))
                continue

            photo.climate_data = climate_data
            photo.save(update_fields=["climate_data"])
            updated += 1
            self.stdout.write(self.style.SUCCESS(f"{prefix} updated"))

        self.stdout.write(
            self.style.SUCCESS(
                "Done. "
                f"Updated: {updated}, "
                f"skipped: {skipped}, "
                f"failed: {failed}, "
                f"dry_run: {str(dry_run).lower()}"
            )
        )

    def _format_prefix(self, index, total, photo):
        username = photo.user.username if photo.user_id else "-"
        filename = photo.image.name if photo.image else "-"
        return f"[{index}/{total}] Photo {photo.pk} user={username} file={filename}"
