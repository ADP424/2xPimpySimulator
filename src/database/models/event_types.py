from __future__ import annotations

from typing import Literal, NotRequired, TypeAlias, TypedDict

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]

EventSeverity: TypeAlias = Literal["trivial", "minor", "moderate", "major", "critical"]
EventRarity: TypeAlias = Literal["common", "uncommon", "rare", "novel", "extraordinary"]
EventTargetType: TypeAlias = Literal["owner", "pooch", "kennel", "server"]
EventEntitySelector: TypeAlias = Literal["selected", "random", "all", "random_exclude", "all_exclude"]
EventActionType: TypeAlias = Literal[
    "modify_money",
    "modify_bloodskulls",
    "modify_base_health",
    "modify_pooch_health",  # legacy alias for modify_base_health
    "modify_pooch_age",
    "modify_strength",
    "modify_cuteness",
    "modify_fluffiness",
    "modify_intelligence",
    "modify_dexterity",
    "modify_fertility",
    "modify_aggressiveness",
    "modify_breeding_cooldown",
    "set_breeding_cooldown",  # legacy alias for modify_breeding_cooldown
    "kill_pooch",
    "damn_pooch",
    "revive_pooch",
    "conjure_pooch",
    "sacrifice_pooch",
    "add_mutation",
    "remove_mutation",
    "add_breed",
    "remove_breed",
    "transfer_pooch",
    "create_pooch",
    "clone_pooch",
    "modify_kennel_capacity",
    "rename_pooch",
    "start_event",
    "start_stray_event",
    "breed_pooches",
    "sell_pooch",
    "buy_pooch",
    "release_stray",
    "receive_stray",
    "enter_kennel",
    "enter_vendor_stock",
    "select_pooch",
]

StrayEventActionType: TypeAlias = Literal[
    "modify_base_health",
    "modify_pooch_health",  # legacy alias for modify_base_health
    "modify_pooch_age",
    "modify_strength",
    "modify_cuteness",
    "modify_fluffiness",
    "modify_intelligence",
    "modify_dexterity",
    "modify_fertility",
    "modify_aggressiveness",
    "modify_breeding_cooldown",
    "set_breeding_cooldown",  # legacy alias for modify_breeding_cooldown
    "kill_pooch",
    "damn_pooch",
    "revive_pooch",
    "add_mutation",
    "remove_mutation",
    "add_breed",
    "remove_breed",
    "create_pooch",
    "clone_pooch",
    "rename_pooch",
    "breed_pooches",
    "enter_kennel",
    "enter_vendor_stock",
    "start_stray_event",
]

StrayEventEntitySelector: TypeAlias = Literal["random", "random_exclude", "all", "all_exclude"]


class PoochFilterSpec(TypedDict, total=False):
    min_count: int
    max_count: int
    description: str
    min_age: int
    max_age: int
    exclude_age: list[int]
    sex: str
    min_health: int
    max_health: int
    exclude_health: list[int]
    is_virgin: bool
    is_alive: bool
    min_breeding_cooldown: int
    max_breeding_cooldown: int
    exclude_breeding_cooldown: list[int]
    has_any_breed: list[str]
    has_all_breeds: list[str]
    exclude_breeds: list[str]
    has_any_mutation: list[str]
    has_all_mutations: list[str]
    exclude_mutations: list[str]
    location: str


class KennelFilterSpec(TypedDict, total=False):
    min_count: int
    max_count: int
    description: str
    min_capacity: int
    max_capacity: int
    exclude_capacity: list[int]
    min_pooches: int
    max_pooches: int | str
    exclude_pooches: list[int]
    pooches: list[PoochFilterSpec]


class OwnerEventFilterSpec(TypedDict, total=False):
    min_money: int
    max_money: int
    exclude_money: list[int]
    min_bloodskulls: int
    max_bloodskulls: int
    exclude_bloodskulls: list[int]
    min_pooches: int
    max_pooches: int
    exclude_pooches: list[int]
    min_kennels: int
    max_kennels: int
    exclude_kennels: list[int]
    kennels: list[KennelFilterSpec]
    pooches: list[PoochFilterSpec]
    graveyard_pooches: list[PoochFilterSpec]
    hell_pooches: list[PoochFilterSpec]


class StrayEventFilterSpec(TypedDict, total=False):
    """Top-level filter for a stray event — determines which strays on a server are eligible targets."""

    min_count: int
    max_count: int
    description: str
    pooches: list[PoochFilterSpec]


