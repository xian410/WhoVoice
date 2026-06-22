from django.urls import path, re_path
from .views import (
    VoiceMatchView, TaskStatusView, AudioSampleView,
    FaissIndexDownloadView, FaissVisualizerView, FaissScatterView,
    LeaderboardSubmitView, LeaderboardCelebrityView,
    LeaderboardGlobalView, LeaderboardMyView,
)

urlpatterns = [
    path("match/", VoiceMatchView.as_view(), name="voice-match"),
    path("status/<uuid:task_id>/", TaskStatusView.as_view(), name="task-status"),
    path("faiss-index/", FaissIndexDownloadView.as_view(), name="faiss-index-download"),
    path("faiss-visualizer/", FaissVisualizerView.as_view(), name="faiss-visualizer"),
    path("faiss-scatter/", FaissScatterView.as_view(), name="faiss-scatter"),
    re_path(r"^sample/(?P<name>[^/]+)/$", AudioSampleView.as_view(), name="audio-sample"),
    # 排行榜
    path("leaderboard/submit/", LeaderboardSubmitView.as_view(), name="leaderboard-submit"),
    re_path(r"^leaderboard/(?P<celebrity_name>[^/]+)/$", LeaderboardCelebrityView.as_view(), name="leaderboard-celebrity"),
    path("leaderboard/my/", LeaderboardMyView.as_view(), name="leaderboard-my"),
    path("leaderboard/", LeaderboardGlobalView.as_view(), name="leaderboard-global"),
]
