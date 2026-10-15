"""Contract tests for src/bot/ui/auction.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from src.bot.ui.auction import (
    AuctionBrowsePageSource,
    AuctionHouseView,
    BountyBrowsePageSource,
    _BountyBuilderView,
    _BountyTitleEscrowModal,
    _BreedCriterionModal,
    _build_bounty_listing_embed,
    _build_sale_listing_embed,
    _CreateSaleListingFlow,
    _FulfillBountyFlow,
    _MinRarityCriterionModal,
    _MinStatCriterionModal,
    _MutationCriterionModal,
    _MyBountiesView,
    _MyListingsView,
    _SexCriterionModal,
)


def _make_interaction(user_id=100):
    interaction = MagicMock()
    interaction.user = MagicMock()
    interaction.user.id = user_id
    interaction.guild_id = 200
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=False)
    interaction.response.send_message = AsyncMock()
    interaction.response.edit_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    interaction.message = None
    interaction.channel = MagicMock()
    interaction.channel.send = AsyncMock()
    interaction.data = {"values": []}
    return interaction


def _make_sale_listing(
    id=1,
    seller_discord_id=100,
    pooch_name="Buddy",
    minimum_bid=50,
    highest_bid=None,
    bid_count=0,
    expires_at=None,
    server_discord_id=200,
):
    listing = MagicMock()
    listing.id = id
    listing.seller_discord_id = seller_discord_id
    listing.minimum_bid = minimum_bid
    listing.highest_bid = highest_bid
    listing.bid_count = bid_count
    listing.expires_at = expires_at
    listing.server_discord_id = server_discord_id
    listing.pooch = MagicMock()
    listing.pooch.name = pooch_name
    listing.pooch.breeds = []
    listing.pooch.mutations = []
    listing.pooch.age = 5
    listing.pooch.sex = "male"
    return listing


def _make_bounty_listing(
    id=1,
    buyer_discord_id=100,
    title="Wanted",
    escrow_amount=200,
    criteria=None,
):
    listing = MagicMock()
    listing.id = id
    listing.buyer_discord_id = buyer_discord_id
    listing.title = title
    listing.escrow_amount = escrow_amount
    listing.criteria = criteria or []
    return listing


def _make_kennel(id=1, name="My Kennel"):
    kennel = MagicMock()
    kennel.id = id
    kennel.name = name
    return kennel


def _make_pooch(id=1, name="Rex", alive=True):
    pooch = MagicMock()
    pooch.id = id
    pooch.name = name
    pooch.alive = alive
    return pooch


# ---------------------------------------------------------------------------
# AuctionHouseView
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestAuctionHouseView:
    async def test_creates_view(self):
        view = AuctionHouseView(server_discord_id=200, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_has_select_and_back_button(self):
        view = AuctionHouseView(server_discord_id=200, owner_discord_id=100)
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        buttons = [c for c in view.children if isinstance(c, discord.ui.Button)]
        assert len(selects) >= 1
        assert any(b.label == "Marketplace" for b in buttons)

    async def test_interaction_check_owner_passes(self):
        view = AuctionHouseView(server_discord_id=200, owner_discord_id=100)
        interaction = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True

    async def test_interaction_check_non_owner_fails(self):
        view = AuctionHouseView(server_discord_id=200, owner_discord_id=100)
        interaction = MagicMock()
        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False

    async def test_back_button_replies_with_marketplace(self):
        view = AuctionHouseView(server_discord_id=200, owner_discord_id=100)
        interaction = _make_interaction()

        with (
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
            patch("src.bot.ui.marketplace.MarketplaceView"),
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_back(interaction)

        mock_r.reply.assert_called_once()
        kwargs = mock_r.reply.call_args[1]
        assert "view" in kwargs

    async def test_select_has_all_six_options(self):
        view = AuctionHouseView(server_discord_id=200, owner_discord_id=100)
        select = next(c for c in view.children if isinstance(c, discord.ui.Select))
        values = {opt.value for opt in select.options}
        assert values == {
            "browse_auctions",
            "my_listings",
            "browse_bounties",
            "my_bounties",
            "post_listing",
            "post_bounty",
        }

    async def test_select_post_bounty_sends_modal(self):
        view = AuctionHouseView(server_discord_id=200, owner_discord_id=100)
        select = next(c for c in view.children if isinstance(c, discord.ui.Select))
        interaction = _make_interaction()
        interaction.data = {"values": ["post_bounty"]}

        with patch.object(type(select), "values", new_callable=lambda: property(lambda self: ["post_bounty"])):
            await select.callback(interaction)

        interaction.response.send_modal.assert_called_once()
        modal_arg = interaction.response.send_modal.call_args[0][0]
        assert isinstance(modal_arg, _BountyTitleEscrowModal)


# ---------------------------------------------------------------------------
# AuctionBrowsePageSource
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestAuctionBrowsePageSource:
    async def test_load_calls_game_fn(self):
        source = AuctionBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_server_sale_listings", new_callable=AsyncMock, return_value=[]) as mock_fn:
            await source.load()
        mock_fn.assert_called_once_with(200)

    async def test_page_count_empty_returns_1(self):
        source = AuctionBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_server_sale_listings", new_callable=AsyncMock, return_value=[]):
            await source.load()
        assert source.page_count() == 1

    async def test_page_count_reflects_listing_count(self):
        listings = [_make_sale_listing(id=i) for i in range(5)]
        source = AuctionBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_server_sale_listings", new_callable=AsyncMock, return_value=listings):
            await source.load()
        assert source.page_count() == 5

    async def test_render_empty_no_auctions_embed(self):
        source = AuctionBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_server_sale_listings", new_callable=AsyncMock, return_value=[]):
            await source.load()
        view = MagicMock()
        view.add_item = MagicMock()
        _, embed = await source.render(view, 0)
        assert "No active auctions" in embed.description

    async def test_render_shows_listing_embed(self):
        listing = _make_sale_listing(id=42, pooch_name="Fluffy")
        source = AuctionBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_server_sale_listings", new_callable=AsyncMock, return_value=[listing]):
            await source.load()
        view = MagicMock()
        view.add_item = MagicMock()
        content, embed = await source.render(view, 0)
        assert embed.title == "Fluffy"
        assert "42" in embed.footer.text

    async def test_render_attaches_controls_to_view(self):
        listing = _make_sale_listing(id=1)
        source = AuctionBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_server_sale_listings", new_callable=AsyncMock, return_value=[listing]):
            await source.load()
        view = MagicMock()
        view.add_item = MagicMock()
        await source.render(view, 0)
        assert view.add_item.called


# ---------------------------------------------------------------------------
# BountyBrowsePageSource
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestBountyBrowsePageSource:
    async def test_load_calls_game_fn(self):
        source = BountyBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch(
            "src.bot.ui.auction.list_server_bounty_listings", new_callable=AsyncMock, return_value=[]
        ) as mock_fn:
            await source.load()
        mock_fn.assert_called_once_with(200)

    async def test_page_count_empty_returns_1(self):
        source = BountyBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_server_bounty_listings", new_callable=AsyncMock, return_value=[]):
            await source.load()
        assert source.page_count() == 1

    async def test_page_count_with_listings(self):
        listings = [_make_bounty_listing(id=i) for i in range(3)]
        source = BountyBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_server_bounty_listings", new_callable=AsyncMock, return_value=listings):
            await source.load()
        assert source.page_count() == 3

    async def test_render_empty_no_bounties_embed(self):
        source = BountyBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_server_bounty_listings", new_callable=AsyncMock, return_value=[]):
            await source.load()
        view = MagicMock()
        view.add_item = MagicMock()
        _, embed = await source.render(view, 0)
        assert "No active bounties" in embed.description

    async def test_render_shows_bounty_embed(self):
        listing = _make_bounty_listing(id=7, title="Fluffy Wanted")
        source = BountyBrowsePageSource(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_server_bounty_listings", new_callable=AsyncMock, return_value=[listing]):
            await source.load()
        view = MagicMock()
        view.add_item = MagicMock()
        content, embed = await source.render(view, 0)
        assert embed.title == "Fluffy Wanted"
        assert "7" in embed.footer.text


# ---------------------------------------------------------------------------
# _build_sale_listing_embed
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestBuildSaleListingEmbed:
    def test_embed_title_is_pooch_name(self):
        listing = _make_sale_listing(pooch_name="Sparky")
        embed = _build_sale_listing_embed(listing)
        assert embed.title == "Sparky"

    def test_shows_minimum_bid_when_no_highest_bid(self):
        listing = _make_sale_listing(minimum_bid=50, highest_bid=None)
        embed = _build_sale_listing_embed(listing)
        bid_field = next(f for f in embed.fields if f.name == "Current Bid")
        assert "$50" in bid_field.value
        assert "(min)" in bid_field.value

    def test_shows_highest_bid_when_present(self):
        listing = _make_sale_listing(minimum_bid=50, highest_bid=75)
        embed = _build_sale_listing_embed(listing)
        bid_field = next(f for f in embed.fields if f.name == "Current Bid")
        assert "$75" in bid_field.value

    def test_footer_contains_listing_id(self):
        listing = _make_sale_listing(id=42)
        embed = _build_sale_listing_embed(listing)
        assert "42" in embed.footer.text

    def test_mutations_none_when_empty(self):
        listing = _make_sale_listing()
        listing.pooch.mutations = []
        embed = _build_sale_listing_embed(listing)
        mut_field = next(f for f in embed.fields if f.name == "Mutations")
        assert mut_field.value == "None"


# ---------------------------------------------------------------------------
# _build_bounty_listing_embed
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestBuildBountyListingEmbed:
    def test_embed_title_defaults_to_wanted(self):
        listing = _make_bounty_listing(title=None)
        embed = _build_bounty_listing_embed(listing)
        assert embed.title == "Wanted"

    def test_embed_title_from_listing(self):
        listing = _make_bounty_listing(title="Fluffy Wanted")
        embed = _build_bounty_listing_embed(listing)
        assert embed.title == "Fluffy Wanted"

    def test_shows_escrow_amount(self):
        listing = _make_bounty_listing(escrow_amount=300)
        embed = _build_bounty_listing_embed(listing)
        escrow_field = next(f for f in embed.fields if "Escrow" in f.name)
        assert "$300" in escrow_field.value

    def test_breed_criterion_rendered(self):
        listing = _make_bounty_listing(
            criteria=[{"type": "breed", "breed_name": "Poodle", "min_weight": 0.5, "dollar_value": 50}]
        )
        embed = _build_bounty_listing_embed(listing)
        criteria_field = next(f for f in embed.fields if f.name == "Criteria")
        assert "Poodle" in criteria_field.value
        assert "50%" in criteria_field.value
        assert "$50" in criteria_field.value

    def test_mutation_criterion_rendered(self):
        listing = _make_bounty_listing(criteria=[{"type": "mutation", "mutation_name": "Dwarfism", "dollar_value": 30}])
        embed = _build_bounty_listing_embed(listing)
        criteria_field = next(f for f in embed.fields if f.name == "Criteria")
        assert "Dwarfism" in criteria_field.value
        assert "$30" in criteria_field.value

    def test_sex_criterion_with_preferred(self):
        listing = _make_bounty_listing(
            criteria=[{"type": "sex", "value": "either", "preferred_sex": "female", "dollar_value": 20}]
        )
        embed = _build_bounty_listing_embed(listing)
        criteria_field = next(f for f in embed.fields if f.name == "Criteria")
        assert "prefers female" in criteria_field.value


# ---------------------------------------------------------------------------
# _MyListingsView
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestMyListingsView:
    async def test_creates_view(self):
        view = _MyListingsView(server_discord_id=200, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_interaction_check_owner_only(self):
        view = _MyListingsView(server_discord_id=200, owner_discord_id=100)
        interaction = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True
        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False

    async def test_build_embed_empty_listings(self):
        view = _MyListingsView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_sale_listings", new_callable=AsyncMock, return_value=[]):
            embed = await view.build_embed()
        assert "no active auction listings" in embed.description.lower()
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        assert len(selects) == 0

    async def test_build_embed_with_listings(self):
        listing = _make_sale_listing(id=1, pooch_name="Rex")
        view = _MyListingsView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_sale_listings", new_callable=AsyncMock, return_value=[listing]):
            embed = await view.build_embed()
        assert "Rex" in embed.description
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        assert len(selects) >= 1

    async def test_on_select_sets_selected_and_enables_close(self):
        listing = _make_sale_listing(id=1)
        view = _MyListingsView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_sale_listings", new_callable=AsyncMock, return_value=[listing]):
            await view.build_embed()

        interaction = _make_interaction()
        interaction.data = {"values": ["1"]}
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_select(interaction)

        assert view._selected is not None
        assert view._close_button.disabled is False

    async def test_on_close_calls_close_listing(self):
        listing = _make_sale_listing(id=1)
        view = _MyListingsView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_sale_listings", new_callable=AsyncMock, return_value=[listing]):
            await view.build_embed()
        view._selected = listing

        interaction = _make_interaction()
        with (
            patch(
                "src.bot.ui.auction.close_sale_listing", new_callable=AsyncMock, return_value=(True, "Closed!")
            ) as mock_close,
            patch("src.bot.ui.auction.list_owner_sale_listings", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_close(interaction)

        mock_close.assert_called_once_with(100, 1)

    async def test_on_close_success_refreshes_embed(self):
        listing = _make_sale_listing(id=1)
        view = _MyListingsView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_sale_listings", new_callable=AsyncMock, return_value=[listing]):
            await view.build_embed()
        view._selected = listing

        interaction = _make_interaction()
        with (
            patch("src.bot.ui.auction.close_sale_listing", new_callable=AsyncMock, return_value=(True, "Closed!")),
            patch("src.bot.ui.auction.list_owner_sale_listings", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_close(interaction)

        mock_r.reply.assert_called_once()
        mock_r.edit.assert_called()

    async def test_on_close_failure_shows_error(self):
        listing = _make_sale_listing(id=1)
        view = _MyListingsView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_sale_listings", new_callable=AsyncMock, return_value=[listing]):
            await view.build_embed()
        view._selected = listing

        interaction = _make_interaction()
        with (
            patch("src.bot.ui.auction.close_sale_listing", new_callable=AsyncMock, side_effect=Exception("DB error")),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.finish_with_error = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_close(interaction)

        mock_r.finish_with_error.assert_called_once()


# ---------------------------------------------------------------------------
# _MyBountiesView
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestMyBountiesView:
    async def test_creates_view(self):
        view = _MyBountiesView(server_discord_id=200, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_interaction_check_owner_only(self):
        view = _MyBountiesView(server_discord_id=200, owner_discord_id=100)
        interaction = MagicMock()
        interaction.user.id = 100
        assert await view.interaction_check(interaction) is True
        interaction.user.id = 999
        assert await view.interaction_check(interaction) is False

    async def test_build_embed_empty(self):
        view = _MyBountiesView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_bounty_listings", new_callable=AsyncMock, return_value=[]):
            embed = await view.build_embed()
        assert "no active bounty listings" in embed.description.lower()

    async def test_build_embed_with_bounties(self):
        listing = _make_bounty_listing(id=1, title="Wanted: Fluffy")
        view = _MyBountiesView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_bounty_listings", new_callable=AsyncMock, return_value=[listing]):
            embed = await view.build_embed()
        assert "Wanted: Fluffy" in embed.description
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        assert len(selects) >= 1

    async def test_on_select_enables_cancel_button(self):
        listing = _make_bounty_listing(id=1)
        view = _MyBountiesView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_bounty_listings", new_callable=AsyncMock, return_value=[listing]):
            await view.build_embed()

        interaction = _make_interaction()
        interaction.data = {"values": ["1"]}
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_select(interaction)

        assert view._cancel_button.disabled is False

    async def test_on_cancel_calls_game_fn(self):
        listing = _make_bounty_listing(id=1)
        view = _MyBountiesView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_bounty_listings", new_callable=AsyncMock, return_value=[listing]):
            await view.build_embed()
        view._selected = listing

        interaction = _make_interaction()
        with (
            patch(
                "src.bot.ui.auction.cancel_bounty_listing", new_callable=AsyncMock, return_value=(True, "Cancelled")
            ) as mock_cancel,
            patch("src.bot.ui.auction.list_owner_bounty_listings", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_cancel(interaction)

        mock_cancel.assert_called_once_with(100, 1)

    async def test_on_cancel_failure_shows_error(self):
        listing = _make_bounty_listing(id=1)
        view = _MyBountiesView(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_bounty_listings", new_callable=AsyncMock, return_value=[listing]):
            await view.build_embed()
        view._selected = listing

        interaction = _make_interaction()
        with (
            patch("src.bot.ui.auction.cancel_bounty_listing", new_callable=AsyncMock, side_effect=Exception("err")),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.finish_with_error = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_cancel(interaction)

        mock_r.finish_with_error.assert_called_once()


# ---------------------------------------------------------------------------
# _FulfillBountyFlow
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestFulfillBountyFlow:
    async def test_creates_view(self):
        listing = _make_bounty_listing()
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        assert isinstance(view, discord.ui.View)

    async def test_build_embed_no_kennels(self):
        listing = _make_bounty_listing()
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[]):
            embed = await view.build_embed()
        field_names = [f.name for f in embed.fields]
        assert "Error" in field_names
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        assert len(selects) == 0

    async def test_build_embed_with_kennels(self):
        listing = _make_bounty_listing()
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        kennel = _make_kennel(id=1, name="Kennel A")
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        assert len(selects) >= 1
        # Confirm button is disabled until preview
        assert view._confirm_button.disabled is True

    async def test_on_kennel_select_loads_pooches(self):
        listing = _make_bounty_listing()
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        kennel = _make_kennel(id=1)
        pooches = [_make_pooch(id=1, name="Rex", alive=True)]
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()

        interaction = _make_interaction()
        interaction.data = {"values": ["1"]}
        with (
            patch("src.bot.ui.auction.list_kennel_pooches", new_callable=AsyncMock, return_value=pooches),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_kennel_select(interaction)

        assert view._pooch_select.disabled is False

    async def test_on_kennel_select_empty_kennel_disables_pooch_select(self):
        listing = _make_bounty_listing()
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        kennel = _make_kennel(id=1)
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()

        interaction = _make_interaction()
        interaction.data = {"values": ["1"]}
        with (
            patch("src.bot.ui.auction.list_kennel_pooches", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_kennel_select(interaction)

        assert view._pooch_select.disabled is True

    async def test_on_pooch_select_sets_pooch(self):
        listing = _make_bounty_listing()
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        kennel = _make_kennel(id=1)
        pooch = _make_pooch(id=1)
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        view._pooches = [pooch]
        # Manually create the pooch select
        view._pooch_select.options = [discord.SelectOption(label="Rex", value="1")]

        interaction = _make_interaction()
        interaction.data = {"values": ["1"]}
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_pooch_select(interaction)

        assert view._selected_pooch is not None
        # confirm must remain disabled — preview required first
        assert view._confirm_button.disabled is True

    async def test_on_pooch_select_none_value_clears_pooch(self):
        listing = _make_bounty_listing()
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        kennel = _make_kennel(id=1)
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        view._pooch_select.options = [discord.SelectOption(label="None", value="__none__")]

        interaction = _make_interaction()
        interaction.data = {"values": ["__none__"]}
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_pooch_select(interaction)

        assert view._selected_pooch is None
        assert view._confirm_button.disabled is True

    async def test_on_preview_calls_evaluate_match(self):
        listing = _make_bounty_listing(escrow_amount=100)
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        pooch = _make_pooch(id=1, name="Rex")

        match = MagicMock()
        match.payout = 50
        match.matched_criteria = []

        kennel = _make_kennel()
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        # set AFTER build_embed since build_embed resets _selected_pooch
        view._selected_pooch = pooch

        interaction = _make_interaction()
        with (
            patch("src.bot.ui.auction.evaluate_bounty_match", new_callable=AsyncMock, return_value=match) as mock_eval,
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_preview(interaction)

        mock_eval.assert_called_once_with(listing.id, pooch.id)

    async def test_on_preview_nonzero_payout_enables_confirm(self):
        listing = _make_bounty_listing(escrow_amount=100)
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        pooch = _make_pooch(id=1)

        match = MagicMock()
        match.payout = 50
        match.matched_criteria = []

        kennel = _make_kennel()
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        view._selected_pooch = pooch

        interaction = _make_interaction()
        with (
            patch("src.bot.ui.auction.evaluate_bounty_match", new_callable=AsyncMock, return_value=match),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_preview(interaction)

        assert view._confirm_button.disabled is False

    async def test_on_preview_zero_payout_leaves_confirm_disabled(self):
        listing = _make_bounty_listing(escrow_amount=100)
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        pooch = _make_pooch(id=1)

        match = MagicMock()
        match.payout = 0
        match.matched_criteria = []

        kennel = _make_kennel()
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        view._selected_pooch = pooch

        interaction = _make_interaction()
        with (
            patch("src.bot.ui.auction.evaluate_bounty_match", new_callable=AsyncMock, return_value=match),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_preview(interaction)

        assert view._confirm_button.disabled is True

    async def test_on_confirm_calls_fulfill_bounty(self):
        listing = _make_bounty_listing(id=3)
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)
        pooch = _make_pooch(id=5)

        kennel = _make_kennel()
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        view._selected_pooch = pooch

        interaction = _make_interaction()
        with (
            patch("src.bot.ui.auction.fulfill_bounty", new_callable=AsyncMock, return_value=(True, "Done!")) as mock_fn,
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_confirm(interaction)

        mock_fn.assert_called_once_with(100, 3, 5)

    async def test_on_confirm_exception_shows_error(self):
        listing = _make_bounty_listing()
        view = _FulfillBountyFlow(owner_discord_id=100, listing=listing)

        kennel = _make_kennel()
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        view._selected_pooch = _make_pooch(id=1)

        interaction = _make_interaction()
        with (
            patch("src.bot.ui.auction.fulfill_bounty", new_callable=AsyncMock, side_effect=Exception("err")),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.finish_with_error = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_confirm(interaction)

        mock_r.finish_with_error.assert_called_once()


# ---------------------------------------------------------------------------
# _CreateSaleListingFlow
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestCreateSaleListingFlow:
    async def test_creates_view(self):
        view = _CreateSaleListingFlow(server_discord_id=200, owner_discord_id=100)
        assert isinstance(view, discord.ui.View)

    async def test_build_embed_no_kennels(self):
        view = _CreateSaleListingFlow(server_discord_id=200, owner_discord_id=100)
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[]):
            embed = await view.build_embed()
        assert "don't have any kennels" in embed.description.lower() or "kennels" in embed.description.lower()

    async def test_build_embed_with_kennels(self):
        view = _CreateSaleListingFlow(server_discord_id=200, owner_discord_id=100)
        kennel = _make_kennel(id=1, name="Kennel A")
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
        assert len(selects) >= 1
        assert view._list_button.disabled is True

    async def test_on_kennel_select_populates_pooch_select(self):
        view = _CreateSaleListingFlow(server_discord_id=200, owner_discord_id=100)
        kennel = _make_kennel(id=1)
        pooches = [_make_pooch(id=1, name="Rex", alive=True)]
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()

        interaction = _make_interaction()
        interaction.data = {"values": ["1"]}
        with (
            patch("src.bot.ui.auction.list_kennel_pooches", new_callable=AsyncMock, return_value=pooches),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_kennel_select(interaction)

        assert view._pooch_select.disabled is False

    async def test_on_kennel_select_empty_kennel(self):
        view = _CreateSaleListingFlow(server_discord_id=200, owner_discord_id=100)
        kennel = _make_kennel(id=1)
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()

        interaction = _make_interaction()
        interaction.data = {"values": ["1"]}
        with (
            patch("src.bot.ui.auction.list_kennel_pooches", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_kennel_select(interaction)

        assert view._pooch_select.disabled is True
        assert any("No living pooches" in opt.label for opt in view._pooch_select.options)

    async def test_on_pooch_select_enables_list_button(self):
        view = _CreateSaleListingFlow(server_discord_id=200, owner_discord_id=100)
        kennel = _make_kennel(id=1)
        pooch = _make_pooch(id=5)
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        view._pooches = [pooch]
        view._pooch_select.options = [discord.SelectOption(label="Rex", value="5")]

        interaction = _make_interaction()
        interaction.data = {"values": ["5"]}
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_pooch_select(interaction)

        assert view._list_button.disabled is False

    async def test_on_pooch_select_none_disables_list_button(self):
        view = _CreateSaleListingFlow(server_discord_id=200, owner_discord_id=100)
        kennel = _make_kennel(id=1)
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        view._pooch_select.options = [discord.SelectOption(label="None", value="__none__")]

        interaction = _make_interaction()
        interaction.data = {"values": ["__none__"]}
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.edit = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_pooch_select(interaction)

        assert view._list_button.disabled is True

    async def test_on_list_sends_sale_listing_modal(self):
        view = _CreateSaleListingFlow(server_discord_id=200, owner_discord_id=100)
        kennel = _make_kennel(id=1)
        with patch("src.bot.ui.auction.list_owner_kennels", new_callable=AsyncMock, return_value=[kennel]):
            await view.build_embed()
        view._selected_pooch = _make_pooch(id=1, name="Rex")

        interaction = _make_interaction()
        await view._on_list(interaction)

        interaction.response.send_modal.assert_called_once()
        from src.bot.ui.auction import _SaleListingModal

        assert isinstance(interaction.response.send_modal.call_args[0][0], _SaleListingModal)


# ---------------------------------------------------------------------------
# _BountyBuilderView
# ---------------------------------------------------------------------------


@pytest.mark.contract
class TestBountyBuilderView:
    def _make_builder(self):
        view = _BountyBuilderView(
            server_discord_id=200,
            owner_discord_id=100,
            title="Wanted",
            escrow_amount=200,
        )
        return view

    async def test_creates_view(self):
        view = self._make_builder()
        assert isinstance(view, discord.ui.View)

    async def test_build_embed_loads_breeds_and_mutations(self):
        view = self._make_builder()
        with (
            patch("src.bot.ui.auction.list_all_breeds", new_callable=AsyncMock, return_value=[]) as mock_breeds,
            patch("src.bot.ui.auction.list_all_mutations", new_callable=AsyncMock, return_value=[]) as mock_muts,
        ):
            await view.build_embed()
        mock_breeds.assert_called_once()
        mock_muts.assert_called_once()

    async def test_confirm_disabled_with_no_criteria(self):
        view = self._make_builder()
        with (
            patch("src.bot.ui.auction.list_all_breeds", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.auction.list_all_mutations", new_callable=AsyncMock, return_value=[]),
        ):
            await view.build_embed()
        confirm_buttons = [
            c for c in view.children if isinstance(c, discord.ui.Button) and "Post Bounty" in (c.label or "")
        ]
        assert len(confirm_buttons) == 1
        assert confirm_buttons[0].disabled is True

    async def test_confirm_enabled_with_criteria(self):
        view = self._make_builder()
        view._criteria = [{"type": "breed", "breed_name": "Poodle", "min_weight": 0.5, "dollar_value": 50}]
        with (
            patch("src.bot.ui.auction.list_all_breeds", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.auction.list_all_mutations", new_callable=AsyncMock, return_value=[]),
        ):
            await view.build_embed()
        confirm_buttons = [
            c for c in view.children if isinstance(c, discord.ui.Button) and "Post Bounty" in (c.label or "")
        ]
        assert confirm_buttons[0].disabled is False

    async def test_build_embed_shows_criteria_summary(self):
        view = self._make_builder()
        view._criteria = [{"type": "breed", "breed_name": "Poodle", "min_weight": 0.5, "dollar_value": 50}]
        with (
            patch("src.bot.ui.auction.list_all_breeds", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.auction.list_all_mutations", new_callable=AsyncMock, return_value=[]),
        ):
            embed = await view.build_embed()
        field_values = " ".join(f.value for f in embed.fields)
        assert "Poodle" in field_values
        assert "$50" in field_values

    async def test_on_type_select_breed_sends_modal(self):
        view = self._make_builder()
        view._all_breeds = []
        view._all_mutations = []

        interaction = _make_interaction()
        interaction.data = {"values": ["breed"]}
        await view._on_type_select(interaction)
        interaction.response.send_modal.assert_called_once()
        assert isinstance(interaction.response.send_modal.call_args[0][0], _BreedCriterionModal)

    async def test_on_type_select_mutation_sends_modal(self):
        view = self._make_builder()
        view._all_mutations = []
        interaction = _make_interaction()
        interaction.data = {"values": ["mutation"]}
        await view._on_type_select(interaction)
        interaction.response.send_modal.assert_called_once()
        assert isinstance(interaction.response.send_modal.call_args[0][0], _MutationCriterionModal)

    async def test_on_type_select_sex_sends_modal(self):
        view = self._make_builder()
        interaction = _make_interaction()
        interaction.data = {"values": ["sex"]}
        await view._on_type_select(interaction)
        interaction.response.send_modal.assert_called_once()
        assert isinstance(interaction.response.send_modal.call_args[0][0], _SexCriterionModal)

    async def test_on_type_select_min_stat_sends_modal(self):
        view = self._make_builder()
        interaction = _make_interaction()
        interaction.data = {"values": ["min_stat"]}
        await view._on_type_select(interaction)
        interaction.response.send_modal.assert_called_once()
        assert isinstance(interaction.response.send_modal.call_args[0][0], _MinStatCriterionModal)

    async def test_on_type_select_min_rarity_sends_modal(self):
        view = self._make_builder()
        interaction = _make_interaction()
        interaction.data = {"values": ["min_rarity"]}
        await view._on_type_select(interaction)
        interaction.response.send_modal.assert_called_once()
        assert isinstance(interaction.response.send_modal.call_args[0][0], _MinRarityCriterionModal)

    async def test_add_criterion_and_refresh_appends_and_rebuilds(self):
        view = self._make_builder()
        criterion = {"type": "breed", "breed_name": "Poodle", "min_weight": 0.5, "dollar_value": 50}
        interaction = _make_interaction()

        with (
            patch("src.bot.ui.auction.list_all_breeds", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.auction.list_all_mutations", new_callable=AsyncMock, return_value=[]),
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view.add_criterion_and_refresh(criterion, interaction)

        assert len(view._criteria) == 1
        mock_r.reply.assert_called_once()

    async def test_on_confirm_calls_create_bounty_listing(self):
        view = self._make_builder()
        view._criteria = [{"type": "breed", "breed_name": "Poodle", "min_weight": 0.5, "dollar_value": 50}]

        interaction = _make_interaction()
        with (
            patch(
                "src.bot.ui.auction.create_bounty_listing", new_callable=AsyncMock, return_value=(True, "Posted!")
            ) as mock_fn,
            patch("src.bot.ui.auction.InteractionResponder") as MockResponder,
        ):
            mock_r = MagicMock()
            mock_r.defer = AsyncMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await view._on_confirm(interaction)

        mock_fn.assert_called_once_with(
            owner_discord_id=100,
            server_discord_id=200,
            title="Wanted",
            escrow_amount=200,
            criteria=view._criteria,
        )


# ---------------------------------------------------------------------------
# Criterion Modal Validation
# ---------------------------------------------------------------------------


def _make_builder_view():
    view = _BountyBuilderView(server_discord_id=200, owner_discord_id=100, title="Test", escrow_amount=100)
    view._all_breeds = []
    view._all_mutations = []
    return view


def _input(value: str):
    """Create a mock TextInput with the given value (TextInput.value is read-only in discord.py)."""
    m = MagicMock()
    m.value = value
    return m


@pytest.mark.contract
class TestCriterionModalValidation:
    # --- _BreedCriterionModal ---

    async def test_breed_valid_appends_criterion(self):
        builder = _make_builder_view()
        fake_breed = MagicMock()
        fake_breed.id = 1
        fake_breed.name = "Poodle"
        builder._all_breeds = [fake_breed]

        modal = _BreedCriterionModal(builder=builder, breed_options=[])
        modal.breed_name_input = _input("Poodle")
        modal.min_weight_input = _input("50")
        modal.dollar_value_input = _input("75")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            builder.add_criterion_and_refresh = AsyncMock()
            await modal.on_submit(interaction)

        builder.add_criterion_and_refresh.assert_called_once()
        criterion = builder.add_criterion_and_refresh.call_args[0][0]
        assert criterion["type"] == "breed"
        assert criterion["min_weight"] == 0.5

    async def test_breed_unknown_name_replies_error(self):
        builder = _make_builder_view()
        modal = _BreedCriterionModal(builder=builder, breed_options=[])
        modal.breed_name_input = _input("FakeBreed")
        modal.min_weight_input = _input("50")
        modal.dollar_value_input = _input("75")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()
        assert "No breed found" in mock_r.reply.call_args[1]["content"]

    async def test_breed_invalid_percent_replies_error(self):
        builder = _make_builder_view()
        fake_breed = MagicMock()
        fake_breed.name = "Poodle"
        builder._all_breeds = [fake_breed]

        modal = _BreedCriterionModal(builder=builder, breed_options=[])
        modal.breed_name_input = _input("Poodle")
        modal.min_weight_input = _input("abc")
        modal.dollar_value_input = _input("75")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()
        assert "whole numbers" in mock_r.reply.call_args[1]["content"].lower()

    async def test_breed_percent_out_of_range_replies_error(self):
        builder = _make_builder_view()
        fake_breed = MagicMock()
        fake_breed.name = "Poodle"
        builder._all_breeds = [fake_breed]

        modal = _BreedCriterionModal(builder=builder, breed_options=[])
        modal.breed_name_input = _input("Poodle")
        modal.min_weight_input = _input("0")
        modal.dollar_value_input = _input("75")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()
        assert "between 1 and 100" in mock_r.reply.call_args[1]["content"].lower()

    # --- _MutationCriterionModal ---

    async def test_mutation_valid_appends_criterion(self):
        builder = _make_builder_view()
        fake_mut = MagicMock()
        fake_mut.id = 1
        fake_mut.name = "Dwarfism"
        builder._all_mutations = [fake_mut]

        modal = _MutationCriterionModal(builder=builder, all_mutations=[])
        modal.mutation_name_input = _input("Dwarfism")
        modal.dollar_value_input = _input("30")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            builder.add_criterion_and_refresh = AsyncMock()
            await modal.on_submit(interaction)

        builder.add_criterion_and_refresh.assert_called_once()
        criterion = builder.add_criterion_and_refresh.call_args[0][0]
        assert criterion["type"] == "mutation"
        assert criterion["mutation_name"] == "Dwarfism"

    async def test_mutation_unknown_replies_error(self):
        builder = _make_builder_view()
        modal = _MutationCriterionModal(builder=builder, all_mutations=[])
        modal.mutation_name_input = _input("FakeMut")
        modal.dollar_value_input = _input("30")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()
        assert "No mutation found" in mock_r.reply.call_args[1]["content"]

    async def test_mutation_invalid_payout_replies_error(self):
        builder = _make_builder_view()
        fake_mut = MagicMock()
        fake_mut.name = "Dwarfism"
        builder._all_mutations = [fake_mut]

        modal = _MutationCriterionModal(builder=builder, all_mutations=[])
        modal.mutation_name_input = _input("Dwarfism")
        modal.dollar_value_input = _input("notanumber")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()

    # --- _SexCriterionModal ---

    async def test_sex_valid_male_appends_criterion(self):
        builder = _make_builder_view()
        modal = _SexCriterionModal(builder=builder)
        modal.sex_input = _input("male")
        modal.preferred_sex_input = _input("")
        modal.dollar_value_input = _input("20")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            builder.add_criterion_and_refresh = AsyncMock()
            await modal.on_submit(interaction)

        builder.add_criterion_and_refresh.assert_called_once()
        criterion = builder.add_criterion_and_refresh.call_args[0][0]
        assert criterion["type"] == "sex"
        assert criterion["value"] == "male"

    async def test_sex_invalid_value_replies_error(self):
        builder = _make_builder_view()
        modal = _SexCriterionModal(builder=builder)
        modal.sex_input = _input("nonbinary")
        modal.preferred_sex_input = _input("")
        modal.dollar_value_input = _input("20")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()
        assert "male" in mock_r.reply.call_args[1]["content"].lower()

    async def test_sex_either_without_preferred_replies_error(self):
        builder = _make_builder_view()
        modal = _SexCriterionModal(builder=builder)
        modal.sex_input = _input("either")
        modal.preferred_sex_input = _input("")
        modal.dollar_value_input = _input("20")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()
        assert "preferred_sex" in mock_r.reply.call_args[1]["content"]

    async def test_sex_either_with_valid_preferred(self):
        builder = _make_builder_view()
        modal = _SexCriterionModal(builder=builder)
        modal.sex_input = _input("either")
        modal.preferred_sex_input = _input("female")
        modal.dollar_value_input = _input("20")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            builder.add_criterion_and_refresh = AsyncMock()
            await modal.on_submit(interaction)

        builder.add_criterion_and_refresh.assert_called_once()
        criterion = builder.add_criterion_and_refresh.call_args[0][0]
        assert criterion.get("preferred_sex") == "female"

    # --- _MinStatCriterionModal ---

    async def test_min_stat_valid_appends_criterion(self):
        builder = _make_builder_view()
        modal = _MinStatCriterionModal(builder=builder)
        modal.stat_input = _input("strength")
        modal.threshold_input = _input("15")
        modal.dollar_value_input = _input("25")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            builder.add_criterion_and_refresh = AsyncMock()
            await modal.on_submit(interaction)

        builder.add_criterion_and_refresh.assert_called_once()
        criterion = builder.add_criterion_and_refresh.call_args[0][0]
        assert criterion["type"] == "min_stat"
        assert criterion["stat"] == "strength"
        assert criterion["threshold"] == 15

    async def test_min_stat_invalid_stat_name_replies_error(self):
        builder = _make_builder_view()
        modal = _MinStatCriterionModal(builder=builder)
        modal.stat_input = _input("toughness")
        modal.threshold_input = _input("15")
        modal.dollar_value_input = _input("25")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()
        content = mock_r.reply.call_args[1]["content"]
        assert "strength" in content.lower() or "stat" in content.lower()

    async def test_min_stat_non_digit_threshold_replies_error(self):
        builder = _make_builder_view()
        modal = _MinStatCriterionModal(builder=builder)
        modal.stat_input = _input("strength")
        modal.threshold_input = _input("abc")
        modal.dollar_value_input = _input("25")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()

    async def test_min_stat_non_digit_payout_replies_error(self):
        builder = _make_builder_view()
        modal = _MinStatCriterionModal(builder=builder)
        modal.stat_input = _input("strength")
        modal.threshold_input = _input("15")
        modal.dollar_value_input = _input("notanumber")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()

    # --- _MinRarityCriterionModal ---

    async def test_min_rarity_valid_appends_criterion(self):
        builder = _make_builder_view()
        modal = _MinRarityCriterionModal(builder=builder)
        modal.rarity_input = _input("rare")
        modal.dollar_value_input = _input("40")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            builder.add_criterion_and_refresh = AsyncMock()
            await modal.on_submit(interaction)

        builder.add_criterion_and_refresh.assert_called_once()
        criterion = builder.add_criterion_and_refresh.call_args[0][0]
        assert criterion["type"] == "min_rarity"
        assert criterion["value"] == "rare"

    async def test_min_rarity_invalid_replies_error(self):
        builder = _make_builder_view()
        modal = _MinRarityCriterionModal(builder=builder)
        modal.rarity_input = _input("legendary")
        modal.dollar_value_input = _input("40")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()
        content = mock_r.reply.call_args[1]["content"]
        assert "common" in content.lower() or "rarity" in content.lower()

    async def test_min_rarity_non_digit_payout_replies_error(self):
        builder = _make_builder_view()
        modal = _MinRarityCriterionModal(builder=builder)
        modal.rarity_input = _input("rare")
        modal.dollar_value_input = _input("abc")

        interaction = _make_interaction()
        with patch("src.bot.ui.auction.InteractionResponder") as MockResponder:
            mock_r = MagicMock()
            mock_r.reply = AsyncMock()
            MockResponder.return_value = mock_r
            await modal.on_submit(interaction)

        mock_r.reply.assert_called_once()
