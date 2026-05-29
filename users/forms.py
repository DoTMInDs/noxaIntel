from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser, Profile


class CustomUserCreationForm(UserCreationForm):
    phone_number = forms.CharField(
        max_length=20, 
        required=True,
        label="Phone Number",
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'e.g. +1234567890'})
    )
    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'e.g. user@example.com'})
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('phone_number', 'email')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['phone_number']
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            self.fields['username'].label = "Phone Number"
            self.fields['username'].widget.attrs.update({
                'placeholder': 'e.g. +1234567890',
                'class': 'input input-bordered w-full bg-base-300/40 focus:border-primary'
            })
        if 'password' in self.fields:
            self.fields['password'].widget.attrs.update({
                'class': 'input input-bordered w-full bg-base-300/40 focus:border-primary'
            })



class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('email_notifications', 'push_notifications', 'favorite_leagues')
        widgets = {
            'favorite_leagues': forms.TextInput(attrs={'class': 'input input-bordered w-full'}),
            'email_notifications': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
            'push_notifications': forms.CheckboxInput(attrs={'class': 'toggle toggle-primary'}),
        }
