class PoochNotFound(Exception):
    """
    Exception raised when a pooch corresponding to an ID isn't found.

    Attributes
    ----------
    pooch_id: int
        The ID that failed to correspond to a pooch.
    """

    def __init__(self, pooch_id: int):
        message = f"Pooch with ID '{pooch_id}' not found."
        super().__init__(message)
