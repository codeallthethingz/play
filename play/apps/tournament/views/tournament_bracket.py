import csv

from django import forms
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from apps.tournament.forms import TournamentBracketForm
from apps.tournament.models import Tournament, TournamentBracket, TournamentSnake, Heat, HeatGame
from apps.authentication.decorators import admin_required


@admin_required
@login_required
@transaction.atomic
def new(request, tournament_id):
    tournament = Tournament.objects.get(id=tournament_id)

    if request.method == 'POST':
        form = TournamentBracketForm(request.POST)

        if form.is_valid():
            bracket = form.save(commit=False)
            bracket.tournament=tournament
            bracket.save()

            # Save related sneks
            for snake in form.cleaned_data["snakes"]:
                # There has to be a tournament / snake relation, or its an error
                # (ie: can't add snake from outside the tournament)
                ts, _ = TournamentSnake.objects.get_or_create(tournament=tournament, snake=snake)
                ts.bracket = bracket
                ts.save()

            messages.success(request, f'Tournament "{tournament.name}" successfully created')
            return redirect('/tournaments/')
    else:
        form = TournamentBracketForm()
    return render(request, 'tournament_bracket/new.html',  {'form': form, 'tournament':tournament})


@admin_required
@login_required
def edit(request, bracket_id):
    tournament_bracket = TournamentBracket.objects.get(id=bracket_id)
    if request.method == 'POST':
        form = TournamentBracketForm(request.POST, instance=tournament_bracket)

        if form.is_valid():
            bracket = form.save(commit=False)
            bracket.save()

            # Save related sneks
            for snake in form.cleaned_data["snakes"]:
                # There has to be a tournament / snake relation, or its an error
                # (ie: can't add snake from outside the tournament)
                ts, _ = TournamentSnake.objects.get_or_create(tournament=tournament_bracket.tournament, snake=snake)
                ts.bracket = bracket
                ts.save()

            messages.success(request, f'Tournament Bracket "{tournament_bracket.name}" updated')
            return redirect('/tournaments/')
    else:
        form = TournamentBracketForm(instance=tournament_bracket)

    return render(request, 'tournament_bracket/edit.html', {'form': form})


@admin_required
@login_required
def show_current_game(request, id):
    tournament_bracket = TournamentBracket.objects.get(id=id)

    if request.GET.get('json') == 'true':
        details = tournament_bracket.game_details()
        return JsonResponse({"games": details})

    return render(request, 'tournament_bracket/show_current_game.html', {
        'tournament_bracket': tournament_bracket,
    })

@admin_required
@login_required
def show(request, id):
    tournament_bracket = TournamentBracket.objects.get(id=id)

    progression_details = []
    round = 1
    total_snakes = tournament_bracket.snakes.count()

    import math
    game_count = math.ceil(total_snakes/8)
    snakes_per_game = total_snakes/game_count
    min_snakes_per_game = math.floor(snakes_per_game)
    max_snakes_per_game = math.ceil(snakes_per_game)
    snakes_advancing = game_count*2

    snakes_per_game_msg = f"{min_snakes_per_game}-{max_snakes_per_game}" if min_snakes_per_game != max_snakes_per_game else f"{min_snakes_per_game}"
    while total_snakes > 8:
        print(round, game_count, (min_snakes_per_game, max_snakes_per_game), snakes_advancing)
        progression_details.append({
            "round": round,
            "num_games": game_count,
            "snakes_per_game": snakes_per_game_msg,
            "advancing": snakes_advancing,
        })
        round += 1
        total_snakes = snakes_advancing

    progression_details.append({
        "round": round,
        "num_games": game_count,
        "snakes_per_game": snakes_per_game_msg,
        "advancing": snakes_advancing,
    })
    print(round, game_count, (min_snakes_per_game, max_snakes_per_game), snakes_advancing)

    return render(request, 'tournament_bracket/show.html', {
        'tournament_bracket': tournament_bracket,
        "progression": progression_details,
    })


@admin_required
@login_required
def show_csv(request, id):
    tournament_bracket = TournamentBracket.objects.get(id=id)
    # Create the HttpResponse object with the appropriate CSV header.
    filename = f'{tournament_bracket.tournament.name}_{tournament_bracket.name}.csv'
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    for row in tournament_bracket.export():
        writer.writerow(row)

    return response


@admin_required
@login_required
def create_next_round(request, id):
    tournament_bracket = TournamentBracket.objects.get(id=id)
    tournament_bracket.create_next_round()
    return redirect(f'/tournament/bracket/{id}')


@admin_required
@login_required
def create_game(request, id, heat_id):
    heat = Heat.objects.get(id=heat_id)
    heat.create_next_game()
    return redirect(f'/tournament/bracket/{id}/')


@admin_required
@login_required
def run_game(request, id, heat_id, heat_game_number):
    heat_game = HeatGame.objects.get(heat_id=heat_id, number=heat_game_number)
    if heat_game.game is None or heat_game.game.engine_id is None:
        heat_game.game.create()
        heat_game.game.run()

    if 'autoplay' in request.META['QUERY_STRING']:
        return redirect(f'/games/{heat_game.game.engine_id}?autoplay=true')

    return redirect(f'/games/{heat_game.game.engine_id}')
