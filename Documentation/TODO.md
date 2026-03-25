# Features

# Miscellaneous
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Create new breeds at runtime ???                                                                                              | ???    |
| Get breed population stats for server (add this info to the vet)                                                              | 3      |
| Have rarity be rolled first, then pick one from that rarity (mutations, breeds, events, etc.)                                 | 2      |

## UI
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Remove showing markup on vendors                                                                                              | 1      |
| In the rarity filter menu (for mutations and breeds) sort by decreasing weight                                                | 3      |
| Have timeline per pooch showing birthday / other significant events (like being bought) / death using cool timeline comp      | 8      |
| Obfuscate mutations (so they don't tell you exactly what a pooch has unless you get it checked at vet)                        | 8      |
| Gendered pronoun placeholders in JSON where it's relevant                                                                     | 3      |

## Random Events
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Dog show where you want to match closest to breed, mutations, and stats                                                       | 13     |

## Seasons
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Certain diseases, mutations (and maybe breeds) that can only show up in certain seasons                                       | 13     |

## Blood Magic
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Clone your pooches by spending bloodskulls (better breeds = more expensive)                                                   | 5      |
| Spend bloodskulls to reset pooch age (but at some EVIL cost)                                                                  | 5      |
| Spend a LOT of bloodskulls to make your pooch IMMORTAL (but infertile, like a vampire, also can't go out at night)            | 5      |
| Change pooch's gender for bloodskulls                                                                                         | 5      |
| Have lots of body parts, not just bloodskulls, each with different uses ? (frankenweenie)                                     | 21     |

## Diseases
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Add diseases, the same way mutations and breeds are added                                                                     | 5      |
| Each day, there's a chance for each pooch (kennels, strays) to contract a disease, affected by kennel messiness               | 8      |
| Pooches have a chance each day to spread diseases to others in their kennel (like heritability chance in mutations)           | 5      |
| Add constitution stat for pooches, which improves their chance of resisting diseases (both new and spread)                    | 5      |
| Diseases have a recovery immunity period, meaning the pooch can't contract it for that number of days                         | 5      |
| Diseases have a list of possible messages they say when a pooch gets it for ambiguity on what disease it is                   | 2      |
| Diseases have a base recovery chance (0 means can't recover w/o medication, -1 means can't recover ever)                      | 3      |
| STDS! STDS! STDS!                                                                                                             | 3      |
| Add ability for diseases to be inherited, like mutations                                                                      | 3      |
| Add ability for mutations to predispose a pooch to getting certain diseases more often                                        | 3      |
| Add incompatible diseases to mutations                                                                                        | 2      |
| Kennel cleanliness stat, which affects disease chance                                                                         | 3      |
| Buy cleaning products to clean kennels                                                                                        | 5      |
| Dogs have a randomized mess stat (affected by mutations and breeds via advanced options) - produces mess each day in kennel   | 8      |

## Canine Violence
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Add tiers of injury beyond just death - pooches can be healed at the vet                                                      | 8      |
| Add injure on_death as an advanced option to mutations                                                                        | 3      |
| Add aggressiveness stat that makes dogs have a chance each day to fight another dog (causing injury or DEATH)                 | 8      |
| Add a strength stat which dictates how well a dog fights (and how likely they are to be injured/injure another in a fight)    | 3      |
| Add a pooch fight event action type with its own internal logic for determining winners and damage and such                   | 5      |

## Breeding
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Make breeding have a chance to involve a second member you didn't choose (affected by fertility)                              | 5      |
| Stillbirths/miscarriages                                                                                                      | 3      |
| Add option to neuter dogs at the vet                                                                                          | 3      |
| Have percentage of a breed increase by more if both pooches have a bit of that breed (so you can get closer to pure)          | 2      |

## Stat Management
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Maybe make female pooches 1 size smaller (or some percentage smaller or something)                                            | 1      |
| Add "pooch snapshots" you can get from the vet clinic that show a pooch's stats at that point in time                         | 13     |
| Special procedure to get exact numbers on the buffs/debuffs pooches have on their stats                                       | 13     |
| Pooch snapshots should display on pooch info pages (and it makes it easier to tell the value of auction pooches)              | 5      |

## Food
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Add consumption stat that determines food need per day for a pooch (affected by mutations/breeds/diseases)                    | 2      |
| Add starvation counter, which affects fertility/strength/health/etc. the worse it gets                                        | 3      |
| Cannibalism (debuffs pooches when they do it unless they have the cannibalism mutations)                                      | 5      |


# Bug Fixes

## Miscellaneous
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Websocket doesn't do anything                                                                                                 | 2      |

## UI/UX
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Sanitize inputs!!!                                                                                                            | 8      |
| Authenticate owner permission to rename pooches, breed pooches, etc.                                                          | 8      |
| Clean quotes (HTML-relavent characters)                                                                                       | 5      |