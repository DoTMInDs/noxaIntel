from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser, Profile


class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email')


class CustomAuthenticationForm(AuthenticationForm):
    class Meta:
        model = CustomUser


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('email_notifications', 'push_notifications', 'favorite_leagues')
        widgets = {
            'favorite_leagues': forms.TextInput(attrs={'class': 'input input-bordered w-full'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'push_notifications': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
        }
