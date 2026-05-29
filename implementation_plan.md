# High-Performance AI Soccer Betting Analysis Platform (Django + HTMX + Redis + Celery)

This document outlines the architecture, design, and implementation plan for building a production-grade, low-latency AI sports betting intelligence platform. The platform delivers near real-time soccer predictions, automated betting recommendations, an AI assistant, and a Progressive Web App (PWA) experience—all built without Django REST Framework, utilizing HTMX for dynamic partial page updates, Tailwind CSS + DaisyUI for premium aesthetics, Redis for aggressive caching, and Celery for asynchronous background ML processing.

---

## User Review Required

> [!IMPORTANT]
> **Database Configuration & Environment**: By default, the plan configures PostgreSQL as the primary database with a seamless fallback to SQLite for local development and testing if PostgreSQL environment variables are not supplied. Please confirm if you have a local PostgreSQL instance running or prefer starting with SQLite for immediate local verification.

> [!TIP]
> **Tailwind CSS & DaisyUI Setup**: To ensure zero build-step friction while maintaining full customization, we will utilize the Tailwind CSS Play CDN configured with DaisyUI plugins in `base.html` for local development, alongside static asset fallbacks.

> [!WARNING]
> **Redis & Celery Requirement**: Low-latency caching and background task execution rely on Redis. Ensure a local Redis server (e.g., `redis://localhost:6379/0`) is running for caching and Celery broker functionality.

---

## Open Questions

> [!IMPORTANT]
> 1. **External Football Data Provider**: Do you have a specific football API provider in mind (e.g., API-Football, Football-Data.org) for live odds and match fixtures, or should we implement a robust mock simulation service that mirrors live data feeds?
> 2. **AI/ML Model Weights**: Should we include a lightweight scikit-learn/PyTorch training script that generates synthetic baseline models on initial setup, ensuring the precomputation engine works out-of-the-box?

---

## Proposed Changes

### Project Setup & Core Configuration

We will establish the root Django project structure, dependency management, core settings configured for Redis caching, Celery integration, and main routing.

#### [NEW] [requirements.txt](file:///c:/Users/HP/OneDrive/Documents/noxaintel/requirements.txt)
- Defines project dependencies: `Django`, `celery`, `redis`, `django-redis`, `django-htmx`, `django-environ`, `psycopg2-binary`, `scikit-learn`, `torch`, `Pillow`.

#### [NEW] [manage.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/manage.py)
- Standard Django entry point script.

#### [NEW] [config/__init__.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/config/__init__.py)
- Initializes Celery app alongside Django.

#### [NEW] [config/settings.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/config/settings.py)
- Configures installed apps, middleware (including `django-htmx.middleware.HtmxMiddleware`), Redis cache backend (`django_redis.cache.RedisCache`), Celery broker/result backend, templates, and database settings.

#### [NEW] [config/urls.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/config/urls.py)
- Root URL configuration routing to all custom modular apps.

#### [NEW] [config/celery.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/config/celery.py)
- Celery configuration and app instantiation for async background task processing.

#### [NEW] [config/wsgi.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/config/wsgi.py)
- WSGI application specification.

#### [NEW] [config/asgi.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/config/asgi.py)
- ASGI application specification for potential future async/SSE capabilities.

---

### App: Users

Manages custom user accounts, profile details, authentication flows, and subscription tiers.

#### [NEW] [users/models.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/users/models.py)
- `CustomUser`: Extends `AbstractUser`.
- `SubscriptionTier`: Tiers (Free, Premium, VIP) with feature access flags.
- `Profile`: Links user to subscription tier, betting preferences, and notification settings.

#### [NEW] [users/views.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/users/views.py)
- Authentication views (login, register, logout) tailored for HTMX forms and standard navigation.
- Profile management and subscription tier selection views.

#### [NEW] [users/urls.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/users/urls.py)
- URL routes for authentication and profile management.

#### [NEW] [users/forms.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/users/forms.py)
- Django forms for user registration, login, and profile updates.

---

### App: Matches

Handles soccer leagues, teams, match fixtures, live scores, and odds snapshots.

