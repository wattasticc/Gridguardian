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
CREATE TABLE IF NOT EXISTS polls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    creator_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    options TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    closed_at DATETIME
)
""")

db.commit()


# =========================================================
# POLL EMOJIS
# =========================================================

POLL_EMOJIS = [
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "4️⃣",
    "5️⃣",
    "6️⃣",
    "7️⃣",
    "8️⃣",
    "9️⃣",
    "🔟"
]


# =========================================================
# POLLS COG
# =========================================================

class Polls(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # =====================================================
    # CREATE POLL
    # =====================================================

    @commands.command()
    @commands.guild_only()
    async def poll(self, ctx, *, poll_text: str = None):

        """
        Create a poll.

        Example:

        !poll What should we play? | Apex Legends | Fortnite | Minecraft
        """

        if poll_text is None:

            return await ctx.send(
                "❌ Please provide a question and options.\n\n"
                "**Example:**\n"
                "`!poll What should we play? | Apex Legends | Fortnite | Minecraft`"
            )


        # -------------------------------------------------
        # SPLIT QUESTION AND OPTIONS
        # -------------------------------------------------

        parts = [
            part.strip()
            for part in poll_text.split("|")
            if part.strip()
        ]


        if len(parts) < 3:

            return await ctx.send(
                "❌ A poll needs a question and at least "
                "**2 options**.\n\n"
                "**Example:**\n"
                "`!poll Best Legend? | Wattson | Wraith`"
            )


        question = parts[0]

        options = parts[1:]


        # -------------------------------------------------
        # MAX OPTIONS
        # -------------------------------------------------

        if len(options) > 10:

            return await ctx.send(
                "❌ Polls can have a maximum of **10 options**."
            )


        # -------------------------------------------------
        # CHECK DUPLICATES
        # -------------------------------------------------

        normalized_options = [
            option.lower()
            for option in options
        ]

        if len(normalized_options) != len(
            set(normalized_options)
        ):

            return await ctx.send(
                "❌ Your poll contains duplicate options."
            )


        # -------------------------------------------------
        # CREATE EMBED
        # -------------------------------------------------

        embed = discord.Embed(
            title="📊 Poll",
            description=f"**{question}**",
            color=EMBED_COLOR
        )


        option_text = []


        for index, option in enumerate(options):

            emoji = POLL_EMOJIS[index]

            option_text.append(
                f"{emoji} **{option}**"
            )


        embed.add_field(
            name="Options",
            value="\n".join(option_text),
            inline=False
        )


        embed.set_footer(
            text=(
                f"Poll created by {ctx.author.display_name}"
            )
        )


        # -------------------------------------------------
        # SEND POLL
        # -------------------------------------------------

        message = await ctx.send(
            embed=embed
        )


        # -------------------------------------------------
        # ADD REACTIONS
        # -------------------------------------------------

        for index in range(len(options)):

            try:

                await message.add_reaction(
                    POLL_EMOJIS[index]
                )

            except discord.HTTPException:

                pass


        # -------------------------------------------------
        # SAVE TO DATABASE
        # -------------------------------------------------

        cursor.execute("""
        INSERT INTO polls (
            guild_id,
            channel_id,
            message_id,
            creator_id,
            question,
            options,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'open')
        """, (
            ctx.guild.id,
            ctx.channel.id,
            message.id,
            ctx.author.id,
            question,
            " | ".join(options)
        ))

        db.commit()

        poll_id = cursor.lastrowid


        # -------------------------------------------------
        # UPDATE FOOTER WITH POLL ID
        # -------------------------------------------------

        embed.set_footer(
            text=(
                f"Poll ID: #{poll_id} • "
                f"Created by {ctx.author.display_name}"
            )
        )

        try:

            await message.edit(
                embed=embed
            )

        except discord.HTTPException:

            pass


    # =====================================================
    # QUICK POLL
    # =====================================================

    @commands.command()
    @commands.guild_only()
    async def quickpoll(
        self,
        ctx,
        *,
        question: str = None
    ):

        """
        Create a simple Yes / No poll.

        Example:

        !quickpoll Should we play Apex tonight?
        """

        if not question:

            return await ctx.send(
                "❌ Please provide a poll question.\n\n"
                "**Example:**\n"
                "`!quickpoll Should we play Apex tonight?`"
            )


        # -------------------------------------------------
        # CREATE EMBED
        # -------------------------------------------------

        embed = discord.Embed(
            title="⚡ Quick Poll",
            description=f"**{question}**",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="Vote",
            value=(
                "👍 **Yes**\n"
                "👎 **No**"
            ),
            inline=False
        )

        embed.set_footer(
            text=(
                f"Poll created by {ctx.author.display_name}"
            )
        )


        # -------------------------------------------------
        # SEND POLL
        # -------------------------------------------------

        message = await ctx.send(
            embed=embed
        )


        # -------------------------------------------------
        # ADD REACTIONS
        # -------------------------------------------------

        try:

            await message.add_reaction("👍")
            await message.add_reaction("👎")

        except discord.HTTPException:

            pass


        # -------------------------------------------------
        # SAVE TO DATABASE
        # -------------------------------------------------

        cursor.execute("""
        INSERT INTO polls (
            guild_id,
            channel_id,
            message_id,
            creator_id,
            question,
            options,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, 'open')
        """, (
            ctx.guild.id,
            ctx.channel.id,
            message.id,
            ctx.author.id,
            question,
            "Yes | No"
        ))

        db.commit()

        poll_id = cursor.lastrowid


        # -------------------------------------------------
        # UPDATE FOOTER
        # -------------------------------------------------

        embed.set_footer(
            text=(
                f"Poll ID: #{poll_id} • "
                f"Created by {ctx.author.display_name}"
            )
        )

        try:

            await message.edit(
                embed=embed
            )

        except discord.HTTPException:

            pass


    # =====================================================
    # CLOSE POLL
    # =====================================================

    @commands.command()
    @commands.guild_only()
    async def closepoll(
        self,
        ctx,
        poll_id: int = None
    ):

        """
        Close a poll.

        Example:

        !closepoll 1
        """

        if poll_id is None:

            return await ctx.send(
                "❌ Please provide a poll ID.\n\n"
                "**Example:**\n"
                "`!closepoll 1`"
            )


        # -------------------------------------------------
        # FIND POLL
        # -------------------------------------------------

        cursor.execute("""
        SELECT
            guild_id,
            channel_id,
            message_id,
            creator_id,
            question,
            options,
            status
        FROM polls
        WHERE id=?
        """, (
            poll_id,
        ))

        poll = cursor.fetchone()


        if poll is None:

            return await ctx.send(
                "❌ I couldn't find a poll with that ID."
            )


        (
            guild_id,
            channel_id,
            message_id,
            creator_id,
            question,
            options_text,
            status
        ) = poll


        # -------------------------------------------------
        # CHECK SERVER
        # -------------------------------------------------

        if guild_id != ctx.guild.id:

            return await ctx.send(
                "❌ That poll belongs to another server."
            )


        # -------------------------------------------------
        # CHECK STATUS
        # -------------------------------------------------

        if status != "open":

            return await ctx.send(
                "❌ That poll is already closed."
            )


        # -------------------------------------------------
        # CHECK PERMISSIONS
        # -------------------------------------------------

        is_creator = (
            ctx.author.id == creator_id
        )

        is_staff = (
            ctx.author.guild_permissions.manage_guild
        )


        if not is_creator and not is_staff:

            return await ctx.send(
                "❌ Only the poll creator or server staff "
                "can close this poll."
            )


        # -------------------------------------------------
        # GET CHANNEL
        # -------------------------------------------------

        channel = ctx.guild.get_channel(
            channel_id
        )


        if channel is None:

            return await ctx.send(
                "❌ The channel containing this poll "
                "couldn't be found."
            )


        # -------------------------------------------------
        # GET MESSAGE
        # -------------------------------------------------

        try:

            message = await channel.fetch_message(
                message_id
            )

        except discord.NotFound:

            cursor.execute("""
            UPDATE polls
            SET status='closed',
                closed_at=CURRENT_TIMESTAMP
            WHERE id=?
            """, (
                poll_id,
            ))

            db.commit()

            return await ctx.send(
                "⚠️ The poll message was deleted, so the "
                "poll has been marked as closed."
            )

        except discord.HTTPException:

            return await ctx.send(
                "❌ I couldn't access the poll message."
            )


        # -------------------------------------------------
        # GET OPTIONS
        # -------------------------------------------------

        options = [
            option.strip()
            for option in options_text.split("|")
        ]


        # -------------------------------------------------
        # COUNT VOTES
        # -------------------------------------------------

        results = []


        # Check if it is a quick poll.
        if options == ["Yes", "No"]:

            emojis = [
                "👍",
                "👎"
            ]

        else:

            emojis = POLL_EMOJIS[
                :len(options)
            ]


        for index, option in enumerate(options):

            emoji = emojis[index]

            votes = 0


            for reaction in message.reactions:

                if str(reaction.emoji) == emoji:

                    # Subtract the bot's own reaction.
                    votes = max(
                        0,
                        reaction.count - 1
                    )

                    break


            results.append(
                (
                    emoji,
                    option,
                    votes
                )
            )


        # -------------------------------------------------
        # FIND WINNER
        # -------------------------------------------------

        highest_votes = max(
            result[2]
            for result in results
        )

        winners = [
            result
            for result in results
            if result[2] == highest_votes
        ]


        # -------------------------------------------------
        # CREATE RESULTS
        # -------------------------------------------------

        result_lines = []


        for emoji, option, votes in results:

            result_lines.append(
                f"{emoji} **{option}** — "
                f"**{votes} vote(s)**"
            )


        # -------------------------------------------------
        # WINNER TEXT
        # -------------------------------------------------

        if highest_votes == 0:

            winner_text = (
                "No votes were cast."
            )

        elif len(winners) > 1:

            winner_names = ", ".join(
                winner[1]
                for winner in winners
            )

            winner_text = (
                f"🤝 **Tie:** {winner_names}"
            )

        else:

            winner_text = (
                f"🏆 **Winner:** "
                f"{winners[0][1]}"
            )


        # -------------------------------------------------
        # RESULTS EMBED
        # -------------------------------------------------

        embed = discord.Embed(
            title="📊 Poll Closed",
            description=f"**{question}**",
            color=discord.Color.red()
        )

        embed.add_field(
            name="Results",
            value="\n".join(
                result_lines
            ),
            inline=False
        )

        embed.add_field(
            name="Final Result",
            value=winner_text,
            inline=False
        )

        embed.add_field(
            name="🔒 Closed By",
            value=ctx.author.mention,
            inline=True
        )

        embed.set_footer(
            text=f"Poll ID: #{poll_id}"
        )


        # -------------------------------------------------
        # UPDATE POLL MESSAGE
        # -------------------------------------------------

        try:

            await message.edit(
                embed=embed
            )

        except discord.HTTPException:

            pass


        # -------------------------------------------------
        # MARK AS CLOSED
        # -------------------------------------------------

        cursor.execute("""
        UPDATE polls
        SET status='closed',
            closed_at=CURRENT_TIMESTAMP
        WHERE id=?
        """, (
            poll_id,
        ))

        db.commit()


        # -------------------------------------------------
        # CONFIRMATION
        # -------------------------------------------------

        await ctx.send(
            f"🔒 Poll **#{poll_id}** has been closed."
        )


    # =====================================================
    # VIEW OPEN POLLS
    # =====================================================

    @commands.command()
    @commands.guild_only()
    async def polls(self, ctx):

        cursor.execute("""
        SELECT
            id,
            question,
            creator_id
        FROM polls
        WHERE guild_id=?
        AND status='open'
        ORDER BY id DESC
        LIMIT 10
        """, (
            ctx.guild.id,
        ))

        active_polls = cursor.fetchall()


        if not active_polls:

            return await ctx.send(
                "📊 There are currently no open polls."
            )


        embed = discord.Embed(
            title="📊 Active Polls",
            description=(
                "Here are the currently open polls "
                "in this server."
            ),
            color=EMBED_COLOR
        )


        for (
            poll_id,
            question,
            creator_id
        ) in active_polls:

            embed.add_field(
                name=f"#{poll_id} • {question}",
                value=(
                    f"Created by <@{creator_id}>"
                ),
                inline=False
            )


        embed.set_footer(
            text=(
                "Use !closepoll <ID> to close a poll"
            )
        )


        await ctx.send(
            embed=embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Polls(bot)
    )