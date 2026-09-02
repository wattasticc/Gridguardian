import json
import os
from datetime import datetime

import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

BACKUP_FOLDER = "backups"


class Backup(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

        # Make sure the backup folder exists
        os.makedirs(BACKUP_FOLDER, exist_ok=True)

    # ==========================================================
    # CREATE BACKUP
    # ==========================================================

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def backup(self, ctx):

        await ctx.send("⏳ Creating server backup...")

        guild = ctx.guild

        data = {
            "server_name": guild.name,
            "server_id": guild.id,
            "created_at": datetime.utcnow().isoformat(),

            "roles": [],
            "categories": [],
            "channels": []
        }

        # ======================================================
        # SAVE ROLES
        # ======================================================

        for role in guild.roles:

            # Never save @everyone
            if role.is_default():
                continue

            # Skip managed/integration roles
            if role.managed:
                continue

            data["roles"].append({
                "name": role.name,
                "color": role.color.value,
                "permissions": role.permissions.value,
                "hoist": role.hoist,
                "mentionable": role.mentionable,
                "position": role.position
            })

        # ======================================================
        # SAVE CATEGORIES
        # ======================================================

        for category in guild.categories:

            overwrites = []

            for target, overwrite in category.overwrites.items():

                if isinstance(target, discord.Role):

                    overwrites.append({
                        "type": "role",
                        "name": target.name,
                        "allow": overwrite.pair()[0].value,
                        "deny": overwrite.pair()[1].value
                    })

            data["categories"].append({
                "name": category.name,
                "position": category.position,
                "overwrites": overwrites
            })

        # ======================================================
        # SAVE CHANNELS
        # ======================================================

        for channel in guild.channels:

            if isinstance(channel, discord.CategoryChannel):
                continue

            channel_data = {
                "name": channel.name,
                "position": channel.position,
                "category": (
                    channel.category.name
                    if channel.category
                    else None
                ),
                "type": None,
                "overwrites": []
            }

            # --------------------------------------------------
            # CHANNEL TYPE
            # --------------------------------------------------

            if isinstance(channel, discord.TextChannel):
                channel_data["type"] = "text"

            elif isinstance(channel, discord.VoiceChannel):
                channel_data["type"] = "voice"

            elif isinstance(channel, discord.StageChannel):
                channel_data["type"] = "stage"

            else:
                continue

            # --------------------------------------------------
            # PERMISSION OVERWRITES
            # --------------------------------------------------

            for target, overwrite in channel.overwrites.items():

                if isinstance(target, discord.Role):

                    channel_data["overwrites"].append({
                        "type": "role",
                        "name": target.name,
                        "allow": overwrite.pair()[0].value,
                        "deny": overwrite.pair()[1].value
                    })

            # --------------------------------------------------
            # EXTRA CHANNEL SETTINGS
            # --------------------------------------------------

            if isinstance(channel, discord.TextChannel):

                channel_data["topic"] = channel.topic
                channel_data["slowmode_delay"] = channel.slowmode_delay

            if isinstance(channel, discord.VoiceChannel):

                channel_data["bitrate"] = channel.bitrate
                channel_data["user_limit"] = channel.user_limit

            data["channels"].append(channel_data)

        # ======================================================
        # SAVE FILE
        # ======================================================

        timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")

        filename = (
            f"{guild.id}_{timestamp}.json"
        )

        filepath = os.path.join(
            BACKUP_FOLDER,
            filename
        )

        with open(filepath, "w", encoding="utf-8") as file:

            json.dump(
                data,
                file,
                indent=4
            )

        # ======================================================
        # CONFIRMATION
        # ======================================================

        embed = discord.Embed(
            title="✅ Backup Created",
            description=(
                f"Successfully backed up **{guild.name}**."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="🎭 Roles",
            value=str(len(data["roles"])),
            inline=True
        )

        embed.add_field(
            name="📁 Categories",
            value=str(len(data["categories"])),
            inline=True
        )

        embed.add_field(
            name="💬 Channels",
            value=str(len(data["channels"])),
            inline=True
        )

        embed.set_footer(
            text=f"Backup ID: {timestamp}"
        )

        await ctx.send(
            embed=embed,
            file=discord.File(filepath)
        )

    # ==========================================================
    # LIST BACKUPS
    # ==========================================================

    @commands.command(name="backups")
    @commands.has_permissions(administrator=True)
    async def backups(self, ctx):

        guild = ctx.guild

        files = []

        if not os.path.exists(BACKUP_FOLDER):
            return await ctx.send(
                "📦 There are no backups yet."
            )

        for filename in os.listdir(BACKUP_FOLDER):

            if not filename.endswith(".json"):
                continue

            if filename.startswith(f"{guild.id}_"):
                files.append(filename)

        if not files:
            return await ctx.send(
                "📦 This server has no backups."
            )

        files.sort(reverse=True)

        embed = discord.Embed(
            title="📦 Server Backups",
            description=(
                f"Backups for **{guild.name}**"
            ),
            color=EMBED_COLOR
        )

        for index, filename in enumerate(files[:10], start=1):

            backup_id = filename[
                len(str(guild.id)) + 1:
                -5
            ]

            embed.add_field(
                name=f"{index}. {backup_id}",
                value=f"`{filename}`",
                inline=False
            )

        if len(files) > 10:

            embed.set_footer(
                text=f"Showing 10 of {len(files)} backups."
            )

        await ctx.send(embed=embed)

    # ==========================================================
    # DELETE BACKUP
    # ==========================================================

    @commands.command(name="deletebackup")
    @commands.has_permissions(administrator=True)
    async def deletebackup(self, ctx, backup_id: str):

        guild = ctx.guild

        filename = (
            f"{guild.id}_{backup_id}.json"
        )

        filepath = os.path.join(
            BACKUP_FOLDER,
            filename
        )

        if not os.path.exists(filepath):

            return await ctx.send(
                "❌ I couldn't find that backup."
            )

        os.remove(filepath)

        await ctx.send(
            f"🗑️ Backup `{backup_id}` has been deleted."
        )

    # ==========================================================
    # RESTORE BACKUP
    # ==========================================================

    @commands.command(name="restore")
    @commands.has_permissions(administrator=True)
    async def restore(self, ctx, backup_id: str):

        guild = ctx.guild

        filename = (
            f"{guild.id}_{backup_id}.json"
        )

        filepath = os.path.join(
            BACKUP_FOLDER,
            filename
        )

        if not os.path.exists(filepath):

            return await ctx.send(
                "❌ I couldn't find that backup."
            )

        # ------------------------------------------------------
        # LOAD BACKUP
        # ------------------------------------------------------

        try:

            with open(
                filepath,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

        except Exception as error:

            return await ctx.send(
                f"❌ Failed to read the backup.\n```{error}```"
            )

        await ctx.send(
            "⏳ Restoring server structure...\n"
            "This may take a moment."
        )

        # ======================================================
        # RESTORE ROLES
        # ======================================================

        role_map = {}

        for role_data in data.get("roles", []):

            existing_role = discord.utils.get(
                guild.roles,
                name=role_data["name"]
            )

            if existing_role:

                role_map[
                    role_data["name"]
                ] = existing_role

                continue

            try:

                new_role = await guild.create_role(
                    name=role_data["name"],
                    colour=discord.Colour(
                        role_data["color"]
                    ),
                    permissions=discord.Permissions(
                        role_data["permissions"]
                    ),
                    hoist=role_data["hoist"],
                    mentionable=role_data["mentionable"],
                    reason="Grid Guardian backup restore"
                )

                role_map[
                    role_data["name"]
                ] = new_role

            except discord.Forbidden:
                continue

        # ======================================================
        # RESTORE CATEGORIES
        # ======================================================

        category_map = {}

        for category_data in data.get(
            "categories",
            []
        ):

            existing_category = discord.utils.get(
                guild.categories,
                name=category_data["name"]
            )

            if existing_category:

                category_map[
                    category_data["name"]
                ] = existing_category

                continue

            overwrites = {}

            for overwrite_data in category_data.get(
                "overwrites",
                []
            ):

                if overwrite_data["type"] != "role":
                    continue

                role = role_map.get(
                    overwrite_data["name"]
                )

                if role is None:
                    continue

                allow = discord.Permissions(
                    overwrite_data["allow"]
                )

                deny = discord.Permissions(
                    overwrite_data["deny"]
                )

                overwrites[role] = discord.PermissionOverwrite.from_pair(
                    allow,
                    deny
                )

            try:

                category = await guild.create_category(
                    name=category_data["name"],
                    overwrites=overwrites,
                    reason="Grid Guardian backup restore"
                )

                category_map[
                    category_data["name"]
                ] = category

            except discord.Forbidden:
                continue

        # ======================================================
        # RESTORE CHANNELS
        # ======================================================

        restored_channels = 0

        for channel_data in data.get(
            "channels",
            []
        ):

            existing_channel = discord.utils.get(
                guild.channels,
                name=channel_data["name"]
            )

            if existing_channel:
                continue

            category = None

            if channel_data["category"]:

                category = category_map.get(
                    channel_data["category"]
                )

                if category is None:

                    category = discord.utils.get(
                        guild.categories,
                        name=channel_data["category"]
                    )

            # --------------------------------------------------
            # PERMISSION OVERWRITES
            # --------------------------------------------------

            overwrites = {}

            for overwrite_data in channel_data.get(
                "overwrites",
                []
            ):

                if overwrite_data["type"] != "role":
                    continue

                role = role_map.get(
                    overwrite_data["name"]
                )

                if role is None:
                    continue

                allow = discord.Permissions(
                    overwrite_data["allow"]
                )

                deny = discord.Permissions(
                    overwrite_data["deny"]
                )

                overwrites[role] = discord.PermissionOverwrite.from_pair(
                    allow,
                    deny
                )

            # --------------------------------------------------
            # CREATE TEXT CHANNEL
            # --------------------------------------------------

            try:

                if channel_data["type"] == "text":

                    new_channel = await guild.create_text_channel(
                        channel_data["name"],
                        category=category,
                        overwrites=overwrites,
                        topic=channel_data.get("topic"),
                        slowmode_delay=channel_data.get(
                            "slowmode_delay",
                            0
                        ),
                        reason="Grid Guardian backup restore"
                    )

                # --------------------------------------------------
                # CREATE VOICE CHANNEL
                # --------------------------------------------------

                elif channel_data["type"] == "voice":

                    new_channel = await guild.create_voice_channel(
                        channel_data["name"],
                        category=category,
                        overwrites=overwrites,
                        bitrate=channel_data.get(
                            "bitrate"
                        ),
                        user_limit=channel_data.get(
                            "user_limit",
                            0
                        ),
                        reason="Grid Guardian backup restore"
                    )

                # --------------------------------------------------
                # CREATE STAGE CHANNEL
                # --------------------------------------------------

                elif channel_data["type"] == "stage":

                    new_channel = await guild.create_stage_channel(
                        channel_data["name"],
                        category=category,
                        overwrites=overwrites,
                        reason="Grid Guardian backup restore"
                    )

                else:
                    continue

                restored_channels += 1

            except discord.Forbidden:
                continue

            except discord.HTTPException:
                continue

        # ======================================================
        # FINISHED
        # ======================================================

        embed = discord.Embed(
            title="✅ Backup Restored",
            description=(
                f"Backup **{backup_id}** has been restored."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="🎭 Roles",
            value=str(
                len(data.get("roles", []))
            ),
            inline=True
        )

        embed.add_field(
            name="📁 Categories",
            value=str(
                len(data.get("categories", []))
            ),
            inline=True
        )

        embed.add_field(
            name="💬 Channels Restored",
            value=str(restored_channels),
            inline=True
        )

        embed.set_footer(
            text="Existing channels and roles were not duplicated."
        )

        await ctx.send(embed=embed)


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):
    await bot.add_cog(Backup(bot))