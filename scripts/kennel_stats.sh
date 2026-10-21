#!/usr/bin/env bash
# Show an owner's kennels (mess, food, hours of food left) and their living pooches (cooldown, pregnancy,
# hunger, upkeep, base stats) straight from the database. Read-only. Stats are the stored base values,
# not effective stats (breeds, mutations, injuries and hunger change those).
# Usage: scripts/kennel_stats.sh [discord_name]      (default: dogdroid; matched case-insensitively)
#        scripts/kennel_stats.sh --owners            (list every owner with their money and pooch counts)
set -euo pipefail

cd "$(dirname "$0")/.."

command -v docker > /dev/null || { echo "docker not found." >&2; exit 1; }

case "${1:-}" in
    -h | --help) sed -n 2,6p "$0"; exit 0 ;;
    --owners)
        docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1' <<'SQL'
\pset footer off
SELECT o.discord_id, o.discord_name, o.dollars, o.bloodskulls,
       (SELECT COUNT(*) FROM kennels k WHERE k.owner_discord_id = o.discord_id) AS kennels,
       (SELECT COUNT(*) FROM pooches p WHERE p.owner_discord_id = o.discord_id AND p.alive) AS living_pooches,
       o.joined_at::date AS joined
FROM owners o
ORDER BY living_pooches DESC, o.discord_name;
SQL
        exit 0
        ;;
esac
OWNER="${1:-dogdroid}"

# The labels mirror messiness_label / starvation_label / get_breeding_status in src/game.
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -v owner="$1"' _ "$OWNER" <<'SQL'
\pset footer off

SELECT current_day, current_hour, current_season FROM global_state;

\echo '== Kennels'
SELECT k.id, k.name, k.messiness AS mess,
       CASE
         WHEN k.messiness <= 0 THEN 'Spotless'
         WHEN k.messiness < 3 THEN 'Mostly Clean'
         WHEN k.messiness < 8 THEN 'Messy'
         WHEN k.messiness < 15 THEN 'Very Messy'
         WHEN k.messiness < 25 THEN 'Disgusting'
         ELSE 'Biohazard'
       END AS mess_label,
       k.food_stock AS food,
       COALESCE(SUM(p.consumption), 0) AS eats_per_hour,
       CASE WHEN COALESCE(SUM(p.consumption), 0) > 0
            THEN ROUND(k.food_stock::numeric / SUM(p.consumption), 1) END AS food_hours_left,
       COUNT(p.id) || '/' || k.pooch_limit AS pooches
FROM kennels k
JOIN owners o ON o.discord_id = k.owner_discord_id
LEFT JOIN kennel_pooches kp ON kp.kennel_id = k.id
LEFT JOIN pooches p ON p.id = kp.pooch_id AND p.alive
WHERE o.discord_name ILIKE :'owner'
GROUP BY k.id
ORDER BY k.id;

\echo '== Pooches'
SELECT k.name AS kennel, p.id, p.name, p.sex, p.age,
       p.breeding_cooldown AS cooldown,
       CASE
         WHEN p.breeding_cooldown = 0 THEN 'In Heat'
         WHEN p.breeding_cooldown <= 5 THEN 'Heating Up'
         ELSE 'Cooled'
       END AS breeding,
       p.pregnancy_timer AS preg_hours,
       p.starvation AS starv,
       CASE
         WHEN p.starvation <= 0 THEN 'Well-fed'
         WHEN p.starvation <= 5 THEN 'Peckish'
         WHEN p.starvation <= 12 THEN 'Hungry'
         WHEN p.starvation <= 24 THEN 'Famished'
         WHEN p.starvation <= 48 THEN 'Starving'
         ELSE 'Dying of Hunger'
       END AS hunger,
       p.consumption AS eats, p.mess_output AS mess, p.size,
       p.fertility AS fert, p.base_health AS hp, p.strength AS str, p.constitution AS con,
       p.immortal, p.mood
FROM pooches p
JOIN owners o ON o.discord_id = p.owner_discord_id
LEFT JOIN kennel_pooches kp ON kp.pooch_id = p.id
LEFT JOIN kennels k ON k.id = kp.kennel_id
WHERE o.discord_name ILIKE :'owner' AND p.alive
ORDER BY k.id NULLS LAST, p.breeding_cooldown, p.id;
SQL
