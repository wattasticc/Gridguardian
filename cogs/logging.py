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
CREATE TABLE IF NOT EXISTS settings (
    guild_id INTEGER PRIMARY KEY,
    welcome_channel_id INTEGER,
    log_channel_id INTEGER,
    suggestion_channel_id INTEGER,
    autorole_id INTEGER
)
""")

db.commit()


# =========================================================
# LOGGING COG
# =========================================================

class Logging(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    # =====================================================
    # GET LOG CHANNEL
    # =====================================================

    def get_log_channel(self, guild):

        cursor.execute("""
        SELECT log_channel_id
        FROM settings
        WHERE guild_id=?
        """, (guild.id,))

        result = cursor.fetchone()

        if result is None or result[0] is None:
            return None

        return guild.get_channel(result[0])

    # =====================================================
    # SEND LOG
    # =====================================================

    async def send_log(self, guild, embed):

        channel = self.get_log_channel(guild)

        if channel is None:
            return

        try:
            await channel.send(embed=embed)

        except discord.Forbidden:
            print(
                f"⚠️ Grid Guardian cannot send logs in "
                f"{guild.name}."
            )

        except discord.HTTPException as error:
            print(
                f"⚠️ Failed to send log: {error}"
            )

    # =====================================================
    # MESSAGE DELETED
    # =====================================================

    @commands.Cog.listener()
    async def on_message_delete(self, message):

        if message.guild is None:
            return

        if message.author.bot:
            return

        content = message.content or "*No text content*"

        if len(content) > 1000:
            content = content[:997] + "..."

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            color=discord.Color.red()
        )

        embed.add_field(
            name="👤 Author",
            value=message.author.mention,
            inline=True
        )

        embed.add_field(
            name="📍 Channel",
            value=message.channel.mention,
            inline=True
        )

        embed.add_field(
            name="💬 Content",
            value=content,
            inline=False
        )

        embed.set_footer(
            text=f"User ID: {message.author.id}"
        )

        await self.send_log(
            message.guild,
            embed
        )

    # =====================================================
    # MESSAGE EDITED
    # =====================================================

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):

        if before.guild is None:
            return

        if before.author.bot:
            return

        if before.content == after.content:
            return

        before_content = before.content or "*No text content*"
        after_content = after.content or "*No text content*"

        if len(before_content) > 1000:
            before_content = before_content[:997] + "..."

        if len(after_content) > 1000:
            after_content = after_content[:997] + "..."

        embed = discord.Embed(
            title="✏️ Message Edited",
            color=discord.Color.orange()
        )

        embed.add_field(
            name="👤 Author",
            value=before.author.mention,
            inline=True
        )

        embed.add_field(
            name="📍 Channel",
            value=before.channel.mention,
            inline=True
        )

        embed.add_field(
            name="⬅️ Before",
            value=before_content,
            inline=False
        )

        embed.add_field(
            name="➡️ After",
            value=after_content,
            inline=False
        )

        embed.set_footer(
            text=f"User ID: {before.author.id}"
        )

        await self.send_log(
            before.guild,
            embed
        )

    # =====================================================
    # MEMBER JOIN
    # =====================================================

    @commands.Cog.listener()
    async def on_member_join(self, member):

        embed = discord.Embed(
            title="✅ Member Joined",
            description=(
                f"{member.mention} joined the server."
            ),
            color=discord.Color.green()
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="👥 Member Count",
            value=str(member.guild.member_count),
            inline=True
        )

        embed.add_field(
            name="📅 Account Created",
            value=discord.utils.format_dt(
                member.created_at,
                style="R"
            ),
            inline=True
        )

        embed.set_footer(
            text=f"User ID: {member.id}"
        )

        await self.send_log(
            member.guild,
            embed
        )

    # =====================================================
    # MEMBER LEAVE
    # =====================================================

    @commands.Cog.listener()
    async def on_member_remove(self, member):

        embed = discord.Embed(
            title="👋 Member Left",
            description=(
                f"**{member}** left the server."
            ),
            color=discord.Color.red()
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="👥 Member Count",
            value=str(member.guild.member_count),
            inline=True
        )

        embed.set_footer(
            text=f"User ID: {member.id}"
        )

        await self.send_log(
            member.guild,
            embed
        )

    # =====================================================
    # MEMBER BANNED
    # =====================================================

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):

        embed = discord.Embed(
            title="🔨 Member Banned",
            description=(
                f"**{user}** was banned from the server."
            ),
            color=discord.Color.red()
        )

        embed.set_thumbnail(
            url=user.display_avatar.url
        )

        embed.set_footer(
            text=f"User ID: {user.id}"
        )

        await self.send_log(
            guild,
            embed
        )

    # =====================================================
    # MEMBER UNBANNED
    # =====================================================

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):

        embed = discord.Embed(
            title="🔓 Member Unbanned",
            description=(
                f"**{user}** was unbanned."
            ),
            color=discord.Color.green()
        )

        embed.set_thumbnail(
            url=user.display_avatar.url
        )

        embed.set_footer(
            text=f"User ID: {user.id}"
        )

        await self.send_log(
            guild,
            embed
        )

    # =====================================================
    # ROLE CREATED
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):

        embed = discord.Embed(
            title="🎭 Role Created",
            description=(
                f"Role {role.mention} was created."
            ),
            color=discord.Color.green()
        )

        embed.set_footer(
            text=f"Role ID: {role.id}"
        )

        await self.send_log(
            role.guild,
            embed
        )

    # =====================================================
    # ROLE DELETED
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):

        embed = discord.Embed(
            title="🗑️ Role Deleted",
            description=(
                f"Role **{role.name}** was deleted."
            ),
            color=discord.Color.red()
        )

        embed.set_footer(
            text=f"Role ID: {role.id}"
        )

        await self.send_log(
            role.guild,
            embed
        )

    # =====================================================
    # CHANNEL CREATED
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):

        embed = discord.Embed(
            title="📁 Channel Created",
            description=(
                f"Channel {channel.mention} was created."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="Type",
            value=str(channel.type),
            inline=True
        )

        embed.set_footer(
            text=f"Channel ID: {channel.id}"
        )

        await self.send_log(
            channel.guild,
            embed
        )

    # =====================================================
    # CHANNEL DELETED
    # =====================================================

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):

        embed = discord.Embed(
            title="🗑️ Channel Deleted",
            description=(
                f"Channel **{channel.name}** was deleted."
            ),
            color=discord.Color.red()
        )

        embed.add_field(
            name="Type",
            value=str(channel.type),
            inline=True
        )

        embed.set_footer(
            text=f"Channel ID: {channel.id}"
        )

        await self.send_log(
            channel.guild,
            embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):
    await bot.add_cog(Logging(bot))