import discord
from discord.ext import commands

from cogs.utils.achievement_manager import (
    unlock,
    get_achievements
)


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


class Achievements(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # ==========================================================
    # VIEW ACHIEVEMENTS
    # ==========================================================

    @commands.command()
    async def achievements(
        self,
        ctx,
        member: discord.Member = None
    ):

        if member is None:
            member = ctx.author

        unlocked = get_achievements(member.id)

        embed = discord.Embed(
            title=f"🏅 {member.display_name}'s Achievements",
            color=EMBED_COLOR
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        if not unlocked:

            embed.description = (
                "No achievements unlocked yet.\n\n"
                "Keep chatting, leveling up, completing quests, "
                "and using Grid Guardian!"
            )

        else:

            embed.description = "\n".join(
                f"✅ {achievement}"
                for achievement in unlocked
            )

        embed.set_footer(
            text=f"{len(unlocked)} Achievement(s) Unlocked"
        )

        await ctx.send(
            embed=embed
        )

    # ==========================================================
    # GIVE ACHIEVEMENT
    # ==========================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def giveachievement(
        self,
        ctx,
        member: discord.Member,
        *,
        achievement
    ):

        was_new = unlock(
            member.id,
            achievement
        )

        if not was_new:

            return await ctx.send(
                f"⚠️ {member.mention} already has "
                f"**{achievement}**."
            )

        embed = discord.Embed(
            title="🏅 Achievement Awarded",
            description=(
                f"{member.mention} unlocked\n"
                f"**{achievement}**"
            ),
            color=discord.Color.gold()
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        await ctx.send(
            embed=embed
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Achievements(bot)
    )