import discord
from discord.ext import commands
import sqlite3
import random
import time

DB_PATH = "gridguardian.db"

WEAPONS = {
    "assault_rifles": [
        ("R-301 Carbine", "Light"), ("VK-47 Flatline", "Heavy"),
        ("Hemlok Burst AR", "Heavy"), ("Havoc Rifle", "Energy"),
        ("Nemesis Burst AR", "Energy"),
    ],
    "smgs": [
        ("Alternator SMG", "Light"), ("R-99", "Light"),
        ("Volt SMG", "Energy"), ("C.A.R. SMG", "Light/Heavy"),
        ("Prowler Burst PDW", "Heavy"),
    ],
    "lmg": [
        ("M600 Spitfire", "Light"), ("Devotion LMG", "Energy"),
        ("L-STAR EMG", "Energy"), ("Rampage LMG", "Heavy"),
    ],
    "marksman": [
        ("G7 Scout", "Light"), ("30-30 Repeater", "Heavy"),
        ("Triple Take", "Energy"), ("Bocek Compound Bow", "Arrows"),
    ],
    "snipers": [
        ("Longbow DMR", "Sniper"), ("Sentinel", "Sniper"),
        ("Charge Rifle", "Sniper"),
    ],
    "shotguns": [
        ("EVA-8 Auto", "Shotgun"), ("Mastiff Shotgun", "Shotgun"),
        ("Peacekeeper", "Shotgun"), ("Mozambique Shotgun", "Shotgun"),
    ],
    "pistols": [
        ("RE-45 Auto", "Light"), ("Wingman", "Heavy"),
    ],
}

ALL_WEAPONS = [w for category in WEAPONS.values() for w in category]
WEAPON_CATEGORY = {
    weapon: category
    for category, weapons in WEAPONS.items()
    for weapon, ammo in weapons
}

LEGENDS = [
    "Wattson", "Wraith", "Horizon", "Pathfinder", "Bangalore", "Bloodhound",
    "Lifeline", "Newcastle", "Catalyst", "Conduit", "Valkyrie", "Crypto",
    "Loba", "Fuse", "Mad Maggie", "Rampart", "Caustic", "Gibraltar",
    "Revenant", "Seer", "Alter", "Ash", "Ballistic", "Mirage",
]


