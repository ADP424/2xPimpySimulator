"""Auction House UI — Want to Sell (sale listings) and Want to Buy (bounty listings)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Modal, Select, TextInput, View

from src.bot.constants import VIEW_TIMEOUT
from src.game import (
    cancel_bounty_listing,
    close_sale_listing,
    create_bounty_listing,
    create_sale_listing,
    evaluate_bounty_match,
    fulfill_bounty,
    get_or_create_owner,
    get_or_create_server,
    list_all_breeds,
    list_all_mutations,
    list_kennel_pooches,
    list_owner_bounty_listings,
    list_owner_kennels,
    list_owner_sale_listings,
    list_server_bounty_listings,
    list_server_sale_listings,
    place_bid,
)
from src.logger import get_logger

from .components import (
    PageSource,
    PaginatorView,
)
from .pooch_info import PoochInfoView
from .util import InteractionResponder

if TYPE_CHECKING:
    from src.game.models import AuctionBountyListing, AuctionSaleListing, Kennel, Pooch

logger = get_logger("bot/ui/auction")

_STATS = [
    "strength",
    "cuteness",
    "fluffiness",
    "intelligence",
    "dexterity",
    "fertility",
    "aggressiveness",
    "constitution",
    "size",
]
_RARITIES = ["common", "uncommon", "novel", "rare", "unprecedented", "remarkable", "extraordinary", "unique"]


# ---------------------------------------------------------------------------
# Hub
# ---------------------------------------------------------------------------


class AuctionHouseView(View):
    """Top-level Auction House hub."""

    def __init__(self, server_discord_id: int, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.add_item(_AuctionHouseSelect(server_discord_id=server_discord_id, owner_discord_id=owner_discord_id))
        back = Button(label="Marketplace", style=discord.ButtonStyle.secondary, row=1)
        back.callback = self._on_back
        self.add_item(back)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id

    async def _on_back(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        from .marketplace import MarketplaceView

        view = MarketplaceView(server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id)
        await r.reply(content="**Marketplace**", view=view)


class _AuctionHouseSelect(Select):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        super().__init__(
            placeholder="What would you like to do?",
            options=[
                discord.SelectOption(
                    label="Browse Auctions", value="browse_auctions", description="Bid on pooches for sale"
                ),
                discord.SelectOption(
                    label="My Listings", value="my_listings", description="Manage your active sale listings"
                ),
                discord.SelectOption(
                    label="Browse Bounties", value="browse_bounties", description="Fulfill want-to-buy requests"
                ),
                discord.SelectOption(
                    label="My Bounties", value="my_bounties", description="Manage your bounty listings"
                ),
                discord.SelectOption(
                    label="Post Auction", value="post_listing", description="List one of your pooches for sale"
                ),
                discord.SelectOption(
                    label="Post Bounty", value="post_bounty", description="Post a want-to-buy request"
                ),
            ],
            row=0,
        )
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]

        # Modals must be the first and only response — don't edit the view first.
        if choice == "post_bounty":
            modal = _BountyTitleEscrowModal(
                server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id
            )
            await interaction.response.send_modal(modal)
            return

        r = InteractionResponder(interaction)
        for opt in self.options:
            opt.default = opt.value == choice
        await r.edit(view=self.view)

        if choice == "browse_auctions":
            source = AuctionBrowsePageSource(
                server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id
            )
            view = PaginatorView(source, owner_discord_id=self.owner_discord_id)
            content, embed = await view.build_first_page()
            await r.reply(content=content or "**Auction House — Browse**", embed=embed, view=view)

        elif choice == "my_listings":
            view = _MyListingsView(server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id)
            embed = await view.build_embed()
            await r.reply(content="**My Auction Listings**", embed=embed, view=view)

        elif choice == "browse_bounties":
            source = BountyBrowsePageSource(
                server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id
            )
            view = PaginatorView(source, owner_discord_id=self.owner_discord_id)
            content, embed = await view.build_first_page()
            await r.reply(content=content or "**Auction House — Bounties**", embed=embed, view=view)

        elif choice == "my_bounties":
            view = _MyBountiesView(server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id)
            embed = await view.build_embed()
            await r.reply(content="**My Bounty Listings**", embed=embed, view=view)

        elif choice == "post_listing":
            view = _CreateSaleListingFlow(
                server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id
            )
            embed = await view.build_embed()
            await r.reply(content="**Post an Auction — Choose a Kennel**", embed=embed, view=view)


# ---------------------------------------------------------------------------
# Browse Auctions (sale listings)
# ---------------------------------------------------------------------------


class AuctionBrowsePageSource(PageSource):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self._listings: list[AuctionSaleListing] = []

    async def load(self):
        self._listings = await list_server_sale_listings(self.server_discord_id)

    def page_count(self) -> int:
        return max(len(self._listings), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._listings:
            return None, discord.Embed(title="Auction House", description="No active auctions right now.")

        listing = self._listings[page_index]
        embed = _build_sale_listing_embed(listing)

        controls = _AuctionListingControls(
            owner_discord_id=self.owner_discord_id,
            listing=listing,
        )
        controls.attach(view)
        return f"**Auction House** — listing {listing.id}", embed


def _build_sale_listing_embed(listing: AuctionSaleListing) -> discord.Embed:
    p = listing.pooch
    top_breed = max(p.breeds, key=lambda b: b.relative_weight).breed.name if p.breeds else "Unknown"
    mutations = ", ".join(m.name for m in p.mutations) if p.mutations else "None"

    high_str = f"${listing.highest_bid}" if listing.highest_bid is not None else f"${listing.minimum_bid} (min)"
    expires_str = f"<t:{int(listing.expires_at.timestamp())}:R>" if listing.expires_at else "No expiry (manual close)"

    embed = discord.Embed(
        title=p.name,
        description=f"Listed by <@{listing.seller_discord_id}>",
    )
    embed.add_field(name="Breed", value=top_breed, inline=True)
    embed.add_field(name="Age", value=f"{p.age} days", inline=True)
    embed.add_field(name="Sex", value=p.sex.capitalize(), inline=True)
    embed.add_field(name="Mutations", value=mutations, inline=False)
    embed.add_field(name="Current Bid", value=high_str, inline=True)
    embed.add_field(name="Bids", value=str(listing.bid_count), inline=True)
    embed.add_field(name="Expires", value=expires_str, inline=False)
    embed.set_footer(text=f"Listing #{listing.id}")
    return embed


class _AuctionListingControls:
    def __init__(self, owner_discord_id: int, listing: AuctionSaleListing):
        self.owner_discord_id = owner_discord_id
        self.listing = listing

        self.bid_button = Button(label="Place Bid", style=discord.ButtonStyle.success)
        self.bid_button.callback = self._on_bid

        self.info_button = Button(label="View Pooch", style=discord.ButtonStyle.primary)
        self.info_button.callback = self._on_info

        self.close_button = Button(label="End Auction", style=discord.ButtonStyle.danger)
        self.close_button.callback = self._on_close
        # Only the seller can see/use "End Auction"
        self.close_button.disabled = listing.seller_discord_id != owner_discord_id

    def attach(self, view: View):
        self.bid_button.row = 1
        self.info_button.row = 1
        self.close_button.row = 1
        view.add_item(self.bid_button)
        view.add_item(self.info_button)
        if self.listing.seller_discord_id == self.owner_discord_id:
            view.add_item(self.close_button)

    async def _on_bid(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_discord_id:
            return
        modal = _BidModal(listing=self.listing)
        await interaction.response.send_modal(modal)

    async def _on_info(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_discord_id:
            return
        r = InteractionResponder(interaction)
        p = self.listing.pooch
        server_discord_id = self.listing.server_discord_id
        server = await get_or_create_server(server_discord_id)
        owner = await get_or_create_owner(server_discord_id, self.owner_discord_id)
        view = PoochInfoView(server=server, pooch=p, owner=owner)
        embed = await view.build_embed()
        await r.reply(embed=embed, view=view)

    async def _on_close(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_discord_id:
            return
        r = InteractionResponder(interaction)
        if self.listing.seller_discord_id != self.owner_discord_id:
            await r.reply(content="You don't own this listing.")
            return
        await r.defer(thinking=True)
        try:
            success, message = await close_sale_listing(self.owner_discord_id, self.listing.id)
        except Exception as exc:
            logger.error(f"Error closing sale listing: {exc}")
            await r.finish_with_error("Failed to close the listing.")
            return
        prefix = "✅ " if success else ""
        await r.reply(content=f"{prefix}{message}")


class _BidModal(Modal, title="Place a Bid"):
    amount_input: TextInput = TextInput(
        label="Bid amount ($)",
        placeholder="Enter a whole dollar amount",
        min_length=1,
        max_length=10,
    )

    def __init__(self, listing: AuctionSaleListing):
        super().__init__()
        self.listing = listing
        hint = (
            f"Current high: ${self.listing.highest_bid}"
            if self.listing.highest_bid
            else f"Minimum bid: ${self.listing.minimum_bid}"
        )
        self.amount_input.placeholder = hint

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        raw = self.amount_input.value.strip().lstrip("$")
        if not raw.isdigit():
            await r.reply(content="Please enter a whole dollar amount (no decimals).")
            return
        amount = int(raw)
        await r.defer(thinking=True)
        try:
            success, message = await place_bid(interaction.user.id, self.listing.id, amount)
        except Exception as exc:
            logger.error(f"Error placing bid: {exc}")
            await r.finish_with_error("Bid failed unexpectedly.")
            return
        prefix = "✅ " if success else ""
        await r.reply(content=f"{prefix}{message}")


# ---------------------------------------------------------------------------
# My Listings
# ---------------------------------------------------------------------------


class _MyListingsView(View):
    def __init__(self, server_discord_id: int, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self._listings: list[AuctionSaleListing] = []
        self._selected: Optional[AuctionSaleListing] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id

    async def build_embed(self) -> discord.Embed:
        self.clear_items()
        self._listings = await list_owner_sale_listings(self.owner_discord_id)
        self._selected = None

        embed = discord.Embed(title="My Auction Listings")

        if not self._listings:
            embed.description = "You have no active auction listings."
            return embed

        lines = []
        options = []
        for listing in self._listings:
            high_str = f"${listing.highest_bid}" if listing.highest_bid is not None else f"${listing.minimum_bid} min"
            expires_str = f"<t:{int(listing.expires_at.timestamp())}:R>" if listing.expires_at else "manual"
            lines.append(
                f"**#{listing.id}** — {listing.pooch.name} | High: {high_str} | Bids: {listing.bid_count}"
                f" | Expires: {expires_str}"
            )
            options.append(
                discord.SelectOption(
                    label=f"#{listing.id}: {listing.pooch.name}"[:100],
                    value=str(listing.id),
                    description=f"High: {high_str}, {listing.bid_count} bid(s)"[:100],
                )
            )

        embed.description = "\n".join(lines)

        select = Select(placeholder="Select a listing to manage", options=options, row=0)
        select.callback = self._on_select
        self.add_item(select)

        self._close_button = Button(label="End Auction", style=discord.ButtonStyle.danger, disabled=True, row=1)
        self._close_button.callback = self._on_close
        self.add_item(self._close_button)

        return embed

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        listing_id = int(interaction.data["values"][0])
        self._selected = next((listing for listing in self._listings if listing.id == listing_id), None)
        for item in self.children:
            if isinstance(item, Select):
                for opt in item.options:
                    opt.default = opt.value == str(listing_id)
        self._close_button.disabled = self._selected is None
        await r.edit(view=self)

    async def _on_close(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self._selected is None:
            return
        await r.defer(thinking=True)
        try:
            success, message = await close_sale_listing(self.owner_discord_id, self._selected.id)
        except Exception as exc:
            logger.error(f"Error closing listing: {exc}")
            await r.finish_with_error("Failed to close the listing.")
            return
        prefix = "✅ " if success else ""
        await r.reply(content=f"{prefix}{message}")
        if success:
            embed = await self.build_embed()
            await r.edit(embed=embed, view=self)


# ---------------------------------------------------------------------------
# Browse Bounties
# ---------------------------------------------------------------------------


class BountyBrowsePageSource(PageSource):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self._listings: list[AuctionBountyListing] = []

    async def load(self):
        self._listings = await list_server_bounty_listings(self.server_discord_id)

    def page_count(self) -> int:
        return max(len(self._listings), 1)

    async def render(self, view: View, page_index: int) -> tuple[Optional[str], Optional[discord.Embed]]:
        if not self._listings:
            return None, discord.Embed(title="Bounty Board", description="No active bounties right now.")

        listing = self._listings[page_index]
        embed = _build_bounty_listing_embed(listing)

        controls = _BountyListingControls(
            owner_discord_id=self.owner_discord_id,
            listing=listing,
        )
        controls.attach(view)
        return f"**Bounty Board** — #{listing.id}", embed


def _build_bounty_listing_embed(listing: AuctionBountyListing) -> discord.Embed:
    criteria_lines = []
    for c in listing.criteria:
        ctype = c.get("type", "?")
        dv = c.get("dollar_value", 0)
        if ctype == "breed":
            name = c.get("breed_name") or f"ID {c.get('breed_id')}"
            criteria_lines.append(f"• {name} ≥{round(c.get('min_weight', 0) * 100)}% — ${dv}")
        elif ctype == "mutation":
            name = c.get("mutation_name") or f"ID {c.get('mutation_id')}"
            criteria_lines.append(f"• {name} — ${dv}")
        elif ctype == "sex":
            val = c.get("value", "?")
            pref = c.get("preferred_sex")
            label = val.capitalize()
            if val == "either" and pref:
                label += f" (prefers {pref})"
            criteria_lines.append(f"• Sex: {label} — ${dv}")
        elif ctype == "min_stat":
            criteria_lines.append(f"• {c.get('stat', '?').capitalize()} ≥ {c.get('threshold', 0)} — ${dv}")
        elif ctype == "min_rarity":
            criteria_lines.append(f"• Rarity ≥ {c.get('value', '?').capitalize()} — ${dv}")
        else:
            criteria_lines.append(f"• {ctype} — ${dv}")

    embed = discord.Embed(
        title=listing.title or "Wanted",
        description=f"Posted by <@{listing.buyer_discord_id}>",
    )
    embed.add_field(name="Escrow / Max Payout", value=f"${listing.escrow_amount}", inline=True)
    embed.add_field(name="Criteria", value="\n".join(criteria_lines) or "None", inline=False)
    embed.set_footer(text=f"Bounty #{listing.id}")
    return embed


class _BountyListingControls:
    def __init__(self, owner_discord_id: int, listing: AuctionBountyListing):
        self.owner_discord_id = owner_discord_id
        self.listing = listing

        self.fulfill_button = Button(label="Fulfill Bounty", style=discord.ButtonStyle.success)
        self.fulfill_button.callback = self._on_fulfill

        self.cancel_button = Button(label="Cancel Bounty", style=discord.ButtonStyle.danger)
        self.cancel_button.callback = self._on_cancel
        self.cancel_button.disabled = listing.buyer_discord_id != owner_discord_id

    def attach(self, view: View):
        self.fulfill_button.row = 1
        self.cancel_button.row = 1
        view.add_item(self.fulfill_button)
        if self.listing.buyer_discord_id == self.owner_discord_id:
            view.add_item(self.cancel_button)

    async def _on_fulfill(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_discord_id:
            return
        r = InteractionResponder(interaction)
        view = _FulfillBountyFlow(
            owner_discord_id=self.owner_discord_id,
            listing=self.listing,
        )
        embed = await view.build_embed()
        await r.reply(content=f"**Fulfill Bounty #{self.listing.id} — Choose a Kennel**", embed=embed, view=view)

    async def _on_cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_discord_id:
            return
        r = InteractionResponder(interaction)
        if self.listing.buyer_discord_id != self.owner_discord_id:
            await r.reply(content="You don't own this bounty.")
            return
        await r.defer(thinking=True)
        try:
            success, message = await cancel_bounty_listing(self.owner_discord_id, self.listing.id)
        except Exception as exc:
            logger.error(f"Error cancelling bounty: {exc}")
            await r.finish_with_error("Failed to cancel the bounty.")
            return
        prefix = "✅ " if success else ""
        await r.reply(content=f"{prefix}{message}")


# ---------------------------------------------------------------------------
# My Bounties
# ---------------------------------------------------------------------------


class _MyBountiesView(View):
    def __init__(self, server_discord_id: int, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self._listings: list[AuctionBountyListing] = []
        self._selected: Optional[AuctionBountyListing] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id

    async def build_embed(self) -> discord.Embed:
        self.clear_items()
        self._listings = await list_owner_bounty_listings(self.owner_discord_id)
        self._selected = None

        embed = discord.Embed(title="My Bounty Listings")

        if not self._listings:
            embed.description = "You have no active bounty listings."
            return embed

        lines = []
        options = []
        for listing in self._listings:
            lines.append(
                f"**#{listing.id}** — {listing.title or 'Wanted'} | Escrow: ${listing.escrow_amount}"
                f" | {len(listing.criteria)} criterion/a"
            )
            options.append(
                discord.SelectOption(
                    label=f"#{listing.id}: {listing.title or 'Wanted'}"[:100],
                    value=str(listing.id),
                    description=f"Escrow: ${listing.escrow_amount}"[:100],
                )
            )

        embed.description = "\n".join(lines)

        select = Select(placeholder="Select a bounty to manage", options=options, row=0)
        select.callback = self._on_select
        self.add_item(select)

        self._cancel_button = Button(label="Cancel Bounty", style=discord.ButtonStyle.danger, disabled=True, row=1)
        self._cancel_button.callback = self._on_cancel
        self.add_item(self._cancel_button)

        return embed

    async def _on_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        listing_id = int(interaction.data["values"][0])
        self._selected = next((listing for listing in self._listings if listing.id == listing_id), None)
        for item in self.children:
            if isinstance(item, Select):
                for opt in item.options:
                    opt.default = opt.value == str(listing_id)
        self._cancel_button.disabled = self._selected is None
        await r.edit(view=self)

    async def _on_cancel(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self._selected is None:
            return
        await r.defer(thinking=True)
        try:
            success, message = await cancel_bounty_listing(self.owner_discord_id, self._selected.id)
        except Exception as exc:
            logger.error(f"Error cancelling bounty: {exc}")
            await r.finish_with_error("Failed to cancel the bounty.")
            return
        prefix = "✅ " if success else ""
        await r.reply(content=f"{prefix}{message}")
        if success:
            embed = await self.build_embed()
            await r.edit(embed=embed, view=self)


# ---------------------------------------------------------------------------
# Fulfill Bounty flow: kennel select → pooch select → preview → confirm
# ---------------------------------------------------------------------------


class _FulfillBountyFlow(View):
    def __init__(self, owner_discord_id: int, listing: AuctionBountyListing, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.owner_discord_id = owner_discord_id
        self.listing = listing
        self._kennels: list[Kennel] = []
        self._pooches: list[Pooch] = []
        self._selected_kennel: Optional[Kennel] = None
        self._selected_pooch: Optional[Pooch] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id

    async def build_embed(self) -> discord.Embed:
        self.clear_items()
        self._kennels = await list_owner_kennels(self.owner_discord_id)
        self._selected_kennel = None
        self._selected_pooch = None

        embed = discord.Embed(
            title=f"Fulfill Bounty #{self.listing.id}",
            description=_build_bounty_listing_embed(self.listing).description,
        )
        for field in _build_bounty_listing_embed(self.listing).fields:
            embed.add_field(name=field.name, value=field.value, inline=field.inline)

        if not self._kennels:
            embed.add_field(name="Error", value="You have no kennels.", inline=False)
            return embed

        kennel_options = [discord.SelectOption(label=k.name, value=str(k.id)) for k in self._kennels]
        kennel_select = Select(placeholder="Choose a kennel", options=kennel_options, row=0)
        kennel_select.callback = self._on_kennel_select
        self.add_item(kennel_select)

        self._pooch_select = Select(
            placeholder="Choose a pooch (select kennel first)",
            options=[discord.SelectOption(label="— select kennel first —", value="__none__")],
            disabled=True,
            row=1,
        )
        self._pooch_select.callback = self._on_pooch_select
        self.add_item(self._pooch_select)

        self._preview_button = Button(label="Preview Payout", style=discord.ButtonStyle.primary, disabled=True, row=2)
        self._preview_button.callback = self._on_preview
        self.add_item(self._preview_button)

        self._confirm_button = Button(label="Confirm Sale", style=discord.ButtonStyle.success, disabled=True, row=3)
        self._confirm_button.callback = self._on_confirm
        self.add_item(self._confirm_button)

        return embed

    async def _on_kennel_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        kennel_id = int(interaction.data["values"][0])
        self._selected_kennel = next((k for k in self._kennels if k.id == kennel_id), None)
        self._selected_pooch = None
        self._confirm_button.disabled = True

        if self._selected_kennel is not None:
            self._pooches = [p for p in await list_kennel_pooches(kennel_id) if p.alive]
            if self._pooches:
                self._pooch_select.options = [
                    discord.SelectOption(label=p.name, value=str(p.id)) for p in self._pooches
                ]
                self._pooch_select.disabled = False
                self._preview_button.disabled = False
            else:
                self._pooch_select.options = [discord.SelectOption(label="No living pooches", value="__none__")]
                self._pooch_select.disabled = True
                self._preview_button.disabled = True

        # Update kennel select default
        for item in self.children:
            if isinstance(item, Select) and item.row == 0:
                for opt in item.options:
                    opt.default = opt.value == str(kennel_id)

        await r.edit(view=self)

    async def _on_pooch_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = interaction.data["values"][0]
        if value == "__none__":
            self._selected_pooch = None
            self._confirm_button.disabled = True
        else:
            pooch_id = int(value)
            self._selected_pooch = next((p for p in self._pooches if p.id == pooch_id), None)

        for opt in self._pooch_select.options:
            opt.default = opt.value == value
        self._confirm_button.disabled = True  # must preview first
        self._preview_button.disabled = self._selected_pooch is None

        await r.edit(view=self)

    async def _on_preview(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self._selected_pooch is None:
            await r.reply(content="Select a pooch first.")
            return
        await r.defer(thinking=True)
        try:
            match = await evaluate_bounty_match(self.listing.id, self._selected_pooch.id)
        except Exception as exc:
            logger.error(f"Error evaluating bounty match: {exc}")
            await r.finish_with_error("Failed to evaluate match.")
            return

        lines = []
        for entry in match.matched_criteria:
            ctype = entry.get("type", "?")
            dv = entry.get("dollar_value", 0)
            matched = entry.get("matched", False)
            tick = "✅" if matched else "❌"
            if ctype == "breed":
                name = entry.get("breed_name") or f"ID {entry.get('breed_id')}"
                label = f"{name} ≥{round(entry.get('min_weight', 0) * 100)}%"
            elif ctype == "mutation":
                name = entry.get("mutation_name") or f"ID {entry.get('mutation_id')}"
                label = f"{name}"
            elif ctype == "sex":
                val = entry.get("value", "?")
                pref = entry.get("preferred_sex")
                label = f"Sex: {val.capitalize()}"
                if val == "either" and pref:
                    label += f" (prefers {pref})"
            elif ctype == "min_stat":
                label = f"{entry.get('stat', '?').capitalize()} ≥ {entry.get('threshold', 0)}"
            elif ctype == "min_rarity":
                label = f"Rarity ≥ {entry.get('value', '?').capitalize()}"
            else:
                label = ctype
            earned = dv if matched else 0
            lines.append(f"{tick} {label} — ${earned} / ${dv}")

        embed = discord.Embed(
            title=f"Payout Preview for {self._selected_pooch.name}",
            description="\n".join(lines) or "No criteria.",
        )
        embed.add_field(name="Total Payout", value=f"**${match.payout}**", inline=True)
        embed.add_field(
            name="Escrow Refund to Buyer", value=f"${self.listing.escrow_amount - match.payout}", inline=True
        )

        if match.payout > 0:
            self._confirm_button.disabled = False
            await r.edit(view=self)

        await r.reply(embed=embed)

    async def _on_confirm(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self._selected_pooch is None:
            return
        await r.defer(thinking=True)
        try:
            success, message = await fulfill_bounty(self.owner_discord_id, self.listing.id, self._selected_pooch.id)
        except Exception as exc:
            logger.error(f"Error fulfilling bounty: {exc}")
            await r.finish_with_error("Failed to fulfill bounty.")
            return
        prefix = "✅ " if success else ""
        await r.reply(content=f"{prefix}{message}")


# ---------------------------------------------------------------------------
# Create Sale Listing flow: kennel select → pooch select → modal → create
# ---------------------------------------------------------------------------


class _CreateSaleListingFlow(View):
    def __init__(self, server_discord_id: int, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self._kennels: list[Kennel] = []
        self._pooches: list[Pooch] = []
        self._selected_kennel: Optional[Kennel] = None
        self._selected_pooch: Optional[Pooch] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id

    async def build_embed(self) -> discord.Embed:
        self.clear_items()
        self._kennels = await list_owner_kennels(self.owner_discord_id)
        self._selected_kennel = None
        self._selected_pooch = None

        embed = discord.Embed(
            title="Post an Auction",
            description="Select a kennel, then a pooch, then set the starting price.",
        )

        if not self._kennels:
            embed.description = "You don't have any kennels yet."
            return embed

        kennel_options = [discord.SelectOption(label=k.name, value=str(k.id)) for k in self._kennels]
        kennel_select = Select(placeholder="Choose a kennel", options=kennel_options, row=0)
        kennel_select.callback = self._on_kennel_select
        self.add_item(kennel_select)

        self._pooch_select = Select(
            placeholder="Choose a pooch (select kennel first)",
            options=[discord.SelectOption(label="— select kennel first —", value="__none__")],
            disabled=True,
            row=1,
        )
        self._pooch_select.callback = self._on_pooch_select
        self.add_item(self._pooch_select)

        self._list_button = Button(label="Set Price & List", style=discord.ButtonStyle.success, disabled=True, row=2)
        self._list_button.callback = self._on_list
        self.add_item(self._list_button)

        return embed

    async def _on_kennel_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        kennel_id = int(interaction.data["values"][0])
        self._selected_kennel = next((k for k in self._kennels if k.id == kennel_id), None)
        self._selected_pooch = None
        self._list_button.disabled = True

        if self._selected_kennel is not None:
            self._pooches = [p for p in await list_kennel_pooches(kennel_id) if p.alive]
            if self._pooches:
                self._pooch_select.options = [
                    discord.SelectOption(label=p.name, value=str(p.id)) for p in self._pooches
                ]
                self._pooch_select.disabled = False
            else:
                self._pooch_select.options = [discord.SelectOption(label="No living pooches", value="__none__")]
                self._pooch_select.disabled = True

        for item in self.children:
            if isinstance(item, Select) and item.row == 0:
                for opt in item.options:
                    opt.default = opt.value == str(kennel_id)

        await r.edit(view=self)

    async def _on_pooch_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = interaction.data["values"][0]
        if value == "__none__":
            self._selected_pooch = None
            self._list_button.disabled = True
        else:
            pooch_id = int(value)
            self._selected_pooch = next((p for p in self._pooches if p.id == pooch_id), None)
            self._list_button.disabled = self._selected_pooch is None

        for opt in self._pooch_select.options:
            opt.default = opt.value == value

        await r.edit(view=self)

    async def _on_list(self, interaction: discord.Interaction):
        if self._selected_pooch is None:
            return
        modal = _SaleListingModal(
            pooch_name=self._selected_pooch.name,
            server_discord_id=self.server_discord_id,
            owner_discord_id=self.owner_discord_id,
            pooch_id=self._selected_pooch.id,
        )
        await interaction.response.send_modal(modal)


class _SaleListingModal(Modal, title="List Pooch for Auction"):
    min_bid_input: TextInput = TextInput(
        label="Minimum bid ($)",
        placeholder="e.g. 50",
        min_length=1,
        max_length=10,
    )
    duration_input: TextInput = TextInput(
        label="Duration (hours, leave blank for no expiry)",
        placeholder="e.g. 24",
        required=False,
        min_length=0,
        max_length=5,
    )

    def __init__(self, pooch_name: str, server_discord_id: int, owner_discord_id: int, pooch_id: int):
        super().__init__()
        self.title = f"List {pooch_name} for Auction"
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.pooch_id = pooch_id

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)

        raw_bid = self.min_bid_input.value.strip().lstrip("$")
        if not raw_bid.isdigit():
            await r.reply(content="Minimum bid must be a whole dollar amount.")
            return
        minimum_bid = int(raw_bid)

        duration_hours: Optional[int] = None
        raw_dur = self.duration_input.value.strip()
        if raw_dur:
            if not raw_dur.isdigit():
                await r.reply(content="Duration must be a whole number of hours, or leave blank.")
                return
            duration_hours = int(raw_dur)

        await r.defer(thinking=True)
        try:
            success, message = await create_sale_listing(
                owner_discord_id=self.owner_discord_id,
                pooch_id=self.pooch_id,
                server_discord_id=self.server_discord_id,
                minimum_bid=minimum_bid,
                duration_hours=duration_hours,
            )
        except Exception as exc:
            logger.error(f"Error creating sale listing: {exc}")
            await r.finish_with_error("Listing failed unexpectedly.")
            return
        prefix = "✅ " if success else ""
        await r.reply(content=f"{prefix}{message}")


# ---------------------------------------------------------------------------
# Create Bounty flow: title+escrow modal → criteria builder loop → confirm
# ---------------------------------------------------------------------------


class _BountyTitleEscrowModal(Modal, title="Post a Bounty — Setup"):
    title_input: TextInput = TextInput(
        label="Title",
        placeholder="e.g. Wanted: Fluffy Champion",
        max_length=100,
    )
    escrow_input: TextInput = TextInput(
        label="Total budget / max payout ($)",
        placeholder="e.g. 200",
        min_length=1,
        max_length=10,
    )

    def __init__(self, server_discord_id: int, owner_discord_id: int):
        super().__init__()
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        raw = self.escrow_input.value.strip().lstrip("$")
        if not raw.isdigit():
            await r.reply(content="Budget must be a whole dollar amount.")
            return
        escrow_amount = int(raw)
        title = self.title_input.value.strip()

        view = _BountyBuilderView(
            server_discord_id=self.server_discord_id,
            owner_discord_id=self.owner_discord_id,
            title=title,
            escrow_amount=escrow_amount,
        )
        embed = await view.build_embed()
        await r.reply(content="**Post a Bounty — Add Criteria**", embed=embed, view=view)


class _BountyBuilderView(View):
    """Criteria builder loop for creating a bounty listing."""

    def __init__(
        self,
        server_discord_id: int,
        owner_discord_id: int,
        title: str,
        escrow_amount: int,
        timeout: float = VIEW_TIMEOUT,
    ):
        super().__init__(timeout=timeout)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.title = title
        self.escrow_amount = escrow_amount
        self._criteria: list[dict] = []
        self._all_breeds: list = []
        self._all_mutations: list = []

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id

    async def build_embed(self) -> discord.Embed:
        self.clear_items()

        if not self._all_breeds:
            self._all_breeds = await list_all_breeds()
        if not self._all_mutations:
            self._all_mutations = await list_all_mutations()

        embed = discord.Embed(
            title=f"Bounty: {self.title or 'Wanted'}",
            description=f"Budget: **${self.escrow_amount}**\n\nUse the dropdown to add criteria.",
        )
        if self._criteria:
            lines = []
            total = 0
            for c in self._criteria:
                ctype = c.get("type", "?")
                dv = c.get("dollar_value", 0)
                total += dv
                if ctype == "breed":
                    name = c.get("breed_name") or f"ID {c.get('breed_id')}"
                    lines.append(f"• {name} ≥{round(c.get('min_weight', 0) * 100)}% — ${dv}")
                elif ctype == "mutation":
                    name = c.get("mutation_name") or f"ID {c.get('mutation_id')}"
                    lines.append(f"• {name} — ${dv}")
                elif ctype == "sex":
                    val = c.get("value", "?")
                    pref = c.get("preferred_sex")
                    label = val.capitalize()
                    if val == "either" and pref:
                        label += f" (prefers {pref})"
                    lines.append(f"• Sex: {label} — ${dv}")
                elif ctype == "min_stat":
                    lines.append(f"• {c.get('stat', '?').capitalize()} ≥ {c.get('threshold', 0)} — ${dv}")
                elif ctype == "min_rarity":
                    lines.append(f"• Rarity ≥ {c.get('value', '?').capitalize()} — ${dv}")
                else:
                    lines.append(f"• {ctype} — ${dv}")
            embed.add_field(
                name=f"Criteria so far (total: ${total} / budget: ${self.escrow_amount})",
                value="\n".join(lines),
                inline=False,
            )

        # Criterion type selector
        type_select = Select(
            placeholder="Add a criterion type...",
            options=[
                discord.SelectOption(label="Breed", value="breed", description="Require a specific breed"),
                discord.SelectOption(label="Mutation", value="mutation", description="Require a specific mutation"),
                discord.SelectOption(label="Sex preference", value="sex", description="Preferred sex"),
                discord.SelectOption(label="Minimum stat", value="min_stat", description="Require a stat threshold"),
                discord.SelectOption(
                    label="Minimum rarity", value="min_rarity", description="Require a minimum breed rarity"
                ),
            ],
            row=0,
        )
        type_select.callback = self._on_type_select
        self.add_item(type_select)

        confirm_button = Button(
            label="Post Bounty",
            style=discord.ButtonStyle.success,
            disabled=not bool(self._criteria),
            row=1,
        )
        confirm_button.callback = self._on_confirm
        self.add_item(confirm_button)

        return embed

    async def _on_type_select(self, interaction: discord.Interaction):
        ctype = interaction.data["values"][0]
        if ctype == "breed":
            # Pick from breed list via dropdown; truncate to 25 for Discord
            breeds_short = self._all_breeds[:25]
            options = [discord.SelectOption(label=b.name[:100], value=str(b.id)) for b in breeds_short]
            modal = _BreedCriterionModal(builder=self, breed_options=options)
            await interaction.response.send_modal(modal)
        elif ctype == "mutation":
            modal = _MutationCriterionModal(builder=self, all_mutations=self._all_mutations)
            await interaction.response.send_modal(modal)
        elif ctype == "sex":
            modal = _SexCriterionModal(builder=self)
            await interaction.response.send_modal(modal)
        elif ctype == "min_stat":
            modal = _MinStatCriterionModal(builder=self)
            await interaction.response.send_modal(modal)
        elif ctype == "min_rarity":
            modal = _MinRarityCriterionModal(builder=self)
            await interaction.response.send_modal(modal)

    async def add_criterion_and_refresh(self, criterion: dict, interaction: discord.Interaction):
        """Called by the criterion modals when they complete successfully."""
        self._criteria.append(criterion)
        r = InteractionResponder(interaction)
        embed = await self.build_embed()
        await r.reply(content="**Post a Bounty — Add Criteria**", embed=embed, view=self)

    async def _on_confirm(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if not self._criteria:
            await r.reply(content="Add at least one criterion first.")
            return
        await r.defer(thinking=True)
        try:
            success, message = await create_bounty_listing(
                owner_discord_id=self.owner_discord_id,
                server_discord_id=self.server_discord_id,
                title=self.title,
                escrow_amount=self.escrow_amount,
                criteria=self._criteria,
            )
        except Exception as exc:
            logger.error(f"Error creating bounty listing: {exc}")
            await r.finish_with_error("Failed to post bounty.")
            return
        prefix = "✅ " if success else ""
        await r.reply(content=f"{prefix}{message}")


# ---------------------------------------------------------------------------
# Criterion modals — each submits a validated dict to _BountyBuilderView
# ---------------------------------------------------------------------------


class _BreedCriterionModal(Modal, title="Add Breed Criterion"):
    breed_name_input: TextInput = TextInput(
        label="Breed name",
        placeholder="e.g. Golden Retriever",
        min_length=1,
        max_length=100,
    )
    min_weight_input: TextInput = TextInput(
        label="Minimum breed % (1-100)",
        placeholder="e.g. 50",
        min_length=1,
        max_length=5,
    )
    dollar_value_input: TextInput = TextInput(
        label="Payout value ($)",
        placeholder="e.g. 75",
        min_length=1,
        max_length=10,
    )

    def __init__(self, builder: _BountyBuilderView, breed_options: list):
        super().__init__()
        self.builder = builder

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        raw_name = self.breed_name_input.value.strip()
        raw_w = self.min_weight_input.value.strip().rstrip("%")
        raw_dv = self.dollar_value_input.value.strip().lstrip("$")

        breed = next(
            (b for b in self.builder._all_breeds if b.name.lower() == raw_name.lower()),
            None,
        )
        if breed is None:
            await r.reply(content=f"No breed found named **{raw_name}**. Check the spelling.")
            return
        if not raw_w.isdigit() or not raw_dv.isdigit():
            await r.reply(content="Minimum % and payout must be whole numbers.")
            return
        min_weight = int(raw_w)
        if not 1 <= min_weight <= 100:
            await r.reply(content="Minimum breed % must be between 1 and 100.")
            return
        criterion = {
            "type": "breed",
            "breed_id": breed.id,
            "breed_name": breed.name,
            "min_weight": min_weight / 100,
            "dollar_value": int(raw_dv),
        }
        await self.builder.add_criterion_and_refresh(criterion, interaction)


class _MutationCriterionModal(Modal, title="Add Mutation Criterion"):
    mutation_name_input: TextInput = TextInput(
        label="Mutation name",
        placeholder="e.g. Dwarfism",
        min_length=1,
        max_length=100,
    )
    dollar_value_input: TextInput = TextInput(
        label="Payout value ($)",
        placeholder="e.g. 30",
        min_length=1,
        max_length=10,
    )

    def __init__(self, builder: _BountyBuilderView, all_mutations: list):
        super().__init__()
        self.builder = builder

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        raw_name = self.mutation_name_input.value.strip()
        raw_dv = self.dollar_value_input.value.strip().lstrip("$")

        mutation = next(
            (m for m in self.builder._all_mutations if m.name.lower() == raw_name.lower()),
            None,
        )
        if mutation is None:
            await r.reply(content=f"No mutation found named **{raw_name}**. Check the spelling.")
            return
        if not raw_dv.isdigit():
            await r.reply(content="Payout value must be a whole dollar amount.")
            return
        criterion = {
            "type": "mutation",
            "mutation_id": mutation.id,
            "mutation_name": mutation.name,
            "dollar_value": int(raw_dv),
        }
        await self.builder.add_criterion_and_refresh(criterion, interaction)


class _SexCriterionModal(Modal, title="Add Sex Criterion"):
    sex_input: TextInput = TextInput(
        label="Sex value: male / female / either",
        placeholder="male",
        min_length=4,
        max_length=6,
    )
    preferred_sex_input: TextInput = TextInput(
        label="Preferred sex (if 'either'): male / female",
        placeholder="Leave blank if value is not 'either'",
        required=False,
        min_length=0,
        max_length=6,
    )
    dollar_value_input: TextInput = TextInput(
        label="Payout value ($)",
        placeholder="e.g. 20",
        min_length=1,
        max_length=10,
    )

    def __init__(self, builder: _BountyBuilderView):
        super().__init__()
        self.builder = builder

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        value = self.sex_input.value.strip().lower()
        preferred = self.preferred_sex_input.value.strip().lower() or None
        raw_dv = self.dollar_value_input.value.strip().lstrip("$")

        if value not in ("male", "female", "either"):
            await r.reply(content="Sex value must be 'male', 'female', or 'either'.")
            return
        if value == "either" and preferred not in ("male", "female"):
            await r.reply(content="When value='either', preferred_sex must be 'male' or 'female'.")
            return
        if not raw_dv.isdigit():
            await r.reply(content="Payout value must be a whole dollar amount.")
            return

        criterion: dict = {"type": "sex", "value": value, "dollar_value": int(raw_dv)}
        if value == "either":
            criterion["preferred_sex"] = preferred
        await self.builder.add_criterion_and_refresh(criterion, interaction)


class _MinStatCriterionModal(Modal, title="Add Min Stat Criterion"):
    stat_input: TextInput = TextInput(
        label="Stat name",
        placeholder="strength / cuteness / size / ...",
        min_length=3,
        max_length=20,
    )
    threshold_input: TextInput = TextInput(
        label="Minimum value",
        placeholder="e.g. 15",
        min_length=1,
        max_length=6,
    )
    dollar_value_input: TextInput = TextInput(
        label="Payout value ($)",
        placeholder="e.g. 25",
        min_length=1,
        max_length=10,
    )

    def __init__(self, builder: _BountyBuilderView):
        super().__init__()
        self.builder = builder

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        stat = self.stat_input.value.strip().lower()
        raw_thr = self.threshold_input.value.strip()
        raw_dv = self.dollar_value_input.value.strip().lstrip("$")

        if stat not in _STATS:
            await r.reply(content=f"Stat must be one of: {', '.join(_STATS)}.")
            return
        if not raw_thr.isdigit() or not raw_dv.isdigit():
            await r.reply(content="Threshold and payout must be whole numbers.")
            return

        criterion = {
            "type": "min_stat",
            "stat": stat,
            "threshold": int(raw_thr),
            "dollar_value": int(raw_dv),
        }
        await self.builder.add_criterion_and_refresh(criterion, interaction)


class _MinRarityCriterionModal(Modal, title="Add Min Rarity Criterion"):
    rarity_input: TextInput = TextInput(
        label="Minimum rarity",
        placeholder="common / uncommon / rare / unique / ...",
        min_length=3,
        max_length=20,
    )
    dollar_value_input: TextInput = TextInput(
        label="Payout value ($)",
        placeholder="e.g. 40",
        min_length=1,
        max_length=10,
    )

    def __init__(self, builder: _BountyBuilderView):
        super().__init__()
        self.builder = builder

    async def on_submit(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        rarity = self.rarity_input.value.strip().lower()
        raw_dv = self.dollar_value_input.value.strip().lstrip("$")

        if rarity not in _RARITIES:
            await r.reply(content=f"Rarity must be one of: {', '.join(_RARITIES)}.")
            return
        if not raw_dv.isdigit():
            await r.reply(content="Payout value must be a whole dollar amount.")
            return

        criterion = {
            "type": "min_rarity",
            "value": rarity,
            "dollar_value": int(raw_dv),
        }
        await self.builder.add_criterion_and_refresh(criterion, interaction)
