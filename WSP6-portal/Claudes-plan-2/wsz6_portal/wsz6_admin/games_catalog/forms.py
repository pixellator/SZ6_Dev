"""wsz6_admin/games_catalog/forms.py"""

from django import forms
from django.conf import settings
from .models import Game


class GameInstallForm(forms.Form):
    """Form for uploading and installing a new SOLUZION6 game."""

    name = forms.CharField(
        max_length=200,
        help_text='Human-readable game name, e.g. "Tic-Tac-Toe".',
    )
    slug = forms.SlugField(
        max_length=100,
        help_text='URL-safe identifier, e.g. "tic-tac-toe". Must be unique.',
    )
    brief_desc = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label='Brief description',
    )
    status = forms.ChoiceField(
        choices=Game.STATUS_CHOICES,
        initial=Game.STATUS_DEV,
    )
    min_players = forms.IntegerField(min_value=1, initial=1)
    max_players = forms.IntegerField(min_value=1, initial=10)
    zip_file = forms.FileField(
        label='Game ZIP archive',
        help_text=(
            f'Upload a .zip file containing the PFF (.py) and any '
            f'supporting files. Maximum size: '
            f'{settings.GAME_ZIP_MAX_SIZE // (1024*1024)} MB.'
        ),
    )

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if Game.objects.filter(slug=slug).exists():
            raise forms.ValidationError(f'A game with slug "{slug}" already exists.')
        return slug

    def clean_zip_file(self):
        f = self.cleaned_data['zip_file']
        if f.size > settings.GAME_ZIP_MAX_SIZE:
            max_mb = settings.GAME_ZIP_MAX_SIZE // (1024 * 1024)
            raise forms.ValidationError(f'File too large. Maximum allowed size is {max_mb} MB.')
        if not f.name.lower().endswith('.zip'):
            raise forms.ValidationError('File must be a .zip archive.')
        return f


class GameEditForm(forms.ModelForm):
    """Form for editing an existing game's metadata and status."""

    class Meta:
        model = Game
        fields = ['name', 'brief_desc', 'status', 'min_players', 'max_players']
