from django.contrib import admin
from .models import League, Team, Match, OddsSnapshot


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'code')
    search_fields = ('name', 'country', 'code')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'league')
    list_filter = ('league',)
    search_fields = ('name', 'code')


class OddsSnapshotInline(admin.TabularInline):
    model = OddsSnapshot
    extra = 0
    readonly_fields = ('timestamp',)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'league', 'status', 'home_score', 'away_score', 'match_date')
    list_filter = ('status', 'league')
    search_fields = ('home_team__name', 'away_team__name')
    inlines = [OddsSnapshotInline]


@admin.register(OddsSnapshot)
class OddsSnapshotAdmin(admin.ModelAdmin):
    list_display = ('match', 'timestamp', 'home_odds', 'draw_odds', 'away_odds')
    list_filter = ('match__league',)
    readonly_fields = ('timestamp',)
