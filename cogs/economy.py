import random
import sqlite3
from datetime import datetime, timedelta

import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# =========================================================
# DATABASE
# =========================================================

DB_PATH = "gridguardian.db"


def _open_db():
    return sqlite3.connect(DB_PATH, timeout=15)


def _ensure_economy_schema():
    """Create/migrate the economy table into one canonical schema.

    Older Grid Guardian versions used a `balance` column.  Simply adding a
    `wallet` column is not enough when that old column is NOT NULL, because
    new INSERTs can then fail.  We rebuild the table when necessary and
    preserve the old balances.
    """
    with _open_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='economy'")
        exists = cur.fetchone() is not None

        if not exists:
            cur.execute("""
                CREATE TABLE economy (
                    user_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL,
                    wallet INTEGER DEFAULT 0,
                    bank INTEGER DEFAULT 0,
                    last_work TEXT,
                    last_beg TEXT,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            return

        cur.execute("PRAGMA table_info(economy)")
        columns = {row[1] for row in cur.fetchall()}
        required = {"user_id", "guild_id", "wallet", "bank", "last_work", "last_beg"}

        # A clean canonical table can be left alone.
        if required.issubset(columns) and "balance" not in columns:
            return

        # Rebuild incompatible/legacy schemas safely.
        cur.execute("""
            CREATE TABLE economy_new (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                wallet INTEGER DEFAULT 0,
                bank INTEGER DEFAULT 0,
                last_work TEXT,
                last_beg TEXT,
                PRIMARY KEY (user_id, guild_id)
            )
        """)

        def col(name, fallback):
            return name if name in columns else fallback

        wallet_expr = (
            "CASE WHEN wallet IS NULL OR wallet = 0 "
            "THEN COALESCE(balance, 0) ELSE wallet END"
            if "wallet" in columns and "balance" in columns
            else ("wallet" if "wallet" in columns else ("balance" if "balance" in columns else "0"))
        )
        bank_expr = col("bank", "0")
        work_expr = col("last_work", "NULL")
        beg_expr = col("last_beg", "NULL")

        if "user_id" in columns and "guild_id" in columns:
            cur.execute(f"""
                INSERT INTO economy_new (user_id, guild_id, wallet, bank, last_work, last_beg)
                SELECT user_id, guild_id,
                       COALESCE({wallet_expr}, 0),
                       COALESCE({bank_expr}, 0),
                       {work_expr},
                       {beg_expr}
                FROM economy
            """)

        # Keep the old table as a backup instead of deleting it.
        cur.execute("DROP TABLE IF EXISTS economy_legacy_backup")
        cur.execute("ALTER TABLE economy RENAME TO economy_legacy_backup")
        cur.execute("ALTER TABLE economy_new RENAME TO economy")
        conn.commit()


_ensure_economy_schema()


def _get_conn():
    return _open_db()

# Compatibility connection for the existing command handlers.
db = _open_db()
cursor = db.cursor()


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def ensure_account(guild_id, user_id):
    with _get_conn() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO economy (user_id, guild_id, wallet, bank)
            VALUES (?, ?, 0, 0)
        """, (user_id, guild_id))


def get_account(guild_id, user_id):
    ensure_account(guild_id, user_id)
    with _get_conn() as conn:
        row = conn.execute("""
            SELECT wallet, bank, last_work, last_beg
            FROM economy
            WHERE guild_id=? AND user_id=?
        """, (guild_id, user_id)).fetchone()
    return row


def add_wallet(guild_id, user_id, amount):
    ensure_account(guild_id, user_id)
    with _get_conn() as conn:
        conn.execute("""
            UPDATE economy
            SET wallet = wallet + ?
            WHERE guild_id=? AND user_id=?
        """, (amount, guild_id, user_id))
    return True


def get_wallet(guild_id, user_id):
    wallet, _, _, _ = get_account(guild_id, user_id)
    return wallet


def format_time(seconds):

    seconds = max(
        0,
        int(seconds)
    )

    minutes, seconds = divmod(
        seconds,
        60
    )

    hours, minutes = divmod(
        minutes,
        60
    )

    if hours > 0:

        return (
            f"{hours}h "
            f"{minutes}m "
            f"{seconds}s"
        )

    if minutes > 0:

        return (
            f"{minutes}m "
            f"{seconds}s"
        )

    return f"{seconds}s"


# =========================================================
# ECONOMY COG
# =========================================================

