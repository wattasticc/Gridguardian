import discord


# =====================================================
# BASE ROLE VIEW
# =====================================================

class BaseRoleView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)


    async def toggle_role(
        self,
        interaction: discord.Interaction,
        role_name: str
    ):

        if interaction.guild is None:
            return await interaction.response.send_message(
                "❌ This can only be used inside a server.",
                ephemeral=True
            )

        role = discord.utils.get(
            interaction.guild.roles,
            name=role_name
        )

        if role is None:
            return await interaction.response.send_message(
                (
                    f"❌ The **{role_name}** role doesn't "
                    "exist in this server."
                ),
                ephemeral=True
            )

        bot_member = interaction.guild.me

        if bot_member is None:
            return await interaction.response.send_message(
                "❌ I couldn't verify my role permissions.",
                ephemeral=True
            )

        if role >= bot_member.top_role:
            return await interaction.response.send_message(
                (
                    f"❌ I can't manage **{role_name}** because "
                    "that role is above or equal to my bot role."
                ),
                ephemeral=True
            )

        if role.managed:
            return await interaction.response.send_message(
                (
                    f"❌ The **{role_name}** role is managed by "
                    "another integration and can't be assigned."
                ),
                ephemeral=True
            )

        try:

            if role in interaction.user.roles:

                await interaction.user.remove_roles(
                    role,
                    reason="Self-assigned role removed"
                )

                await interaction.response.send_message(
                    f"➖ Removed **{role_name}**.",
                    ephemeral=True
                )

            else:

                await interaction.user.add_roles(
                    role,
                    reason="Self-assigned role added"
                )

                await interaction.response.send_message(
                    f"✅ Added **{role_name}**!",
                    ephemeral=True
                )

        except discord.Forbidden:

            await interaction.response.send_message(
                (
                    "❌ I don't have permission to manage "
                    "that role."
                ),
                ephemeral=True
            )

        except discord.HTTPException:

            await interaction.response.send_message(
                (
                    "❌ Something went wrong while updating "
                    "your role. Please try again."
                ),
                ephemeral=True
            )


# =====================================================
# PLATFORM ROLE VIEW
# =====================================================

class PlatformRoleView(BaseRoleView):

    @discord.ui.button(
        label="🖥️ PC",
        style=discord.ButtonStyle.secondary,
        custom_id="platform_pc"
    )
    async def pc(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "PC"
        )


    @discord.ui.button(
        label="🎮 PlayStation",
        style=discord.ButtonStyle.primary,
        custom_id="platform_playstation"
    )
    async def playstation(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "PlayStation"
        )


    @discord.ui.button(
        label="🟩 Xbox",
        style=discord.ButtonStyle.success,
        custom_id="platform_xbox"
    )
    async def xbox(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Xbox"
        )


# =====================================================
# ASSAULT LEGEND ROLE VIEW
# =====================================================

class AssaultRoleView(BaseRoleView):

    @discord.ui.button(
        label="Ballistic",
        emoji="🎯",
        style=discord.ButtonStyle.secondary,
        custom_id="assault_ballistic"
    )
    async def ballistic(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Ballistic"
        )


    @discord.ui.button(
        label="Bangalore",
        emoji="💥",
        style=discord.ButtonStyle.primary,
        custom_id="assault_bangalore"
    )
    async def bangalore(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Bangalore"
        )


    @discord.ui.button(
        label="Fuse",
        emoji="💣",
        style=discord.ButtonStyle.danger,
        custom_id="assault_fuse"
    )
    async def fuse(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Fuse"
        )


    @discord.ui.button(
        label="Mad Maggie",
        emoji="🔥",
        style=discord.ButtonStyle.danger,
        custom_id="assault_madmaggie"
    )
    async def mad_maggie(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Mad Maggie"
        )


    @discord.ui.button(
        label="Revenant",
        emoji="👻",
        style=discord.ButtonStyle.danger,
        custom_id="assault_revenant"
    )
    async def revenant(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Revenant"
        )


# =====================================================
# SKIRMISHER LEGEND ROLE VIEW
# =====================================================