class OwnerFilterSpec(TypedDict, total=False):
    """Per-owner filter inside a ServerEventFilterSpec.owners list.

    min_count / max_count specify how many owners in the server must satisfy these criteria.
    All other fields mirror OwnerEventFilterSpec but add graveyard_pooches and hell_pooches.
    """

    min_count: int
    max_count: int
    # Money / bloodskulls
    min_money: int
    max_money: int
    exclude_money: list[int]
    min_bloodskulls: int
    max_bloodskulls: int
    exclude_bloodskulls: list[int]
    # Pooch / kennel aggregate counts
    min_pooches: int
    max_pooches: int
    exclude_pooches: list[int]
    min_kennels: int
    max_kennels: int
    exclude_kennels: list[int]
    # Sub-filters
    kennels: list[KennelFilterSpec]
    pooches: list[PoochFilterSpec]
    graveyard_pooches: list[PoochFilterSpec]
    hell_pooches: list[PoochFilterSpec]


class ServerEventFilterSpec(TypedDict, total=False):
    """Top-level filter for a server event — determines which servers are eligible for the event."""

    # Owner count
    min_owners: int
    max_owners: int
    # Server-wide pooch pool counts
    min_strays: int
    max_strays: int
    min_dead: int
    max_dead: int
    min_in_hell: int
    max_in_hell: int
    # Pool-specific PoochFilterSpec requirements
    stray_pooches: list[PoochFilterSpec]
    dead_pooches: list[PoochFilterSpec]
    hell_pooches: list[PoochFilterSpec]
    # Per-owner sub-filter
    owners: list[OwnerFilterSpec]


class ScoringSource(TypedDict, total=False):
    """A single contribution to a player's score for a server event menu option submission."""

    type: str  # "random" | "pooch_stat" | "owner_stat" | "constant"
    # For "random":
    min: float
    max: float
    # For "pooch_stat" / "owner_stat":
    stat: str  # e.g. "base_health", "strength", "money", "bloodskulls"
    scale: float  # multiplier per stat point relative to pivot; default 1.0
    pivot: float  # stat value where contribution = scale * 1.0; default 10.0
    direction: float  # 1.0 = higher is better, -1.0 = lower is better; default 1.0
    # For "constant":
    value: float


class ScoringSpec(TypedDict, total=False):
    """Defines how a menu option submission contributes to a player's total score."""

    aggregate: str  # "sum" | "average" | "max" — how to combine multiple submissions; default "sum"
    sources: list[ScoringSource]


class StrayEventContextDict(TypedDict):
    server_discord_id: int
    affected_pooch_ids: list[int]
    extra_data: JsonObject


class EventContextDict(TypedDict):
    owner_discord_id: int
    affected_pooch_ids: list[int]
    affected_kennel_ids: list[int]
    selected_pooch_id: int | None
    selected_kennel_id: int | None
    extra_data: JsonObject


class EventResultDict(TypedDict):
    success: bool
    message: str
    money_changed: int
    bloodskulls_changed: int
    pooches_affected: list[int]
    pooches_killed: list[int]
    pooches_created: list[int]
    mutations_added: list[list[int]]
    mutations_removed: list[list[int]]
    extra_data: JsonObject


class ServerEventContextDict(TypedDict):
    server_discord_id: int
    featured_pooch_ids: list[int]
    featured_breed_ids: list[int]
    featured_mutation_ids: list[int]
    extra_data: JsonObject
    saved_owner_slots: dict[str, list[int]]


class ServerEventAdvancedOptions(TypedDict, total=False):
    enabled: bool
    metadata: JsonObject


class ServerEventOptionAdvancedOptions(TypedDict, total=False):
    enabled: bool
    metadata: JsonObject


class ServerEventOutcomeAdvancedOptions(TypedDict, total=False):
    enabled: bool
    metadata: JsonObject


class EventAdvancedOptions(TypedDict, total=False):
    enabled: bool
    metadata: JsonObject


class EventOptionAdvancedOptions(TypedDict, total=False):
    enabled: bool
    metadata: JsonObject


class EventOutcomeAdvancedOptions(TypedDict, total=False):
    enabled: bool
    metadata: JsonObject


class OutcomeStatWeight(TypedDict, total=False):
    stat: str  # required: stat name (strength, fertility, base_health, size, etc.)
    pooch: str  # optional: named save_as slot or "random"; default "random"
    scale: float  # required: multiplier magnitude per stat point from pivot
    pivot: float  # optional: stat value where modifier = 1.0; default 10.0
    direction: float  # optional: 1.0 = higher stat boosts outcome, -1.0 = hurts it; default 1.0


class EventActionBaseParameters(TypedDict, total=False):
    selector: EventEntitySelector
    count: int  # for "random": how many to pick; for "random_exclude": how many to exclude
    filter: JsonObject
    save_as: str
    save_kennel: bool
    save_owner: bool
    use_saved: str


class EventAmountParameters(EventActionBaseParameters, total=False):
    amount: int
    min_amount: int
    max_amount: int
    roll_once: bool


class EventMutationParameters(EventActionBaseParameters, total=False):
    mutation: str
    mutation_id: int
    # Rarity filter (for random selection only — ignored when mutation_id is specified)
    min_rarity: str  # e.g. "common", "rare", "unique"
    max_rarity: str
    # Health impact filter (for random selection only)
    min_health_impact: str  # e.g. "instant_death", "neutral", "immortality"
    max_health_impact: str


