import discord

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(
        label="📊 Utility",
        style=discord.ButtonStyle.blurple
    )
    async def utility(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            title="📊 Utility Commands",
            color=EMBED_COLOR
        )

        embed.description = (
            "`!ping` - Check bot latency\n"
            "`!hello` - Say hello\n"
            "`!avatar [user]` - View a user's avatar\n"
            "`!userinfo [user]` - User information\n"
            "`!serverinfo` - Server information\n"
            "`!help` - Open this menu"
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    @discord.ui.button(
        label="🛡 Moderation",
        style=discord.ButtonStyle.red
    )
    async def moderation(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            title="🛡 Moderation Commands",
            color=discord.Color.red()
        )

        embed.description = (
            "`!ban`\n"
            "`!kick`\n"
            "`!timeout`\n"
            "`!warn`\n"
            "`!warnings`\n"
            "`!purge`"
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    @discord.ui.button(
        label="⭐ Leveling",
        style=discord.ButtonStyle.green
    )
    async def leveling(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            title="⭐ Leveling Commands",
            color=discord.Color.green()
        )

        embed.description = (
            "`!rank`\n"
            "`!leaderboard`\n"
            "`!setlevelrole` *(Admin)*"
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    @discord.ui.button(
        label="💰 Economy",
        style=discord.ButtonStyle.success
    )
    async def economy(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            title="💰 Economy Commands",
            color=discord.Color.gold()
        )

        embed.description = (
            "`!balance`\n"
            "`!daily`\n"
            "`!work`\n"
            "`!pay`\n"
            "`!deposit`\n"
            "`!withdraw`"
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    @discord.ui.button(
        label="🎟 Tickets",
        style=discord.ButtonStyle.secondary
    )
    async def tickets(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            title="🎟 Ticket Commands",
            color=discord.Color.blue()
        )

        embed.description = (
            "`!ticketpanel`\n"
            "Create support tickets using buttons."
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )

    @discord.ui.button(
        label="🎮 Apex",
        style=discord.ButtonStyle.primary
    )
    async def apex(self, interaction: discord.Interaction, button: discord.ui.Button):

        embed = discord.Embed(
            title="🎮 Apex Commands",
            color=discord.Color.orange()
        )

        embed.description = (
            "`!legend`\n"
            "`!weapon` *(Coming Soon)*\n"
            "`!maps` *(Coming Soon)*\n"
            "`!news` *(Coming Soon)*"
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self
        )