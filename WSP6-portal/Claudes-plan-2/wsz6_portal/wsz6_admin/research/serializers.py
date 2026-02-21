"""
wsz6_admin/research/serializers.py

DRF serializers for the external research REST API (R7).
"""

from rest_framework import serializers


class SessionSerializer(serializers.Serializer):
    session_key  = serializers.UUIDField()
    game_slug    = serializers.CharField(source='game.slug')
    game_name    = serializers.CharField(source='game.name')
    owner        = serializers.CharField(source='owner.username')
    status       = serializers.CharField()
    started_at   = serializers.DateTimeField()
    ended_at     = serializers.DateTimeField(allow_null=True)
    summary      = serializers.JSONField(source='summary_json', allow_null=True)


class PlayThroughSerializer(serializers.Serializer):
    playthrough_id = serializers.UUIDField()
    session_key    = serializers.UUIDField()
    started_at     = serializers.DateTimeField()
    ended_at       = serializers.DateTimeField(allow_null=True)
    outcome        = serializers.CharField(allow_null=True, allow_blank=True)
    step_count     = serializers.IntegerField()
    log_url        = serializers.SerializerMethodField()
    jsonl_url      = serializers.SerializerMethodField()

    def get_log_url(self, obj):
        sk  = obj.session_key
        pid = obj.playthrough_id
        return f'/api/v1/sessions/{sk}/playthroughs/{pid}/log/'

    def get_jsonl_url(self, obj):
        sk  = obj.session_key
        pid = obj.playthrough_id
        return f'/api/v1/sessions/{sk}/playthroughs/{pid}/log.jsonl'
