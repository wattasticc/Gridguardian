import sqlite3

import discord
from discord.ext import commands


# ==========================================================
# CONFIGURATION
# ==========================================================

DATABASE_PATH = "gridguardian.db"

EMBED_COLOR = discord.Color.from_rgb(
    80,
    220,
    255
)


# ==========================================================
# DATABASE
# ==========================================================

def setup_database():

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    cursor = connection.cursor()


    cursor.execute("""
    CREATE TABLE IF NOT EXISTS verification_settings (
        guild_id INTEGER PRIMARY KEY,
        verified_role_id INTEGER,
        unverified_role_id INTEGER,
        verification_channel_id INTEGER
    )
    """)


    connection.commit()

    connection.close()


setup_database()


# ==========================================================
# DATABASE HELPERS
# ==========================================================

def get_verification_settings(guild_id):

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    cursor = connection.cursor()


    cursor.execute("""
    SELECT
        verified_role_id,
        unverified_role_id,
        verification_channel_id
    FROM verification_settings
    WHERE guild_id = ?
    """, (
        guild_id,
    ))


    result = cursor.fetchone()

    connection.close()


    if result is None:

        return None


    return {
        "verified_role_id": result[0],
        "unverified_role_id": result[1],
        "verification_channel_id": result[2]
    }


def save_verification_settings(
    guild_id,
    verified_role_id,
    unverified_role_id,
    verification_channel_id
):

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    cursor = connection.cursor()


    cursor.execute("""
    INSERT OR REPLACE INTO verification_settings (
        guild_id,
        verified_role_id,
        unverified_role_id,
        verification_channel_id
    )
    VALUES (?, ?, ?, ?)
    """, (
        guild_id,
        verified_role_id,
        unverified_role_id,
        verification_channel_id
    ))


    connection.commit()

    connection.close()


# ==========================================================
# VERIFICATION BUTTON
# ==========================================================

class VerificationView(discord.ui.View):

    def __init__(self):

        # timeout=None makes this persistent.
        super().__init__(
            timeout=None
        )


    @discord.ui.button(
        label="Verify",
        emoji="🛡️",
        style=discord.ButtonStyle.success,
        custom_id="gridguardian_verify_button"
    )
    async def verify_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        # --------------------------------------------------
        # GUILD CHECK
        # --------------------------------------------------

        if interaction.guild is None:

            await interaction.response.send_message(
                "❌ Verification can only be used inside a server.",
                ephemeral=True
            )

            return


        # --------------------------------------------------
        # GET SETTINGS
        # --------------------------------------------------

        settings = get_verification_settings(
            interaction.guild.id
        )


        if settings is None:

            await interaction.response.send_message(
                "❌ The verification system has not been configured yet.",
                ephemeral=True
            )

            return


        verified_role_id = settings[
            "verified_role_id"
        ]


        unverified_role_id = settings[
            "unverified_role_id"
        ]


        verified_role = interaction.guild.get_role(
            verified_role_id
        )


        # --------------------------------------------------
        # CHECK VERIFIED ROLE
        # --------------------------------------------------

        if verified_role is None:

            await interaction.response.send_message(
                "❌ The configured Verified role no longer exists.\n"
                "Please contact a server administrator.",
                ephemeral=True
            )

            return


        # --------------------------------------------------
        # CHECK IF ALREADY VERIFIED
        # --------------------------------------------------

        member = interaction.user


        if verified_role in member.roles:

            await interaction.response.send_message(
                "✅ You are already verified!",
                ephemeral=True
            )

            return


        # --------------------------------------------------
        # CHECK BOT PERMISSIONS
        # --------------------------------------------------

        bot_member = interaction.guild.me


        if bot_member is None:

            await interaction.response.send_message(
                "❌ I could not access my server permissions.",
                ephemeral=True
            )

            return


        if not bot_member.guild_permissions.manage_roles:

            await interaction.response.send_message(
                "❌ I need the **Manage Roles** permission to verify members.",
                ephemeral=True
            )

            return


        if verified_role >= bot_member.top_role:

            await interaction.response.send_message(
                "❌ My role needs to be above the Verified role.\n"
                "Please contact a server administrator.",
                ephemeral=True
            )

            return


        # --------------------------------------------------
        # ADD VERIFIED ROLE
        # --------------------------------------------------

        try:

            await member.add_roles(
                verified_role,
                reason=(
                    "Grid Guardian verification completed"
                )
            )


        except discord.Forbidden:

            await interaction.response.send_message(
                "❌ I don't have permission to give you the Verified role.",
                ephemeral=True
            )

            return


        except discord.HTTPException:

            await interaction.response.send_message(
                "❌ Something went wrong while verifying you. Please try again.",
                ephemeral=True
            )

            return


        # --------------------------------------------------
        # REMOVE UNVERIFIED ROLE
        # --------------------------------------------------

        if unverified_role_id is not None:

            unverified_role = interaction.guild.get_role(
                unverified_role_id
            )


            if (
                unverified_role is not None
                and unverified_role in member.roles
            ):

                # Only remove the role if the bot can manage it.

                if unverified_role < bot_member.top_role:

                    try:

                        await member.remove_roles(
                            unverified_role,
                            reason=(
                                "Grid Guardian verification completed"
                            )
                        )

                    except discord.HTTPException:

                        pass


        # --------------------------------------------------
        # SUCCESS
        # --------------------------------------------------

        embed = discord.Embed(
            title="🛡️ Verification Complete!",
            description=(
                f"Welcome, {member.mention}!\n\n"
                "You have successfully been verified and now "
                "have access to the server."
            ),
            color=EMBED_COLOR
        )


        embed.set_footer(
            text=(
                "Grid Guardian • Verification System"
            )
        )


        await interaction.response.send_message(
            embed=embed,
            ephemeral=True
        )


