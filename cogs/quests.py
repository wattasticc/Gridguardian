import sqlite3
import time
import random

import discord
from discord.ext import commands


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# ==========================================================
# DATABASE
# ==========================================================

db = sqlite3.connect("gridguardian.db")
cursor = db.cursor()


# ----------------------------------------------------------
# QUEST PROGRESS
# ----------------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS quests (
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    quest_id INTEGER NOT NULL,
    quest_name TEXT NOT NULL,
    target INTEGER NOT NULL,
    progress INTEGER DEFAULT 0,
    reward INTEGER NOT NULL,
    claimed INTEGER DEFAULT 0,
    created_at REAL NOT NULL,
    PRIMARY KEY (user_id, guild_id, quest_id)
)
""")


# ----------------------------------------------------------
# QUEST DATABASE COMPATIBILITY
#
# Fixes older versions of the quests table that were created
# before the quest_id column existed.
# ----------------------------------------------------------

cursor.execute("PRAGMA table_info(quests)")

quest_columns = [
    column[1]
    for column in cursor.fetchall()
]


if "quest_id" not in quest_columns:

    print(
        "⚠️ Old quests table detected. "
        "Recreating quests database table..."
    )

    cursor.execute(
        "DROP TABLE IF EXISTS quests"
    )

    cursor.execute("""
    CREATE TABLE quests (
        user_id INTEGER NOT NULL,
        guild_id INTEGER NOT NULL,
        quest_id INTEGER NOT NULL,
        quest_name TEXT NOT NULL,
        target INTEGER NOT NULL,
        progress INTEGER DEFAULT 0,
        reward INTEGER NOT NULL,
        claimed INTEGER DEFAULT 0,
        created_at REAL NOT NULL,
        PRIMARY KEY (
            user_id,
            guild_id,
            quest_id
        )
    )
    """)

    db.commit()

    print(
        "✅ Quests table recreated successfully."
    )


# ----------------------------------------------------------
# ECONOMY TABLE SAFETY CHECK
# ----------------------------------------------------------

cursor.execute("""
CREATE TABLE IF NOT EXISTS economy (
    user_id INTEGER NOT NULL,
    guild_id INTEGER NOT NULL,
    balance INTEGER DEFAULT 0,
    bank INTEGER DEFAULT 0,
    last_work REAL DEFAULT 0,
    PRIMARY KEY (user_id, guild_id)
)
""")


db.commit()


# ==========================================================
# QUEST SETTINGS
# ==========================================================

QUEST_RESET_TIME = 60 * 60 * 24


QUEST_TEMPLATES = [

    {
        "name": "💬 Send 10 Messages",
        "target": 10,
        "reward": 100
    },

    {
        "name": "💬 Send 25 Messages",
        "target": 25,
        "reward": 250
    },

    {
        "name": "💬 Send 50 Messages",
        "target": 50,
        "reward": 500
    },

    {
        "name": "🔥 Send 75 Messages",
        "target": 75,
        "reward": 750
    },

    {
        "name": "⚡ Send 100 Messages",
        "target": 100,
        "reward": 1000
    }

]


# ==========================================================
# HELPER FUNCTIONS
# ==========================================================

def ensure_economy_user(user_id, guild_id):

    cursor.execute("""
    INSERT OR IGNORE INTO economy (
        user_id,
        guild_id,
        balance,
        bank,
        last_work
    )
    VALUES (?, ?, 0, 0, 0)
    """, (
        user_id,
        guild_id
    ))

    db.commit()


def add_coins(user_id, guild_id, amount):

    ensure_economy_user(
        user_id,
        guild_id
    )

    cursor.execute("""
    UPDATE economy
    SET balance = balance + ?
    WHERE user_id=?
    AND guild_id=?
    """, (
        amount,
        user_id,
        guild_id
    ))

    db.commit()


# ==========================================================
# CHECK IF USER HAS QUESTS
# ==========================================================

def get_user_quests(user_id, guild_id):

    cursor.execute("""
    SELECT
        quest_id,
        quest_name,
        target,
        progress,
        reward,
        claimed,
        created_at
    FROM quests
    WHERE user_id=?
    AND guild_id=?
    ORDER BY quest_id
    """, (
        user_id,
        guild_id
    ))

    return cursor.fetchall()


# ==========================================================
# DELETE OLD QUESTS
# ==========================================================

def reset_quests(user_id, guild_id):

    cursor.execute("""
    DELETE FROM quests
    WHERE user_id=?
    AND guild_id=?
    """, (
        user_id,
        guild_id
    ))

    db.commit()


# ==========================================================
# CREATE NEW QUESTS
# ==========================================================

def create_quests(user_id, guild_id):

    current_time = time.time()

    selected_quests = random.sample(
        QUEST_TEMPLATES,
        3
    )

    for quest_id, quest in enumerate(
        selected_quests,
        start=1
    ):

        cursor.execute("""
        INSERT INTO quests (
            user_id,
            guild_id,
            quest_id,
            quest_name,
            target,
            progress,
            reward,
            claimed,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, 0, ?, 0, ?)
        """, (
            user_id,
            guild_id,
            quest_id,
            quest["name"],
            quest["target"],
            quest["reward"],
            current_time
        ))

    db.commit()


# ==========================================================
# ENSURE USER HAS ACTIVE QUESTS
# ==========================================================

def ensure_quests(user_id, guild_id):

    quests = get_user_quests(
        user_id,
        guild_id
    )

    # ------------------------------------------------------
    # NO QUESTS
    # ------------------------------------------------------

    if not quests:

        create_quests(
            user_id,
            guild_id
        )

        return get_user_quests(
            user_id,
            guild_id
        )

    # ------------------------------------------------------
    # CHECK RESET TIME
    # ------------------------------------------------------

    created_at = quests[0][6]

    current_time = time.time()

    if current_time - created_at >= QUEST_RESET_TIME:

        reset_quests(
            user_id,
            guild_id
        )

        create_quests(
            user_id,
            guild_id
        )

    return get_user_quests(
        user_id,
        guild_id
    )


# ==========================================================
# FORMAT TIME
# ==========================================================

def format_time(seconds):

    seconds = max(
        0,
        int(seconds)
    )

    hours, remainder = divmod(
        seconds,
        3600
    )

    minutes, seconds = divmod(
        remainder,
        60
    )

    if hours > 0:

        return (
            f"{hours}h "
            f"{minutes}m"
        )

    return (
        f"{minutes}m "
        f"{seconds}s"
    )


# ==========================================================
# QUESTS COG
# ==========================================================

class Quests(commands.Cog):

    def __init__(self, bot):

        self.bot = bot


    # ======================================================
    # MESSAGE TRACKING
    # ======================================================

    @commands.Cog.listener()
    async def on_message(self, message):

        # --------------------------------------------------
        # IGNORE BOTS
        # --------------------------------------------------

        if message.author.bot:

            return

        # --------------------------------------------------
        # IGNORE DMS
        # --------------------------------------------------

        if message.guild is None:

            return

        user_id = message.author.id
        guild_id = message.guild.id

        # --------------------------------------------------
        # MAKE SURE QUESTS EXIST
        # --------------------------------------------------

        quests = ensure_quests(
            user_id,
            guild_id
        )

        # --------------------------------------------------
        # UPDATE EVERY UNCLAIMED QUEST
        # --------------------------------------------------

        for quest in quests:

            quest_id = quest[0]
            target = quest[2]
            progress = quest[3]
            claimed = quest[5]

            # Don't continue completed quests.
            if claimed:

                continue

            # Don't increase past target.
            if progress >= target:

                continue

            cursor.execute("""
            UPDATE quests
            SET progress = progress + 1
            WHERE user_id=?
            AND guild_id=?
            AND quest_id=?
            """, (
                user_id,
                guild_id,
                quest_id
            ))

        db.commit()


    # ======================================================
    # VIEW QUESTS
    # ======================================================

    @commands.command(
        aliases=["quest"]
    )
    async def quests(self, ctx):

        user_id = ctx.author.id
        guild_id = ctx.guild.id

        quests = ensure_quests(
            user_id,
            guild_id
        )

        # --------------------------------------------------
        # RESET TIMER
        # --------------------------------------------------

        created_at = quests[0][6]

        time_remaining = (
            QUEST_RESET_TIME
            - (
                time.time()
                - created_at
            )
        )

        # --------------------------------------------------
        # EMBED
        # --------------------------------------------------

        embed = discord.Embed(
            title="📋 Daily Quests",
            description=(
                "Complete your quests to earn coins!\n\n"
                f"🔄 **Resets in:** "
                f"{format_time(time_remaining)}"
            ),
            color=EMBED_COLOR
        )

        # --------------------------------------------------
        # ADD QUESTS
        # --------------------------------------------------

        for quest in quests:

            quest_id = quest[0]
            quest_name = quest[1]
            target = quest[2]
            progress = quest[3]
            reward = quest[4]
            claimed = quest[5]

            # ------------------------------------------------
            # PROGRESS BAR
            # ------------------------------------------------

            percentage = (
                progress
                / target
            )

            filled = int(
                percentage * 10
            )

            filled = min(
                filled,
                10
            )

            empty = (
                10
                - filled
            )

            progress_bar = (
                "🟦" * filled
                + "⬛" * empty
            )

            # ------------------------------------------------
            # STATUS
            # ------------------------------------------------

            if claimed:

                status = "✅ **Claimed**"

            elif progress >= target:

                status = (
                    "🎉 **Completed! "
                    f"Use `!claimquest {quest_id}`**"
                )

            else:

                status = (
                    f"📈 {progress}/{target}"
                )

            embed.add_field(
                name=(
                    f"Quest {quest_id} — "
                    f"{quest_name}"
                ),
                value=(
                    f"{progress_bar}\n"
                    f"{status}\n"
                    f"💰 Reward: "
                    f"**{reward:,} coins**"
                ),
                inline=False
            )

        embed.set_footer(
            text=(
                "Grid Guardian • "
                "Complete quests and earn rewards"
            )
        )

        await ctx.send(
            embed=embed
        )


    # ======================================================
    # CLAIM QUEST
    # ======================================================

    @commands.command(
        aliases=["claim"]
    )
    async def claimquest(
        self,
        ctx,
        quest_id: int
    ):

        user_id = ctx.author.id
        guild_id = ctx.guild.id

        # --------------------------------------------------
        # VALID QUEST NUMBER
        # --------------------------------------------------

        if quest_id not in [1, 2, 3]:

            return await ctx.send(
                "❌ Please choose quest "
                "`1`, `2`, or `3`."
            )

        # --------------------------------------------------
        # ENSURE QUESTS EXIST
        # --------------------------------------------------

        ensure_quests(
            user_id,
            guild_id
        )

        # --------------------------------------------------
        # GET QUEST
        # --------------------------------------------------

        cursor.execute("""
        SELECT
            quest_name,
            target,
            progress,
            reward,
            claimed
        FROM quests
        WHERE user_id=?
        AND guild_id=?
        AND quest_id=?
        """, (
            user_id,
            guild_id,
            quest_id
        ))

        quest = cursor.fetchone()

        if quest is None:

            return await ctx.send(
                "❌ That quest doesn't exist."
            )

        quest_name = quest[0]
        target = quest[1]
        progress = quest[2]
        reward = quest[3]
        claimed = quest[4]

        # --------------------------------------------------
        # ALREADY CLAIMED
        # --------------------------------------------------

        if claimed:

            return await ctx.send(
                "❌ You already claimed "
                "this quest."
            )

        # --------------------------------------------------
        # NOT COMPLETE
        # --------------------------------------------------

        if progress < target:

            remaining = (
                target
                - progress
            )

            return await ctx.send(
                f"❌ You haven't completed "
                f"this quest yet.\n"
                f"You need **{remaining} more "
                f"messages**."
            )

        # --------------------------------------------------
        # GIVE REWARD
        # --------------------------------------------------

        add_coins(
            user_id,
            guild_id,
            reward
        )

        # --------------------------------------------------
        # MARK CLAIMED
        # --------------------------------------------------

        cursor.execute("""
        UPDATE quests
        SET claimed=1
        WHERE user_id=?
        AND guild_id=?
        AND quest_id=?
        """, (
            user_id,
            guild_id,
            quest_id
        ))

        db.commit()

        # --------------------------------------------------
        # SUCCESS EMBED
        # --------------------------------------------------

        embed = discord.Embed(
            title="🎉 Quest Reward Claimed!",
            description=(
                f"You completed:\n"
                f"**{quest_name}**\n\n"
                f"💰 You earned "
                f"**{reward:,} coins!**"
            ),
            color=discord.Color.green()
        )

        embed.set_thumbnail(
            url=ctx.author.display_avatar.url
        )

        embed.set_footer(
            text="Grid Guardian Daily Quests"
        )

        await ctx.send(
            embed=embed
        )


    # ======================================================
    # QUEST STATUS
    # ======================================================

    @commands.command()
    async def queststatus(
        self,
        ctx,
        member: discord.Member = None
    ):

        member = member or ctx.author

        quests = ensure_quests(
            member.id,
            ctx.guild.id
        )

        completed = 0
        claimed = 0

        for quest in quests:

            target = quest[2]
            progress = quest[3]
            quest_claimed = quest[5]

            if progress >= target:

                completed += 1

            if quest_claimed:

                claimed += 1

        embed = discord.Embed(
            title=(
                f"📊 {member.display_name}'s "
                "Quest Progress"
            ),
            color=EMBED_COLOR
        )

        embed.set_thumbnail(
            url=member.display_avatar.url
        )

        embed.add_field(
            name="📋 Total Quests",
            value="3",
            inline=True
        )

        embed.add_field(
            name="🎉 Completed",
            value=str(completed),
            inline=True
        )

        embed.add_field(
            name="💰 Claimed",
            value=str(claimed),
            inline=True
        )

        await ctx.send(
            embed=embed
        )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Quests(bot)
    )