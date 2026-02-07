# Breeding Impacts

### breeding_cooldown
How many more/fewer age cycles before the pooch can breed again.


# Death Impacts

### death_message
A custom message to replace the standard one with when the pooch dies of this mutation.
- "[pooch]" is replaced by the name of the pooch with the mutation.

### kill_message
A custom message to replace the standard one with when this mutation kills another pooch with an `on_death` `kill` effect.
- "[pooch]" is replaced by the name of the pooch with the mutation.
- "[victim]" is replaced by the name of the pooch killed by the mutation.

### on_death
An effect the pooch has on its targets when it dies (see `on_death_targets`).
- `kill`: Causes every target to immediately die.
- `spread`: Causes every target to immediately inherit this mutation.
- `spread_all`: Causes every target to immediately inherit ALL mutations the pooch with this mutation has.

### on_death_chance
The percent chance, as a number between 0 and 100, that the `on_death` effect will happen.
This chance is rolled individually for each member in the `on_death_targets`.
The chance is 100% by default.

### always_on_death
Whether the `on_death` effect should always trigger or only trigger if the mutation is the one that killed the pooch.
- `0`: The `on_death` will only trigger if it was this mutation that killed the pooch. This is the default.
- `1`: The `on_death` will trigger when the pooch dies, no matter what kills it. Anything other than a 0 is equivalent to this choice.

### on_death_targets
If the pooch has an on_death impact, who are the targets?
- `none`: No targets. This is the default.
- `all`: Every other pooch in the kennel is a target.
- `random`: A random pooch in the kennel is a target.


# Heritability Impacts

### incompatible_mutations
A list of names of other mutations the pooch cannot get if they have this mutation.<br>
You can also list mutation categories here.


# Value Impacts

### bloodskull_value_add
A number to add to the pooch's bloodskull value (before multiplication).

### bloodskull_value_mult
A number to multiply the pooch's bloodskull value by (after addition).

### dollar_value_add
A number to add to the pooch's dollar value (before multiplication).

### dollar_value_mult
A number to multiply the pooch's dollar value by (after addition).
