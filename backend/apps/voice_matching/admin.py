from django.contrib import admin
from .models import MatchTask, LeaderboardEntry


@admin.register(MatchTask)
class MatchTaskAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'created_at', 'index_type', 'audio_name']
    list_filter = ['status', 'index_type']
    search_fields = ['id', 'audio_name']
    ordering = ['-created_at']


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ['nickname', 'celebrity_name', 'score', 'created_at']
    list_filter = ['celebrity_name']
    search_fields = ['nickname', 'celebrity_name', 'task_id']
    ordering = ['-score']