# ==========================================================
# VERIFICATION COG
# ==========================================================

class Verification(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


        # Register the persistent button.

        self.bot.add_view(
            VerificationView()
        )


    # ======================================================
    # SETUP COMMAND
    # ======================================================

    @commands.command(
        name="verifysetup"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def verifysetup(
        self,
        ctx,
        verified_role: discord.Role,
        channel: discord.TextChannel = None,
        unverified_role: discord.Role = None
    ):

        # --------------------------------------------------
        # DEFAULT CHANNEL
        # --------------------------------------------------

        if channel is None:

            channel = ctx.channel


        # --------------------------------------------------
        # CHECK BOT ROLE
        # --------------------------------------------------

        bot_member = ctx.guild.me


        if verified_role >= bot_member.top_role:

            return await ctx.send(
                "❌ My highest role must be above the "
                f"{verified_role.mention} role.\n\n"
                "Move my bot role higher in the server's role list "
                "and try again."
            )


        # --------------------------------------------------
        # CHECK UNVERIFIED ROLE
        # --------------------------------------------------

        if unverified_role is not None:

            if unverified_role >= bot_member.top_role:

                return await ctx.send(
                    "❌ My highest role must also be above the "
                    f"{unverified_role.mention} role."
                )


        # --------------------------------------------------
        # SAVE SETTINGS
        # --------------------------------------------------

        save_verification_settings(
            ctx.guild.id,
            verified_role.id,
            (
                unverified_role.id
                if unverified_role is not None
                else None
            ),
            channel.id
        )


        embed = discord.Embed(
            title="🛡️ Verification Setup Complete",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="✅ Verified Role",
            value=verified_role.mention,
            inline=False
        )


        if unverified_role is not None:

            embed.add_field(
                name="🔒 Unverified Role",
                value=unverified_role.mention,
                inline=False
            )


        else:

            embed.add_field(
                name="🔒 Unverified Role",
                value="Not configured",
                inline=False
            )


        embed.add_field(
            name="📢 Verification Channel",
            value=channel.mention,
            inline=False
        )


        embed.add_field(
            name="➡️ Next Step",
            value=(
                "Use `!verifypanel` to send the "
                "verification panel."
            ),
            inline=False
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # VERIFICATION PANEL
    # ======================================================

    @commands.command(
        name="verifypanel"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def verifypanel(
        self,
        ctx
    ):

        settings = get_verification_settings(
            ctx.guild.id
        )


        if settings is None:

            return await ctx.send(
                "❌ Verification has not been configured yet.\n\n"
                "Use:\n"
                "`!verifysetup @VerifiedRole`"
            )


        channel_id = settings[
            "verification_channel_id"
        ]


        channel = ctx.guild.get_channel(
            channel_id
        )


        if channel is None:

            return await ctx.send(
                "❌ The configured verification channel no longer exists.\n\n"
                "Run `!verifysetup` again."
            )


        embed = discord.Embed(
            title="🛡️ Server Verification",
            description=(
                "Welcome!\n\n"
                "Please click the button below to verify yourself "
                "and gain access to the server.\n\n"
                "Once verified, you will receive the "
                "**Verified** role."
            ),
            color=EMBED_COLOR
        )


        embed.set_footer(
            text=(
                "Grid Guardian • Secure Verification"
            )
        )


        view = VerificationView()


        await channel.send(
            embed=embed,
            view=view
        )


        if ctx.channel.id == channel.id:

            await ctx.send(
                "✅ Verification panel created!"
            )


        else:

            await ctx.send(
                f"✅ Verification panel created in {channel.mention}!"
            )


    # ======================================================
    # VERIFICATION STATUS
    # ======================================================

    @commands.command(
        name="verifystatus"
    )
    @commands.has_permissions(
        administrator=True
    )
    async def verifystatus(
        self,
        ctx
    ):

        settings = get_verification_settings(
            ctx.guild.id
        )


        if settings is None:

            return await ctx.send(
                "❌ Verification is not configured yet."
            )


        verified_role = ctx.guild.get_role(
            settings[
                "verified_role_id"
            ]
        )


        unverified_role = None


        if (
            settings[
                "unverified_role_id"
            ]
            is not None
        ):

            unverified_role = ctx.guild.get_role(
                settings[
                    "unverified_role_id"
                ]
            )


        channel = ctx.guild.get_channel(
            settings[
                "verification_channel_id"
            ]
        )


        embed = discord.Embed(
            title="🛡️ Verification Status",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="✅ Verified Role",
            value=(
                verified_role.mention
                if verified_role is not None
                else "❌ Role not found"
            ),
            inline=False
        )


        embed.add_field(
            name="🔒 Unverified Role",
            value=(
                unverified_role.mention
                if unverified_role is not None
                else "Not configured"
            ),
            inline=False
        )


        embed.add_field(
            name="📢 Verification Channel",
            value=(
                channel.mention
                if channel is not None
                else "❌ Channel not found"
            ),
            inline=False
        )


        await ctx.send(
            embed=embed
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Verification(bot)
    )