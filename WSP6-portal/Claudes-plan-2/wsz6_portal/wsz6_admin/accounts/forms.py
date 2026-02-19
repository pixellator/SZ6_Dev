"""wsz6_admin/accounts/forms.py"""

from django import forms
from .models import WSZUser


class UserEditForm(forms.ModelForm):
    """Form for admins to edit another user's WSZ6 settings."""

    class Meta:
        model = WSZUser
        fields = [
            'first_name', 'last_name', 'email',
            'user_type', 'game_access_level', 'allowed_games',
            'is_active',
        ]
        widgets = {
            'allowed_games': forms.CheckboxSelectMultiple(),
        }
        help_texts = {
            'allowed_games': 'Only used when Game Access Level is set to "Custom list".',
        }
