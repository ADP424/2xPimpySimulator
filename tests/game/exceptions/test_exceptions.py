import pytest

from src.game.exceptions import (
    KennelNotFound,
    OwnerNotFound,
    PoochNotFound,
    VendorNotFound,
)


class TestKennelNotFound:
    def test_message_format(self):
        exc = KennelNotFound(42)
        assert str(exc) == "Kennel with ID '42' not found."

    def test_is_exception(self):
        assert issubclass(KennelNotFound, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(KennelNotFound, match="Kennel with ID '99' not found."):
            raise KennelNotFound(99)


class TestOwnerNotFound:
    def test_message_format(self):
        exc = OwnerNotFound(123456)
        assert str(exc) == "Owner with ID '123456' not found."

    def test_is_exception(self):
        assert issubclass(OwnerNotFound, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(OwnerNotFound, match="Owner with ID '789' not found."):
            raise OwnerNotFound(789)


class TestPoochNotFound:
    def test_message_format(self):
        exc = PoochNotFound(7)
        assert str(exc) == "Pooch with ID '7' not found."

    def test_is_exception(self):
        assert issubclass(PoochNotFound, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(PoochNotFound, match="Pooch with ID '1' not found."):
            raise PoochNotFound(1)


class TestVendorNotFound:
    def test_message_format(self):
        exc = VendorNotFound(55)
        assert str(exc) == "Vendor with ID '55' not found."

    def test_is_exception(self):
        assert issubclass(VendorNotFound, Exception)

    def test_can_be_raised_and_caught(self):
        with pytest.raises(VendorNotFound, match="Vendor with ID '100' not found."):
            raise VendorNotFound(100)


class TestExceptionInheritance:
    def test_all_are_exceptions(self):
        for cls in (KennelNotFound, OwnerNotFound, PoochNotFound, VendorNotFound):
            assert issubclass(cls, Exception)

    def test_caught_by_generic_except(self):
        try:
            raise PoochNotFound(1)
        except Exception as e:
            assert "Pooch" in str(e)
