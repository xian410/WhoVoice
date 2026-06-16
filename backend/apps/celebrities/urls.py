from django.urls import path
from .views import CelebrityListView

urlpatterns = [
    path("list/", CelebrityListView.as_view(), name="celebrity-list"),
]
