import sqlite3

import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS level_rewards (
    guild_id INTEGER NOT NULL,
    level INTEGER NOT NULL,
    role_id INTEGER NOT NULL,

    PRIMARY KEY (guild_id, level)
)
""")


db.commit()


# =========================================================
# LEVEL REWARDS COG
# =========================================================

class LevelRewards(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # =====================================================
    # GET MEMBER LEVEL
    # =====================================================

    def get_member_level(
        self,
        guild_id,
        user_id
    ):

        """
        Checks several common leveling database layouts.

        Your existing leveling.py should already store
        member XP and levels somewhere in gridguardian.db.
        """

        tables_to_check = [
            (
                "levels",
                "guild_id",
                "user_id",
                "level"
            ),
            (
                "leveling",
                "guild_id",
                "user_id",
                "level"
            ),
            (
                "users",
                "guild_id",
                "user_id",
                "level"
            )
        ]


        for (
            table,
            guild_column,
            user_column,
            level_column
        ) in tables_to_check:

            try:

                cursor.execute(
                    f"""
                    SELECT {level_column}
                    FROM {table}
                    WHERE {guild_column}=?
                    AND {user_column}=?
                    """,
                    (
                        guild_id,
                        user_id
                    )
                )


                result = cursor.fetchone()


                if result:

                    return result[0]


            except sqlite3.Error:

                continue


        return None


    # =====================================================
    # CHECK REWARDS
    # =====================================================

    async def check_rewards(
        self,
        member,
        level
    ):

        cursor.execute("""
        SELECT level, role_id
        FROM level_rewards
        WHERE guild_id=?
        AND level<=?
        ORDER BY level ASC
        """, (
            member.guild.id,
            level
        ))


        rewards = cursor.fetchall()


        for reward_level, role_id in rewards:

            role = member.guild.get_role(
                role_id
            )


            if role is None:

                continue


            if role in member.roles:

                continue


            try:

                await member.add_roles(
                    role,
                    reason=(
                        f"Level reward for reaching "
                        f"level {reward_level}"
                    )
                )


            except (
                discord.Forbidden,
                discord.HTTPException
            ):

                pass


    # =====================================================
    # LISTENER
    # =====================================================

    @commands.Cog.listener()
    async def on_message(
        self,
        message
    ):

        if message.author.bot:

            return


        if message.guild is None:

            return


        member = message.author


        level = self.get_member_level(
            message.guild.id,
            member.id
        )


        if level is None:

            return


        await self.check_rewards(
            member,
            level
        )


    # =====================================================
    # ADD LEVEL REWARD
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def setlevelreward(
        self,
        ctx,
        level: int,
        role: discord.Role
    ):

        if level < 1:

            return await ctx.send(
                "❌ The level must be at least 1."
            )


        if role.is_default():

            return await ctx.send(
                "❌ You cannot use the @everyone role."
            )


        if role.managed:

            return await ctx.send(
                "❌ That role is managed by an integration and cannot be used."
            )


        bot_member = ctx.guild.me


        if role >= bot_member.top_role:

            return await ctx.send(
                "❌ That role is higher than or equal to my highest role.\n\n"
                "Move my role above the reward role and try again."
            )


        cursor.execute("""
        INSERT INTO level_rewards(
            guild_id,
            level,
            role_id
        )
        VALUES (?, ?, ?)

        ON CONFLICT(guild_id, level)
        DO UPDATE SET
        role_id=excluded.role_id
        """, (
            ctx.guild.id,
            level,
            role.id
        ))


        db.commit()


        embed = discord.Embed(
            title="🏆 Level Reward Added",
            description=(
                f"Members will receive {role.mention} "
                f"when they reach **Level {level}**."
            ),
            color=discord.Color.green()
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # REMOVE LEVEL REWARD
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def removelevelreward(
        self,
        ctx,
        level: int
    ):

        cursor.execute("""
        SELECT role_id
        FROM level_rewards
        WHERE guild_id=?
        AND level=?
        """, (
            ctx.guild.id,
            level
        ))


        result = cursor.fetchone()


        if result is None:

            return await ctx.send(
                f"❌ There is no reward set for Level {level}."
            )


        cursor.execute("""
        DELETE FROM level_rewards
        WHERE guild_id=?
        AND level=?
        """, (
            ctx.guild.id,
            level
        ))


        db.commit()


        embed = discord.Embed(
            title="🗑️ Level Reward Removed",
            description=(
                f"The reward for **Level {level}** "
                "has been removed."
            ),
            color=discord.Color.red()
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # LIST LEVEL REWARDS
    # =====================================================

    @commands.command()
    async def levelrewards(
        self,
        ctx
    ):

        cursor.execute("""
        SELECT level, role_id
        FROM level_rewards
        WHERE guild_id=?
        ORDER BY level ASC
        """, (
            ctx.guild.id,
        ))


        rewards = cursor.fetchall()


        if not rewards:

            return await ctx.send(
                "❌ No level rewards have been configured yet."
            )


        embed = discord.Embed(
            title="🏆 Level Rewards",
            description=(
                "Members automatically receive these "
                "roles when reaching the required level."
            ),
            color=EMBED_COLOR
        )


        for level, role_id in rewards:

            role = ctx.guild.get_role(
                role_id
            )


            role_text = (
                role.mention
                if role
                else "⚠️ Deleted Role"
            )


            embed.add_field(
                name=f"Level {level}",
                value=role_text,
                inline=False
            )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # CHECK YOUR REWARDS
    # =====================================================

    @commands.command()
    async def checkrewards(
        self,
        ctx
    ):

        member = ctx.author


        level = self.get_member_level(
            ctx.guild.id,
            member.id
        )


        if level is None:

            return await ctx.send(
                "❌ I couldn't find your level data."
            )


        cursor.execute("""
        SELECT level, role_id
        FROM level_rewards
        WHERE guild_id=?
        ORDER BY level ASC
        """, (
            ctx.guild.id,
        ))


        rewards = cursor.fetchall()


        embed = discord.Embed(
            title="🏆 Your Level Rewards",
            description=(
                f"Current Level: **{level}**"
            ),
            color=EMBED_COLOR
        )


        if not rewards:

            embed.add_field(
                name="Rewards",
                value="No rewards have been configured yet.",
                inline=False
            )


        else:

            for reward_level, role_id in rewards:

                role = ctx.guild.get_role(
                    role_id
                )


                if role is None:

                    continue


                if level >= reward_level:

                    status = "✅ Unlocked"

                else:

                    status = (
                        f"🔒 Unlocks at Level {reward_level}"
                    )


                embed.add_field(
                    name=role.name,
                    value=status,
                    inline=False
                )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # GIVE EXISTING REWARDS
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def synclevelrewards(
        self,
        ctx
    ):

        await ctx.send(
            "🔄 Checking level rewards for server members..."
        )


        rewarded_members = 0


        for member in ctx.guild.members:

            if member.bot:

                continue


            level = self.get_member_level(
                ctx.guild.id,
                member.id
            )


            if level is None:

                continue


            before_roles = set(
                role.id
                for role in member.roles
            )


            await self.check_rewards(
                member,
                level
            )


            after_roles = set(
                role.id
                for role in member.roles
            )


            if before_roles != after_roles:

                rewarded_members += 1


        embed = discord.Embed(
            title="🔄 Level Rewards Synced",
            description=(
                f"Updated rewards for **{rewarded_members} member(s)**."
            ),
            color=discord.Color.green()
        )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # ERROR HANDLER
    # =====================================================

    @setlevelreward.error
    @removelevelreward.error
    @synclevelrewards.error
    async def level_rewards_error(
        self,
        ctx,
        error
    ):

        if isinstance(
            error,
            commands.MissingPermissions
        ):

            return await ctx.send(
                "❌ You don't have permission to manage level rewards."
            )


        if isinstance(
            error,
            commands.MissingRequiredArgument
        ):

            return await ctx.send(
                "❌ You're missing a required argument."
            )


        if isinstance(
            error,
            commands.BadArgument
        ):

            return await ctx.send(
                "❌ One of the arguments you entered is invalid."
            )


        raise error


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        LevelRewards(bot)
    )