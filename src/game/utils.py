from src.database import list_pooch_mutations


async def get_pooch_mutation_parameter_total(pooch_id: int, parameter: str, sum: bool = True) -> int | float:
    """
    Return the total for a given summable/multiplicable parameter for mutations (like `dollar_value_add`).

    Parameters
    ----------
    pooch_id: int
        The ID of the pooch to get the mutation parameter total for.

    parameter: str
        The key for the parameter to get the total of.

    sum: bool, default : True
        Whether to sum or multiply the parameter values. If sum is false, multiply.

    Returns
    -------
    int | float
        The total as an int or float, depending on the parameter's type and summing vs multiplying.
        If the parameter isn't found, the default return for summing is **0**, and the default return
        for multiplying is **1**.
    """

    mutations = await list_pooch_mutations(pooch_id)
    total = 0 if sum else 1
    for mutation in mutations:
        if sum:
            total += mutation.parameters.get(parameter, 0)
        else:
            total *= mutation.parameters.get(parameter, 1)

    return total
