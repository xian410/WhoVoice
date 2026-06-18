from django.urls import path
from .views import CelebrityListView, CelebrityDetailView, LyricsTemplateView

urlpatterns = [
    path("list/", CelebrityListView.as_view(), name="celebrity-list"),
    path("lyrics-templates/", LyricsTemplateView.as_view(), name="lyrics-templates"),
    path("<str:name>/", CelebrityDetailView.as_view(), name="celebrity-detail"),
]
