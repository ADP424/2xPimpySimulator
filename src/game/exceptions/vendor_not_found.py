from __future__ import annotations


class VendorNotFound(Exception):
    """
    Exception raised when a vendor corresponding to an ID isn't found.

    Attributes
    ----------
    vendor_id: int
        The ID that failed to correspond to a vendor.
    """

    def __init__(self, vendor_id: int):
        message = f"Vendor with ID '{vendor_id}' not found."
        super().__init__(message)
