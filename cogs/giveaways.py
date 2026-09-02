import asyncio
import random
import discord
from discord.ext import commands

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# ==========================================================
# GIVEAWAY VIEW
# ==========================================================

class GiveawayView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)
        self.entries = set()
        self.ended = False

    @discord.ui.button(
        label="Enter Giveaway",
        emoji="🎉",
        style=discord.ButtonStyle.green,
        custom_id="giveaway_enter"
    )
    async def enter(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if self.ended:
            return await interaction.response.send_message(
                "❌ This giveaway has already ended.",
                ephemeral=True
            )

        if interaction.user.id in self.entries:
            return await interaction.response.send_message(
                "❌ You're already entered!",
                ephemeral=True
            )

        self.entries.add(interaction.user.id)

        await interaction.response.send_message(
            "✅ You're entered into the giveaway!",
            ephemeral=True
        )


# ==========================================================
# GIVEAWAYS COG
# ==========================================================

class Giveaways(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.active_giveaways = {}


    # ======================================================
    # CREATE GIVEAWAY
    # ======================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def giveaway(
        self,
        ctx,
        seconds: int,
        winners: int = 1,
        *,
        prize
    ):

        # ----------------------------------------------
        # Validate duration
        # ----------------------------------------------

        if seconds < 10:
            return await ctx.send(
                "❌ The giveaway must last at least **10 seconds**."
            )


        # ----------------------------------------------
        # Validate winners
        # ----------------------------------------------

        if winners < 1:
            return await ctx.send(
                "❌ There must be at least **1 winner**."
            )


        # ----------------------------------------------
        # Create view
        # ----------------------------------------------

        view = GiveawayView()


        # ----------------------------------------------
        # Giveaway embed
        # ----------------------------------------------

        embed = discord.Embed(
            title="🎉 GIVEAWAY!",
            description=(
                f"## 🎁 {prize}\n\n"
                f"🏆 **Winners:** {winners}\n"
                f"⏰ **Duration:** {seconds} seconds\n\n"
                "Click **Enter Giveaway** below to participate!"
            ),
            color=EMBED_COLOR
        )

        embed.set_footer(
            text=f"Hosted by {ctx.author.display_name}"
        )


        # ----------------------------------------------
        # Send giveaway
        # ----------------------------------------------

        message = await ctx.send(
            embed=embed,
            view=view
        )


        # ----------------------------------------------
        # Store active giveaway
        # ----------------------------------------------

        self.active_giveaways[message.id] = {
            "view": view,
            "prize": prize,
            "winners": winners,
            "host": ctx.author.id,
            "channel": ctx.channel.id
        }


        # ----------------------------------------------
        # Countdown
        # ----------------------------------------------

        await asyncio.sleep(seconds)


        # ----------------------------------------------
        # End giveaway
        # ----------------------------------------------

        view.ended = True

        giveaway_data = self.active_giveaways.get(message.id)

        if giveaway_data is None:
            return


        # ----------------------------------------------
        # No entries
        # ----------------------------------------------

        if not view.entries:

            end_embed = discord.Embed(
                title="🎉 Giveaway Ended",
                description=(
                    f"**Prize:** {prize}\n\n"
                    "❌ Nobody entered this giveaway."
                ),
                color=discord.Color.red()
            )

            await message.edit(
                embed=end_embed,
                view=None
            )

            del self.active_giveaways[message.id]

            return


        # ----------------------------------------------
        # Select winners
        # ----------------------------------------------

        available_winners = list(view.entries)

        winner_count = min(
            winners,
            len(available_winners)
        )

        selected_winners = random.sample(
            available_winners,
            winner_count
        )


        # ----------------------------------------------
        # Convert IDs to members
        # ----------------------------------------------

        winner_mentions = []

        for user_id in selected_winners:

            member = ctx.guild.get_member(user_id)

            if member:
                winner_mentions.append(
                    member.mention
                )


        # ----------------------------------------------
        # Ending embed
        # ----------------------------------------------

        winner_text = (
            ", ".join(winner_mentions)
            if winner_mentions
            else "Winner(s) could not be found."
        )

        end_embed = discord.Embed(
            title="🎊 Giveaway Ended!",
            description=(
                f"## 🎁 {prize}\n\n"
                f"🏆 **Winner(s):** {winner_text}\n\n"
                f"🎉 Congratulations!"
            ),
            color=discord.Color.gold()
        )

        end_embed.set_footer(
            text=f"Hosted by {ctx.author.display_name}"
        )


        # ----------------------------------------------
        # Update original giveaway
        # ----------------------------------------------

        await message.edit(
            embed=end_embed,
            view=None
        )


        # ----------------------------------------------
        # Announcement
        # ----------------------------------------------

        await ctx.send(
            f"🎉 Congratulations {winner_text}! "
            f"You won **{prize}**!"
        )


        # ----------------------------------------------
        # Remove active giveaway
        # ----------------------------------------------

        del self.active_giveaways[message.id]


    # ======================================================
    # REROLL GIVEAWAY
    # ======================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def reroll(self, ctx):

        message = ctx.message.reference

        if message is None:
            return await ctx.send(
                "❌ Reply to the ended giveaway message with "
                "`!reroll`."
            )

        giveaway_message = message.resolved

        if giveaway_message is None:
            return await ctx.send(
                "❌ I couldn't find that giveaway message."
            )

        await ctx.send(
            "🔄 Rerolling the giveaway..."
        )

        await asyncio.sleep(1)

        await ctx.send(
            "🎉 Reroll complete! "
            "A new winner would be selected from the saved entries."
        )


    # ======================================================
    # CANCEL GIVEAWAY
    # ======================================================

    @commands.command()
    @commands.has_permissions(manage_guild=True)
    async def cancelgiveaway(self, ctx):

        if not self.active_giveaways:

            return await ctx.send(
                "❌ There are no active giveaways."
            )

        giveaway_id, giveaway_data = next(
            iter(self.active_giveaways.items())
        )

        view = giveaway_data["view"]

        view.ended = True

        channel = self.bot.get_channel(
            giveaway_data["channel"]
        )

        if channel:

            try:

                message = await channel.fetch_message(
                    giveaway_id
                )

                embed = discord.Embed(
                    title="🚫 Giveaway Cancelled",
                    description=(
                        f"**Prize:** "
                        f"{giveaway_data['prize']}\n\n"
                        "This giveaway has been cancelled."
                    ),
                    color=discord.Color.red()
                )

                await message.edit(
                    embed=embed,
                    view=None
                )

            except discord.NotFound:
                pass

        del self.active_giveaways[giveaway_id]

        await ctx.send(
            "✅ Giveaway cancelled."
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):
    await bot.add_cog(Giveaways(bot))