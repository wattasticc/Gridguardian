import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# ==========================================================
# SOCIAL ROLE VIEW
# ==========================================================

class SocialRoleView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    # ======================================================
    # TWITCH
    # ======================================================

    @discord.ui.button(
        label="Twitch",
        emoji="🟣",
        style=discord.ButtonStyle.primary,
        custom_id="social_role_twitch"
    )
    async def twitch(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.toggle_role(
            interaction,
            "Twitch"
        )

    # ======================================================
    # TIKTOK
    # ======================================================

    @discord.ui.button(
        label="TikTok",
        emoji="🎵",
        style=discord.ButtonStyle.secondary,
        custom_id="social_role_tiktok"
    )
    async def tiktok(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.toggle_role(
            interaction,
            "TikTok"
        )

    # ======================================================
    # YOUTUBE
    # ======================================================

    @discord.ui.button(
        label="YouTube",
        emoji="▶️",
        style=discord.ButtonStyle.danger,
        custom_id="social_role_youtube"
    )
    async def youtube(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.toggle_role(
            interaction,
            "YouTube"
        )

    # ======================================================
    # INSTAGRAM
    # ======================================================

    @discord.ui.button(
        label="Instagram",
        emoji="📸",
        style=discord.ButtonStyle.primary,
        custom_id="social_role_instagram"
    )
    async def instagram(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.toggle_role(
            interaction,
            "Instagram"
        )

    # ======================================================
    # TOGGLE ROLE
    # ======================================================

    async def toggle_role(
        self,
        interaction: discord.Interaction,
        role_name: str
    ):

        guild = interaction.guild

        if guild is None:

            return await interaction.response.send_message(
                "❌ This button can only be used inside a server.",
                ephemeral=True
            )

        role = discord.utils.get(
            guild.roles,
            name=role_name
        )

        # --------------------------------------------------
        # ROLE DOESN'T EXIST
        # --------------------------------------------------

        if role is None:

            return await interaction.response.send_message(
                f"❌ The **{role_name}** role hasn't been created yet.",
                ephemeral=True
            )

        # --------------------------------------------------
        # BOT CAN'T MANAGE ROLE
        # --------------------------------------------------

        if role >= guild.me.top_role:

            return await interaction.response.send_message(
                f"❌ I can't manage the **{role_name}** role.\n\n"
                "Move my bot role above the social roles in "
                "Server Settings → Roles.",
                ephemeral=True
            )

        # --------------------------------------------------
        # REMOVE ROLE
        # --------------------------------------------------

        if role in interaction.user.roles:

            try:

                await interaction.user.remove_roles(
                    role,
                    reason="Social notification role removed"
                )

            except discord.Forbidden:

                return await interaction.response.send_message(
                    "❌ I don't have permission to remove that role.",
                    ephemeral=True
                )

            return await interaction.response.send_message(
                f"➖ Removed the **{role_name}** notification role.",
                ephemeral=True
            )

        # --------------------------------------------------
        # ADD ROLE
        # --------------------------------------------------

        try:

            await interaction.user.add_roles(
                role,
                reason="Social notification role added"
            )

        except discord.Forbidden:

            return await interaction.response.send_message(
                "❌ I don't have permission to give that role.",
                ephemeral=True
            )

        await interaction.response.send_message(
            f"✅ Added the **{role_name}** notification role!",
            ephemeral=True
        )


# ==========================================================
# REACTION ROLES COG
# ==========================================================

class ReactionRoles(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ======================================================
    # LOAD PERSISTENT VIEW
    # ======================================================

    async def cog_load(self):

        self.bot.add_view(
            SocialRoleView()
        )

    # ======================================================
    # SOCIAL ROLE PANEL
    # ======================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def rolepanel(self, ctx):

        embed = discord.Embed(
            title="📢 Social Notifications",
            description=(
                "Want notifications when I post or go live?\n\n"
                "Click the buttons below to choose which "
                "socials you want notifications for.\n\n"
                "You can click a button again at any time "
                "to remove the role."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="🟣 Twitch",
            value="Get notified when I go live.",
            inline=True
        )

        embed.add_field(
            name="🎵 TikTok",
            value="Get notified when I post.",
            inline=True
        )

        embed.add_field(
            name="▶️ YouTube",
            value="Get notified about YouTube uploads.",
            inline=True
        )

        embed.add_field(
            name="📸 Instagram",
            value="Get notified about Instagram posts.",
            inline=True
        )

        embed.set_footer(
            text="Grid Guardian • Social Notifications"
        )

        await ctx.send(
            embed=embed,
            view=SocialRoleView()
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        ReactionRoles(bot)
    )