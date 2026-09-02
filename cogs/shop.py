import sqlite3
import discord
from discord.ext import commands

EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()

# --------------------------------------------------
# DATABASE
# --------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS shop_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    price INTEGER NOT NULL,
    role_id INTEGER
)
""")

db.commit()


class Shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --------------------------------------------------
    # SHOP
    # --------------------------------------------------

    @commands.command()
    async def shop(self, ctx):

        cursor.execute("""
        SELECT id, name, description, price, role_id
        FROM shop_items
        WHERE guild_id=?
        ORDER BY price ASC
        """, (ctx.guild.id,))

        items = cursor.fetchall()

        embed = discord.Embed(
            title="🛒 Grid Guardian Shop",
            description="Spend your coins on rewards!",
            color=EMBED_COLOR
        )

        if not items:
            embed.description = (
                "The shop is currently empty.\n\n"
                "An administrator can add items with:\n"
                "`!addshopitem`"
            )

            return await ctx.send(embed=embed)

        for item_id, name, description, price, role_id in items:

            embed.add_field(
                name=f"🛍️ {name} — 💰 {price:,}",
                value=(
                    f"{description}\n"
                    f"**Item ID:** `{item_id}`"
                ),
                inline=False
            )

        embed.set_footer(
            text="Use !buy <item ID> to purchase an item."
        )

        await ctx.send(embed=embed)

    # --------------------------------------------------
    # BUY
    # --------------------------------------------------

    @commands.command()
    async def buy(self, ctx, item_id: int):

        cursor.execute("""
        SELECT name, description, price, role_id
        FROM shop_items
        WHERE id=? AND guild_id=?
        """, (
            item_id,
            ctx.guild.id
        ))

        item = cursor.fetchone()

        if item is None:
            return await ctx.send(
                "❌ That shop item doesn't exist."
            )

        name, description, price, role_id = item

        # Get balance
        cursor.execute("""
        SELECT balance
        FROM economy
        WHERE user_id=?
        """, (ctx.author.id,))

        balance_data = cursor.fetchone()

        if balance_data is None:
            balance = 0

            cursor.execute("""
            INSERT INTO economy(user_id, balance, last_daily)
            VALUES (?, 0, 0)
            """, (ctx.author.id,))

            db.commit()

        else:
            balance = balance_data[0]

        # Check balance
        if balance < price:

            missing = price - balance

            return await ctx.send(
                f"❌ You don't have enough coins.\n\n"
                f"💰 Your balance: **{balance:,}**\n"
                f"💵 Price: **{price:,}**\n"
                f"📉 You need **{missing:,}** more."
            )

        # --------------------------------------------------
        # ROLE ITEM
        # --------------------------------------------------

        if role_id:

            role = ctx.guild.get_role(role_id)

            if role is None:
                return await ctx.send(
                    "❌ This shop item's role no longer exists."
                )

            if role in ctx.author.roles:
                return await ctx.send(
                    f"❌ You already have the {role.mention} role."
                )

            try:
                await ctx.author.add_roles(role)
            except discord.Forbidden:
                return await ctx.send(
                    "❌ I don't have permission to give that role."
                )

        # Remove coins
        cursor.execute("""
        UPDATE economy
        SET balance = balance - ?
        WHERE user_id=?
        """, (
            price,
            ctx.author.id
        ))

        db.commit()

        new_balance = balance - price

        embed = discord.Embed(
            title="🛍️ Purchase Complete!",
            description=(
                f"{ctx.author.mention} purchased "
                f"**{name}**!"
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="💰 Cost",
            value=f"{price:,} coins",
            inline=True
        )

        embed.add_field(
            name="💵 Remaining Balance",
            value=f"{new_balance:,} coins",
            inline=True
        )

        if role_id:
            role = ctx.guild.get_role(role_id)

            if role:
                embed.add_field(
                    name="🎭 Reward",
                    value=role.mention,
                    inline=False
                )

        await ctx.send(embed=embed)

    # --------------------------------------------------
    # ADD SHOP ITEM
    # --------------------------------------------------

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def addshopitem(
        self,
        ctx,
        name: str,
        price: int,
        role: discord.Role = None,
        *,
        description: str = "A special Grid Guardian reward."
    ):

        if price <= 0:
            return await ctx.send(
                "❌ The price must be greater than 0."
            )

        cursor.execute("""
        INSERT INTO shop_items(
            guild_id,
            name,
            description,
            price,
            role_id
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            ctx.guild.id,
            name,
            description,
            price,
            role.id if role else None
        ))

        db.commit()

        embed = discord.Embed(
            title="✅ Shop Item Added",
            color=discord.Color.green()
        )

        embed.add_field(
            name="🛍️ Item",
            value=name,
            inline=False
        )

        embed.add_field(
            name="💰 Price",
            value=f"{price:,} coins",
            inline=True
        )

        embed.add_field(
            name="📝 Description",
            value=description,
            inline=False
        )

        if role:
            embed.add_field(
                name="🎭 Role Reward",
                value=role.mention,
                inline=False
            )

        await ctx.send(embed=embed)

    # --------------------------------------------------
    # REMOVE SHOP ITEM
    # --------------------------------------------------

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def removeshopitem(self, ctx, item_id: int):

        cursor.execute("""
        SELECT name
        FROM shop_items
        WHERE id=? AND guild_id=?
        """, (
            item_id,
            ctx.guild.id
        ))

        item = cursor.fetchone()

        if item is None:
            return await ctx.send(
                "❌ That shop item doesn't exist."
            )

        name = item[0]

        cursor.execute("""
        DELETE FROM shop_items
        WHERE id=? AND guild_id=?
        """, (
            item_id,
            ctx.guild.id
        ))

        db.commit()

        await ctx.send(
            f"🗑️ Removed **{name}** from the shop."
        )

    # --------------------------------------------------
    # CLEAR SHOP
    # --------------------------------------------------

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def clearshop(self, ctx):

        cursor.execute("""
        SELECT COUNT(*)
        FROM shop_items
        WHERE guild_id=?
        """, (ctx.guild.id,))

        count = cursor.fetchone()[0]

        if count == 0:
            return await ctx.send(
                "🛒 The shop is already empty."
            )

        cursor.execute("""
        DELETE FROM shop_items
        WHERE guild_id=?
        """, (ctx.guild.id,))

        db.commit()

        await ctx.send(
            f"🗑️ Removed **{count}** item(s) from the shop."
        )


async def setup(bot):
    await bot.add_cog(Shop(bot))