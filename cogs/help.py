import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# ==========================================================
# MEMBER HELP DROPDOWN
# ==========================================================

class MemberHelpSelect(discord.ui.Select):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="Utility",
                description="Helpful everyday commands.",
                emoji="🛠️"
            ),

            discord.SelectOption(
                label="Community",
                description="AFK, achievements, and quests.",
                emoji="🏆"
            ),

            discord.SelectOption(
                label="Apex Legends",
                description="Live Apex information and Legend commands.",
                emoji="🎮"
            ),

            discord.SelectOption(
                label="Wattson Coaching",
                description="Tips and guides for playing Wattson.",
                emoji="⚡"
            ),

            discord.SelectOption(
                label="Tickets",
                description="Get help from the server staff.",
                emoji="🎟️"
            )
        ]

        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options
        )


    async def callback(self, interaction: discord.Interaction):

        category = self.values[0]


        # ==================================================
        # UTILITY
        # ==================================================

        if category == "Utility":

            embed = discord.Embed(
                title="🛠️ Utility Commands",
                description=(
                    "`!ping` — Check the bot's latency\n"
                    "`!avatar [member]` — View a user's avatar\n"
                    "`!userinfo [member]` — View user information\n"
                    "`!serverinfo` — View server information"
                ),
                color=EMBED_COLOR
            )


        # ==================================================
        # COMMUNITY
        # ==================================================

        elif category == "Community":

            embed = discord.Embed(
                title="🏆 Community Commands",
                description=(
                    "`!afk [reason]` — Set yourself as AFK\n"
                    "`!achievements [member]` — View achievements\n"
                    "`!quests` — View your quests"
                ),
                color=EMBED_COLOR
            )


        # ==================================================
        # APEX LEGENDS
        # ==================================================

        elif category == "Apex Legends":

            embed = discord.Embed(
                title="🎮 Apex Legends Commands",
                description=(
                    "`!apexstats <platform> <player>` — View player stats\n"
                    "`!apexmap` — View the current map rotation\n"
                    "`!predator` — View current Predator requirements\n"
                    "`!apexservers` — Check Apex server status\n"
                    "`!apexuid <platform> <player>` — Look up a player's UID\n"
                    "`!legend <name>` — View information about a Legend\n"
                    "`!legends` — View the full Legend roster"
                ),
                color=EMBED_COLOR
            )


        # ==================================================
        # WATTSON COACHING
        # ==================================================

        elif category == "Wattson Coaching":

            embed = discord.Embed(
                title="⚡ Wattson Coaching Commands",
                description=(
                    "`!fence` — Fence placement tips\n"
                    "`!pylon` — Pylon and ultimate tips\n"
                    "`!rotation` — Rotation advice\n"
                    "`!anchor` — Playing as the team anchor\n"
                    "`!mistakes` — Common Wattson mistakes\n"
                    "`!mindset` — Wattson mindset tips\n"
                    "`!endgame` — Endgame advice\n"
                    "`!coach` — View all coaching commands"
                ),
                color=EMBED_COLOR
            )


        # ==================================================
        # TICKETS
        # ==================================================

        else:

            embed = discord.Embed(
                title="🎟️ Support Tickets",
                description=(
                    "Need help from the server staff?\n\n"
                    "Go to the server's **ticket panel** and "
                    "select the type of ticket you need.\n\n"
                    "**Available departments:**\n"
                    "🛠️ General Support\n"
                    "🐛 Report a Bug\n"
                    "🤝 Partnership\n"
                    "🚨 Report a Player/User\n\n"
                    "**Ticket Command:**\n"
                    "`!closeticket` — Close your ticket"
                ),
                color=EMBED_COLOR
            )


        embed.set_footer(
            text="Grid Guardian • Interactive Help"
        )

        await interaction.response.edit_message(
            embed=embed
        )


# ==========================================================
# ADMIN HELP DROPDOWN
# ==========================================================