class Economy(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        # Cooldowns in seconds
        self.work_cooldown = 60 * 30
        self.beg_cooldown = 60 * 10


    # =====================================================
    # BALANCE
    # =====================================================

    @commands.command(
        aliases=[
            "bal",
            "money",
            "cash"
        ]
    )
    async def balance(
        self,
        ctx,
        member: discord.Member = None
    ):

        member = member or ctx.author

        wallet, bank, _, _ = get_account(
            ctx.guild.id,
            member.id
        )

        total = wallet + bank

        embed = discord.Embed(
            title=f"💰 {member.display_name}'s Balance",
            color=EMBED_COLOR
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="👛 Wallet",
            value=f"**{wallet:,} coins**",
            inline=True
        )

        embed.add_field(
            name="🏦 Bank",
            value=f"**{bank:,} coins**",
            inline=True
        )

        embed.add_field(
            name="💎 Total",
            value=f"**{total:,} coins**",
            inline=False
        )

        embed.set_footer(
            text="Grid Guardian Economy"
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # WORK
    # =====================================================

    @commands.command()
    async def work(self, ctx):

        wallet, bank, last_work, _ = get_account(
            ctx.guild.id,
            ctx.author.id
        )

        now = datetime.utcnow()

        # -------------------------------------------------
        # COOLDOWN
        # -------------------------------------------------

        if last_work:

            try:

                last_work_time = datetime.fromisoformat(
                    last_work
                )

                elapsed = (
                    now -
                    last_work_time
                ).total_seconds()

                if elapsed < self.work_cooldown:

                    remaining = (
                        self.work_cooldown -
                        elapsed
                    )

                    return await ctx.send(
                        f"⏳ {ctx.author.mention}, "
                        f"you can work again in "
                        f"**{format_time(remaining)}**."
                    )

            except ValueError:
                pass

        # -------------------------------------------------
        # REWARD
        # -------------------------------------------------

        reward = random.randint(
            100,
            500
        )

        jobs = [

            "⚡ Repaired Wattson fences",

            "🎮 Won an Apex tournament",

            "🛠️ Helped repair Grid Guardian",

            "📦 Delivered supplies",

            "💻 Completed a programming job",

            "🔧 Fixed some server problems",

            "🏆 Won a gaming competition"

        ]

        job = random.choice(
            jobs
        )

        new_wallet = (
            wallet +
            reward
        )

        cursor.execute("""
        UPDATE economy
        SET wallet=?,
            last_work=?
        WHERE guild_id=?
        AND user_id=?
        """, (
            new_wallet,
            now.isoformat(),
            ctx.guild.id,
            ctx.author.id
        ))

        db.commit()

        embed = discord.Embed(
            title="💼 Work Complete!",
            description=(
                f"{job}\n\n"
                f"You earned **{reward:,} coins**!"
            ),
            color=discord.Color.green()
        )

        embed.add_field(
            name="👛 New Wallet Balance",
            value=f"**{new_wallet:,} coins**",
            inline=False
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # BEG
    # =====================================================

    @commands.command()
    async def beg(self, ctx):

        wallet, bank, _, last_beg = get_account(
            ctx.guild.id,
            ctx.author.id
        )

        now = datetime.utcnow()

        # -------------------------------------------------
        # COOLDOWN
        # -------------------------------------------------

        if last_beg:

            try:

                last_beg_time = datetime.fromisoformat(
                    last_beg
                )

                elapsed = (
                    now -
                    last_beg_time
                ).total_seconds()

                if elapsed < self.beg_cooldown:

                    remaining = (
                        self.beg_cooldown -
                        elapsed
                    )

                    return await ctx.send(
                        f"⏳ {ctx.author.mention}, "
                        f"you can beg again in "
                        f"**{format_time(remaining)}**."
                    )

            except ValueError:
                pass

        # -------------------------------------------------
        # RANDOM RESULT
        # -------------------------------------------------

        success = random.choice(
            [
                True,
                True,
                True,
                False
            ]
        )

        if not success:

            cursor.execute("""
            UPDATE economy
            SET last_beg=?
            WHERE guild_id=?
            AND user_id=?
            """, (
                now.isoformat(),
                ctx.guild.id,
                ctx.author.id
            ))

            db.commit()

            embed = discord.Embed(
                title="🥲 Nobody Helped",
                description=(
                    "Unfortunately, nobody gave you any coins."
                ),
                color=discord.Color.red()
            )

            return await ctx.send(
                embed=embed
            )

        reward = random.randint(
            10,
            100
        )

        new_wallet = (
            wallet +
            reward
        )

        cursor.execute("""
        UPDATE economy
        SET wallet=?,
            last_beg=?
        WHERE guild_id=?
        AND user_id=?
        """, (
            new_wallet,
            now.isoformat(),
            ctx.guild.id,
            ctx.author.id
        ))

        db.commit()

        responses = [

            "A generous stranger gave you some coins!",

            "Someone liked your Wattson gameplay and tipped you!",

            "You found some coins on the ground!",

            "A friendly player decided to help you!"

        ]

        embed = discord.Embed(
            title="🪙 You Got Lucky!",
            description=(
                f"{random.choice(responses)}\n\n"
                f"You received **{reward:,} coins**!"
            ),
            color=discord.Color.green()
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # DEPOSIT
    # =====================================================

    @commands.command(
        aliases=[
            "dep"
        ]
    )
    async def deposit(
        self,
        ctx,
        amount: str
    ):

        wallet, bank, _, _ = get_account(
            ctx.guild.id,
            ctx.author.id
        )

        # -------------------------------------------------
        # ALL
        # -------------------------------------------------

        if amount.lower() == "all":

            amount_value = wallet

        else:

            try:

                amount_value = int(
                    amount.replace(
                        ",",
                        ""
                    )
                )

            except ValueError:

                return await ctx.send(
                    "❌ Please enter a valid number or `all`."
                )

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if amount_value <= 0:

            return await ctx.send(
                "❌ You must deposit more than 0 coins."
            )

        if amount_value > wallet:

            return await ctx.send(
                "❌ You don't have that many coins in your wallet."
            )

        # -------------------------------------------------
        # UPDATE
        # -------------------------------------------------

        new_wallet = (
            wallet -
            amount_value
        )

        new_bank = (
            bank +
            amount_value
        )

        cursor.execute("""
        UPDATE economy
        SET wallet=?,
            bank=?
        WHERE guild_id=?
        AND user_id=?
        """, (
            new_wallet,
            new_bank,
            ctx.guild.id,
            ctx.author.id
        ))

        db.commit()

        embed = discord.Embed(
            title="🏦 Deposit Successful",
            description=(
                f"You deposited **{amount_value:,} coins** "
                f"into your bank."
            ),
            color=discord.Color.green()
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # WITHDRAW
    # =====================================================

    @commands.command(
        aliases=[
            "with"
        ]
    )
    async def withdraw(
        self,
        ctx,
        amount: str
    ):

        wallet, bank, _, _ = get_account(
            ctx.guild.id,
            ctx.author.id
        )

        # -------------------------------------------------
        # ALL
        # -------------------------------------------------

        if amount.lower() == "all":

            amount_value = bank

        else:

            try:

                amount_value = int(
                    amount.replace(
                        ",",
                        ""
                    )
                )

            except ValueError:

                return await ctx.send(
                    "❌ Please enter a valid number or `all`."
                )

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if amount_value <= 0:

            return await ctx.send(
                "❌ You must withdraw more than 0 coins."
            )

        if amount_value > bank:

            return await ctx.send(
                "❌ You don't have that many coins in your bank."
            )

        # -------------------------------------------------
        # UPDATE
        # -------------------------------------------------

        new_wallet = (
            wallet +
            amount_value
        )

        new_bank = (
            bank -
            amount_value
        )

        cursor.execute("""
        UPDATE economy
        SET wallet=?,
            bank=?
        WHERE guild_id=?
        AND user_id=?
        """, (
            new_wallet,
            new_bank,
            ctx.guild.id,
            ctx.author.id
        ))

        db.commit()

        embed = discord.Embed(
            title="💵 Withdrawal Successful",
            description=(
                f"You withdrew **{amount_value:,} coins** "
                f"from your bank."
            ),
            color=discord.Color.green()
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # PAY
    # =====================================================

    @commands.command(
        aliases=[
            "give"
        ]
    )
    async def pay(
        self,
        ctx,
        member: discord.Member,
        amount: int
    ):

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if member.bot:

            return await ctx.send(
                "❌ You can't give coins to bots."
            )

        if member.id == ctx.author.id:

            return await ctx.send(
                "❌ You can't give coins to yourself."
            )

        if amount <= 0:

            return await ctx.send(
                "❌ The amount must be greater than 0."
            )

        # -------------------------------------------------
        # GET ACCOUNTS
        # -------------------------------------------------

        sender_wallet, _, _, _ = get_account(
            ctx.guild.id,
            ctx.author.id
        )

        receiver_wallet, _, _, _ = get_account(
            ctx.guild.id,
            member.id
        )

        # -------------------------------------------------
        # CHECK MONEY
        # -------------------------------------------------

        if amount > sender_wallet:

            return await ctx.send(
                "❌ You don't have enough coins."
            )

        # -------------------------------------------------
        # UPDATE SENDER
        # -------------------------------------------------

        cursor.execute("""
        UPDATE economy
        SET wallet=?
        WHERE guild_id=?
        AND user_id=?
        """, (
            sender_wallet - amount,
            ctx.guild.id,
            ctx.author.id
        ))

        # -------------------------------------------------
        # UPDATE RECEIVER
        # -------------------------------------------------

        cursor.execute("""
        UPDATE economy
        SET wallet=?
        WHERE guild_id=?
        AND user_id=?
        """, (
            receiver_wallet + amount,
            ctx.guild.id,
            member.id
        ))

        db.commit()

        embed = discord.Embed(
            title="💸 Payment Sent!",
            description=(
                f"{ctx.author.mention} gave "
                f"{member.mention} "
                f"**{amount:,} coins**!"
            ),
            color=discord.Color.green()
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # LEADERBOARD
    # =====================================================

    @commands.command(
        name="balanceleaderboard",
        aliases=[
            "blb",
            "moneylb",
            "rich",
            "richest"
        ]
    )
    async def leaderboard(self, ctx):

        cursor.execute("""
        SELECT user_id, wallet, bank
        FROM economy
        WHERE guild_id=?
        ORDER BY (wallet + bank) DESC
        LIMIT 10
        """, (
            ctx.guild.id,
        ))

        results = cursor.fetchall()

        if not results:

            return await ctx.send(
                "❌ Nobody has any economy data yet."
            )

        medals = [
            "🥇",
            "🥈",
            "🥉"
        ]

        leaderboard_text = ""

        for position, (
            user_id,
            wallet,
            bank
        ) in enumerate(
            results,
            start=1
        ):

            member = ctx.guild.get_member(
                user_id
            )

            name = (
                member.display_name
                if member
                else f"Unknown User ({user_id})"
            )

            total = (
                wallet +
                bank
            )

            if position <= 3:

                prefix = medals[
                    position - 1
                ]

            else:

                prefix = (
                    f"**#{position}**"
                )

            leaderboard_text += (
                f"{prefix} "
                f"**{name}** — "
                f"{total:,} coins\n"
            )

        embed = discord.Embed(
            title="🏆 Economy Leaderboard",
            description=leaderboard_text,
            color=discord.Color.gold()
        )

        embed.set_footer(
            text="Total wealth = Wallet + Bank"
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # ADMIN GIVE MONEY
    # =====================================================

    @commands.command(
        aliases=[
            "addmoney",
            "givecoins"
        ]
    )
    @commands.has_permissions(
        manage_guild=True
    )
    async def givemoney(
        self,
        ctx,
        member: discord.Member,
        amount: int
    ):

        if amount <= 0:

            return await ctx.send(
                "❌ The amount must be greater than 0."
            )

        wallet, _, _, _ = get_account(
            ctx.guild.id,
            member.id
        )

        new_wallet = (
            wallet +
            amount
        )

        cursor.execute("""
        UPDATE economy
        SET wallet=?
        WHERE guild_id=?
        AND user_id=?
        """, (
            new_wallet,
            ctx.guild.id,
            member.id
        ))

        db.commit()

        embed = discord.Embed(
            title="💰 Coins Added",
            description=(
                f"Added **{amount:,} coins** "
                f"to {member.mention}."
            ),
            color=discord.Color.green()
        )

        await ctx.send(
            embed=embed
        )


    # =====================================================
    # ADMIN REMOVE MONEY
    # =====================================================

    @commands.command(
        aliases=[
            "removecoins"
        ]
    )
    @commands.has_permissions(
        manage_guild=True
    )
    async def removemoney(
        self,
        ctx,
        member: discord.Member,
        amount: int
    ):

        if amount <= 0:

            return await ctx.send(
                "❌ The amount must be greater than 0."
            )

        wallet, _, _, _ = get_account(
            ctx.guild.id,
            member.id
        )

        amount_removed = min(
            wallet,
            amount
        )

        new_wallet = (
            wallet -
            amount_removed
        )

        cursor.execute("""
        UPDATE economy
        SET wallet=?
        WHERE guild_id=?
        AND user_id=?
        """, (
            new_wallet,
            ctx.guild.id,
            member.id
        ))

        db.commit()

        embed = discord.Embed(
            title="💸 Coins Removed",
            description=(
                f"Removed **{amount_removed:,} coins** "
                f"from {member.mention}."
            ),
            color=discord.Color.red()
        )

        await ctx.send(
            embed=embed
        )


# =========================================================
# SETUP
# =========================================================

async def setup(bot):

    await bot.add_cog(
        Economy(bot)
    )