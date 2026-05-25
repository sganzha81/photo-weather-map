import os

from django.core.management.base import BaseCommand

from photos.models import Photo


class Command(BaseCommand):
    help = "Заполняет file_size для старых фотографий."

    def handle(self, *args, **options):
        updated = 0
        skipped = 0
        errors = 0

        photos = Photo.objects.filter(file_size__isnull=True).only("id", "image")

        for photo in photos.iterator():
            if not photo.image:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(f"Photo {photo.pk}: нет файла изображения")
                )
                continue

            try:
                size = None

                try:
                    size = photo.image.size
                except Exception:
                    try:
                        image_path = photo.image.path
                    except Exception:
                        image_path = None

                    if image_path and os.path.exists(image_path):
                        size = os.path.getsize(image_path)

                if size is None:
                    skipped += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"Photo {photo.pk}: файл не найден ({photo.image.name})"
                        )
                    )
                    continue

                photo.file_size = size
                photo.save(update_fields=["file_size"])
                updated += 1

            except Exception as e:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Photo {photo.pk}: ошибка {type(e).__name__}: {e}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово. Обновлено: {updated}; пропущено: {skipped}; ошибок: {errors}."
            )
        )
