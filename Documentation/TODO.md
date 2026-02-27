# Features

| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Refresh one vendor at random per day                                                                                          | 1      |
| Implement random events (player-specific)                                                                                     | 21     |
| Implement random events (server-specific) that last for a day or days                                                         | 21     |
| Vendors desire specific breeds (at least one of each rarity)                                                                  | 5      |
| Sacrifice for bloodskulls (and random bones)                                                                                  | 3      |
| Spend bloodskulls to summon pooches (more bloodskulls = more rerolls for cool breeds)                                         | 3      |
| Owners can kick their dogs onto the street and they become wandering strays                                                   | 5      |
| Randomly generated strays wandering towns (servers)                                                                           | 3      |
| Players can adopt strays by spending bones for a chance to attract one                                                        | 3      |
| Add ability to upgrade kennel slots (5 starting, +5 each tier, 20 max)                                                        | 3      |
| Add ability to buy more kennels (limit of 5 total kennels)                                                                    | 3      |
| fertility stat (higher fertility = can breed more often, more likely to unapproved breed)                                     | 5      |
| Make breeding have a chance to involve a second member you didn't choose (affected by fertility)                              | 5      |
| Add tiers of injury beyond just death - pooches can be healed at the vet                                                      | 8      |
| Add injure on_death as an advanced option to mutations                                                                        | 3      |
| Add aggressiveness stat that makes dogs have a chance each day to fight another dog (causing injury or DEATH)                 | 8      |
| Add stat increase/decrease advanced options that mutations have to breeds also                                                | 5      |
| Add stat increase/decrease advanced options for fertility and aggressiveness                                                  | 3      |
| Have per-server auction houses players can put their pooches in / players bid, highest bid by EOD gets the pooch              | 8      |
| Create new breeds at runtime ???                                                                                              | ???    |
| Let owners rename their kennels                                                                                               | 1      |
| Let owners name pooches when they're born in their kennels                                                                    | 1      |
| Let owners rename their pooches (for a price!)                                                                                | 3      |
| Kennel cleanliness stat, which affects disease chance                                                                         | 3      |
| Buy cleaning products to clean kennels                                                                                        | 5      |
| Dogs have a randomized mess stat (affected by mutations and breeds via advanced options) - produces mess each day in kennel   | 8      |
| Add diseases, the same way mutations and breeds are added                                                                     | 5      |
| Each day, there's a chance for each pooch (kennels, strays) to contract a disease, affected by kennel messiness               | 8      |
| Pooches have a chance each day to spread diseases to others in their kennel (like heritability chance in mutations)           | 5      |
| Add constitution stat for pooches, which improves their chance of resisting diseases (both new and spread)                    | 5      |
| Diseases have a recovery immunity period, meaning the pooch can't contract it for that number of days                         | 5      |
| Diseases have a list of possible messages they say when a pooch gets it for ambiguity on what disease it is                   | 3      |
| Diseases have a base recovery chance (0 means can't recover w/o medication, -1 means can't recover ever)                      | 3      |
| STDS! STDS! STDS!                                                                                                             | 3      |
| Add ability for diseases to be inherited, like mutations                                                                      | 3      |
| Get breed population stats for server (add this info to the vet)                                                              | 3      |
| Add ability for mutations to predispose a pooch to getting certain diseases more often                                        | 3      |
| Add incompatible diseases to mutations                                                                                        | 3      |
| Add a strength stat which dictates how well a dog fights (and how likely they are to be injured/injure another in a fight)    | 3      |
| Add a dog fighting ring in each server with gambling                                                                          | 8      |
| Have pooch stats (fertility, aggressiveness, etc.) be partially inherited                                                     | 3      |
| Add consumption stat that determines food need per day for a pooch (affected by mutations/breeds/diseases)                    | 1      |
| Add starvation counter, which affects fertility/strength/health/etc. the worse it gets                                        | 3      |
| Add sorting to the lists on the website, as well as filtering and searching                                                   | 1      |
| Stillbirths/miscarriages                                                                                                      | 3      |

# Bug Fixes
| Feature                                                                                                                       | Points |
| ----------------------------------------------------------------------------------------------------------------------------- | ------ |
| Don't build the image in session - store it on the bloody machine                                                             | 1      |
| Male dogs contract female mutations??? (and vice versa I imagine)                                                             | 1      |
| Dogs can have breeds with 0% weight                                                                                           | 1      |
| Websocket is borked                                                                                                           | 3      |
| Vendor stock in UI shows 0, even when they have dogs for sale                                                                 | 1      |
| Adding babies to kennels is breaking (Pooch ID not found error)                                                               | 3      |