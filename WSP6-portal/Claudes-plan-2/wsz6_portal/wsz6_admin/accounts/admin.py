from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import WSZUser


@admin.register(WSZUser)
class WSZUserAdmin(UserAdmin):
    list_display  = ('username', 'email', 'user_type', 'game_access_level', 'is_active')
    list_filter   = ('user_type', 'game_access_level', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')

    fieldsets = UserAdmin.fieldsets + (
        ('WSZ6 Settings', {
            'fields': ('user_type', 'game_access_level', 'allowed_games'),
        }),
    )
