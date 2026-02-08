# Core tables
from .kennel import Kennel
from .owner import Owner
from .pooch import Pooch
from .server import Server
from .vendor import Vendor

# Relationship tables
from .relationships.graveyard_pooch import GraveyardPooch
from .relationships.hell_pooch import HellPooch
from .relationships.kennel_pooch import KennelPooch
from .relationships.pooch_parentage import PoochParentage
from .relationships.pooch_pregnancy import PoochPregnancy
from .relationships.vendor_pooch_for_sale import VendorPoochForSale

# Static tables
from .static.breed import Breed
from .static.dog_name import DogName
from .static.mutation import Mutation
from .static.vendor_first_name import VendorFirstName
from .static.vendor_last_name import VendorLastName

# Static relationship tables
from .static_relationships.pooch_breed import PoochBreed
from .static_relationships.pooch_mutation import PoochMutation

# Enum tables
from .enums.health_impact_weight import HealthImpactWeight
from .enums.rarity_weight import RarityWeight

__all__ = [
    "Kennel",
    "Owner",
    "Pooch",
    "Server",
    "Vendor",
    "GraveyardPooch",
    "HellPooch",
    "KennelPooch",
    "PoochParentage",
    "PoochPregnancy",
    "VendorPoochForSale",
    "Breed",
    "DogName",
    "Mutation",
    "VendorFirstName",
    "VendorLastName",
    "PoochBreed",
    "PoochMutation",
    "HealthImpactWeight",
    "RarityWeight",
]
