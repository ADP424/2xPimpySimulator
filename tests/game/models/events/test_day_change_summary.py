from src.game.models.events.birth_event import BirthEvent
from src.game.models.events.day_change_summary import DayChangeSummary
from src.game.models.events.death_event import DeathEvent
from src.game.models.events.other_event import OtherEvent
from src.game.models.pooch import Pooch
from src.game.models.server import Server


def _make_server() -> Server:
    return Server(discord_id=1, event_channel_discord_id=2)


def _make_pooch(id: int, name: str = "Dog") -> Pooch:
    return Pooch(
        id=id,
        name=name,
        age=2,
        sex="male",
        base_health=10,
        health_loss_age=0,
        strength=10,
        cuteness=10,
        fluffiness=10,
        intelligence=10,
        dexterity=10,
        fertility=10,
        aggressiveness=10,
        constitution=10,
        breeding_cooldown=0,
        alive=True,
        virgin=True,
        owner_discord_id=None,
        vendor_id=None,
        created_at=None,
        size=10,
        health=10,
        mood=None,
        owner=None,
        vendor=None,
        breeds=[],
        mutations=[],
    )


class TestBirthedPooches:
    def test_empty_births(self):
        summary = DayChangeSummary(server=_make_server(), births=[], deaths=[], other_events=[])
        assert summary.birthed_pooches == []

    def test_single_birth(self):
        server = _make_server()
        mother = _make_pooch(1, "Mom")
        child = _make_pooch(2, "Pup")
        birth = BirthEvent(server=server, mother=mother, child=child, message="Born!")
        summary = DayChangeSummary(server=server, births=[birth], deaths=[], other_events=[])
        assert len(summary.birthed_pooches) == 1
        assert summary.birthed_pooches[0].id == 2

    def test_deduplicates_births(self):
        server = _make_server()
        mother1 = _make_pooch(1, "Mom1")
        mother2 = _make_pooch(3, "Mom2")
        child = _make_pooch(2, "Pup")
        b1 = BirthEvent(server=server, mother=mother1, child=child, message="Born!")
        b2 = BirthEvent(server=server, mother=mother2, child=child, message="Also born!")
        summary = DayChangeSummary(server=server, births=[b1, b2], deaths=[], other_events=[])
        assert len(summary.birthed_pooches) == 1
        assert summary.birthed_pooches[0].id == 2

    def test_multiple_distinct_births(self):
        server = _make_server()
        mother = _make_pooch(1, "Mom")
        c1 = _make_pooch(2, "Pup1")
        c2 = _make_pooch(3, "Pup2")
        b1 = BirthEvent(server=server, mother=mother, child=c1, message="Born!")
        b2 = BirthEvent(server=server, mother=mother, child=c2, message="Born!")
        summary = DayChangeSummary(server=server, births=[b1, b2], deaths=[], other_events=[])
        assert len(summary.birthed_pooches) == 2
        ids = {p.id for p in summary.birthed_pooches}
        assert ids == {2, 3}


class TestDeadPooches:
    def test_empty_deaths(self):
        summary = DayChangeSummary(server=_make_server(), births=[], deaths=[], other_events=[])
        assert summary.dead_pooches == []

    def test_single_death(self):
        server = _make_server()
        pooch = _make_pooch(5, "Fido")
        death = DeathEvent(server=server, pooch=pooch, message="RIP")
        summary = DayChangeSummary(server=server, births=[], deaths=[death], other_events=[])
        assert len(summary.dead_pooches) == 1
        assert summary.dead_pooches[0].id == 5

    def test_deduplicates_deaths(self):
        server = _make_server()
        pooch = _make_pooch(5, "Fido")
        d1 = DeathEvent(server=server, pooch=pooch, message="RIP1")
        d2 = DeathEvent(server=server, pooch=pooch, message="RIP2")
        summary = DayChangeSummary(server=server, births=[], deaths=[d1, d2], other_events=[])
        assert len(summary.dead_pooches) == 1

    def test_multiple_distinct_deaths(self):
        server = _make_server()
        p1 = _make_pooch(5, "Fido")
        p2 = _make_pooch(6, "Spot")
        d1 = DeathEvent(server=server, pooch=p1, message="RIP")
        d2 = DeathEvent(server=server, pooch=p2, message="RIP")
        summary = DayChangeSummary(server=server, births=[], deaths=[d1, d2], other_events=[])
        assert len(summary.dead_pooches) == 2


class TestOtherPooches:
    def test_empty_other(self):
        summary = DayChangeSummary(server=_make_server(), births=[], deaths=[], other_events=[])
        assert summary.other_pooches == []

    def test_single_other_event(self):
        server = _make_server()
        pooch = _make_pooch(7, "Rex")
        evt = OtherEvent(server=server, pooch=pooch, message="Something happened")
        summary = DayChangeSummary(server=server, births=[], deaths=[], other_events=[evt])
        assert len(summary.other_pooches) == 1
        assert summary.other_pooches[0].id == 7

    def test_deduplicates_other_events(self):
        server = _make_server()
        pooch = _make_pooch(7, "Rex")
        e1 = OtherEvent(server=server, pooch=pooch, message="Event 1")
        e2 = OtherEvent(server=server, pooch=pooch, message="Event 2")
        summary = DayChangeSummary(server=server, births=[], deaths=[], other_events=[e1, e2])
        assert len(summary.other_pooches) == 1

    def test_multiple_distinct_other_events(self):
        server = _make_server()
        p1 = _make_pooch(7, "Rex")
        p2 = _make_pooch(8, "Duke")
        e1 = OtherEvent(server=server, pooch=p1, message="Event 1")
        e2 = OtherEvent(server=server, pooch=p2, message="Event 2")
        summary = DayChangeSummary(server=server, births=[], deaths=[], other_events=[e1, e2])
        assert len(summary.other_pooches) == 2
