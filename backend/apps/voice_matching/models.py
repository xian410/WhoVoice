import uuid
from django.db import models


class MatchTask(models.Model):
    """声纹匹配排队任务"""
    STATUS_CHOICES = [
        ('pending', '排队中'),
        ('processing', '处理中'),
        ('done', '已完成'),
        ('error', '失败'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    audio_path = models.CharField(max_length=512, blank=True, default='')
    audio_name = models.CharField(max_length=255, default='recording.webm')
    index_type = models.CharField(max_length=20, default='clean')
    result_json = models.TextField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = '匹配任务'
        verbose_name_plural = '匹配任务'

    def __str__(self):
        return f"MatchTask({self.id}) status={self.status}"


class LeaderboardEntry(models.Model):
    """声纹匹配排行榜条目"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    celebrity_name = models.CharField(max_length=255, db_index=True)
    nickname = models.CharField(max_length=50, default='')
    score = models.FloatField(db_index=True)
    audio_path = models.CharField(max_length=512, blank=True, default='')
    task_id = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-score', 'created_at']
        indexes = [
            models.Index(fields=['celebrity_name', '-score']),
        ]
        verbose_name = '排行榜条目'
        verbose_name_plural = '排行榜条目'

    def __str__(self):
        display_name = self.nickname or '匿名'
        return f"{display_name} → {self.celebrity_name} ({self.score:.2%})"
