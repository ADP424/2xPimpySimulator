class KennelNotFound(Exception):
    """
    Exception raised when a kennel corresponding to an ID isn't found.

    Attributes
    ----------
    kennel_id: int
        The ID that failed to correspond to a kennel.
    """

    def __init__(self, kennel_id: int):
        message = f"Kennel with ID '{kennel_id}' not found."
        super().__init__(message)
