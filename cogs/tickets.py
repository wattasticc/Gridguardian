import io
import sqlite3
from datetime import datetime, timezone

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
    autorole_id INTEGER,
    ticket_category_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    department TEXT DEFAULT 'General Support',
    status TEXT DEFAULT 'open',
    claimed_by INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    closed_at DATETIME
)
""")

db.commit()


# =========================================================
# DATABASE COMPATIBILITY
# =========================================================

def ensure_column(table, column, definition):

    cursor.execute(f"PRAGMA table_info({table})")

    columns = [
        row[1]
        for row in cursor.fetchall()
    ]

    if column not in columns:

        cursor.execute(
            f"ALTER TABLE {table} "
            f"ADD COLUMN {column} {definition}"
        )

        db.commit()


ensure_column(
    "tickets",
    "department",
    "TEXT DEFAULT 'General Support'"
)

ensure_column(
    "tickets",
    "claimed_by",
    "INTEGER"
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_ticket_category(guild):

    cursor.execute("""
    SELECT ticket_category_id
    FROM settings
    WHERE guild_id=?
    """, (guild.id,))

    result = cursor.fetchone()

    if result and result[0]:

        category = guild.get_channel(
            result[0]
        )

        if isinstance(
            category,
            discord.CategoryChannel
        ):
            return category

    return None


def get_open_ticket(
    guild_id,
    user_id
):

    cursor.execute("""
    SELECT id, channel_id
    FROM tickets
    WHERE guild_id=?
    AND user_id=?
    AND status='open'
    """, (
        guild_id,
        user_id
    ))

    return cursor.fetchone()


def get_ticket(channel_id):

    cursor.execute("""
    SELECT
        id,
        guild_id,
        user_id,
        channel_id,
        department,
        status,
        claimed_by,
        created_at,
        closed_at
    FROM tickets
    WHERE channel_id=?
    """, (channel_id,))

    return cursor.fetchone()


def is_staff(member):

    return (
        member.guild_permissions.manage_guild
        or member.guild_permissions.administrator
    )


async def send_ticket_log(
    guild,
    title,
    description,
    color
):

    cursor.execute("""
    SELECT log_channel_id
    FROM settings
    WHERE guild_id=?
    """, (guild.id,))

    result = cursor.fetchone()

    if not result or not result[0]:
        return

    log_channel = guild.get_channel(
        result[0]
    )

    if not isinstance(
        log_channel,
        discord.TextChannel
    ):
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.now(timezone.utc)
    )

    try:

        await log_channel.send(
            embed=embed
        )

    except discord.HTTPException:
        pass


async def create_transcript(channel):

    lines = []

    async for message in channel.history(
        limit=None,
        oldest_first=True
    ):

        timestamp = message.created_at.strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

        author = (
            f"{message.author} "
            f"({message.author.id})"
        )

        content = message.content

        if not content:
            content = "[No text content]"

        if message.attachments:

            attachment_urls = ", ".join(
                attachment.url
                for attachment
                in message.attachments
            )

            content += (
                "\nAttachments: "
                f"{attachment_urls}"
            )

        lines.append(
            f"[{timestamp}] "
            f"{author}: "
            f"{content}"
        )

    if not lines:

        lines.append(
            "No messages found in this ticket."
        )

    return "\n".join(lines)


# =========================================================
# TICKET ACTION VIEW
# =========================================================

class TicketActionView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)


    # =====================================================
    # CLAIM
    # =====================================================

    @discord.ui.button(
        label="Claim",
        emoji="👤",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_claim"
    )
    async def claim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):

            return await interaction.response.send_message(
                "❌ Only staff members can claim tickets.",
                ephemeral=True
            )

        ticket = get_ticket(
            interaction.channel.id
        )

        if ticket is None:

            return await interaction.response.send_message(
                "❌ This isn't a registered ticket.",
                ephemeral=True
            )

        (
            ticket_id,
            guild_id,
            user_id,
            channel_id,
            department,
            status,
            claimed_by,
            created_at,
            closed_at
        ) = ticket

        if status != "open":

            return await interaction.response.send_message(
                "❌ This ticket is closed.",
                ephemeral=True
            )

        if claimed_by:

            member = interaction.guild.get_member(
                claimed_by
            )

            if member:

                return await interaction.response.send_message(
                    (
                        "❌ This ticket is already "
                        f"claimed by {member.mention}."
                    ),
                    ephemeral=True
                )

        cursor.execute("""
        UPDATE tickets
        SET claimed_by=?
        WHERE channel_id=?
        """, (
            interaction.user.id,
            interaction.channel.id
        ))

        db.commit()

        await interaction.response.send_message(
            (
                "👤 Ticket claimed by "
                f"{interaction.user.mention}."
            )
        )

        await send_ticket_log(
            interaction.guild,
            "👤 Ticket Claimed",
            (
                f"**Ticket:** "
                f"{interaction.channel.mention}\n"
                f"**Ticket ID:** #{ticket_id}\n"
                f"**Claimed By:** "
                f"{interaction.user.mention}"
            ),
            discord.Color.blue()
        )


    # =====================================================
    # UNCLAIM
    # =====================================================

    @discord.ui.button(
        label="Unclaim",
        emoji="↩️",
        style=discord.ButtonStyle.secondary,
        custom_id="ticket_unclaim"
    )
    async def unclaim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):

            return await interaction.response.send_message(
                "❌ Only staff members can unclaim tickets.",
                ephemeral=True
            )

        ticket = get_ticket(
            interaction.channel.id
        )

        if ticket is None:

            return await interaction.response.send_message(
                "❌ This isn't a registered ticket.",
                ephemeral=True
            )

        ticket_id = ticket[0]
        claimed_by = ticket[6]

        if not claimed_by:

            return await interaction.response.send_message(
                "❌ This ticket is not currently claimed.",
                ephemeral=True
            )

        if (
            claimed_by != interaction.user.id
            and not interaction.user.guild_permissions.administrator
        ):

            return await interaction.response.send_message(
                (
                    "❌ Only the staff member who "
                    "claimed this ticket or an "
                    "administrator can unclaim it."
                ),
                ephemeral=True
            )

        cursor.execute("""
        UPDATE tickets
        SET claimed_by=NULL
        WHERE channel_id=?
        """, (
            interaction.channel.id,
        ))

        db.commit()

        await interaction.response.send_message(
            "↩️ Ticket has been unclaimed."
        )

        await send_ticket_log(
            interaction.guild,
            "↩️ Ticket Unclaimed",
            (
                f"**Ticket:** "
                f"{interaction.channel.mention}\n"
                f"**Ticket ID:** #{ticket_id}\n"
                f"**Unclaimed By:** "
                f"{interaction.user.mention}"
            ),
            discord.Color.light_grey()
        )


    # =====================================================
    # CLOSE
    # =====================================================

    @discord.ui.button(
        label="Close",
        emoji="🔒",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        ticket = get_ticket(
            interaction.channel.id
        )

        if ticket is None:

            return await interaction.response.send_message(
                "❌ This isn't a registered ticket.",
                ephemeral=True
            )

        (
            ticket_id,
            guild_id,
            owner_id,
            channel_id,
            department,
            status,
            claimed_by,
            created_at,
            closed_at
        ) = ticket

        if status != "open":

            return await interaction.response.send_message(
                "❌ This ticket is already closed.",
                ephemeral=True
            )

        if (
            interaction.user.id != owner_id
            and not is_staff(interaction.user)
        ):

            return await interaction.response.send_message(
                (
                    "❌ Only the ticket owner or "
                    "staff can close this ticket."
                ),
                ephemeral=True
            )

        owner = interaction.guild.get_member(
            owner_id
        )

        if owner:

            try:

                await interaction.channel.set_permissions(
                    owner,
                    send_messages=False
                )

            except discord.HTTPException:
                pass

        cursor.execute("""
        UPDATE tickets
        SET status='closed',
            closed_at=CURRENT_TIMESTAMP
        WHERE channel_id=?
        """, (
            interaction.channel.id,
        ))

        db.commit()

        try:

            current_name = interaction.channel.name

            if not current_name.startswith(
                "closed-"
            ):

                await interaction.channel.edit(
                    name=(
                        f"closed-"
                        f"{current_name}"
                    )
                )

        except discord.HTTPException:
            pass

        closed_embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=(
                "This ticket has been closed.\n\n"
                "Staff can reopen or delete it "
                "using the buttons below."
            ),
            color=discord.Color.red()
        )

        closed_embed.add_field(
            name="🎫 Ticket ID",
            value=f"#{ticket_id}",
            inline=True
        )

        closed_embed.add_field(
            name="🔒 Closed By",
            value=interaction.user.mention,
            inline=True
        )

        closed_embed.add_field(
            name="📂 Department",
            value=department,
            inline=False
        )

        await interaction.response.edit_message(
            embed=closed_embed,
            view=ClosedTicketView()
        )

        await send_ticket_log(
            interaction.guild,
            "🔒 Ticket Closed",
            (
                f"**Ticket:** "
                f"{interaction.channel.mention}\n"
                f"**Ticket ID:** #{ticket_id}\n"
                f"**Department:** "
                f"{department}\n"
                f"**Closed By:** "
                f"{interaction.user.mention}"
            ),
            discord.Color.red()
        )


# =========================================================
# CLOSED TICKET VIEW
# =========================================================

class ClosedTicketView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)


    # =====================================================
    # REOPEN
    # =====================================================

    @discord.ui.button(
        label="Reopen",
        emoji="🔓",
        style=discord.ButtonStyle.success,
        custom_id="ticket_reopen"
    )
    async def reopen_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):

            return await interaction.response.send_message(
                "❌ Only staff members can reopen tickets.",
                ephemeral=True
            )

        ticket = get_ticket(
            interaction.channel.id
        )

        if ticket is None:

            return await interaction.response.send_message(
                "❌ This isn't a registered ticket.",
                ephemeral=True
            )

        (
            ticket_id,
            guild_id,
            owner_id,
            channel_id,
            department,
            status,
            claimed_by,
            created_at,
            closed_at
        ) = ticket

        if status != "closed":

            return await interaction.response.send_message(
                "❌ This ticket isn't closed.",
                ephemeral=True
            )

        owner = interaction.guild.get_member(
            owner_id
        )

        if owner:

            try:

                await interaction.channel.set_permissions(
                    owner,
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    read_message_history=True
                )

            except discord.HTTPException:
                pass

        cursor.execute("""
        UPDATE tickets
        SET status='open',
            closed_at=NULL
        WHERE channel_id=?
        """, (
            interaction.channel.id,
        ))

        db.commit()

        try:

            current_name = interaction.channel.name

            if current_name.startswith(
                "closed-"
            ):

                new_name = current_name.replace(
                    "closed-",
                    "",
                    1
                )

                await interaction.channel.edit(
                    name=new_name
                )

        except discord.HTTPException:
            pass

        embed = discord.Embed(
            title="🔓 Ticket Reopened",
            description=(
                "This ticket has been reopened by "
                f"{interaction.user.mention}."
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="🎫 Ticket ID",
            value=f"#{ticket_id}",
            inline=True
        )

        embed.add_field(
            name="📂 Department",
            value=department,
            inline=True
        )

        await interaction.response.edit_message(
            embed=embed,
            view=TicketActionView()
        )

        await send_ticket_log(
            interaction.guild,
            "🔓 Ticket Reopened",
            (
                f"**Ticket:** "
                f"{interaction.channel.mention}\n"
                f"**Ticket ID:** #{ticket_id}\n"
                f"**Reopened By:** "
                f"{interaction.user.mention}"
            ),
            discord.Color.green()
        )


    # =====================================================
    # DELETE
    # =====================================================

    @discord.ui.button(
        label="Delete",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_delete"
    )
    async def delete_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_staff(interaction.user):

            return await interaction.response.send_message(
                "❌ Only staff members can delete tickets.",
                ephemeral=True
            )

        ticket = get_ticket(
            interaction.channel.id
        )

        if ticket is None:

            return await interaction.response.send_message(
                "❌ This isn't a registered ticket.",
                ephemeral=True
            )

        # Immediately acknowledge the interaction
        # so Discord does not time out.
        await interaction.response.defer()

        ticket_id = ticket[0]
        department = ticket[4]
        owner_id = ticket[2]

        transcript_file = None

        try:

            transcript = await create_transcript(
                interaction.channel
            )

            transcript_file = discord.File(
                io.BytesIO(
                    transcript.encode("utf-8")
                ),
                filename=(
                    f"{interaction.channel.name}"
                    "-transcript.txt"
                )
            )

        except Exception as error:

            print(
                f"⚠️ Transcript error: {error}"
            )

        cursor.execute("""
        SELECT log_channel_id
        FROM settings
        WHERE guild_id=?
        """, (
            interaction.guild.id,
        ))

        result = cursor.fetchone()

        if result and result[0]:

            log_channel = (
                interaction.guild.get_channel(
                    result[0]
                )
            )

            if isinstance(
                log_channel,
                discord.TextChannel
            ):

                embed = discord.Embed(
                    title="🗑️ Ticket Deleted",
                    description=(
                        f"**Ticket:** "
                        f"{interaction.channel.name}\n"
                        f"**Ticket ID:** "
                        f"#{ticket_id}\n"
                        f"**Department:** "
                        f"{department}\n"
                        f"**Deleted By:** "
                        f"{interaction.user.mention}"
                    ),
                    color=discord.Color.dark_red(),
                    timestamp=datetime.now(
                        timezone.utc
                    )
                )

                owner = (
                    interaction.guild.get_member(
                        owner_id
                    )
                )

                if owner:

                    embed.add_field(
                        name="👤 Ticket Owner",
                        value=owner.mention,
                        inline=False
                    )

                try:

                    if transcript_file:

                        await log_channel.send(
                            embed=embed,
                            file=transcript_file
                        )

                    else:

                        await log_channel.send(
                            embed=embed
                        )

                except discord.HTTPException:
                    pass

        cursor.execute("""
        UPDATE tickets
        SET status='deleted'
        WHERE channel_id=?
        """, (
            interaction.channel.id,
        ))

        db.commit()

        try:

            await interaction.channel.delete(
                reason=(
                    f"Ticket deleted by "
                    f"{interaction.user}"
                )
            )

        except discord.HTTPException:
            pass


# =========================================================
# TICKET DEPARTMENT SELECT
# =========================================================

class TicketDepartmentSelect(discord.ui.Select):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="General Support",
                description=(
                    "Get help from the server staff."
                ),
                emoji="🛠️",
                value="general"
            ),

            discord.SelectOption(
                label="Report a Bug",
                description=(
                    "Report a problem or bug."
                ),
                emoji="🐛",
                value="bug"
            ),

            discord.SelectOption(
                label="Partnership",
                description=(
                    "Discuss a partnership."
                ),
                emoji="🤝",
                value="partnership"
            ),

            discord.SelectOption(
                label="Report a Player/User",
                description=(
                    "Report inappropriate behavior."
                ),
                emoji="🚨",
                value="report"
            )
        ]

        super().__init__(
            placeholder=(
                "Select a ticket department..."
            ),
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_department_select"
        )


    async def callback(
        self,
        interaction: discord.Interaction
    ):

        # =================================================
        # IMPORTANT
        # Respond immediately so Discord knows the bot is
        # processing the ticket creation.
        # =================================================

        await interaction.response.defer(
            ephemeral=True
        )

        guild = interaction.guild
        user = interaction.user

        if guild is None:

            return await interaction.followup.send(
                (
                    "❌ Tickets can only be created "
                    "inside a server."
                ),
                ephemeral=True
            )

        department_data = {

            "general": (
                "General Support",
                "general"
            ),

            "bug": (
                "Report a Bug",
                "bug"
            ),

            "partnership": (
                "Partnership",
                "partnership"
            ),

            "report": (
                "Report a Player/User",
                "report"
            )
        }

        department, channel_prefix = (
            department_data[
                self.values[0]
            ]
        )

        # =================================================
        # CHECK EXISTING OPEN TICKET
        # =================================================

        existing = get_open_ticket(
            guild.id,
            user.id
        )

        if existing:

            _, channel_id = existing

            existing_channel = guild.get_channel(
                channel_id
            )

            if existing_channel:

                return await interaction.followup.send(
                    (
                        "❌ You already have an open "
                        f"ticket: {existing_channel.mention}"
                    ),
                    ephemeral=True
                )

            cursor.execute("""
            UPDATE tickets
            SET status='deleted'
            WHERE channel_id=?
            """, (
                channel_id,
            ))

            db.commit()

        # =================================================
        # GET CATEGORY
        # =================================================

        category = get_ticket_category(
            guild
        )

        if category is None:

            try:

                category = (
                    await guild.create_category(
                        "Tickets"
                    )
                )

            except discord.Forbidden:

                return await interaction.followup.send(
                    (
                        "❌ I don't have permission to "
                        "create the ticket category."
                    ),
                    ephemeral=True
                )

            except discord.HTTPException:

                return await interaction.followup.send(
                    (
                        "❌ Discord rejected the ticket "
                        "category creation."
                    ),
                    ephemeral=True
                )

        # =================================================
        # TICKET NUMBER
        # =================================================

        cursor.execute("""
        SELECT COUNT(*)
        FROM tickets
        WHERE guild_id=?
        """, (
            guild.id,
        ))

        ticket_number = (
            cursor.fetchone()[0] + 1
        )

        # =================================================
        # CHANNEL PERMISSIONS
        # =================================================

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    attach_files=True,
                    embed_links=True,
                    read_message_history=True
                ),

            guild.me:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_channels=True,
                    manage_messages=True,
                    read_message_history=True
                )
        }

        # =================================================
        # STAFF ACCESS
        # =================================================

        for role in guild.roles:

            if (
                role.permissions.manage_guild
                or role.permissions.administrator
            ):

                overwrites[role] = (
                    discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        attach_files=True,
                        read_message_history=True
                    )
                )

        # =================================================
        # CREATE CHANNEL
        # =================================================

        try:

            channel = (
                await guild.create_text_channel(
                    name=(
                        f"{channel_prefix}-"
                        f"{ticket_number}"
                    ),
                    category=category,
                    overwrites=overwrites,
                    reason=(
                        f"{department} ticket "
                        f"created by {user}"
                    )
                )
            )

        except discord.Forbidden:

            return await interaction.followup.send(
                (
                    "❌ I don't have permission to "
                    "create ticket channels."
                ),
                ephemeral=True
            )

        except discord.HTTPException:

            return await interaction.followup.send(
                (
                    "❌ Discord rejected the ticket "
                    "creation."
                ),
                ephemeral=True
            )

        # =================================================
        # DATABASE
        # =================================================

        cursor.execute("""
        INSERT INTO tickets(
            guild_id,
            user_id,
            channel_id,
            department,
            status
        )
        VALUES (?, ?, ?, ?, 'open')
        """, (
            guild.id,
            user.id,
            channel.id,
            department
        ))

        db.commit()

        ticket_id = cursor.lastrowid

        # =================================================
        # TICKET EMBED
        # =================================================

        embed = discord.Embed(
            title=f"🎟️ {department}",
            description=(
                f"Welcome {user.mention}!\n\n"
                "Please describe your issue in as "
                "much detail as possible.\n\n"
                "A staff member will assist you "
                "shortly."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="🎫 Ticket ID",
            value=f"#{ticket_id}",
            inline=True
        )

        embed.add_field(
            name="📂 Department",
            value=department,
            inline=True
        )

        embed.add_field(
            name="👤 Created By",
            value=user.mention,
            inline=False
        )

        embed.add_field(
            name="📌 Staff",
            value=(
                "A staff member can claim this "
                "ticket using the button below."
            ),
            inline=False
        )

        embed.set_footer(
            text=(
                "Grid Guardian Support System"
            )
        )

        await channel.send(
            content=user.mention,
            embed=embed,
            view=TicketActionView()
        )

        # =================================================
        # CONFIRM USER
        # =================================================

        await interaction.followup.send(
            (
                "✅ Your ticket has been created: "
                f"{channel.mention}"
            ),
            ephemeral=True
        )

        # =================================================
        # LOG CREATION
        # =================================================

        await send_ticket_log(
            guild,
            "🎟️ Ticket Created",
            (
                f"**Ticket:** {channel.mention}\n"
                f"**Ticket ID:** #{ticket_id}\n"
                f"**Department:** {department}\n"
                f"**Created By:** {user.mention}"
            ),
            discord.Color.green()
        )


# =========================================================
# TICKET PANEL VIEW
# =========================================================

class TicketPanelView(discord.ui.View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            TicketDepartmentSelect()
        )


# =========================================================
# TICKETS COG
# =========================================================

class Tickets(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # =====================================================
    # PERSISTENT VIEWS
    # =====================================================

    async def cog_load(self):

        self.bot.add_view(
            TicketPanelView()
        )

        self.bot.add_view(
            TicketActionView()
        )

        self.bot.add_view(
            ClosedTicketView()
        )


    # =====================================================
    # TICKET PANEL
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def ticketpanel(
        self,
        ctx
    ):

        embed = discord.Embed(
            title="🎟️ Grid Guardian Support",
            description=(
                "Need help? Select the type of "
                "ticket you would like to create "
                "below.\n\n"
                "🔒 Your ticket will be private and "
                "only visible to you and server staff."
            ),
            color=EMBED_COLOR
        )

        embed.add_field(
            name="🛠️ General Support",
            value=(
                "Questions, account help, or "
                "general server support."
            ),
            inline=False
        )

        embed.add_field(
            name="🐛 Report a Bug",
            value=(
                "Report a problem, glitch, or bug."
            ),
            inline=False
        )

        embed.add_field(
            name="🤝 Partnership",
            value=(
                "Discuss partnerships or "
                "collaborations."
            ),
            inline=False
        )

        embed.add_field(
            name="🚨 Report a Player/User",
            value=(
                "Report inappropriate behavior or "
                "rule violations."
            ),
            inline=False
        )

        embed.set_footer(
            text=(
                "Grid Guardian • Support System"
            )
        )

        await ctx.send(
            embed=embed,
            view=TicketPanelView()
        )


    # =====================================================
    # SET TICKET CATEGORY
    # =====================================================

    @commands.command()
    @commands.has_permissions(
        manage_guild=True
    )
    async def setticketcategory(
        self,
        ctx,
        category: discord.CategoryChannel
    ):

        cursor.execute("""
        INSERT OR IGNORE INTO settings(guild_id)
        VALUES(?)
        """, (
            ctx.guild.id,
        ))

        cursor.execute("""
        UPDATE settings
        SET ticket_category_id=?
        WHERE guild_id=?
        """, (
            category.id,
            ctx.guild.id
        ))

        db.commit()

        embed = discord.Embed(
            title="✅ Ticket Category Updated",
            description=(
                "New tickets will be created in "
                f"**{category.name}**."
            ),
            color=discord.Color.green()
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # CLOSE TICKET COMMAND
    # =====================================================

    @commands.command()
    async def closeticket(
        self,
        ctx
    ):

        ticket = get_ticket(
            ctx.channel.id
        )

        if ticket is None:

            return await ctx.send(
                (
                    "❌ This command can only be used "
                    "inside a ticket."
                )
            )

        (
            ticket_id,
            guild_id,
            owner_id,
            channel_id,
            department,
            status,
            claimed_by,
            created_at,
            closed_at
        ) = ticket

        if status != "open":

            return await ctx.send(
                "❌ This ticket is already closed."
            )

        if (
            ctx.author.id != owner_id
            and not is_staff(ctx.author)
        ):

            return await ctx.send(
                (
                    "❌ Only the ticket owner or "
                    "staff can close this ticket."
                )
            )

        owner = ctx.guild.get_member(
            owner_id
        )

        if owner:

            try:

                await ctx.channel.set_permissions(
                    owner,
                    send_messages=False
                )

            except discord.HTTPException:
                pass

        cursor.execute("""
        UPDATE tickets
        SET status='closed',
            closed_at=CURRENT_TIMESTAMP
        WHERE channel_id=?
        """, (
            ctx.channel.id,
        ))

        db.commit()

        try:

            if not ctx.channel.name.startswith(
                "closed-"
            ):

                await ctx.channel.edit(
                    name=(
                        f"closed-"
                        f"{ctx.channel.name}"
                    )
                )

        except discord.HTTPException:
            pass

        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description=(
                "This ticket has been closed.\n\n"
                "Staff can reopen or delete it using "
                "the buttons below."
            ),
            color=discord.Color.red()
        )

        embed.add_field(
            name="🎫 Ticket ID",
            value=f"#{ticket_id}",
            inline=True
        )

        embed.add_field(
            name="📂 Department",
            value=department,
            inline=True
        )

        await ctx.send(
            embed=embed,
            view=ClosedTicketView()
        )

        await send_ticket_log(
            ctx.guild,
            "🔒 Ticket Closed",
            (
                f"**Ticket:** "
                f"{ctx.channel.mention}\n"
                f"**Ticket ID:** #{ticket_id}\n"
                f"**Department:** "
                f"{department}\n"
                f"**Closed By:** "
                f"{ctx.author.mention}"
            ),
            discord.Color.red()
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Tickets(bot)
    )