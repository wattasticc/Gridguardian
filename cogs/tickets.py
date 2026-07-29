import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Create Ticket",
        emoji="🎟️",
        style=discord.ButtonStyle.green,
        custom_id="create_ticket"
    )
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        guild = interaction.guild

        existing = discord.utils.get(
            guild.channels,
            name=f"ticket-{interaction.user.name.lower()}"
        )

        if existing:
            await interaction.response.send_message(
                "❌ You already have an open ticket.",
                ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                attach_files=True,
                read_message_history=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True
            )
        }

        category = discord.utils.get(guild.categories, name="Tickets")

        if category is None:
            category = await guild.create_category("Tickets")

        channel = await guild.create_text_channel(
            f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        embed = discord.Embed(
            title="🎟️ Support Ticket",
            description=(
                f"Welcome {interaction.user.mention}!\n\n"
                "Describe your issue and a staff member will help you."
            ),
            color=EMBED_COLOR
        )

        await channel.send(embed=embed, view=CloseTicketView())

        await interaction.response.send_message(
            f"✅ Ticket created: {channel.mention}",
            ephemeral=True
        )


class DeleteTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Delete Ticket",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="delete_ticket"
    )
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message(
            "🗑️ Deleting ticket in 5 seconds..."
        )

        await interaction.channel.delete()


class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.channel.edit(
            name=f"closed-{interaction.channel.name}"
        )

        embed = discord.Embed(
            title="🔒 Ticket Closed",
            description="This ticket has been closed.\n\nClick **Delete Ticket** when you're finished.",
            color=discord.Color.red()
        )

        await interaction.response.edit_message(
    embed=embed,
    view=DeleteTicketView()
)


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def ticketpanel(self, ctx):

        embed = discord.Embed(
            title="🎟️ Support Tickets",
            description=(
                "Need help?\n\n"
                "Click the button below to create a private support ticket."
            ),
            color=EMBED_COLOR
        )

        await ctx.send(
            embed=embed,
            view=TicketView()
        )


async def setup(bot):
    await bot.add_cog(Tickets(bot))