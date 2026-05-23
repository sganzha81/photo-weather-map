from django.urls import path
from . import views

urlpatterns = [
    path('data.json', views.photos_geojson, name='photos_geojson'),
    path('my/', views.user_photos, name='user_photos'),
    path("", views.photo_list, name="photo_list"),
    path("upload/", views.upload_photo, name="upload_photo"),
    path("edit/<int:photo_id>/", views.edit_photo, name="edit_photo"),
    path("place/", views.get_place_name, name="get_place_name"),
    path(
        "weather/refresh/<int:photo_id>/",
        views.refresh_weather,
        name="refresh_weather",
    ),
    path(
        "delete/<int:photo_id>/", views.delete_photo, name="delete_photo"
    ),  # новый маршрут
]
