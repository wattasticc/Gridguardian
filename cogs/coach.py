import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


class Coach(commands.Cog):

    def __init__(self, bot):
        self.bot = bot


    # ======================================================
    # FENCE
    # ======================================================

    @commands.command()
    async def fence(self, ctx):

        embed = discord.Embed(
            title="⚡ Fence Placement Guide",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="🚪 Doorways",
            value=(
                "Place fences just inside doors so enemies "
                "must fully commit before destroying them."
            ),
            inline=False
        )

        embed.add_field(
            name="🪢 Ziplines",
            value=(
                "Fence both ends of vertical ziplines whenever possible."
            ),
            inline=False
        )

        embed.add_field(
            name="🚧 Chokepoints",
            value=(
                "Use long fence chains to force enemies into predictable paths."
            ),
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian • Wattson Coaching"
        )

        await ctx.send(embed=embed)


    # ======================================================
    # PYLON
    # ======================================================

    @commands.command()
    async def pylon(self, ctx):

        embed = discord.Embed(
            title="🔋 Pylon Tips",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="🛡️ Placement",
            value=(
                "Hide your pylon behind cover whenever possible."
            ),
            inline=False
        )

        embed.add_field(
            name="⚠️ Don't Waste It",
            value=(
                "Only place it when your team is committing to a position."
            ),
            inline=False
        )

        embed.add_field(
            name="💣 Grenade Denial",
            value=(
                "Use it to help protect your team from grenades and "
                "other incoming ordnance while holding an area."
            ),
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian • Wattson Coaching"
        )

        await ctx.send(embed=embed)


    # ======================================================
    # ROTATION
    # ======================================================

    @commands.command()
    async def rotation(self, ctx):

        embed = discord.Embed(
            title="🗺️ Wattson Rotation Tips",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="🏃 Rotate Early",
            value=(
                "Wattson is strongest when your team reaches a good "
                "position before other teams arrive."
            ),
            inline=False
        )

        embed.add_field(
            name="🏠 Look for Defensible Areas",
            value=(
                "Prioritize buildings, strong cover, high ground, and "
                "areas with limited entrances that can be controlled."
            ),
            inline=False
        )

        embed.add_field(
            name="⚡ Set Up Quickly",
            value=(
                "Once your team chooses a position, place your fences "
                "and pylon early so enemies have less opportunity to "
                "push before your setup is ready."
            ),
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian • Wattson Coaching"
        )

        await ctx.send(embed=embed)


    # ======================================================
    # ANCHOR
    # ======================================================

    @commands.command()
    async def anchor(self, ctx):

        embed = discord.Embed(
            title="⚓ Playing as the Team Anchor",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="🛡️ Hold Important Space",
            value=(
                "Wattson often works best protecting valuable positions "
                "while teammates take fights nearby."
            ),
            inline=False
        )

        embed.add_field(
            name="👀 Watch Your Team",
            value=(
                "Pay attention to where your teammates are fighting so "
                "you can help them retreat toward your protected area."
            ),
            inline=False
        )

        embed.add_field(
            name="⚡ Don't Overextend",
            value=(
                "You don't always need to chase every fight. Keeping a "
                "strong position can be more valuable for the whole team."
            ),
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian • Wattson Coaching"
        )

        await ctx.send(embed=embed)


    # ======================================================
    # MISTAKES
    # ======================================================

    @commands.command()
    async def mistakes(self, ctx):

        embed = discord.Embed(
            title="❌ Common Wattson Mistakes",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="⚡ Fencing Too Slowly",
            value=(
                "Practice placing fences quickly so your team is protected "
                "before enemies are already inside your position."
            ),
            inline=False
        )

        embed.add_field(
            name="🔋 Wasting the Pylon",
            value=(
                "Avoid placing your ultimate when your team will immediately "
                "leave the area unless the situation makes it necessary."
            ),
            inline=False
        )

        embed.add_field(
            name="🏃 Playing Too Far From Your Team",
            value=(
                "A protected position is less useful if your teammates are "
                "too far away to benefit from it."
            ),
            inline=False
        )

        embed.add_field(
            name="🚪 Predictable Fences",
            value=(
                "Don't always place fences in obvious locations. Try using "
                "angles, cover, and unexpected connections to make enemies "
                "hesitate."
            ),
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian • Wattson Coaching"
        )

        await ctx.send(embed=embed)


    # ======================================================
    # MINDSET
    # ======================================================

    @commands.command()
    async def mindset(self, ctx):

        embed = discord.Embed(
            title="🧠 Wattson Mindset",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="⏳ Think Ahead",
            value=(
                "Try to predict where the next fight will happen instead "
                "of waiting until the enemy is already pushing you."
            ),
            inline=False
        )

        embed.add_field(
            name="🎯 Control the Fight",
            value=(
                "Your goal isn't only to deal damage. Use your abilities "
                "to influence where enemies can safely move."
            ),
            inline=False
        )

        embed.add_field(
            name="🛡️ Value Survival",
            value=(
                "Staying alive and keeping your team's position secure can "
                "be more important than taking unnecessary fights."
            ),
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian • Wattson Coaching"
        )

        await ctx.send(embed=embed)


    # ======================================================
    # ENDGAME
    # ======================================================

    @commands.command()
    async def endgame(self, ctx):

        embed = discord.Embed(
            title="🏆 Wattson Endgame Tips",
            color=EMBED_COLOR
        )

        embed.add_field(
            name="🏠 Claim Space Early",
            value=(
                "Try to secure a strong position before the final rings "
                "become crowded."
            ),
            inline=False
        )

        embed.add_field(
            name="⚡ Fence Important Entrances",
            value=(
                "Focus on routes enemies are most likely to use rather "
                "than trying to fence every possible location."
            ),
            inline=False
        )

        embed.add_field(
            name="🔋 Protect Your Pylon",
            value=(
                "Place your pylon where enemies cannot easily destroy it "
                "while still allowing it to support your team."
            ),
            inline=False
        )

        embed.add_field(
            name="👥 Play With Your Team",
            value=(
                "Endgames are chaotic. Your setup works best when your "
                "entire team knows where your protected space is."
            ),
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian • Wattson Coaching"
        )

        await ctx.send(embed=embed)


    # ======================================================
    # COACH HELP
    # ======================================================

    @commands.command()
    async def coach(self, ctx):

        embed = discord.Embed(
            title="⚡ Wattson Coaching Commands",
            description=(
                "**Use these commands to get Wattson tips:**\n\n"
                "`!fence` — Fence placement tips\n"
                "`!pylon` — Ultimate and pylon tips\n"
                "`!rotation` — Rotation advice\n"
                "`!anchor` — How to play as the team anchor\n"
                "`!mistakes` — Common Wattson mistakes\n"
                "`!mindset` — How to think while playing Wattson\n"
                "`!endgame` — Tips for late-game situations"
            ),
            color=EMBED_COLOR
        )

        embed.set_footer(
            text="Grid Guardian • Wattson Coaching"
        )

        await ctx.send(embed=embed)


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):
    await bot.add_cog(Coach(bot))