#### [NEW] [matches/models.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/matches/models.py)
- `League`, `Team`, `Match` (indexed on match date, league, status).
- `OddsSnapshot`: Tracks moneyline, over/under, and BTTS odds over time.

#### [NEW] [matches/views.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/matches/views.py)
- `MatchDashboardView`: Renders main match dashboard.
- `MatchListPartialView`: HTMX endpoint returning filtered match cards (Live, Upcoming, Finished).
- `MatchDetailView`: Detailed match view with live stats.

#### [NEW] [matches/urls.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/matches/urls.py)
- Routes for match dashboard and HTMX partial updates.

---

### App: Predictions

Core engine for precomputed match predictions, probabilities, and cached AI explanations.

#### [NEW] [predictions/models.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/predictions/models.py)
- `Prediction`: Stores precomputed probabilities (home/draw/away, over/under, btts), confidence score, and status.
- `AIAnalysis`: Stores precomputed AI text explanations and tactical breakdowns.

#### [NEW] [predictions/views.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/predictions/views.py)
- `PredictionDetailView`: Renders prediction page with sub-200ms response targets via aggressive Redis caching.
- `PredictionPartialView`: HTMX endpoint implementing stale-while-revalidate caching pattern.

#### [NEW] [predictions/urls.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/predictions/urls.py)
- Routes for fetching predictions and AI analysis partials.

---

### App: Betting

Low-latency recommendation system serving pre-generated betting tips.

#### [NEW] [betting/models.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/betting/models.py)
- `BettingTip`: Stores pre-generated tips (Safe Bet, Value Bet, Accumulator) with associated match, odds, and confidence.

#### [NEW] [betting/views.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/betting/views.py)
- `TipsDashboardView`: Renders betting recommendations.
- `TipsFilterPartialView`: HTMX endpoint for instant category filtering (Safe, Value, Acca) retrieved directly from Redis.

#### [NEW] [betting/urls.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/betting/urls.py)
- Routes for betting tips dashboard and filtering partials.

---

### App: AI Engine

Service layer and background workers for ML inference, precomputation, and the AI Assistant.

#### [NEW] [ai_engine/services.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/ai_engine/services.py)
- Encapsulates ML model loading, feature engineering, prediction precomputation, and Redis caching logic.
- Implements AI Assistant query processing using precomputed match context.

#### [NEW] [ai_engine/tasks.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/ai_engine/tasks.py)
- Celery periodic tasks: `precompute_upcoming_predictions`, `refresh_live_odds`, `generate_betting_tips`.

#### [NEW] [ai_engine/views.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/ai_engine/views.py)
- `AIAssistantChatView`: Renders chat interface.
- `AIAssistantQueryView`: HTMX endpoint processing user questions and returning AI responses without blocking the main request cycle.

#### [NEW] [ai_engine/urls.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/ai_engine/urls.py)
- Routes for AI assistant chat interactions.

---

### App: Notifications

Manages real-time alerts, push notifications, and user subscription preferences.

#### [NEW] [notifications/models.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/notifications/models.py)
- `Notification`: Stores alert messages (match start, goal scored, high-confidence tip) for users.

#### [NEW] [notifications/views.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/notifications/views.py)
- `NotificationListView`: Displays user notifications.
- `NotificationBadgePartialView`: HTMX polling endpoint for unread notification counts.

#### [NEW] [notifications/urls.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/notifications/urls.py)
- Routes for notification management.

---

### App: Analytics

Admin and monitoring dashboard tracking model accuracy, cache performance, and platform metrics.

#### [NEW] [analytics/models.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/analytics/models.py)
- `ModelAccuracyReport`: Tracks historical performance and ROI of AI predictions.
- `CacheMetrics`: Logs Redis cache hit/miss ratios for latency tuning.

#### [NEW] [analytics/views.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/analytics/views.py)
- `AnalyticsDashboardView`: Renders system monitoring charts and accuracy stats.
- `CacheStatsPartialView`: HTMX endpoint for live monitoring of cache performance.

#### [NEW] [analytics/urls.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/analytics/urls.py)
- Routes for analytics dashboard.

---

### App: PWA

Progressive Web App configuration, service workers, and offline capabilities.

#### [NEW] [pwa/views.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/pwa/views.py)
- Renders `manifest.json`, `serviceworker.js`, and `offline.html`.

