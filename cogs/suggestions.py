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
# SETTINGS TABLE
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER PRIMARY KEY,
    welcome_channel_id INTEGER,
    log_channel_id INTEGER,
    suggestion_channel_id INTEGER,
    autorole_id INTEGER
)
""")


# =========================================================
# SUGGESTIONS TABLE
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    message_id INTEGER,
    suggestion TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    staff_id INTEGER,
    staff_reason TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")


# =========================================================
# SUGGESTION VOTES TABLE
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS suggestion_votes (
    suggestion_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    vote INTEGER NOT NULL,
    PRIMARY KEY (suggestion_id, user_id)
)
""")


db.commit()


# =========================================================
# SUGGESTION VIEW
# =========================================================

class SuggestionView(discord.ui.View):

    def __init__(self, suggestion_id):
        super().__init__(timeout=None)

        self.suggestion_id = suggestion_id

    # =====================================================
    # UPVOTE
    # =====================================================

    @discord.ui.button(
        label="0",
        emoji="👍",
        style=discord.ButtonStyle.success,
        custom_id="suggestion_upvote"
    )
    async def upvote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.process_vote(
            interaction,
            1
        )

    # =====================================================
    # DOWNVOTE
    # =====================================================

    @discord.ui.button(
        label="0",
        emoji="👎",
        style=discord.ButtonStyle.danger,
        custom_id="suggestion_downvote"
    )
    async def downvote(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        await self.process_vote(
            interaction,
            -1
        )

    # =====================================================
    # VOTE PROCESSING
    # =====================================================

    async def process_vote(
        self,
        interaction,
        vote
    ):

        cursor.execute("""
        SELECT status
        FROM suggestions
        WHERE id=?
        """, (self.suggestion_id,))

        suggestion = cursor.fetchone()

        if suggestion is None:

            return await interaction.response.send_message(
                "❌ This suggestion no longer exists.",
                ephemeral=True
            )

        status = suggestion[0]

        if status != "pending":

            return await interaction.response.send_message(
                "❌ Voting is closed for this suggestion.",
                ephemeral=True
            )

        # -------------------------------------------------
        # CHECK EXISTING VOTE
        # -------------------------------------------------

        cursor.execute("""
        SELECT vote
        FROM suggestion_votes
        WHERE suggestion_id=?
        AND user_id=?
        """, (
            self.suggestion_id,
            interaction.user.id
        ))

        existing_vote = cursor.fetchone()

        if existing_vote:

            if existing_vote[0] == vote:

                return await interaction.response.send_message(
                    "❌ You already voted this way.",
                    ephemeral=True
                )

            # Change vote

            cursor.execute("""
            UPDATE suggestion_votes
            SET vote=?
            WHERE suggestion_id=?
            AND user_id=?
            """, (
                vote,
                self.suggestion_id,
                interaction.user.id
            ))

            message = "🔄 Your vote has been changed."

        else:

            cursor.execute("""
            INSERT INTO suggestion_votes(
                suggestion_id,
                user_id,
                vote
            )
            VALUES (?, ?, ?)
            """, (
                self.suggestion_id,
                interaction.user.id,
                vote
            ))

            message = "✅ Your vote has been counted."

        db.commit()

        # -------------------------------------------------
        # UPDATE BUTTON COUNTS
        # -------------------------------------------------

        await self.update_vote_counts(
            interaction.message
        )

        await interaction.response.send_message(
            message,
            ephemeral=True
        )

    # =====================================================
    # UPDATE VOTE COUNTS
    # =====================================================

    async def update_vote_counts(self, message):

        cursor.execute("""
        SELECT COUNT(*)
        FROM suggestion_votes
        WHERE suggestion_id=?
        AND vote=1
        """, (self.suggestion_id,))

        upvotes = cursor.fetchone()[0]

        cursor.execute("""
        SELECT COUNT(*)
        FROM suggestion_votes
        WHERE suggestion_id=?
        AND vote=-1
        """, (self.suggestion_id,))

        downvotes = cursor.fetchone()[0]

        self.children[0].label = str(upvotes)
        self.children[1].label = str(downvotes)

        try:
            await message.edit(
                view=self
            )
        except discord.HTTPException:
            pass


# =========================================================
# SUGGESTIONS COG
# =========================================================

class Suggestions(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # GET SUGGESTION CHANNEL
    # =====================================================

    def get_suggestion_channel(self, guild):

        cursor.execute("""
        SELECT suggestion_channel_id
        FROM settings
        WHERE guild_id=?
        """, (guild.id,))

        result = cursor.fetchone()

        if result is None:
            return None

        if result[0] is None:
            return None

        return guild.get_channel(result[0])

    # =====================================================
    # SUGGEST
    # =====================================================

    @commands.command()
    async def suggest(
        self,
        ctx,
        *,
        suggestion
    ):

        channel = self.get_suggestion_channel(
            ctx.guild
        )

        if channel is None:

            return await ctx.send(
                "❌ No suggestion channel has been configured.\n"
                "Use `!setsuggestions #channel` first."
            )

        # -------------------------------------------------
        # CREATE DATABASE ENTRY
        # -------------------------------------------------

        cursor.execute("""
        INSERT INTO suggestions(
            guild_id,
            user_id,
            suggestion,
            status
        )
        VALUES (?, ?, ?, ?)
        """, (
            ctx.guild.id,
            ctx.author.id,
            suggestion,
            "pending"
        ))

        db.commit()

        suggestion_id = cursor.lastrowid

        # -------------------------------------------------
        # CREATE EMBED
        # -------------------------------------------------

        embed = discord.Embed(
            title=f"💡 Suggestion #{suggestion_id}",
            description=suggestion,
            color=EMBED_COLOR,
            timestamp=discord.utils.utcnow()
        )

        embed.set_author(
            name=ctx.author.display_name,
            icon_url=ctx.author.display_avatar.url
        )

        embed.add_field(
            name="📊 Status",
            value="🟡 Pending Review",
            inline=True
        )

        embed.add_field(
            name="🆔 Suggestion ID",
            value=f"#{suggestion_id}",
            inline=True
        )

        embed.set_footer(
            text=f"Suggested by {ctx.author}"
        )

        # -------------------------------------------------
        # SEND SUGGESTION
        # -------------------------------------------------

        view = SuggestionView(
            suggestion_id
        )

        message = await channel.send(
            embed=embed,
            view=view
        )

        # -------------------------------------------------
        # SAVE MESSAGE ID
        # -------------------------------------------------

        cursor.execute("""
        UPDATE suggestions
        SET message_id=?
        WHERE id=?
        """, (
            message.id,
            suggestion_id
        ))

        db.commit()

        # -------------------------------------------------
        # DELETE COMMAND
        # -------------------------------------------------

        try:
            await ctx.message.delete()
        except discord.Forbidden:
            pass

        # -------------------------------------------------
        # CONFIRMATION
        # -------------------------------------------------

        confirmation = discord.Embed(
            title="✅ Suggestion Submitted",
            description=(
                f"Your suggestion was submitted as "
                f"**Suggestion #{suggestion_id}**."
            ),
            color=discord.Color.green()
        )

        try:

            await ctx.author.send(
                embed=confirmation
            )

        except discord.Forbidden:

            await ctx.send(
                embed=confirmation,
                delete_after=5
            )

    # =====================================================
    # VIEW SUGGESTION
    # =====================================================

    @commands.command()
    async def suggestion(
        self,
        ctx,
        suggestion_id: int
    ):

        cursor.execute("""
        SELECT
            user_id,
            suggestion,
            status,
            staff_id,
            staff_reason,
            created_at
        FROM suggestions
        WHERE id=?
        AND guild_id=?
        """, (
            suggestion_id,
            ctx.guild.id
        ))

        data = cursor.fetchone()

        if data is None:

            return await ctx.send(
                "❌ Suggestion not found."
            )

        (
            user_id,
            suggestion_text,
            status,
            staff_id,
            staff_reason,
            created_at
        ) = data

        member = ctx.guild.get_member(
            user_id
        )

        username = (
            member.display_name
            if member
            else f"User {user_id}"
        )

        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        if status == "pending":
            status_text = "🟡 Pending Review"

        elif status == "approved":
            status_text = "🟢 Approved"

        elif status == "denied":
            status_text = "🔴 Denied"

        else:
            status_text = "⚪ Unknown"

        embed = discord.Embed(
            title=f"💡 Suggestion #{suggestion_id}",
            description=suggestion_text,
            color=EMBED_COLOR
        )

        embed.add_field(
            name="👤 Submitted By",
            value=username,
            inline=True
        )

        embed.add_field(
            name="📊 Status",
            value=status_text,
            inline=True
        )

        if staff_reason:

            embed.add_field(
                name="📝 Staff Reason",
                value=staff_reason,
                inline=False
            )

        embed.set_footer(
            text=f"Suggestion #{suggestion_id}"
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # APPROVE
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def approvesuggestion(
        self,
        ctx,
        suggestion_id: int,
        *,
        reason="No reason provided"
    ):

        await self.change_status(
            ctx,
            suggestion_id,
            "approved",
            reason
        )

    # =====================================================
    # DENY
    # =====================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def denysuggestion(
        self,
        ctx,
        suggestion_id: int,
        *,
        reason="No reason provided"
    ):

        await self.change_status(
            ctx,
            suggestion_id,
            "denied",
            reason
        )

    # =====================================================
    # CHANGE STATUS
    # =====================================================

    async def change_status(
        self,
        ctx,
        suggestion_id,
        status,
        reason
    ):

        cursor.execute("""
        SELECT message_id
        FROM suggestions
        WHERE id=?
        AND guild_id=?
        """, (
            suggestion_id,
            ctx.guild.id
        ))

        data = cursor.fetchone()

        if data is None:

            return await ctx.send(
                "❌ Suggestion not found."
            )

        message_id = data[0]

        cursor.execute("""
        UPDATE suggestions
        SET status=?,
            staff_id=?,
            staff_reason=?
        WHERE id=?
        AND guild_id=?
        """, (
            status,
            ctx.author.id,
            reason,
            suggestion_id,
            ctx.guild.id
        ))

        db.commit()

        # -------------------------------------------------
        # GET ORIGINAL MESSAGE
        # -------------------------------------------------

        channel = self.get_suggestion_channel(
            ctx.guild
        )

        if channel and message_id:

            try:

                message = await channel.fetch_message(
                    message_id
                )

                embed = message.embeds[0]

                if status == "approved":

                    embed.color = discord.Color.green()

                    status_text = "🟢 Approved"

                else:

                    embed.color = discord.Color.red()

                    status_text = "🔴 Denied"

                # Remove old status fields
                for field in embed.fields:

                    if field.name == "📊 Status":

                        embed.remove_footer()

                # Rebuild status information
                embed.clear_fields()

                embed.add_field(
                    name="📊 Status",
                    value=status_text,
                    inline=True
                )

                embed.add_field(
                    name="📝 Staff Reason",
                    value=reason,
                    inline=False
                )

                embed.set_footer(
                    text=(
                        f"Reviewed by "
                        f"{ctx.author.display_name}"
                    )
                )

                await message.edit(
                    embed=embed,
                    view=None
                )

            except discord.NotFound:
                pass

            except discord.HTTPException:
                pass

        # -------------------------------------------------
        # CONFIRM
        # -------------------------------------------------

        if status == "approved":

            title = "✅ Suggestion Approved"
            color = discord.Color.green()

        else:

            title = "❌ Suggestion Denied"
            color = discord.Color.red()

        embed = discord.Embed(
            title=title,
            description=(
                f"Suggestion **#{suggestion_id}** "
                f"has been updated."
            ),
            color=color
        )

        embed.add_field(
            name="📝 Reason",
            value=reason,
            inline=False
        )

        await ctx.send(
            embed=embed
        )

    # =====================================================
    # SUGGESTION STATS
    # =====================================================

    @commands.command()
    async def suggestionstats(
        self,
        ctx
    ):

        cursor.execute("""
        SELECT COUNT(*)
        FROM suggestions
        WHERE guild_id=?
        """, (ctx.guild.id,))

        total = cursor.fetchone()[0]

        cursor.execute("""
        SELECT COUNT(*)
        FROM suggestions
        WHERE guild_id=?
        AND status='pending'
        """, (ctx.guild.id,))

        pending = cursor.fetchone()[0]

        cursor.execute("""
        SELECT COUNT(*)
        FROM suggestions
        WHERE guild_id=?
        AND status='approved'
        """, (ctx.guild.id,))

        approved = cursor.fetchone()[0]

        cursor.execute("""
        SELECT COUNT(*)
        FROM suggestions
        WHERE guild_id=?
        AND status='denied'
        """, (ctx.guild.id,))

        denied = cursor.fetchone()[0]

        embed = discord.Embed(
            title="💡 Suggestion Statistics",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="📋 Total",
            value=total,
            inline=True
        )

        embed.add_field(
            name="🟡 Pending",
            value=pending,
            inline=True
        )

        embed.add_field(
            name="🟢 Approved",
            value=approved,
            inline=True
        )

        embed.add_field(
            name="🔴 Denied",
            value=denied,
            inline=True
        )

        await ctx.send(
            embed=embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(Suggestions(bot))