from django.urls import path, re_path
from .views import VoiceMatchView, AudioSampleView

urlpatterns = [
    path("match/", VoiceMatchView.as_view(), name="voice-match"),
    re_path(r"^sample/(?P<name>[^/]+)/$", AudioSampleView.as_view(), name="audio-sample"),
]