#### [NEW] [pwa/urls.py](file:///c:/Users/HP/OneDrive/Documents/noxaintel/pwa/urls.py)
- Routes for PWA service worker and manifest files.

---

### Templates & Frontend Architecture

Rich, premium UI built with Tailwind CSS, DaisyUI, and HTMX partials.

#### [NEW] [templates/base.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/base.html)
- Master HTML layout featuring responsive navigation, DaisyUI dark/light premium themes, HTMX injection, PWA manifest links, and service worker registration.

#### [NEW] [templates/components/navbar.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/components/navbar.html)
- Top navigation bar with notification badges and user profile menu.

#### [NEW] [templates/components/sidebar.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/components/sidebar.html)
- Left navigation sidebar for quick access to Matches, Predictions, Tips, AI Assistant, and Analytics.

#### [NEW] [templates/components/skeleton.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/components/skeleton.html)
- HTMX skeleton loader components to ensure high perceived performance during partial swaps.

#### [NEW] [templates/users/login.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/users/login.html)
- Premium login interface with glassmorphism card design.

#### [NEW] [templates/users/register.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/users/register.html)
- User registration and subscription tier selection interface.

#### [NEW] [templates/users/profile.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/users/profile.html)
- Profile management and preference toggles.

#### [NEW] [templates/matches/dashboard.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/matches/dashboard.html)
- Main match dashboard hosting live and upcoming match containers.

#### [NEW] [templates/matches/partials/match_list.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/matches/partials/match_list.html)
- HTMX partial rendering match cards dynamically based on league/time filters.

#### [NEW] [templates/matches/partials/match_card.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/matches/partials/match_card.html)
- Individual match card displaying teams, live odds, and match status.

#### [NEW] [templates/predictions/detail.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/predictions/detail.html)
- Comprehensive match prediction view showcasing win probabilities, over/under gauges, and AI analysis.

#### [NEW] [templates/predictions/partials/prediction_card.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/predictions/partials/prediction_card.html)
- Compact prediction summary card for list views.

#### [NEW] [templates/betting/dashboard.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/betting/dashboard.html)
- Recommendation dashboard for Safe, Value, and Accumulator tips.

#### [NEW] [templates/betting/partials/tip_list.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/betting/partials/tip_list.html)
- HTMX partial displaying filtered betting recommendations.

#### [NEW] [templates/ai_engine/assistant.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/ai_engine/assistant.html)
- AI Assistant chat interface layout.

#### [NEW] [templates/ai_engine/partials/chat_message.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/ai_engine/partials/chat_message.html)
- HTMX partial rendering individual AI and user chat bubbles.

#### [NEW] [templates/notifications/list.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/notifications/list.html)
- Dropdown/page listing recent notifications.

#### [NEW] [templates/analytics/dashboard.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/analytics/dashboard.html)
- System monitoring and AI accuracy dashboard.

#### [NEW] [templates/pwa/offline.html](file:///c:/Users/HP/OneDrive/Documents/noxaintel/templates/pwa/offline.html)
- Offline fallback page served by the service worker when no network is available.

---

## Verification Plan

### Automated Tests & Verification
1. **Django System Check & Migrations**:
   - Run `python manage.py check` to ensure all app configurations and models are valid.
   - Run `python manage.py makemigrations` and `python manage.py migrate` to verify database schema creation.
2. **Cache & Celery Verification**:
   - Execute a custom management command or test script to verify Redis connection and cache set/get latency (<10ms).
   - Verify Celery task execution for precomputing predictions.
3. **HTMX & View Response Testing**:
   - Use Django test client to verify that HTMX endpoints return correct partial HTML fragments without full page layouts.
   - Assert response times for cached prediction endpoints are well under 200ms.

### Manual Verification
1. **PWA & Service Worker**:
   - Load the application in a browser, verify service worker registration in DevTools, simulate offline mode, and ensure `offline.html` and cached shell UI load instantly.
2. **Interactive UI Flows**:
   - Navigate through Match Dashboard, filter matches via HTMX tabs, view instant AI Predictions, interact with the AI Assistant, and verify smooth, app-like transitions without page reloads.
