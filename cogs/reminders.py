import sqlite3
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# =========================================================
# DATABASE
# =========================================================

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER,
    channel_id INTEGER,
    user_id INTEGER NOT NULL,
    reminder_text TEXT NOT NULL,
    remind_at TEXT NOT NULL,
    created_at TEXT NOT NULL
)
""")

db.commit()


# =========================================================
# TIME PARSER
# =========================================================

def parse_time(time_text):
    """
    Supported formats:

    10s = 10 seconds
    30m = 30 minutes
    2h  = 2 hours
    1d  = 1 day
    """

    if len(time_text) < 2:
        return None

    unit = time_text[-1].lower()
    number_text = time_text[:-1]

    try:
        number = int(number_text)

    except ValueError:
        return None

    if number <= 0:
        return None

    if unit == "s":
        return timedelta(seconds=number)

    if unit == "m":
        return timedelta(minutes=number)

    if unit == "h":
        return timedelta(hours=number)

    if unit == "d":
        return timedelta(days=number)

    return None


# =========================================================
# REMINDERS COG
# =========================================================

class Reminders(commands.Cog):

    def __init__(self, bot):

        self.bot = bot
        self.reminder_loop.start()


    def cog_unload(self):

        self.reminder_loop.cancel()


    # =====================================================
    # CHECK REMINDERS
    # =====================================================

    @tasks.loop(seconds=10)
    async def reminder_loop(self):

        now = datetime.now(timezone.utc)

        cursor.execute("""
        SELECT
            id,
            guild_id,
            channel_id,
            user_id,
            reminder_text,
            remind_at
        FROM reminders
        """)

        reminders = cursor.fetchall()


        for reminder in reminders:

            (
                reminder_id,
                guild_id,
                channel_id,
                user_id,
                reminder_text,
                remind_at
            ) = reminder


            # -------------------------------------------------
            # CONVERT REMINDER TIME
            # -------------------------------------------------

            try:

                reminder_time = datetime.fromisoformat(
                    remind_at
                )

            except ValueError:

                # Delete corrupted reminder.
                cursor.execute("""
                DELETE FROM reminders
                WHERE id=?
                """, (
                    reminder_id,
                ))

                db.commit()

                continue


            # -------------------------------------------------
            # MAKE SURE TIMEZONE EXISTS
            # -------------------------------------------------

            if reminder_time.tzinfo is None:

                reminder_time = reminder_time.replace(
                    tzinfo=timezone.utc
                )


            # -------------------------------------------------
            # NOT READY YET
            # -------------------------------------------------

            if now < reminder_time:
                continue


            # -------------------------------------------------
            # GET USER
            # -------------------------------------------------

            user = self.bot.get_user(user_id)

            if user is None:

                try:

                    user = await self.bot.fetch_user(
                        user_id
                    )

                except (
                    discord.NotFound,
                    discord.HTTPException
                ):

                    user = None


            # -------------------------------------------------
            # CREATE REMINDER EMBED
            # -------------------------------------------------

            embed = discord.Embed(
                title="⏰ Reminder!",
                description=reminder_text,
                color=EMBED_COLOR
            )

            embed.add_field(
                name="🆔 Reminder ID",
                value=f"`{reminder_id}`",
                inline=True
            )

            embed.set_footer(
                text="Grid Guardian Reminder System"
            )


            delivered = False


            # -------------------------------------------------
            # TRY DM FIRST
            # -------------------------------------------------

            if user:

                try:

                    await user.send(
                        embed=embed
                    )

                    delivered = True

                except discord.Forbidden:
                    pass

                except discord.HTTPException:
                    pass


            # -------------------------------------------------
            # FALLBACK TO ORIGINAL CHANNEL
            # -------------------------------------------------

            if not delivered:

                channel = self.bot.get_channel(
                    channel_id
                )

                if channel is None:

                    try:

                        channel = await self.bot.fetch_channel(
                            channel_id
                        )

                    except (
                        discord.NotFound,
                        discord.Forbidden,
                        discord.HTTPException
                    ):

                        channel = None


                if channel:

                    try:

                        await channel.send(
                            content=f"<@{user_id}>",
                            embed=embed
                        )

                        delivered = True

                    except (
                        discord.Forbidden,
                        discord.HTTPException
                    ):

                        pass


            # -------------------------------------------------
            # DELETE COMPLETED REMINDER
            # -------------------------------------------------

            cursor.execute("""
            DELETE FROM reminders
            WHERE id=?
            """, (
                reminder_id,
            ))

            db.commit()


    # =====================================================
    # WAIT UNTIL BOT IS READY
    # =====================================================

    @reminder_loop.before_loop
    async def before_reminder_loop(self):

        await self.bot.wait_until_ready()


    # =====================================================
    # CREATE REMINDER
    # =====================================================

    @commands.command()
    async def remind(
        self,
        ctx,
        time_text: str,
        *,
        reminder_text: str
    ):

        """
        Examples:

        !remind 10s Test reminder
        !remind 30m Practice Apex
        !remind 2h Upload a video
        !remind 1d Check Discord
        """

        duration = parse_time(
            time_text
        )

        if duration is None:

            return await ctx.send(
                "❌ Invalid time format.\n\n"
                "**Examples:**\n"
                "`10s` = 10 seconds\n"
                "`30m` = 30 minutes\n"
                "`2h` = 2 hours\n"
                "`1d` = 1 day"
            )


        # -------------------------------------------------
        # CREATE REMINDER TIME
        # -------------------------------------------------

        now = datetime.now(
            timezone.utc
        )

        remind_at = now + duration


        # -------------------------------------------------
        # SAVE REMINDER
        # -------------------------------------------------

        cursor.execute("""
        INSERT INTO reminders (
            guild_id,
            channel_id,
            user_id,
            reminder_text,
            remind_at,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            ctx.guild.id if ctx.guild else None,
            ctx.channel.id,
            ctx.author.id,
            reminder_text,
            remind_at.isoformat(),
            now.isoformat()
        ))

        db.commit()

        reminder_id = cursor.lastrowid


        # -------------------------------------------------
        # CONFIRMATION EMBED
        # -------------------------------------------------

        embed = discord.Embed(
            title="⏰ Reminder Created",
            description=(
                f"I'll remind you in **{time_text}**."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="📝 Reminder",
            value=reminder_text,
            inline=False
        )

        embed.add_field(
            name="🆔 Reminder ID",
            value=f"`{reminder_id}`",
            inline=True
        )

        embed.add_field(
            name="📅 Reminder Time",
            value=(
                f"<t:{int(remind_at.timestamp())}:R>"
            ),
            inline=True
        )

        embed.set_footer(
            text="Grid Guardian Reminder System"
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # VIEW ACTIVE REMINDERS
    # =====================================================

    @commands.command()
    async def reminders(self, ctx):

        cursor.execute("""
        SELECT
            id,
            reminder_text,
            remind_at
        FROM reminders
        WHERE user_id=?
        ORDER BY remind_at ASC
        """, (
            ctx.author.id,
        ))

        user_reminders = cursor.fetchall()


        if not user_reminders:

            return await ctx.send(
                "⏰ You don't have any active reminders."
            )


        embed = discord.Embed(
            title="⏰ Your Active Reminders",
            color=EMBED_COLOR
        )


        for (
            reminder_id,
            reminder_text,
            remind_at
        ) in user_reminders[:10]:

            try:

                reminder_time = datetime.fromisoformat(
                    remind_at
                )

                timestamp = int(
                    reminder_time.timestamp()
                )

                time_display = (
                    f"<t:{timestamp}:R>"
                )

            except ValueError:

                time_display = "Unknown"


            # Limit text length.
            shortened_text = reminder_text[:150]


            embed.add_field(
                name=(
                    f"#{reminder_id} • "
                    f"{time_display}"
                ),
                value=shortened_text,
                inline=False
            )


        if len(user_reminders) > 10:

            embed.set_footer(
                text=(
                    f"Showing 10 of "
                    f"{len(user_reminders)} reminders"
                )
            )

        else:

            embed.set_footer(
                text=(
                    f"{len(user_reminders)} active "
                    f"reminder(s)"
                )
            )


        await ctx.send(
            embed=embed
        )


    # =====================================================
    # CANCEL REMINDER
    # =====================================================

    @commands.command()
    async def cancelreminder(
        self,
        ctx,
        reminder_id: int
    ):

        cursor.execute("""
        SELECT reminder_text
        FROM reminders
        WHERE id=?
        AND user_id=?
        """, (
            reminder_id,
            ctx.author.id
        ))

        reminder = cursor.fetchone()


        if reminder is None:

            return await ctx.send(
                "❌ I couldn't find one of your "
                "reminders with that ID."
            )


        # -------------------------------------------------
        # DELETE REMINDER
        # -------------------------------------------------

        cursor.execute("""
        DELETE FROM reminders
        WHERE id=?
        AND user_id=?
        """, (
            reminder_id,
            ctx.author.id
        ))

        db.commit()


        # -------------------------------------------------
        # CONFIRMATION
        # -------------------------------------------------

        embed = discord.Embed(
            title="🗑️ Reminder Cancelled",
            description=(
                f"Reminder `#{reminder_id}` has been "
                f"cancelled."
            ),
            color=discord.Color.red()
        )

        embed.add_field(
            name="📝 Reminder",
            value=reminder[0],
            inline=False
        )

        await ctx.send(
            embed=embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Reminders(bot)
    )