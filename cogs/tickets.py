import io
import re
import sqlite3
from datetime import datetime, timezone

import discord
from discord.ext import commands

DB_PATH = "gridguardian.db"
EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)
DEPARTMENTS = {
    "general": ("General Support", "🛠️", "General questions and community support."),
    "bug": ("Report a Bug", "🐛", "Report a bot, server, or feature bug."),
    "partnership": ("Partnership", "🤝", "Partnership and collaboration requests."),
    "report": ("Report a Player/User", "🚨", "Report a player or community user."),
}


def db():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.row_factory = sqlite3.Row
    return c


def ensure_column(c, table, column, definition):
    cols = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS settings (
            guild_id INTEGER PRIMARY KEY, welcome_channel_id INTEGER,
            log_channel_id INTEGER, suggestion_channel_id INTEGER,
            autorole_id INTEGER, ticket_category_id INTEGER)""")
        ensure_column(c, "settings", "ticket_category_id", "INTEGER")
        c.execute("""CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL, channel_id INTEGER NOT NULL,
            department TEXT NOT NULL DEFAULT 'general',
            status TEXT NOT NULL DEFAULT 'open', claimed_by INTEGER,
            created_at TEXT NOT NULL, closed_at TEXT)""")
        ensure_column(c, "tickets", "department", "TEXT NOT NULL DEFAULT 'general'")
        ensure_column(c, "tickets", "claimed_by", "INTEGER")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ticket_user ON tickets(guild_id,user_id,status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ticket_channel ON tickets(channel_id)")


def setting(guild_id):
    with db() as c:
        r = c.execute("SELECT ticket_category_id FROM settings WHERE guild_id=?", (guild_id,)).fetchone()
        return r[0] if r else None


def set_setting(guild_id, category_id):
    with db() as c:
        c.execute("""INSERT INTO settings(guild_id,ticket_category_id) VALUES(?,?)
        ON CONFLICT(guild_id) DO UPDATE SET ticket_category_id=excluded.ticket_category_id""", (guild_id, category_id))


def ticket_channel(channel_id):
    with db() as c:
        return c.execute("SELECT * FROM tickets WHERE channel_id=? LIMIT 1", (channel_id,)).fetchone()


def open_ticket(guild_id, user_id):
    with db() as c:
        return c.execute("""SELECT * FROM tickets WHERE guild_id=? AND user_id=? AND status='open'
        ORDER BY id DESC LIMIT 1""", (guild_id, user_id)).fetchone()


def by_id(ticket_id, guild_id=None):
    with db() as c:
        if guild_id is None:
            return c.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
        return c.execute("SELECT * FROM tickets WHERE id=? AND guild_id=?", (ticket_id, guild_id)).fetchone()


def update(ticket_id, **fields):
    allowed = {"status", "claimed_by", "closed_at", "department", "channel_id"}
    fields = {k: v for k, v in fields.items() if k in allowed}
    if not fields:
        return
    with db() as c:
        c.execute(f"UPDATE tickets SET {', '.join(k+'=?' for k in fields)} WHERE id=?", (*fields.values(), ticket_id))


def staff(m):
    return m.guild_permissions.manage_guild or m.guild_permissions.administrator


def panel_embed():
    e = discord.Embed(title="🎫 Grid Guardian Support", color=EMBED_COLOR,
                      description="Select a department below to open a ticket. Please provide clear details and any useful screenshots, videos, or IDs.")
    for key, (label, emoji, desc) in DEPARTMENTS.items():
        e.add_field(name=f"{emoji} {label}", value=desc, inline=False)
    e.set_footer(text="Grid Guardian • Support System")
    return e


def ticket_embed(t, member):
    label, emoji, _ = DEPARTMENTS.get(t["department"], DEPARTMENTS["general"])
    e = discord.Embed(title=f"{emoji} {label}", color=EMBED_COLOR,
                      description=f"Welcome {member.mention}!\n\nPlease describe your issue clearly. Staff can claim this ticket, and the owner or staff can close it.")
    e.add_field(name="🎫 Ticket", value=f"`#{t['id']}`", inline=True)
    e.add_field(name="📂 Department", value=label, inline=True)
    e.add_field(name="👤 Owner", value=f"<@{t['user_id']}>", inline=True)
    e.add_field(name="📌 Status", value=t["status"].title(), inline=True)
    e.add_field(name="🙋 Claimed By", value=f"<@{t['claimed_by']}>" if t["claimed_by"] else "Unclaimed", inline=True)
    return e


async def log(guild, title, text, color=EMBED_COLOR):
    with db() as c:
        r = c.execute("SELECT log_channel_id FROM settings WHERE guild_id=?", (guild.id,)).fetchone()
    channel = guild.get_channel(r[0]) if r and r[0] else None
    if not isinstance(channel, discord.TextChannel):
        return
    e = discord.Embed(title=title, description=text, color=color, timestamp=datetime.now(timezone.utc))
    try:
        await channel.send(embed=e)
    except (discord.Forbidden, discord.HTTPException):
        pass


async def transcript(channel):
    lines = [f"Grid Guardian Ticket Transcript", f"Guild: {channel.guild.name} ({channel.guild.id})",
             f"Channel: {channel.name} ({channel.id})", f"Generated: {datetime.now(timezone.utc).isoformat()}", "=" * 80, ""]
    try:
        async for m in channel.history(limit=None, oldest_first=True):
            lines += [f"[{m.created_at.isoformat()}] {m.author} ({m.author.id})", m.content or "[no text content]"]
            lines += [f"Attachment: {a.url}" for a in m.attachments]
            lines.append("-" * 80)
    except discord.HTTPException as exc:
        lines.append(f"History error: {exc}")
    data = "\n".join(lines).encode("utf-8", "replace")
    if len(data) > 24 * 1024 * 1024:
        data = data[:24 * 1024 * 1024] + b"\n[Transcript truncated.]"
    return io.BytesIO(data)


async def category(guild):
    cid = setting(guild.id)
    if cid:
        c = guild.get_channel(cid)
        if isinstance(c, discord.CategoryChannel):
            return c
    c = discord.utils.get(guild.categories, name="Tickets")
    if not c:
        try:
            c = await guild.create_category("Tickets", reason="Grid Guardian ticket system")
        except (discord.Forbidden, discord.HTTPException):
            return None
    set_setting(guild.id, c.id)
    return c


def overwrites(guild, user):
    ow = {guild.default_role: discord.PermissionOverwrite(view_channel=False),
          user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)}
    if guild.me:
        ow[guild.me] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, manage_channels=True, manage_messages=True, attach_files=True, embed_links=True)
    for role in guild.roles:
        if not role.is_default() and (role.permissions.administrator or role.permissions.manage_guild):
            ow[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)
    return ow


async def close_ticket(channel, t, actor, message=None):
    update(t["id"], status="closed", closed_at=datetime.now(timezone.utc).isoformat())
    member = channel.guild.get_member(t["user_id"])
    if member:
        try:
            await channel.set_permissions(member, view_channel=True, send_messages=False, read_message_history=True,
                                         reason=f"Ticket #{t['id']} closed")
        except (discord.Forbidden, discord.HTTPException):
            pass
    name = channel.name if channel.name.startswith("closed-") else f"closed-{channel.name}"
    try:
        await channel.edit(name=name, reason=f"Ticket #{t['id']} closed")
    except (discord.Forbidden, discord.HTTPException):
        pass
    t2 = by_id(t["id"], channel.guild.id)
    embed = discord.Embed(title=f"🔒 Ticket #{t['id']} Closed", description="This ticket is closed. Staff can reopen or permanently delete it.", color=discord.Color.orange())
    embed.add_field(name="👤 Owner", value=f"<@{t['user_id']}>")
    if message:
        try: await message.edit(embed=embed, view=ClosedTicketView())
        except discord.HTTPException: pass
    else:
        try: await channel.send(embed=embed, view=ClosedTicketView())
        except discord.HTTPException: pass
    await log(channel.guild, "🔒 Ticket Closed", f"Ticket `#{t['id']}` was closed by {actor.mention}.\nChannel: {channel.mention}", discord.Color.orange())


async def delete_ticket(channel, t, actor):
    data = await transcript(channel)
    with db() as c:
        r = c.execute("SELECT log_channel_id FROM settings WHERE guild_id=?", (channel.guild.id,)).fetchone()
    log_channel = channel.guild.get_channel(r[0]) if r and r[0] else None
    if isinstance(log_channel, discord.TextChannel):
        e = discord.Embed(title="🗑️ Ticket Deleted", description=f"Ticket `#{t['id']}`\nDeleted by: {actor.mention}\nOwner: <@{t['user_id']}>\nDepartment: {DEPARTMENTS.get(t['department'], DEPARTMENTS['general'])[0]}", color=discord.Color.red())
        try:
            await log_channel.send(embed=e, file=discord.File(data, filename=f"ticket-{t['id']}-transcript.txt"))
        except discord.HTTPException:
            try: await log_channel.send(embed=e)
            except discord.HTTPException: pass
    update(t["id"], status="deleted", closed_at=datetime.now(timezone.utc).isoformat())
    try: await channel.delete(reason=f"Ticket #{t['id']} deleted by {actor}")
    except (discord.Forbidden, discord.HTTPException): pass


class TicketActionView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Claim", emoji="🙋", style=discord.ButtonStyle.primary, custom_id="gg:ticket:claim")
    async def claim(self, interaction, button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member): return
        if not staff(interaction.user): return await interaction.response.send_message("❌ Only staff can claim tickets.", ephemeral=True)
        t = ticket_channel(interaction.channel.id)
        if not t or t["status"] != "open": return await interaction.response.send_message("❌ This is not an open ticket.", ephemeral=True)
        if t["claimed_by"]: return await interaction.response.send_message(f"❌ Already claimed by <@{t['claimed_by']}>.", ephemeral=True)
        update(t["id"], claimed_by=interaction.user.id)
        await interaction.response.send_message(f"🙋 {interaction.user.mention} claimed this ticket.")
        await log(interaction.guild, "🙋 Ticket Claimed", f"Ticket `#{t['id']}` claimed by {interaction.user.mention}.", discord.Color.green())

    @discord.ui.button(label="Unclaim", emoji="↩️", style=discord.ButtonStyle.secondary, custom_id="gg:ticket:unclaim")
    async def unclaim(self, interaction, button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member): return
        if not staff(interaction.user): return await interaction.response.send_message("❌ Only staff can unclaim tickets.", ephemeral=True)
        t = ticket_channel(interaction.channel.id)
        if not t or not t["claimed_by"]: return await interaction.response.send_message("ℹ️ This ticket is not claimed.", ephemeral=True)
        if t["claimed_by"] != interaction.user.id and not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Only the claimer or an administrator can unclaim it.", ephemeral=True)
        update(t["id"], claimed_by=None)
        await interaction.response.send_message("↩️ Ticket is now unclaimed.")

    @discord.ui.button(label="Close", emoji="🔒", style=discord.ButtonStyle.danger, custom_id="gg:ticket:close")
    async def close(self, interaction, button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member): return
        t = ticket_channel(interaction.channel.id)
        if not t or t["status"] != "open": return await interaction.response.send_message("❌ This is not an open ticket.", ephemeral=True)
        if not staff(interaction.user) and interaction.user.id != t["user_id"]:
            return await interaction.response.send_message("❌ You cannot close this ticket.", ephemeral=True)
        await interaction.response.defer()
        await close_ticket(interaction.channel, t, interaction.user, interaction.message)


class ClosedTicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="Reopen", emoji="🔓", style=discord.ButtonStyle.success, custom_id="gg:ticket:reopen")
    async def reopen(self, interaction, button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member): return
        if not staff(interaction.user): return await interaction.response.send_message("❌ Only staff can reopen tickets.", ephemeral=True)
        t = ticket_channel(interaction.channel.id)
        if not t or t["status"] != "closed": return await interaction.response.send_message("❌ This ticket is not closed.", ephemeral=True)
        update(t["id"], status="open", closed_at=None)
        member = interaction.guild.get_member(t["user_id"])
        if member:
            try: await interaction.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)
            except (discord.Forbidden, discord.HTTPException): pass
        name = re.sub(r"^closed-", "", interaction.channel.name, flags=re.I)
        try: await interaction.channel.edit(name=name, reason=f"Ticket #{t['id']} reopened")
        except (discord.Forbidden, discord.HTTPException): pass
        await interaction.response.send_message("🔓 Ticket reopened.")
        await log(interaction.guild, "🔓 Ticket Reopened", f"Ticket `#{t['id']}` reopened by {interaction.user.mention}.", discord.Color.green())

    @discord.ui.button(label="Delete", emoji="🗑️", style=discord.ButtonStyle.danger, custom_id="gg:ticket:delete")
    async def delete(self, interaction, button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member): return
        if not staff(interaction.user): return await interaction.response.send_message("❌ Only staff can delete tickets.", ephemeral=True)
        t = ticket_channel(interaction.channel.id)
        if not t: return await interaction.response.send_message("❌ This is not a ticket.", ephemeral=True)
        await interaction.response.defer()
        await delete_ticket(interaction.channel, t, interaction.user)


class TicketDepartmentSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(placeholder="Select a ticket department...", min_values=1, max_values=1,
                         options=[discord.SelectOption(label=v[0], value=k, emoji=v[1], description=v[2]) for k,v in DEPARTMENTS.items()],
                         custom_id="gg:ticket:department")

    async def callback(self, interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member): return
        await interaction.response.defer(ephemeral=True)
        existing = open_ticket(interaction.guild.id, interaction.user.id)
        if existing:
            ch = interaction.guild.get_channel(existing["channel_id"])
            if ch: return await interaction.followup.send(f"❌ You already have an open ticket: {ch.mention}", ephemeral=True)
            update(existing["id"], status="deleted", closed_at=datetime.now(timezone.utc).isoformat())
        cat = await category(interaction.guild)
        if not cat: return await interaction.followup.send("❌ I can't access/create the ticket category. Check Manage Channels.", ephemeral=True)
        try:
            ch = await interaction.guild.create_text_channel("ticket-pending", category=cat, overwrites=overwrites(interaction.guild, interaction.user), reason="Grid Guardian ticket")
        except discord.Forbidden: return await interaction.followup.send("❌ I don't have permission to create ticket channels.", ephemeral=True)
        except discord.HTTPException as e: return await interaction.followup.send(f"❌ Discord rejected ticket creation: `{e}`", ephemeral=True)
        try:
            with db() as c:
                cur = c.execute("INSERT INTO tickets(guild_id,user_id,channel_id,department,status,created_at) VALUES(?,?,?,?,'open',?)",
                                (interaction.guild.id, interaction.user.id, ch.id, self.values[0], datetime.now(timezone.utc).isoformat()))
                tid = cur.lastrowid
        except sqlite3.Error:
            try: await ch.delete(reason="Ticket database error")
            except discord.HTTPException: pass
            return await interaction.followup.send("❌ The ticket could not be saved.", ephemeral=True)
        try: await ch.edit(name=f"ticket-{tid}", reason="Ticket naming")
        except (discord.Forbidden, discord.HTTPException): pass
        t = by_id(tid, interaction.guild.id)
        try: await ch.send(content=interaction.user.mention, embed=ticket_embed(t, interaction.user), view=TicketActionView())
        except discord.HTTPException:
            update(tid, status="deleted")
            try: await ch.delete(reason="Ticket setup message failed")
            except discord.HTTPException: pass
            return await interaction.followup.send("❌ I couldn't finish setting up the ticket.", ephemeral=True)
        await interaction.followup.send(f"✅ Your ticket has been created: {ch.mention}", ephemeral=True)
        await log(interaction.guild, "🎫 Ticket Created", f"Ticket `#{tid}` created by {interaction.user.mention}.\nDepartment: {DEPARTMENTS[self.values[0]][0]}\nChannel: {ch.mention}")


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDepartmentSelect())


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        init_db()

    async def cog_load(self):
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketActionView())
        self.bot.add_view(ClosedTicketView())

    @commands.command(name="ticketpanel")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def ticketpanel(self, ctx):
        await ctx.send(embed=panel_embed(), view=TicketPanelView())

    @commands.command(name="setticketcategory")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def setticketcategory(self, ctx, category: discord.CategoryChannel):
        set_setting(ctx.guild.id, category.id)
        await ctx.send(f"✅ Ticket category set to {category.mention}.")

    @commands.command(name="closeticket")
    @commands.guild_only()
    async def closeticket(self, ctx):
        t = ticket_channel(ctx.channel.id)
        if not t: return await ctx.send("❌ This isn't a Grid Guardian ticket.", delete_after=5)
        if not staff(ctx.author) and ctx.author.id != t["user_id"]: return await ctx.send("❌ You cannot close this ticket.", delete_after=5)
        await close_ticket(ctx.channel, t, ctx.author)

    @commands.command(name="reopenticket")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def reopenticket(self, ctx):
        t = ticket_channel(ctx.channel.id)
        if not t or t["status"] != "closed": return await ctx.send("❌ This is not a closed ticket.", delete_after=5)
        update(t["id"], status="open", closed_at=None)
        member = ctx.guild.get_member(t["user_id"])
        if member:
            try: await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)
            except (discord.Forbidden, discord.HTTPException): pass
        try: await ctx.channel.edit(name=re.sub(r"^closed-", "", ctx.channel.name, flags=re.I))
        except (discord.Forbidden, discord.HTTPException): pass
        await ctx.send("🔓 Ticket reopened.")

    @commands.command(name="ticketclaim")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def ticketclaim(self, ctx):
        t = ticket_channel(ctx.channel.id)
        if not t or t["status"] != "open": return await ctx.send("❌ This isn't an open ticket.", delete_after=5)
        if t["claimed_by"]: return await ctx.send(f"❌ Already claimed by <@{t['claimed_by']}>.", delete_after=5)
        update(t["id"], claimed_by=ctx.author.id)
        await ctx.send(f"🙋 {ctx.author.mention} claimed ticket `#{t['id']}`.")

    @commands.command(name="ticketunclaim")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def ticketunclaim(self, ctx):
        t = ticket_channel(ctx.channel.id)
        if not t or not t["claimed_by"]: return await ctx.send("ℹ️ This ticket is unclaimed.", delete_after=5)
        if t["claimed_by"] != ctx.author.id and not ctx.author.guild_permissions.administrator: return await ctx.send("❌ Only the claimer or an administrator can unclaim it.", delete_after=5)
        update(t["id"], claimed_by=None)
        await ctx.send("↩️ Ticket is now unclaimed.")

    @commands.command(name="ticketadd")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def ticketadd(self, ctx, member: discord.Member):
        t = ticket_channel(ctx.channel.id)
        if not t: return await ctx.send("❌ This isn't a ticket.", delete_after=5)
        try:
            await ctx.channel.set_permissions(member, view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True, reason=f"Added to ticket #{t['id']}")
            await ctx.send(f"✅ Added {member.mention} to the ticket.")
        except discord.Forbidden: await ctx.send("❌ I can't change channel permissions.", delete_after=5)

    @commands.command(name="ticketremove")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def ticketremove(self, ctx, member: discord.Member):
        t = ticket_channel(ctx.channel.id)
        if not t: return await ctx.send("❌ This isn't a ticket.", delete_after=5)
        if member.id == t["user_id"]: return await ctx.send("❌ You cannot remove the ticket owner.", delete_after=5)
        try:
            await ctx.channel.set_permissions(member, overwrite=None, reason=f"Removed from ticket #{t['id']}")
            await ctx.send(f"✅ Removed {member.mention} from the ticket.")
        except discord.Forbidden: await ctx.send("❌ I can't change channel permissions.", delete_after=5)

    @commands.command(name="ticketrename")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def ticketrename(self, ctx, *, new_name: str):
        t = ticket_channel(ctx.channel.id)
        if not t: return await ctx.send("❌ This isn't a ticket.", delete_after=5)
        name = re.sub(r"[^a-zA-Z0-9-_]", "-", new_name).strip("-").lower()[:80]
        if not name: return await ctx.send("❌ Invalid channel name.", delete_after=5)
        if not name.startswith(("ticket-", "closed-")): name = "ticket-" + name
        try: await ctx.channel.edit(name=name, reason=f"Ticket #{t['id']} renamed")
        except discord.Forbidden: return await ctx.send("❌ I can't rename this channel.", delete_after=5)
        await ctx.send(f"✏️ Ticket renamed to `{name}`.")

    @commands.command(name="ticketinfo")
    @commands.guild_only()
    async def ticketinfo(self, ctx):
        t = ticket_channel(ctx.channel.id)
        if not t: return await ctx.send("❌ This isn't a ticket.", delete_after=5)
        label = DEPARTMENTS.get(t["department"], DEPARTMENTS["general"])[0]
        e = discord.Embed(title=f"🎫 Ticket #{t['id']} Information", color=EMBED_COLOR)
        e.add_field(name="👤 Owner", value=f"<@{t['user_id']}>", inline=True)
        e.add_field(name="📂 Department", value=label, inline=True)
        e.add_field(name="📌 Status", value=t["status"].title(), inline=True)
        e.add_field(name="🙋 Claimed By", value=f"<@{t['claimed_by']}>" if t["claimed_by"] else "Unclaimed", inline=True)
        e.add_field(name="🕐 Created", value=t["created_at"], inline=False)
        e.add_field(name="🔒 Closed", value=t["closed_at"] or "Not closed", inline=False)
        await ctx.send(embed=e)

    @commands.command(name="tickettranscript")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def tickettranscript(self, ctx):
        t = ticket_channel(ctx.channel.id)
        if not t: return await ctx.send("❌ This isn't a ticket.", delete_after=5)
        await ctx.send(file=discord.File(await transcript(ctx.channel), filename=f"ticket-{t['id']}-transcript.txt"))

    @commands.command(name="deleteticket")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def deleteticket(self, ctx):
        t = ticket_channel(ctx.channel.id)
        if not t: return await ctx.send("❌ This isn't a ticket.", delete_after=5)
        await ctx.send("🗑️ Creating transcript and deleting ticket...")
        await delete_ticket(ctx.channel, t, ctx.author)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandNotFound): return
        if isinstance(error, commands.MissingPermissions): return await ctx.send("❌ You don't have permission to use that command.", delete_after=5)
        if isinstance(error, commands.MissingRequiredArgument): return await ctx.send("❌ You're missing a required argument.", delete_after=5)
        if isinstance(error, commands.BadArgument): return await ctx.send("❌ I couldn't find that member/category. Check your argument.", delete_after=5)
        raise error


async def setup(bot):
    await bot.add_cog(Tickets(bot))