class AdminHelpSelect(discord.ui.Select):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="Utility",
                description="Helpful everyday commands.",
                emoji="🛠️"
            ),

            discord.SelectOption(
                label="Community",
                description="AFK, achievements, and quests.",
                emoji="🏆"
            ),

            discord.SelectOption(
                label="Apex Legends",
                description="Live Apex information and Legend commands.",
                emoji="🎮"
            ),

            discord.SelectOption(
                label="Wattson Coaching",
                description="Tips and guides for playing Wattson.",
                emoji="⚡"
            ),

            discord.SelectOption(
                label="Tickets",
                description="Ticket setup and management.",
                emoji="🎟️"
            ),

            discord.SelectOption(
                label="Moderation",
                description="Server moderation commands.",
                emoji="🛡️"
            ),

            discord.SelectOption(
                label="Server Settings",
                description="Configure Grid Guardian.",
                emoji="⚙️"
            )
        ]

        super().__init__(
            placeholder="Select a category...",
            min_values=1,
            max_values=1,
            options=options
        )


    async def callback(self, interaction: discord.Interaction):

        category = self.values[0]


        # ==================================================
        # UTILITY
        # ==================================================

        if category == "Utility":

            embed = discord.Embed(
                title="🛠️ Utility Commands",
                description=(
                    "`!ping` — Check the bot's latency\n"
                    "`!avatar [member]` — View a user's avatar\n"
                    "`!userinfo [member]` — View user information\n"
                    "`!serverinfo` — View server information"
                ),
                color=EMBED_COLOR
            )


        # ==================================================
        # COMMUNITY
        # ==================================================

        elif category == "Community":

            embed = discord.Embed(
                title="🏆 Community Commands",
                description=(
                    "`!afk [reason]` — Set yourself as AFK\n"
                    "`!achievements [member]` — View achievements\n"
                    "`!quests` — View your quests"
                ),
                color=EMBED_COLOR
            )


        # ==================================================
        # APEX LEGENDS
        # ==================================================

        elif category == "Apex Legends":

            embed = discord.Embed(
                title="🎮 Apex Legends Commands",
                description=(
                    "`!apexstats <platform> <player>` — View player stats\n"
                    "`!apexmap` — View the current map rotation\n"
                    "`!predator` — View current Predator requirements\n"
                    "`!apexservers` — Check Apex server status\n"
                    "`!apexuid <platform> <player>` — Look up a player's UID\n"
                    "`!legend <name>` — View information about a Legend\n"
                    "`!legends` — View the full Legend roster"
                ),
                color=EMBED_COLOR
            )


        # ==================================================
        # WATTSON COACHING
        # ==================================================

        elif category == "Wattson Coaching":

            embed = discord.Embed(
                title="⚡ Wattson Coaching Commands",
                description=(
                    "`!fence` — Fence placement tips\n"
                    "`!pylon` — Pylon and ultimate tips\n"
                    "`!rotation` — Rotation advice\n"
                    "`!anchor` — Playing as the team anchor\n"
                    "`!mistakes` — Common Wattson mistakes\n"
                    "`!mindset` — Wattson mindset tips\n"
                    "`!endgame` — Endgame advice\n"
                    "`!coach` — View all coaching commands"
                ),
                color=EMBED_COLOR
            )


        # ==================================================
        # TICKETS
        # ==================================================

        elif category == "Tickets":

            embed = discord.Embed(
                title="🎟️ Ticket Commands",
                description=(
                    "`!ticketpanel` — Send the ticket creation panel\n"
                    "`!setticketcategory #category` — Set the category where tickets are created\n"
                    "`!closeticket` — Close the current ticket\n\n"
                    "**Staff Ticket Buttons:**\n"
                    "👤 Claim — Claim an open ticket\n"
                    "↩️ Unclaim — Release a claimed ticket\n"
                    "🔒 Close — Close a ticket\n"
                    "🔓 Reopen — Reopen a closed ticket\n"
                    "🗑️ Delete — Delete a closed ticket and save a transcript"
                ),
                color=EMBED_COLOR
            )


        # ==================================================
        # MODERATION
        # ==================================================

        elif category == "Moderation":

            embed = discord.Embed(
                title="🛡️ Moderation Commands",
                description=(
                    "`!warn @member <reason>` — Warn a member\n"
                    "`!warnings [member]` — View warnings\n"
                    "`!kick @member <reason>` — Kick a member\n"
                    "`!ban @member <reason>` — Ban a member\n"
                    "`!purge <amount>` — Delete messages"
                ),
                color=EMBED_COLOR
            )


        # ==================================================
        # SERVER SETTINGS
        # ==================================================

        else:

            embed = discord.Embed(
                title="⚙️ Server Settings",
                description=(
                    "`!setwelcome #channel` — Set the welcome channel\n"
                    "`!setlogs #channel` — Set the log channel\n"
                    "`!setsuggestions #channel` — Set the suggestions channel\n"
                    "`!setautorole @role` — Set the automatic role\n"
                    "`!settings` — View current settings\n"
                    "`!dashboard` — View the server dashboard\n"
                    "`!updatelegends` — Force a Legend roster update"
                ),
                color=EMBED_COLOR
            )


        embed.set_footer(
            text="Grid Guardian • Interactive Help"
        )

        await interaction.response.edit_message(
            embed=embed
        )


