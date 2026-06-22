from rest_framework import serializers
from .models import LeaderboardEntry


class LeaderboardSubmitSerializer(serializers.ModelSerializer):
    """排行榜提交序列化器"""
    audio = serializers.FileField(write_only=True, required=True)
    nickname = serializers.CharField(
        max_length=50, required=False, allow_blank=True, default=''
    )

    class Meta:
        model = LeaderboardEntry
        fields = ['celebrity_name', 'score', 'nickname', 'audio', 'task_id']

    def validate_score(self, value):
        if value < 0 or value > 1:
            raise serializers.ValidationError('分数必须在 0~1 之间')
        return value

    def validate_celebrity_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('明星名称不能为空')
        return value.strip()


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    """排行榜条目展示序列化器"""
    rank = serializers.SerializerMethodField()

    class Meta:
        model = LeaderboardEntry
        fields = ['id', 'celebrity_name', 'nickname', 'score', 'created_at', 'rank']

    def get_rank(self, obj):
        # rank 由视图层注入 context，这里做 fallback
        return getattr(obj, '_rank', None)
