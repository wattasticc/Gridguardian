import sqlite3
import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()


# =========================================================
# WELCOME COG
# =========================================================

class Welcome(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # MEMBER JOIN
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(self, member):

        # -------------------------------------------------
        # GET SERVER SETTINGS
        # -------------------------------------------------

        cursor.execute("""
        SELECT welcome_channel_id, autorole_id
        FROM settings
        WHERE guild_id=?
        """, (member.guild.id,))

        data = cursor.fetchone()

        # No settings configured
        if data is None:
            return

        welcome_channel_id, autorole_id = data

        # -------------------------------------------------
        # AUTOROLE
        # -------------------------------------------------

        role_given = False
        role = None

        if autorole_id:

            role = member.guild.get_role(autorole_id)

            if role:

                try:

                    await member.add_roles(
                        role,
                        reason="Automatic server role"
                    )

                    role_given = True

                except discord.Forbidden:

                    print(
                        f"⚠️ Grid Guardian cannot give "
                        f"the autorole in {member.guild.name}."
                    )

                except discord.HTTPException as error:

                    print(
                        f"⚠️ Failed to give autorole: {error}"
                    )

        # -------------------------------------------------
        # WELCOME CHANNEL
        # -------------------------------------------------

        if not welcome_channel_id:
            return

        channel = member.guild.get_channel(
            welcome_channel_id
        )

        # Channel doesn't exist anymore
        if channel is None:
            print(
                f"⚠️ Welcome channel no longer exists "
                f"in {member.guild.name}."
            )
            return

        # -------------------------------------------------
        # WELCOME EMBED
        # -------------------------------------------------

        description = (
            f"Welcome {member.mention} to "
            f"**{member.guild.name}**! 🎉\n\n"
            "We're glad to have you here!\n\n"
            "📖 Make sure to read the rules.\n"
            "🎮 Grab your roles.\n"
            "💬 Introduce yourself and have fun!"
        )

        # Mention autorole if successfully given
        if role_given and role:

            description += (
                f"\n\n🎭 You've been given the "
                f"**{role.name}** role!"
            )

        embed = discord.Embed(
            title="👋 Welcome to The Power Grid!",
            description=description,
            color=EMBED_COLOR
        )

        # -------------------------------------------------
        # MEMBER AVATAR
        # -------------------------------------------------

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        # -------------------------------------------------
        # MEMBER COUNT
        # -------------------------------------------------

        embed.add_field(
            name="👥 Member Count",
            value=f"**{member.guild.member_count}**",
            inline=True
        )

        # -------------------------------------------------
        # ACCOUNT CREATED
        # -------------------------------------------------

        account_created = discord.utils.format_dt(
            member.created_at,
            style="R"
        )

        embed.add_field(
            name="📅 Account Created",
            value=account_created,
            inline=True
        )

        # -------------------------------------------------
        # USER
        # -------------------------------------------------

        embed.add_field(
            name="👤 Member",
            value=member.mention,
            inline=False
        )

        # -------------------------------------------------
        # FOOTER
        # -------------------------------------------------

        embed.set_footer(
            text="⚡ Grid Guardian • Welcome!"
        )

        # -------------------------------------------------
        # SEND
        # -------------------------------------------------

        try:

            await channel.send(
                embed=embed
            )

        except discord.Forbidden:

            print(
                f"⚠️ Grid Guardian cannot send messages "
                f"in the welcome channel of "
                f"{member.guild.name}."
            )

        except discord.HTTPException as error:

            print(
                f"⚠️ Failed to send welcome message: {error}"
            )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(Welcome(bot))