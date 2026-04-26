from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import discord
from discord.ui import Button, Select, View

from src.bot.constants import VIEW_TIMEOUT
from src.bot.ui.util import InteractionResponder
from src.game import (
    buy_kennel,
    get_kennel_buy_price,
    get_kennel_upgrade_price,
    get_or_create_owner,
    list_owner_kennels,
    upgrade_kennel,
)
from src.logger import get_logger

if TYPE_CHECKING:
    from src.game.models import Kennel

logger = get_logger("bot/ui/marketplace")


class MarketplaceView(View):
    """Top-level Marketplace hub — choose between Vendors and the Construction Company."""

    def __init__(self, server_discord_id: int, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self.add_item(_MarketplaceSelect(server_discord_id=server_discord_id, owner_discord_id=owner_discord_id))
        self.add_item(_TownButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id


class _TownButton(Button):
    def __init__(self):
        super().__init__(label="Town", style=discord.ButtonStyle.secondary, row=1)

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        from .town import TownView

        await r.reply(content="**Welcome to the Town**", view=TownView())


class _MarketplaceSelect(Select):
    def __init__(self, server_discord_id: int, owner_discord_id: int):
        super().__init__(
            placeholder="Where would you like to go?",
            options=[
                discord.SelectOption(label="Vendors", value="vendors", description="Buy and sell pooches"),
                discord.SelectOption(
                    label="Construction Company",
                    value="construction",
                    description="Buy kennels and upgrade capacity",
                ),
                discord.SelectOption(
                    label="Auction House",
                    value="auction",
                    description="Player-driven auctions and bounty listings",
                ),
            ],
            row=0,
        )
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id

    async def callback(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        for option in self.options:
            option.default = option.value == self.values[0]
        await r.edit(view=self.view)

        if self.values[0] == "vendors":
            from .components import PaginatorView
            from .vendors import VendorsPageSource

            source = VendorsPageSource(server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id)
            view = PaginatorView(source, owner_discord_id=self.owner_discord_id)
            content, embed = await view.build_first_page()
            await r.reply(
                content=content if content is not None else "**Vendor Stalls**",
                embed=embed,
                view=view,
            )

        elif self.values[0] == "construction":
            view = ConstructionCompanyView(
                server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id
            )
            embed = await view.build_embed()
            await r.reply(content="**Construction Company**", embed=embed, view=view)

        elif self.values[0] == "auction":
            from .auction import AuctionHouseView

            view = AuctionHouseView(server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id)
            await r.reply(content="**Auction House**", view=view)


# ---------------------------------------------------------------------------
# Construction Company
# ---------------------------------------------------------------------------


class ConstructionCompanyView(View):
    """
    Lets the owner buy a new kennel or select an existing one to upgrade.
    """

    def __init__(self, server_discord_id: int, owner_discord_id: int, timeout: float = VIEW_TIMEOUT):
        super().__init__(timeout=timeout)
        self.server_discord_id = server_discord_id
        self.owner_discord_id = owner_discord_id
        self._selected_kennel: Optional[Kennel] = None
        self._kennels: list[Kennel] = []

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.owner_discord_id

    async def build_embed(self) -> discord.Embed:
        self.clear_items()
        self._kennels = await list_owner_kennels(self.owner_discord_id)
        owner = await get_or_create_owner(self.server_discord_id, self.owner_discord_id)

        buy_price, buy_status = await get_kennel_buy_price(self.owner_discord_id)

        embed = discord.Embed(
            title="Construction Company",
            description=f"You have ${owner.dollars}.",
        )
        embed.add_field(name="Buy New Kennel", value=buy_status, inline=False)

        if self._kennels:
            upgrade_lines = []
            for kennel in self._kennels:
                _, upgrade_status = await get_kennel_upgrade_price(kennel.id)
                upgrade_lines.append(f"**{kennel.name}** ({kennel.pooch_limit} cap): {upgrade_status}")
            embed.add_field(name="Upgrade a Kennel", value="\n".join(upgrade_lines), inline=False)

        # Buy button
        buy_button = Button(
            label=f"Buy Kennel (${buy_price})" if buy_price is not None else "Buy Kennel (max)",
            style=discord.ButtonStyle.success,
            disabled=(buy_price is None),
            row=0,
        )
        buy_button.callback = self._on_buy_kennel
        self.add_item(buy_button)

        # Kennel select for upgrades
        if self._kennels:
            upgrade_options = []
            for kennel in self._kennels:
                price, status = await get_kennel_upgrade_price(kennel.id)
                label = f"{kennel.name} — {status}"
                upgrade_options.append(
                    discord.SelectOption(
                        label=label[:100],
                        value=str(kennel.id),
                        description=f"Current capacity: {kennel.pooch_limit}",
                    )
                )
            kennel_select = Select(
                placeholder="Select a kennel to upgrade",
                options=upgrade_options,
                row=1,
            )
            kennel_select.callback = self._on_kennel_select
            self.add_item(kennel_select)

            self._upgrade_button = Button(
                label="Upgrade Kennel",
                style=discord.ButtonStyle.primary,
                disabled=True,
                row=2,
            )
            self._upgrade_button.callback = self._on_upgrade_kennel
            self.add_item(self._upgrade_button)
        else:
            self._upgrade_button = None

        back_button = Button(label="Marketplace", style=discord.ButtonStyle.secondary, row=3)
        back_button.callback = self._on_back
        self.add_item(back_button)

        return embed

    async def _on_buy_kennel(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        await r.defer(thinking=True)
        try:
            success, message = await buy_kennel(self.owner_discord_id)
        except Exception as exc:
            logger.error(f"Error buying kennel: {exc}")
            await r.finish_with_error("Purchase failed unexpectedly.")
            return

        prefix = "✅ " if success else ""
        await r.reply(content=f"{prefix}{message}")

        if success:
            embed = await self.build_embed()
            await r.edit(embed=embed, view=self)

    async def _on_kennel_select(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        kennel_id = int(interaction.data["values"][0])
        self._selected_kennel = next((k for k in self._kennels if k.id == kennel_id), None)

        # Update select default highlight
        for item in self.children:
            if isinstance(item, Select):
                for opt in item.options:
                    opt.default = opt.value == str(kennel_id)

        # Enable/disable upgrade button based on whether upgrade is available
        if self._upgrade_button is not None and self._selected_kennel is not None:
            price, _ = await get_kennel_upgrade_price(self._selected_kennel.id)
            self._upgrade_button.disabled = price is None

        await r.edit(view=self)

    async def _on_upgrade_kennel(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        if self._selected_kennel is None:
            return
        await r.defer(thinking=True)
        try:
            success, message = await upgrade_kennel(self.owner_discord_id, self._selected_kennel.id)
        except Exception as exc:
            logger.error(f"Error upgrading kennel: {exc}")
            await r.finish_with_error("Upgrade failed unexpectedly.")
            return

        prefix = "✅ " if success else ""
        await r.reply(content=f"{prefix}{message}")

        if success:
            self._selected_kennel = None
            embed = await self.build_embed()
            await r.edit(embed=embed, view=self)

    async def _on_back(self, interaction: discord.Interaction):
        r = InteractionResponder(interaction)
        view = MarketplaceView(server_discord_id=self.server_discord_id, owner_discord_id=self.owner_discord_id)
        await r.reply(content="**Marketplace**", view=view)
