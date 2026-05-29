from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomAuthenticationForm, ProfileUpdateForm
from .models import SubscriptionTier, Profile


def register(request):
    if request.user.is_authenticated:
        return redirect('matches:dashboard')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Account created successfully! Welcome {user.username}.")
            return redirect('matches:dashboard')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('matches:dashboard')
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('matches:dashboard')
    else:
        form = CustomAuthenticationForm()
    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('users:login')


@login_required
def profile_view(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully.")
            if request.htmx:
                return render(request, 'users/partials/profile_form.html', {'form': form, 'profile': profile})
            return redirect('users:profile')
    else:
        form = ProfileUpdateForm(instance=profile)
    tiers = SubscriptionTier.objects.all()
    return render(request, 'users/profile.html', {'form': form, 'profile': profile, 'tiers': tiers})


@login_required
def subscription_upgrade(request, tier_id):
    tier = get_object_or_404(SubscriptionTier, id=tier_id)
    profile = request.user.profile
    profile.subscription_tier = tier
    profile.save()
    messages.success(request, f"Successfully upgraded to {tier.name} tier!")
    return redirect('users:profile')
