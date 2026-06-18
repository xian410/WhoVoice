from django.urls import path
from .views import CelebrityListView, CelebrityDetailView

urlpatterns = [
    path("list/", CelebrityListView.as_view(), name="celebrity-list"),
    path("<str:name>/", CelebrityDetailView.as_view(), name="celebrity-detail"),
]