class SkirmisherRoleView(BaseRoleView):

    @discord.ui.button(
        label="Alter",
        emoji="🌀",
        style=discord.ButtonStyle.secondary,
        custom_id="skirmisher_alter"
    )
    async def alter(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Alter"
        )


    @discord.ui.button(
        label="Ash",
        emoji="⚔️",
        style=discord.ButtonStyle.danger,
        custom_id="skirmisher_ash"
    )
    async def ash(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Ash"
        )


    @discord.ui.button(
        label="Axle",
        emoji="🏎️",
        style=discord.ButtonStyle.primary,
        custom_id="skirmisher_axle"
    )
    async def axle(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Axle"
        )


    @discord.ui.button(
        label="Horizon",
        emoji="🌌",
        style=discord.ButtonStyle.primary,
        custom_id="skirmisher_horizon"
    )
    async def horizon(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Horizon"
        )


    @discord.ui.button(
        label="Octane",
        emoji="⚡",
        style=discord.ButtonStyle.success,
        custom_id="skirmisher_octane"
    )
    async def octane(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Octane"
        )


    @discord.ui.button(
        label="Pathfinder",
        emoji="🤖",
        style=discord.ButtonStyle.secondary,
        custom_id="skirmisher_pathfinder",
        row=1
    )
    async def pathfinder(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Pathfinder"
        )


    @discord.ui.button(
        label="Wraith",
        emoji="🩸",
        style=discord.ButtonStyle.primary,
        custom_id="skirmisher_wraith",
        row=1
    )
    async def wraith(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Wraith"
        )


# =====================================================
# RECON LEGEND ROLE VIEW
# =====================================================

class ReconRoleView(BaseRoleView):

    @discord.ui.button(
        label="Bloodhound",
        emoji="🔎",
        style=discord.ButtonStyle.danger,
        custom_id="recon_bloodhound"
    )
    async def bloodhound(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Bloodhound"
        )


    @discord.ui.button(
        label="Crypto",
        emoji="💻",
        style=discord.ButtonStyle.secondary,
        custom_id="recon_crypto"
    )
    async def crypto(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Crypto"
        )


    @discord.ui.button(
        label="Seer",
        emoji="👁️",
        style=discord.ButtonStyle.primary,
        custom_id="recon_seer"
    )
    async def seer(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Seer"
        )


    @discord.ui.button(
        label="Sparrow",
        emoji="🏹",
        style=discord.ButtonStyle.success,
        custom_id="recon_sparrow"
    )
    async def sparrow(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Sparrow"
        )


    @discord.ui.button(
        label="Valkyrie",
        emoji="🚀",
        style=discord.ButtonStyle.primary,
        custom_id="recon_valkyrie"
    )
    async def valkyrie(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Valkyrie"
        )


    @discord.ui.button(
        label="Vantage",
        emoji="🎯",
        style=discord.ButtonStyle.secondary,
        custom_id="recon_vantage",
        row=1
    )
    async def vantage(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Vantage"
        )


# =====================================================
# CONTROLLER LEGEND ROLE VIEW
# =====================================================

class ControllerRoleView(BaseRoleView):

    @discord.ui.button(
        label="Catalyst",
        emoji="🌑",
        style=discord.ButtonStyle.secondary,
        custom_id="controller_catalyst"
    )
    async def catalyst(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Catalyst"
        )


    @discord.ui.button(
        label="Caustic",
        emoji="☠️",
        style=discord.ButtonStyle.success,
        custom_id="controller_caustic"
    )
    async def caustic(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Caustic"
        )


    @discord.ui.button(
        label="Rampart",
        emoji="🔧",
        style=discord.ButtonStyle.danger,
        custom_id="controller_rampart"
    )
    async def rampart(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Rampart"
        )


    @discord.ui.button(
        label="Wattson",
        emoji="⚡",
        style=discord.ButtonStyle.primary,
        custom_id="controller_wattson"
    )
    async def wattson(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Wattson"
        )


# =====================================================
# SUPPORT LEGEND ROLE VIEW
# =====================================================

class SupportRoleView(BaseRoleView):

    @discord.ui.button(
        label="Conduit",
        emoji="⚡",
        style=discord.ButtonStyle.primary,
        custom_id="support_conduit"
    )
    async def conduit(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Conduit"
        )


    @discord.ui.button(
        label="Gibraltar",
        emoji="🛡️",
        style=discord.ButtonStyle.secondary,
        custom_id="support_gibraltar"
    )
    async def gibraltar(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Gibraltar"
        )


    @discord.ui.button(
        label="Lifeline",
        emoji="❤️",
        style=discord.ButtonStyle.danger,
        custom_id="support_lifeline"
    )
    async def lifeline(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Lifeline"
        )


    @discord.ui.button(
        label="Loba",
        emoji="💎",
        style=discord.ButtonStyle.primary,
        custom_id="support_loba"
    )
    async def loba(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Loba"
        )


    @discord.ui.button(
        label="Mirage",
        emoji="✨",
        style=discord.ButtonStyle.success,
        custom_id="support_mirage"
    )
    async def mirage(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Mirage"
        )


    @discord.ui.button(
        label="Newcastle",
        emoji="🛡️",
        style=discord.ButtonStyle.primary,
        custom_id="support_newcastle",
        row=1
    )
    async def newcastle(
        self,
        interaction,
        button
    ):

        await self.toggle_role(
            interaction,
            "Newcastle"
        )