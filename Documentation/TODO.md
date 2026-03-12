# Features

# Miscellaneous
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Have per-server auction houses players can put their pooches in / players bid, highest bid by EOD gets the pooch              | 8      |
| Create new breeds at runtime ???                                                                                              | ???    |
| Get breed population stats for server (add this info to the vet)                                                              | 3      |

## UI
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Show where breeds can be obtained from (altar, vendor, etc.) on the breed page                                                | 2      |
| Remove showing markup on vendors                                                                                              | 1      |
| In the rarity filter menu (for mutations and breeds) sort by decreasing weight                                                | 3      |
| Always display your dollars and bloodskulls in the web header                                                                 | 3      |
| Add sorting to the lists on the website, as well as filtering and searching                                                   | 1      |
| Have timeline per pooch showing birthday / other significant events (like being bought) / death using cool timeline comp      | 5      |
| Obfuscate mutations (so they don't tell you exactly what a pooch has unless you get it checked at vet)                        | 8      |
| Gendered pronoun placeholders in JSON where it's relevant                                                                     | 3      |

## Random Events
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Implement random events for an entire server (one per week)                                                                   | 21     |
| Add a dog fighting ring in each server with gambling (winner gets skulls of dead pooches as bloodskulls)                      | 8      |
| Dog show where you want to match closest to breed, mutations, and stats                                                       | 13     |

## Blood Magic
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Make sacrificing pooches give bones (which can be used to tame strays)                                                        | 3      |
| Clone your pooches by spending bloodskulls (better breeds = more expensive)                                                   | 5      |
| Spend bloodskulls to reset pooch age (but at some EVIL cost)                                                                  | 5      |
| Spend a LOT of bloodskulls to make your pooch IMMORTAL (but infertile, like a vampire, also can't go out at night)            | 5      |

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

## Breeding
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Fertility stat (higher fertility = can breed more often, more likely to unapproved breed)                                     | 5      |
| Make breeding have a chance to involve a second member you didn't choose (affected by fertility)                              | 5      |
| Stillbirths/miscarriages                                                                                                      | 3      |
| Have pooch stats (fertility, aggressiveness, etc.) be partially inherited                                                     | 3      |

## Vendors
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Vendors desire specific breeds (at least one of each rarity)                                                                  | 5      |

## Kennel Management
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Add ability to upgrade kennel slots (5 starting, +5 each tier, 20 max)                                                        | 3      |
| Add ability to buy more kennels (limit of 5 total kennels)                                                                    | 3      |

## Strays
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Owners can kick their dogs onto the street and they become wandering strays                                                   | 5      |
| Randomly generated strays wandering towns (servers)                                                                           | 3      |
| Players can adopt strays by spending bones for a chance to attract one                                                        | 3      |

## Stat Management
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Add stat increase/decrease advanced options that mutations have to breeds also                                                | 5      |
| Add stat increase/decrease advanced options for fertility and aggressiveness                                                  | 3      |

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