# ==========================================================
# MEMBER HELP VIEW
# ==========================================================

class MemberHelpView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=180)

        self.add_item(
            MemberHelpSelect()
        )


# ==========================================================
# ADMIN HELP VIEW
# ==========================================================

class AdminHelpView(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=180)

        self.add_item(
            AdminHelpSelect()
        )


# ==========================================================
# HELP COG
# ==========================================================

class Help(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    @commands.command()
    async def help(self, ctx):

        is_admin = (
            ctx.author.guild_permissions.administrator
        )


        # ==================================================
        # ADMIN HELP
        # ==================================================

        if is_admin:

            embed = discord.Embed(
                title="⚡ Grid Guardian Help",
                description=(
                    "Welcome to the Grid Guardian help menu!\n\n"
                    "Select a category below to view commands.\n\n"
                    "🛡️ **Admin commands are available to you.**"
                ),
                color=EMBED_COLOR
            )

            embed.add_field(
                name="🛠️ Utility",
                value="Everyday commands",
                inline=True
            )

            embed.add_field(
                name="🏆 Community",
                value="Community features",
                inline=True
            )

            embed.add_field(
                name="🎮 Apex Legends",
                value="Live Apex information",
                inline=True
            )

            embed.add_field(
                name="⚡ Wattson Coaching",
                value="Wattson guides and tips",
                inline=True
            )

            embed.add_field(
                name="🎟️ Tickets",
                value="Ticket setup and management",
                inline=True
            )

            embed.add_field(
                name="🛡️ Moderation",
                value="Admin moderation tools",
                inline=True
            )

            embed.add_field(
                name="⚙️ Server Settings",
                value="Configure the server",
                inline=True
            )

            embed.set_footer(
                text="Grid Guardian • Administrator Help"
            )

            await ctx.send(
                embed=embed,
                view=AdminHelpView()
            )


        # ==================================================
        # MEMBER HELP
        # ==================================================

        else:

            embed = discord.Embed(
                title="⚡ Grid Guardian Help",
                description=(
                    "Welcome to the Grid Guardian help menu!\n\n"
                    "Select a category below to view available commands."
                ),
                color=EMBED_COLOR
            )

            embed.add_field(
                name="🛠️ Utility",
                value="Everyday commands",
                inline=True
            )

            embed.add_field(
                name="🏆 Community",
                value="Community features",
                inline=True
            )

            embed.add_field(
                name="🎮 Apex Legends",
                value="Live Apex information",
                inline=True
            )

            embed.add_field(
                name="⚡ Wattson Coaching",
                value="Wattson guides and tips",
                inline=True
            )

            embed.add_field(
                name="🎟️ Tickets",
                value="Get help from server staff",
                inline=True
            )

            embed.set_footer(
                text="Grid Guardian • Member Help"
            )

            await ctx.send(
                embed=embed,
                view=MemberHelpView()
            )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):
    await bot.add_cog(
        Help(bot)
    )