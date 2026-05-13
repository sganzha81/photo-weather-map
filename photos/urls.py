from django.urls import path
from . import views

urlpatterns = [
    path('data.json', views.photos_geojson, name='photos_geojson'),
    path('my/', views.user_photos, name='user_photos'),
    path("", views.photo_list, name="photo_list"),
    path("upload/", views.upload_photo, name="upload_photo"),
    path("place/", views.get_place_name, name="get_place_name"),
    path(
        "delete/<int:photo_id>/", views.delete_photo, name="delete_photo"
    ),  # новый маршрут
]
