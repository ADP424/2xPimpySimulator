from __future__ import annotations

from typing import Literal, NotRequired, TypeAlias, TypedDict

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]

EventSeverity: TypeAlias = Literal["trivial", "minor", "moderate", "major", "critical"]
EventRarity: TypeAlias = Literal["common", "uncommon", "rare", "novel", "extraordinary"]
EventTargetType: TypeAlias = Literal["owner", "pooch", "kennel", "all_pooches", "all_kennels"]
EventActionType: TypeAlias = Literal[
    "modify_money",
    "modify_bloodskulls",
    "modify_pooch_health",
    "modify_pooch_age",
    "kill_pooch",
    "add_mutation",
    "remove_mutation",
    "add_breed",
    "transfer_pooch",
    "create_pooch",
    "modify_kennel_capacity",
    "rename_pooch",
    "set_breeding_cooldown",
]
EventEntitySelector: TypeAlias = int | Literal["selected", "random"]


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


class EventAdvancedOptions(TypedDict, total=False):
    enabled: bool
    metadata: JsonObject


class EventOptionAdvancedOptions(TypedDict, total=False):
    enabled: bool
    metadata: JsonObject


class EventOutcomeAdvancedOptions(TypedDict, total=False):
    enabled: bool
    metadata: JsonObject


class EventActionBaseParameters(TypedDict, total=False):
    pooch_id: EventEntitySelector
    kennel_id: EventEntitySelector


class EventAmountParameters(EventActionBaseParameters, total=False):
    amount: int
    min_amount: int
    max_amount: int


class EventMutationParameters(EventActionBaseParameters, total=False):
    mutation: str


class EventBreedParameters(EventActionBaseParameters, total=False):
    breed: str
    weight: float


class EventTransferPoochParameters(EventActionBaseParameters, total=False):
    new_owner_discord_id: int
    vendor_id: int


class EventCreatePoochParameters(TypedDict, total=False):
    name: str
    sex: Literal["female", "male"]
    age: int
    base_health: int
    breeding_cooldown: int


class EventRenamePoochParameters(EventActionBaseParameters, total=False):
    name: str


class EventSetBreedingCooldownParameters(EventActionBaseParameters, total=False):
    cooldown: int


EventActionParameters: TypeAlias = (
    EventAmountParameters
    | EventMutationParameters
    | EventBreedParameters
    | EventTransferPoochParameters
    | EventCreatePoochParameters
    | EventRenamePoochParameters
    | EventSetBreedingCooldownParameters
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
