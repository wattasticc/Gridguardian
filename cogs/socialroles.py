import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# ==========================================================
# ROLE NAMES
# ==========================================================

ROLE_NAMES = {
    "apex": "🎮 Apex",
    "twitch": "🟣 Twitch Notifications",
    "tiktok": "🎵 TikTok Notifications",
    "youtube": "▶️ YouTube Notifications",
    "instagram": "📸 Instagram Notifications",
}


# ==========================================================
# SOCIAL ROLE VIEW
# ==========================================================

class SocialRoleView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)


    async def toggle_role(
        self,
        interaction: discord.Interaction,
        role_name: str
    ):

        guild = interaction.guild
        member = interaction.user

        if guild is None:
            return await interaction.response.send_message(
                "❌ This button can only be used in a server.",
                ephemeral=True
            )

        role = discord.utils.get(
            guild.roles,
            name=role_name
        )

        # --------------------------------------------------
        # Create role if it doesn't exist
        # --------------------------------------------------

        if role is None:

            try:
                role = await guild.create_role(
                    name=role_name,
                    reason="Grid Guardian social role setup"
                )

            except discord.Forbidden:

                return await interaction.response.send_message(
                    "❌ I don't have permission to create roles.",
                    ephemeral=True
                )

        # --------------------------------------------------
        # Remove role
        # --------------------------------------------------

        if role in member.roles:

            try:
                await member.remove_roles(role)

            except discord.Forbidden:

                return await interaction.response.send_message(
                    "❌ I can't manage this role. Make sure my bot role "
                    "is above the role in the server settings.",
                    ephemeral=True
                )

            return await interaction.response.send_message(
                f"✅ Removed **{role.name}** from you.",
                ephemeral=True
            )

        # --------------------------------------------------
        # Add role
        # --------------------------------------------------

        try:
            await member.add_roles(role)

        except discord.Forbidden:

            return await interaction.response.send_message(
                "❌ I can't give you this role. Make sure my bot role "
                "is above the role in the server settings.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"✅ You now have **{role.name}**!",
            ephemeral=True
        )


    # ======================================================
    # APEX ROLE
    # ======================================================

    @discord.ui.button(
        label="Apex",
        emoji="🎮",
        style=discord.ButtonStyle.primary,
        custom_id="social_role_apex"
    )
    async def apex_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.toggle_role(
            interaction,
            ROLE_NAMES["apex"]
        )


    # ======================================================
    # TWITCH ROLE
    # ======================================================

    @discord.ui.button(
        label="Twitch",
        emoji="🟣",
        style=discord.ButtonStyle.secondary,
        custom_id="social_role_twitch"
    )
    async def twitch_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.toggle_role(
            interaction,
            ROLE_NAMES["twitch"]
        )


    # ======================================================
    # TIKTOK ROLE
    # ======================================================

    @discord.ui.button(
        label="TikTok",
        emoji="🎵",
        style=discord.ButtonStyle.secondary,
        custom_id="social_role_tiktok"
    )
    async def tiktok_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.toggle_role(
            interaction,
            ROLE_NAMES["tiktok"]
        )


    # ======================================================
    # YOUTUBE ROLE
    # ======================================================

    @discord.ui.button(
        label="YouTube",
        emoji="▶️",
        style=discord.ButtonStyle.secondary,
        custom_id="social_role_youtube"
    )
    async def youtube_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.toggle_role(
            interaction,
            ROLE_NAMES["youtube"]
        )


    # ======================================================
    # INSTAGRAM ROLE
    # ======================================================

    @discord.ui.button(
        label="Instagram",
        emoji="📸",
        style=discord.ButtonStyle.secondary,
        custom_id="social_role_instagram"
    )
    async def instagram_role(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.toggle_role(
            interaction,
            ROLE_NAMES["instagram"]
        )


# ==========================================================
# SOCIAL ROLES COG
# ==========================================================

class SocialRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    # ======================================================
    # SOCIAL ROLE PANEL
    # ======================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def socialpanel(self, ctx):

        embed = discord.Embed(
            title="🎮 Choose Your Roles",
            description=(
                "Click the buttons below to customize your server roles.\n\n"
                "🎮 **Apex** — Get the Apex role.\n"
                "🟣 **Twitch** — Get notifications for Twitch content.\n"
                "🎵 **TikTok** — Get notifications for TikTok content.\n"
                "▶️ **YouTube** — Get notifications for YouTube content.\n"
                "📸 **Instagram** — Get notifications for Instagram content.\n\n"
                "**Click a role again to remove it.**"
            ),
            color=EMBED_COLOR
        )

        embed.set_footer(
            text="Grid Guardian • Self Roles"
        )

        await ctx.send(
            embed=embed,
            view=SocialRoleView()
        )


    # ======================================================
    # ROLE LIST
    # ======================================================

    @commands.command()
    async def myroles(self, ctx):

        selected = []

        for role_name in ROLE_NAMES.values():

            role = discord.utils.get(
                ctx.guild.roles,
                name=role_name
            )

            if role and role in ctx.author.roles:
                selected.append(role.name)

        embed = discord.Embed(
            title=f"🎭 {ctx.author.display_name}'s Roles",
            color=EMBED_COLOR
        )

        if selected:

            embed.description = "\n".join(
                f"✅ {role}" for role in selected
            )

        else:

            embed.description = (
                "You don't have any of the available self-roles yet.\n\n"
                "Use the social role panel to choose some."
            )

        await ctx.send(embed=embed)


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        SocialRoles(bot)
    )

    # Register persistent buttons
    bot.add_view(
        SocialRoleView()
    )