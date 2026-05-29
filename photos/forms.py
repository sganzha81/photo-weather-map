from django import forms
from django.utils import timezone

from .models import Photo


class PhotoEditForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ["taken_at", "latitude", "longitude", "is_public"]
        widgets = {
            "taken_at": forms.DateTimeInput(
                attrs={"type": "datetime-local"},
                format="%Y-%m-%dT%H:%M",
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "is_public": forms.CheckboxInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["taken_at"].input_formats = ["%Y-%m-%dT%H:%M"]

        if self.instance and self.instance.taken_at and not self.is_bound:
            taken_at = self.instance.taken_at
            if timezone.is_aware(taken_at):
                taken_at = timezone.localtime(taken_at)
            self.initial["taken_at"] = taken_at.strftime("%Y-%m-%dT%H:%M")