class Loadout(commands.Cog):
    """Apex Loadout Generator for Grid Guardian."""

    def __init__(self, bot):
        self.bot = bot
        self.db = sqlite3.connect(DB_PATH)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS saved_loadouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                legend TEXT NOT NULL,
                weapon_one TEXT NOT NULL,
                weapon_two TEXT NOT NULL,
                created_at REAL NOT NULL
            )
        """)
        self.db.commit()
        self.active_loadouts = {}

    def cog_unload(self):
        self.db.close()

    def random_weapon(self, category=None):
        return random.choice(WEAPONS[category] if category else ALL_WEAPONS)

    def choose_weapon_pair(self, mode="normal"):
        if mode == "ranked":
            cats1 = ["assault_rifles", "smgs", "marksman", "lmg", "shotguns"]
            cats2 = ["assault_rifles", "smgs", "marksman", "snipers", "shotguns", "pistols"]
        elif mode == "wattson":
            cats1 = ["assault_rifles", "smgs", "shotguns", "marksman"]
            cats2 = ["smgs", "shotguns", "pistols", "assault_rifles"]
        else:
            cats1 = list(WEAPONS)
            cats2 = list(WEAPONS)

        one = self.random_weapon(random.choice(cats1))
        two = self.random_weapon(random.choice(cats2))
        attempts = 0
        while two[0] == one[0] and attempts < 10:
            two = self.random_weapon(random.choice(cats2))
            attempts += 1
        return one, two

    def build_loadout(self, mode="normal"):
        one, two = self.choose_weapon_pair(mode)
        return {
            "legend": "Wattson" if mode == "wattson" else random.choice(LEGENDS),
            "weapon_one": one[0], "ammo_one": one[1],
            "weapon_two": two[0], "ammo_two": two[1],
            "mode": mode,
        }

    def get_weapon(self, name):
        name = name.lower().strip()
        for weapon, ammo in ALL_WEAPONS:
            if weapon.lower() == name:
                return weapon, ammo
        return None

    def category_display(self, category):
        return {
            "assault_rifles": "Assault Rifles", "smgs": "SMGs", "lmg": "LMGs",
            "marksman": "Marksman", "snipers": "Snipers",
            "shotguns": "Shotguns", "pistols": "Pistols",
        }.get(category, category.title())

    def make_embed(self, loadout, title="⚡ Apex Loadout"):
        embed = discord.Embed(
            title=title,
            description="Your randomized Apex loadout.",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="🧑 Legend", value=loadout["legend"], inline=True)
        embed.add_field(
            name="🔫 Weapon 1",
            value=f"**{loadout['weapon_one']}**\n{loadout['ammo_one']} ammo",
            inline=True,
        )
        embed.add_field(
            name="🔫 Weapon 2",
            value=f"**{loadout['weapon_two']}**\n{loadout['ammo_two']} ammo",
            inline=True,
        )
        embed.add_field(name="🎮 Mode", value=loadout["mode"].title(), inline=True)
        embed.set_footer(text="Grid Guardian • Apex Loadout System")
        return embed

    @commands.group(name="loadout", invoke_without_command=True, case_insensitive=True)
    async def loadout(self, ctx):
        """Generate a random Apex loadout."""
        generated = self.build_loadout()
        self.active_loadouts[ctx.author.id] = generated
        await ctx.send(embed=self.make_embed(generated, "🎲 Random Apex Loadout"))

    @loadout.command(name="random")
    async def random_loadout(self, ctx):
        generated = self.build_loadout()
        self.active_loadouts[ctx.author.id] = generated
        await ctx.send(embed=self.make_embed(generated, "🎲 Random Apex Loadout"))

    @loadout.command(name="ranked")
    async def ranked(self, ctx):
        generated = self.build_loadout("ranked")
        self.active_loadouts[ctx.author.id] = generated
        await ctx.send(embed=self.make_embed(generated, "🏆 Ranked Loadout"))

    @loadout.command(name="pubs")
    async def pubs(self, ctx):
        generated = self.build_loadout("pubs")
        self.active_loadouts[ctx.author.id] = generated
        await ctx.send(embed=self.make_embed(generated, "🔥 Pubs Loadout"))

    @loadout.command(name="wattson")
    async def wattson(self, ctx):
        generated = self.build_loadout("wattson")
        self.active_loadouts[ctx.author.id] = generated
        await ctx.send(embed=self.make_embed(generated, "⚡ Wattson Loadout"))

    @loadout.command(name="challenge")
    async def challenge(self, ctx):
        generated = self.build_loadout("challenge")
        self.active_loadouts[ctx.author.id] = generated
        challenges = [
            "Get 1 knock with each weapon.",
            "Get 500 damage using only your two assigned weapons.",
            "Survive until top 5 while keeping both weapons.",
            "Use your second weapon for your first full fight.",
            "Get a knock with your weaker weapon before your stronger one.",
            "Get 3 knocks without changing your legend.",
        ]
        embed = self.make_embed(generated, "🎯 Apex Loadout Challenge")
        embed.add_field(name="🎯 Challenge", value=random.choice(challenges), inline=False)
        await ctx.send(embed=embed)

    @loadout.command(name="weapon")
    async def weapon(self, ctx, *, weapon_name=None):
        if not weapon_name:
            weapon, ammo = self.random_weapon()
            embed = discord.Embed(title="🎲 Random Weapon", color=discord.Color.orange())
            embed.add_field(name="Weapon", value=f"**{weapon}**", inline=False)
            embed.add_field(name="Ammo / Type", value=ammo, inline=True)
            embed.add_field(
                name="Category",
                value=self.category_display(WEAPON_CATEGORY[weapon]),
                inline=True,
            )
            await ctx.send(embed=embed)
            return

        result = self.get_weapon(weapon_name)
        if not result:
            await ctx.send("❌ I couldn't find that weapon in the Grid Guardian database.")
            return

        weapon, ammo = result
        embed = discord.Embed(title=f"🔫 {weapon}", color=discord.Color.orange())
        embed.add_field(name="Category", value=self.category_display(WEAPON_CATEGORY[weapon]), inline=True)
        embed.add_field(name="Ammo / Type", value=ammo, inline=True)
        await ctx.send(embed=embed)

    @loadout.command(name="reroll")
    async def reroll(self, ctx, slot="all"):
        user_id = ctx.author.id
        if user_id not in self.active_loadouts:
            self.active_loadouts[user_id] = self.build_loadout()

        loadout = self.active_loadouts[user_id]
        slot = slot.lower()

        if slot in ("all", "everything"):
            loadout = self.build_loadout(loadout.get("mode", "normal"))
        elif slot in ("legend", "character"):
            choices = [x for x in LEGENDS if x != loadout["legend"]]
            loadout["legend"] = random.choice(choices)
        elif slot in ("1", "one", "weapon1", "primary"):
            choices = [x for x in ALL_WEAPONS if x[0] != loadout["weapon_one"]]
            weapon = random.choice(choices)
            loadout["weapon_one"], loadout["ammo_one"] = weapon
        elif slot in ("2", "two", "weapon2", "secondary"):
            choices = [x for x in ALL_WEAPONS if x[0] != loadout["weapon_two"]]
            weapon = random.choice(choices)
            loadout["weapon_two"], loadout["ammo_two"] = weapon
        else:
            await ctx.send("❌ Use `!loadout reroll`, `!loadout reroll legend`, `!loadout reroll 1`, or `!loadout reroll 2`.")
            return

        self.active_loadouts[user_id] = loadout
        await ctx.send(embed=self.make_embed(loadout, "🔄 Rerolled Loadout"))

    @loadout.command(name="save")
    async def save(self, ctx, *, name=None):
        if not ctx.guild:
            await ctx.send("❌ Saved loadouts can only be used inside a server.")
            return
        if not name:
            await ctx.send("❌ Give the loadout a name. Example: `!loadout save Ranked Main`")
            return
        if ctx.author.id not in self.active_loadouts:
            self.active_loadouts[ctx.author.id] = self.build_loadout()

        loadout = self.active_loadouts[ctx.author.id]
        name = name[:50]
        self.db.execute(
            """INSERT INTO saved_loadouts
            (user_id, guild_id, name, legend, weapon_one, weapon_two, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (ctx.author.id, ctx.guild.id, name, loadout["legend"],
             loadout["weapon_one"], loadout["weapon_two"], time.time()),
        )
        self.db.commit()
        await ctx.send(f"✅ Saved your current loadout as **{discord.utils.escape_markdown(name)}**.")

    @loadout.command(name="saved")
    async def saved(self, ctx):
        if not ctx.guild:
            await ctx.send("❌ Saved loadouts can only be used inside a server.")
            return

        rows = self.db.execute(
            """SELECT id, name, legend, weapon_one, weapon_two
            FROM saved_loadouts WHERE user_id = ? AND guild_id = ?
            ORDER BY id DESC LIMIT 10""",
            (ctx.author.id, ctx.guild.id),
        ).fetchall()

        if not rows:
            await ctx.send("📭 You don't have any saved loadouts yet. Use `!loadout` then `!loadout save <name>`.")
            return

        embed = discord.Embed(title="📚 Your Saved Loadouts", color=discord.Color.blurple())
        for loadout_id, name, legend, weapon_one, weapon_two in rows:
            embed.add_field(
                name=f"#{loadout_id} • {name}",
                value=f"🧑 {legend}\n🔫 {weapon_one}\n🔫 {weapon_two}",
                inline=False,
            )
        embed.set_footer(text="Showing your 10 most recent saved loadouts.")
        await ctx.send(embed=embed)

    @loadout.command(name="delete")
    async def delete(self, ctx, loadout_id: int = None):
        if not ctx.guild:
            await ctx.send("❌ Saved loadouts can only be used inside a server.")
            return
        if loadout_id is None:
            await ctx.send("❌ Use `!loadout saved` first, then provide the saved loadout ID.")
            return

        row = self.db.execute(
            "SELECT id, name FROM saved_loadouts WHERE id = ? AND user_id = ? AND guild_id = ?",
            (loadout_id, ctx.author.id, ctx.guild.id),
        ).fetchone()

        if not row:
            await ctx.send("❌ I couldn't find a saved loadout with that ID.")
            return

        self.db.execute(
            "DELETE FROM saved_loadouts WHERE id = ? AND user_id = ? AND guild_id = ?",
            (loadout_id, ctx.author.id, ctx.guild.id),
        )
        self.db.commit()
        await ctx.send(f"🗑️ Deleted saved loadout **#{row[0]} — {discord.utils.escape_markdown(row[1])}**.")

    @loadout.command(name="list")
    async def list_weapons(self, ctx):
        embed = discord.Embed(
            title="🔫 Apex Weapon Database",
            description="Weapons currently included in Grid Guardian.",
            color=discord.Color.orange(),
        )
        for category, weapons in WEAPONS.items():
            embed.add_field(
                name=self.category_display(category),
                value="\n".join(f"• {weapon} — {ammo}" for weapon, ammo in weapons),
                inline=False,
            )
        embed.set_footer(text="Use !loadout weapon for a random weapon or weapon information.")
        await ctx.send(embed=embed)

    @loadout.command(name="help")
    async def loadout_help(self, ctx):
        embed = discord.Embed(
            title="⚡ Grid Guardian Loadout System",
            description="Apex loadouts, rerolls, challenges, and saved builds.",
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="Commands",
            value=(
                "`!loadout` — Random loadout\n"
                "`!loadout random` — Random loadout\n"
                "`!loadout ranked` — Ranked loadout\n"
                "`!loadout pubs` — Pubs loadout\n"
                "`!loadout wattson` — Wattson loadout\n"
                "`!loadout challenge` — Loadout + challenge\n"
                "`!loadout weapon` — Random weapon\n"
                "`!loadout weapon <name>` — Weapon info\n"
                "`!loadout reroll` — Reroll everything\n"
                "`!loadout reroll legend` — Reroll legend\n"
                "`!loadout reroll 1` — Reroll weapon 1\n"
                "`!loadout reroll 2` — Reroll weapon 2\n"
                "`!loadout save <name>` — Save active loadout\n"
                "`!loadout saved` — View saved loadouts\n"
                "`!loadout delete <id>` — Delete saved loadout\n"
                "`!loadout list` — List weapons"
            ),
            inline=False,
        )
        embed.set_footer(text="Grid Guardian • Apex Systems")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Loadout(bot))
