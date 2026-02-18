from database import list_pooch_mutations


async def get_pooch_mutation_advanced_option_total(pooch_id: int, advanced_option: str, sum=True) -> int | float:
    """
    Return the total for a given summable/multiplicable advanced option for mutations (like `dollar_value_add`).

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the mutation advanced option total for.

    advanced_option: str
        The key for the advanced option to get the total of.

    sum: bool, default : True
        Whether to sum or multiply the advanced option values. If sum is false, multiply.

    Returns
    -------
    int | float
        The total as an int or float, depending on the advanced option's type and summing vs multiplying.
        If the advanced option isn't found, the default return for summing is **0**, and the default return
        for multiplying is **1**.
    """

    mutations = await list_pooch_mutations(pooch_id)
    total = 0 if sum else 1
    for mutation in mutations:
        if sum:
            total += mutation.advanced_options.get(advanced_option, 0)
        else:
            total *= mutation.advanced_options.get(advanced_option, 1)

    return total
