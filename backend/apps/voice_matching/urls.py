from django.urls import path, re_path
from .views import VoiceMatchView, TaskStatusView, AudioSampleView, FaissIndexDownloadView, FaissVisualizerView, FaissScatterView

urlpatterns = [
    path("match/", VoiceMatchView.as_view(), name="voice-match"),
    path("status/<uuid:task_id>/", TaskStatusView.as_view(), name="task-status"),
    path("faiss-index/", FaissIndexDownloadView.as_view(), name="faiss-index-download"),
    path("faiss-visualizer/", FaissVisualizerView.as_view(), name="faiss-visualizer"),
    path("faiss-scatter/", FaissScatterView.as_view(), name="faiss-scatter"),
    re_path(r"^sample/(?P<name>[^/]+)/$", AudioSampleView.as_view(), name="audio-sample"),
]