class EventBreedParameters(EventActionBaseParameters, total=False):
    breed: str
    breed_id: int
    weight: float
    # Rarity filter (for random selection only — ignored when breed_id is specified)
    min_rarity: str  # e.g. "common", "rare", "unique"
    max_rarity: str


class EventTransferPoochParameters(EventActionBaseParameters, total=False):
    new_owner_discord_id: int
    vendor_id: int


class EventCreatePoochParameters(TypedDict, total=False):
    name: str
    sex: str
    age: int
    base_health: int
    strength: int
    cuteness: int
    fluffiness: int
    intelligence: int
    dexterity: int
    fertility: int
    aggressiveness: int
    breeding_cooldown: int
    destination: str  # "kennel" | "graveyard" | "hell" | "town"
    save_as: str


class EventClonePoochParameters(EventActionBaseParameters, total=False):
    # Overrides inherited from source pooch if provided
    name: str
    sex: str
    age: int
    base_health: int
    strength: int
    cuteness: int
    fluffiness: int
    intelligence: int
    dexterity: int
    fertility: int
    aggressiveness: int
    breeding_cooldown: int
    destination: str  # "kennel" | "graveyard" | "hell" | "town"
    # save_as here supports either a plain str (saves clone) or a list of {slot, target} dicts
    # where target is "clone" or "source"


class EventRenamePoochParameters(EventActionBaseParameters, total=False):
    name: str


class EventModifyBreedingCooldownParameters(EventActionBaseParameters, total=False):
    cooldown: int | Literal["base"]  # "base" resets to the base cooldown constant; only meaningful with mode="set"
    mode: Literal["modify", "set"]  # default "modify"
    amount: int
    min_amount: int
    max_amount: int
    roll_once: bool


# Legacy alias
EventSetBreedingCooldownParameters = EventModifyBreedingCooldownParameters


class EventRevivePoochParameters(EventActionBaseParameters, total=False):
    destination: str  # "kennel" | "graveyard" | "hell" | "town"
    save_as: str


class EventConjurePoochParameters(TypedDict, total=False):
    num_rolls: int  # number of rolls to make (highest value kept), default 1
    destination: str  # "kennel" | "graveyard" | "hell" | "town"
    save_as: str


class EventSacrificePoochParameters(EventActionBaseParameters, total=False):
    value_multiplier: float  # multiply bloodskulls received by this amount


class EventStartEventParameters(TypedDict, total=False):
    event: str
    random_event: bool


class EventBreedPoochesParameters(TypedDict, total=False):
    first_pooch_selector: EventEntitySelector
    first_filter: JsonObject
    second_pooch_selector: EventEntitySelector
    second_filter: JsonObject
    require_unique: bool  # default True — the two selected pooches must be different individuals
    require_same: bool  # default False — force both selectors to resolve to the same pooch
    baby_name: str
    baby_sex: str
    baby_age: int
    baby_base_health: int
    baby_breeding_cooldown: int
    # save_as supports a plain str (saves baby IDs) or a list of {slot, target} dicts
    # where target is "baby", "first_parent", or "second_parent"


class EventSellPoochParameters(EventActionBaseParameters, total=False):
    vendor_id: int  # sell to a specific vendor
    vendor_selector: str  # "random" — pick a random vendor (default if no vendor_id)
    value_multiplier: float  # multiply the pooch's base sell price by this amount


class EventBuyPoochParameters(TypedDict, total=False):
    vendor_id: int  # buy from a specific vendor
    vendor_selector: str  # "random" — pick a random vendor (default if no vendor_id)
    pooch_selector: str  # "random" — pick a random pooch from the vendor's stock (default)
    pooch_filter: JsonObject  # filter the vendor's stock before selecting
    value_multiplier: float  # multiply the pooch's base buy price by this amount
    destination: str  # "kennel" | "graveyard" | "hell" | "town"
    save_as: str


EventActionParameters: TypeAlias = (
    EventAmountParameters
    | EventMutationParameters
    | EventBreedParameters
    | EventTransferPoochParameters
    | EventCreatePoochParameters
    | EventClonePoochParameters
    | EventRenamePoochParameters
    | EventModifyBreedingCooldownParameters
    | EventStartEventParameters
    | EventBreedPoochesParameters
    | EventSellPoochParameters
    | EventBuyPoochParameters
    | EventRevivePoochParameters
    | EventConjurePoochParameters
    | EventSacrificePoochParameters
)


class TriggeredEventOptionDict(TypedDict):
    id: int
    label: str
    description: str
    min_money: int
    min_bloodskulls: int


class TriggeredEventEntityReference(TypedDict):
    id: int
    label: str
    description: NotRequired[str]
