class OwnerNotFound(Exception):
    """
    Exception raised when an owner corresponding to a Discord ID isn't found.

    Attributes
    ----------
    owner_discord_id: int
        The Discord ID that failed to correspond to a kennel.
    """

    def __init__(self, owner_discord_id: int):
        message = f"Owner with ID '{owner_discord_id}' not found."
        super().__init__(message)
