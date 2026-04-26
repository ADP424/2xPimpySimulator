"""
Arena-specific logic for server events (dog fighting arena major event).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from src.database import get_pooch_by_id as db_get_pooch_by_id
from src.database import session_scope, update_server_event_occurrence_context
from src.game.constants import FIGHT_DEFENDER_STRENGTH_BONUS, FIGHT_ROUNDS
from src.game.models.events import ServerEventContext

if TYPE_CHECKING:
    from src.database.models import ServerEventOccurrence

_ARENA_KEY = "arena"
_BET_WINDOW_DEFAULT_MINUTES = 5
_BET_MONEY_DEFAULT_MAX = 100
_BET_BLOODSKULLS_DEFAULT_MAX = 25


def get_arena(server_context: ServerEventContext) -> dict:
    """Return the arena dict from server_context.extra_data, creating it if missing."""
    arena = server_context.extra_data.setdefault(_ARENA_KEY, {})
    arena.setdefault("listed", [])
    arena.setdefault("matchups", [])
    arena.setdefault("fight_wins", {})
    return arena


async def handle_arena_action(
    occurrence: ServerEventOccurrence,
    owner_discord_id: int,
    selected_pooch_id: int | None,
    arena_action: str,
    option_parameters: dict,
    extra_params: dict,
    rng: random.Random,
) -> tuple[bool, str, dict]:
    """Mutate the occurrence's shared arena state for arena-specific actions.

    Returns (success, message, arena_result_dict).
    """
    server_context = ServerEventContext.from_dict(occurrence.context or {})
    arena = get_arena(server_context)

    if arena_action == "list_pooch":
        if selected_pooch_id is None:
            return False, "You must select a pooch to list.", {}
        pooch = await db_get_pooch_by_id(selected_pooch_id)
        if pooch is None or not pooch.alive or pooch.owner_discord_id != owner_discord_id:
            return False, "That pooch is not available.", {}
        if any(entry["pooch_id"] == selected_pooch_id for entry in arena["listed"]):
            return False, "That pooch is already listed.", {}
        arena["listed"].append({"pooch_id": selected_pooch_id, "owner_id": owner_discord_id})
        await update_server_event_occurrence_context(occurrence.id, server_context.to_dict())
        return True, f"{pooch.name} has been listed in the arena!", {"listed_pooch_id": selected_pooch_id}

    elif arena_action == "challenge":
        if selected_pooch_id is None:
            return False, "You must select a pooch to fight with.", {}
        target_pooch_id = extra_params.get("target_listed_pooch_id")
        if not isinstance(target_pooch_id, int):
            return False, "You must specify the pooch you want to challenge.", {}
        listed_entry = next((e for e in arena["listed"] if e["pooch_id"] == target_pooch_id), None)
        if listed_entry is None:
            return False, "That pooch is no longer available to challenge.", {}
        if listed_entry["owner_id"] == owner_discord_id:
            return False, "You cannot challenge your own pooch.", {}
        if selected_pooch_id == target_pooch_id:
            return False, "A pooch cannot fight itself.", {}
        in_matchup = any(
            not m.get("resolved")
            and (m["attacker_pooch_id"] == selected_pooch_id or m["defender_pooch_id"] == selected_pooch_id)
            for m in arena["matchups"]
        )
        if in_matchup:
            return False, "That pooch is already in an active fight.", {}

        arena["listed"] = [e for e in arena["listed"] if e["pooch_id"] != target_pooch_id]
        bet_window = int(option_parameters.get("bet_window_minutes", _BET_WINDOW_DEFAULT_MINUTES))
        bet_deadline = (datetime.now(timezone.utc) + timedelta(minutes=bet_window)).isoformat()
        matchup_id = len(arena["matchups"])

        attacker_pooch = await db_get_pooch_by_id(selected_pooch_id)
        defender_pooch = await db_get_pooch_by_id(target_pooch_id)
        arena["matchups"].append(
            {
                "id": matchup_id,
                "attacker_pooch_id": selected_pooch_id,
                "attacker_owner_id": owner_discord_id,
                "attacker_name": attacker_pooch.name if attacker_pooch else "Unknown",
                "defender_pooch_id": target_pooch_id,
                "defender_owner_id": listed_entry["owner_id"],
                "defender_name": defender_pooch.name if defender_pooch else "Unknown",
                "bet_deadline": bet_deadline,
                "bets": [],
                "fight_result": None,
                "resolved": False,
            }
        )
        await update_server_event_occurrence_context(occurrence.id, server_context.to_dict())
        attacker_name = attacker_pooch.name if attacker_pooch else f"pooch #{selected_pooch_id}"
        defender_name = defender_pooch.name if defender_pooch else f"pooch #{target_pooch_id}"
        return (
            True,
            f"{attacker_name} challenges {defender_name}! Betting window open for {bet_window} minutes.",
            {"matchup_id": matchup_id},
        )

    elif arena_action == "bet":
        matchup_id = extra_params.get("matchup_id")
        side = str(extra_params.get("side", "")).strip().lower()
        if not isinstance(matchup_id, int) or side not in ("attacker", "defender"):
            return False, "Invalid bet parameters.", {}
        matchup = next((m for m in arena["matchups"] if m["id"] == matchup_id), None)
        if matchup is None:
            return False, "That matchup does not exist.", {}
        if matchup.get("resolved"):
            return False, "That fight has already been resolved.", {}
        if owner_discord_id in (matchup["attacker_owner_id"], matchup["defender_owner_id"]):
            return False, "You cannot bet on a fight your own pooch is in.", {}
        deadline = datetime.fromisoformat(matchup["bet_deadline"])
        if datetime.now(timezone.utc) > deadline:
            return False, "The betting window for that fight has closed.", {}
        if any(b["owner_id"] == owner_discord_id for b in matchup["bets"]):
            return False, "You have already placed a bet on that fight.", {}

        bet_money = max(
            0,
            min(int(extra_params.get("money", 0)), int(option_parameters.get("bet_money_max", _BET_MONEY_DEFAULT_MAX))),
        )
        bet_bloodskulls = max(
            0,
            min(
                int(extra_params.get("bloodskulls", 0)),
                int(option_parameters.get("bet_bloodskulls_max", _BET_BLOODSKULLS_DEFAULT_MAX)),
            ),
        )

        if bet_money == 0 and bet_bloodskulls == 0:
            return False, "You must bet at least something.", {}

        matchup["bets"].append(
            {"owner_id": owner_discord_id, "side": side, "money": bet_money, "bloodskulls": bet_bloodskulls}
        )
        await update_server_event_occurrence_context(occurrence.id, server_context.to_dict())
        parts = []
        if bet_money:
            parts.append(f"${bet_money}")
        if bet_bloodskulls:
            parts.append(f"{bet_bloodskulls} bloodskulls")
        return (
            True,
            f"You bet {' and '.join(parts)} on the {side}!",
            {"matchup_id": matchup_id, "side": side, "money": bet_money, "bloodskulls": bet_bloodskulls},
        )

    return True, "", {}


async def resolve_arena_matchups(
    occurrence_id: int,
    server_context: ServerEventContext,
    event_parameters: dict,
    rng: random.Random,
) -> None:
    """Resolve all unresolved arena matchups: fight the pooches, pay out bets and fighter bonuses."""
    from src.database import (
        give_bloodskulls_to_owner,
        give_bones_to_owner,
        give_money_to_owner,
    )
    from src.game.events.shared import handle_fight_pooches

    arena = server_context.extra_data.get(_ARENA_KEY)
    if not arena:
        return

    matchups: list[dict] = arena.get("matchups", [])
    fight_wins: dict[str, int] = arena.get("fight_wins", {})

    fight_params = dict(event_parameters.get("fight_params", {}))
    prize_per_participant = int(event_parameters.get("prize_per_participant", 50))
    fighter_bonus_fraction = float(event_parameters.get("fighter_bonus_fraction", 0.25))
    draw_fighter_bonus_fraction = float(event_parameters.get("draw_fighter_bonus_fraction", 0.125))
    kill_reward_bloodskulls = int(event_parameters.get("kill_reward_bloodskulls", 1))
    kill_reward_bones = int(event_parameters.get("kill_reward_bones", 1))

    any_resolved = False
    for matchup in matchups:
        if matchup.get("resolved"):
            continue
        any_resolved = True

        attacker_id = matchup["attacker_pooch_id"]
        defender_id = matchup["defender_pooch_id"]
        attacker_owner_id = matchup["attacker_owner_id"]
        defender_owner_id = matchup["defender_owner_id"]

        fight_result = await handle_fight_pooches(
            attacker_id,
            defender_id,
            rounds=int(fight_params.get("rounds", FIGHT_ROUNDS)),
            defender_strength_bonus=int(fight_params.get("defender_strength_bonus", FIGHT_DEFENDER_STRENGTH_BONUS)),
            rng=rng,
        )
        matchup["fight_result"] = fight_result
        matchup["resolved"] = True

        winner_id: int | None = fight_result["winner_id"]
        draw: bool = fight_result["draw"]
        att_died: bool = fight_result["attacker_died"]
        def_died: bool = fight_result["defender_died"]

        total_bets_money = sum(b["money"] for b in matchup["bets"])
        total_bets_bloodskulls = sum(b["bloodskulls"] for b in matchup["bets"])
        fighter_bonus_money = int(total_bets_money * fighter_bonus_fraction)
        fighter_bonus_bloodskulls = int(total_bets_bloodskulls * fighter_bonus_fraction)
        draw_bonus_money = int(total_bets_money * draw_fighter_bonus_fraction)
        draw_bonus_bloodskulls = int(total_bets_bloodskulls * draw_fighter_bonus_fraction)

        if draw:
            if draw_bonus_money:
                await give_money_to_owner(attacker_owner_id, draw_bonus_money)
                await give_money_to_owner(defender_owner_id, draw_bonus_money)
            if draw_bonus_bloodskulls:
                await give_bloodskulls_to_owner(attacker_owner_id, draw_bonus_bloodskulls)
                await give_bloodskulls_to_owner(defender_owner_id, draw_bonus_bloodskulls)
        else:
            winner_owner_id = attacker_owner_id if winner_id == attacker_id else defender_owner_id
            if fighter_bonus_money:
                await give_money_to_owner(winner_owner_id, fighter_bonus_money)
            if fighter_bonus_bloodskulls:
                await give_bloodskulls_to_owner(winner_owner_id, fighter_bonus_bloodskulls)
            fight_wins[str(winner_owner_id)] = fight_wins.get(str(winner_owner_id), 0) + 1

        if att_died and kill_reward_bloodskulls:
            await give_bloodskulls_to_owner(defender_owner_id, kill_reward_bloodskulls)
            if kill_reward_bones:
                await give_bones_to_owner(defender_owner_id, kill_reward_bones)
        if def_died and kill_reward_bloodskulls:
            await give_bloodskulls_to_owner(attacker_owner_id, kill_reward_bloodskulls)
            if kill_reward_bones:
                await give_bones_to_owner(attacker_owner_id, kill_reward_bones)

        if not matchup["bets"]:
            continue

        attacker_bets = [b for b in matchup["bets"] if b["side"] == "attacker"]
        defender_bets = [b for b in matchup["bets"] if b["side"] == "defender"]

        if draw:
            for bet in matchup["bets"]:
                if bet["money"]:
                    await give_money_to_owner(bet["owner_id"], bet["money"])
                if bet["bloodskulls"]:
                    await give_bloodskulls_to_owner(bet["owner_id"], bet["bloodskulls"])
        else:
            winning_side = "attacker" if winner_id == attacker_id else "defender"
            winning_bets = attacker_bets if winning_side == "attacker" else defender_bets
            losing_bets = defender_bets if winning_side == "attacker" else attacker_bets

            total_winning_money = sum(b["money"] for b in winning_bets)
            total_winning_bloodskulls = sum(b["bloodskulls"] for b in winning_bets)
            total_losing_money = sum(b["money"] for b in losing_bets)
            total_losing_bloodskulls = sum(b["bloodskulls"] for b in losing_bets)

            for bet in winning_bets:
                payout_money = bet["money"]
                payout_bloodskulls = bet["bloodskulls"]
                if total_winning_money > 0 and total_losing_money > 0:
                    payout_money += int(total_losing_money * (bet["money"] / total_winning_money))
                if total_winning_bloodskulls > 0 and total_losing_bloodskulls > 0:
                    payout_bloodskulls += int(
                        total_losing_bloodskulls * (bet["bloodskulls"] / total_winning_bloodskulls)
                    )
                if payout_money:
                    await give_money_to_owner(bet["owner_id"], payout_money)
                if payout_bloodskulls:
                    await give_bloodskulls_to_owner(bet["owner_id"], payout_bloodskulls)

    arena["fight_wins"] = fight_wins
    if any_resolved and fight_wins:
        from sqlalchemy import select as _sa_select

        from src.database.models import OwnerServer as OwnerServerModel

        async with session_scope() as session:
            result = await session.execute(
                _sa_select(OwnerServerModel.owner_discord_id).where(
                    OwnerServerModel.server_discord_id == server_context.server_discord_id
                )
            )
            participant_count = len(list(result.scalars().all()))

        grand_prize = prize_per_participant * participant_count
        max_wins = max(fight_wins.values())
        grand_prize_winners = [int(oid) for oid, wins in fight_wins.items() if wins == max_wins]
        per_winner = grand_prize // max(1, len(grand_prize_winners))
        for oid in grand_prize_winners:
            if per_winner:
                await give_money_to_owner(oid, per_winner)

    if any_resolved:
        await update_server_event_occurrence_context(occurrence_id, server_context.to_dict())
