import asyncio
import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urljoin

import aiohttp
import discord
from discord.ext import commands, tasks


EMBED_COLOR = discord.Color.from_rgb(80, 220, 255)


# ==========================================================
# CONFIGURATION
# ==========================================================

UPDATE_INTERVAL_MINUTES = 60


# Official EA class pages.
#
# Each page contains Legends belonging ONLY to that class.
# This prevents Legends from being assigned the wrong class
# because of nearby text from another section.
#
# ==========================================================

EA_CLASS_URLS = {

    "Assault": (
        "https://www.ea.com/games/apex-legends/"
        "apex-legends/game-objects/characters-hub/"
        "assault-hub"
    ),

    "Controller": (
        "https://www.ea.com/games/apex-legends/"
        "apex-legends/game-objects/characters-hub/"
        "controller-hub"
    ),

    "Recon": (
        "https://www.ea.com/games/apex-legends/"
        "apex-legends/game-objects/characters-hub/"
        "recon-hub"
    ),

    "Skirmisher": (
        "https://www.ea.com/games/apex-legends/"
        "apex-legends/game-objects/characters-hub/"
        "skirmisher-hub"
    ),

    "Support": (
        "https://www.ea.com/games/apex-legends/"
        "apex-legends/game-objects/characters-hub/"
        "support-hub"
    )
}


# ==========================================================
# CURRENT VERIFIED LEGEND ROSTER
#
# Used as:
#
# 1. A fallback if EA cannot be reached.
# 2. A correction system for old incorrect database entries.
# 3. A minimum validation roster.
#
# ==========================================================

CURRENT_LEGENDS = {

    # Assault
    "Ballistic": "Assault",
    "Bangalore": "Assault",
    "Fuse": "Assault",
    "Mad Maggie": "Assault",
    "Revenant": "Assault",

    # Controller
    "Catalyst": "Controller",
    "Caustic": "Controller",
    "Rampart": "Controller",
    "Wattson": "Controller",

    # Recon
    "Bloodhound": "Recon",
    "Crypto": "Recon",
    "Seer": "Recon",
    "Sparrow": "Recon",
    "Valkyrie": "Recon",
    "Vantage": "Recon",

    # Skirmisher
    "Alter": "Skirmisher",
    "Ash": "Skirmisher",
    "Axle": "Skirmisher",
    "Horizon": "Skirmisher",
    "Octane": "Skirmisher",
    "Pathfinder": "Skirmisher",
    "Wraith": "Skirmisher",

    # Support
    "Conduit": "Support",
    "Gibraltar": "Support",
    "Lifeline": "Support",
    "Loba": "Support",
    "Mirage": "Support",
    "Newcastle": "Support"
}


# ==========================================================
# LEGEND ABILITY NAMES
#
# This gives !legend useful information without allowing
# incorrect class data to affect the command.
#
# ==========================================================

LEGEND_ABILITIES = {

    "Alter": {
        "passive": "Gift from the Rift",
        "tactical": "Void Passage",
        "ultimate": "Void Nexus"
    },

    "Ash": {
        "passive": "Charged Knock",
        "tactical": "Arc Snare",
        "ultimate": "Phase Breach"
    },

    "Axle": {
        "passive": "Drift",
        "tactical": "Nitro Gate",
        "ultimate": "Kickstart"
    },

    "Ballistic": {
        "passive": "Sling",
        "tactical": "Whistler",
        "ultimate": "Tempest"
    },

    "Bangalore": {
        "passive": "Double Time",
        "tactical": "Smoke Launcher",
        "ultimate": "Rolling Thunder"
    },

    "Bloodhound": {
        "passive": "Tracker",
        "tactical": "Eye of the Allfather",
        "ultimate": "Allfather's Cloak"
    },

    "Catalyst": {
        "passive": "Barricade",
        "tactical": "Piercing Spikes",
        "ultimate": "Dark Veil"
    },

    "Caustic": {
        "passive": "Nox Vision",
        "tactical": "Nox Gas Trap",
        "ultimate": "Nox Gas Grenade"
    },

    "Conduit": {
        "passive": "Savior's Speed",
        "tactical": "Radiant Transfer",
        "ultimate": "Energy Barricade"
    },

    "Crypto": {
        "passive": "Neurolink",
        "tactical": "Surveillance Drone",
        "ultimate": "Drone EMP"
    },

    "Fuse": {
        "passive": "Grenadier",
        "tactical": "Knuckle Cluster",
        "ultimate": "The Motherlode"
    },

    "Gibraltar": {
        "passive": "Gun Shield",
        "tactical": "Dome of Protection",
        "ultimate": "Defensive Bombardment"
    },

    "Horizon": {
        "passive": "Spacewalk",
        "tactical": "Gravity Lift",
        "ultimate": "Black Hole"
    },

    "Lifeline": {
        "passive": "Combat Glide",
        "tactical": "D.O.C. Heal Drone",
        "ultimate": "D.O.C. Halo"
    },

    "Loba": {
        "passive": "Eye for Quality",
        "tactical": "Burglar's Best Friend",
        "ultimate": "Black Market Boutique"
    },

    "Mad Maggie": {
        "passive": "Warlord's Ire",
        "tactical": "Riot Drill",
        "ultimate": "Wrecking Ball"
    },

    "Mirage": {
        "passive": "Now You See Me",
        "tactical": "Psyche Out",
        "ultimate": "Life of the Party"
    },

    "Newcastle": {
        "passive": "Retrieve the Wounded",
        "tactical": "Mobile Shield",
        "ultimate": "Castle Wall"
    },

    "Octane": {
        "passive": "Swift Mend",
        "tactical": "Stim",
        "ultimate": "Launch Pad"
    },

    "Pathfinder": {
        "passive": "Insider Knowledge",
        "tactical": "Grappling Hook",
        "ultimate": "Zipline Gun"
    },

    "Rampart": {
        "passive": "Battle Modder",
        "tactical": "Amped Cover",
        "ultimate": "Mobile Minigun Sheila"
    },

    "Revenant": {
        "passive": "Assassin's Instinct",
        "tactical": "Shadow Pounce",
        "ultimate": "Forged Shadows"
    },

    "Seer": {
        "passive": "Heart Seeker",
        "tactical": "Focus of Attention",
        "ultimate": "Exhibit"
    },

    "Sparrow": {
        "passive": "Double Jump",
        "tactical": "Tracker Dart",
        "ultimate": "Stinger Bolt"
    },

    "Valkyrie": {
        "passive": "VTOL Jets",
        "tactical": "Missile Swarm",
        "ultimate": "Skyward Dive"
    },

    "Vantage": {
        "passive": "Spotter's Lens",
        "tactical": "Echo Relocation",
        "ultimate": "Sniper's Mark"
    },

    "Wattson": {
        "passive": "Spark of Genius",
        "tactical": "Perimeter Security",
        "ultimate": "Interception Pylon"
    },

    "Wraith": {
        "passive": "Voices from the Void",
        "tactical": "Into the Void",
        "ultimate": "Dimensional Rift"
    }
}


# ==========================================================
# DATABASE
# ==========================================================

db = sqlite3.connect(
    "gridguardian.db",
    check_same_thread=False
)

cursor = db.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS apex_legends (
    name TEXT PRIMARY KEY,
    class TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
""")


db.commit()


# ==========================================================
# LEGENDS COG
# ==========================================================

class Legends(commands.Cog):

    def __init__(self, bot):

        self.bot = bot

        self.update_lock = asyncio.Lock()

        # Correct any previously saved incorrect classes.
        #
        # This specifically fixes problems such as Vantage
        # accidentally being stored as Controller.

        self.repair_known_legend_classes()

        self.legend_update_loop.start()


    # ======================================================
    # COG UNLOAD
    # ======================================================

    def cog_unload(self):

        self.legend_update_loop.cancel()


    # ======================================================
    # NORMALIZE NAME
    # ======================================================

    @staticmethod
    def normalize_name(name):

        return re.sub(
            r"[^a-z0-9]",
            "",
            name.lower()
        )


    # ======================================================
    # DATABASE HELPERS
    # ======================================================

    def get_database_legends(self):

        cursor.execute("""
        SELECT name, class
        FROM apex_legends
        ORDER BY name ASC
        """)

        rows = cursor.fetchall()


        return {
            name: legend_class
            for name, legend_class in rows
        }


    def save_legends(self, legends):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()


        cursor.execute("""
        DELETE FROM apex_legends
        """)


        for name, legend_class in legends.items():

            cursor.execute("""
            INSERT OR REPLACE INTO apex_legends (
                name,
                class,
                updated_at
            )
            VALUES (?, ?, ?)
            """, (
                name,
                legend_class,
                timestamp
            ))


        db.commit()


    # ======================================================
    # REPAIR KNOWN CLASSES
    #
    # This fixes old incorrect database information without
    # deleting newly discovered Legends.
    # ======================================================

    def repair_known_legend_classes(self):

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()


        for name, correct_class in (
            CURRENT_LEGENDS.items()
        ):

            cursor.execute("""
            INSERT INTO apex_legends (
                name,
                class,
                updated_at
            )
            VALUES (?, ?, ?)

            ON CONFLICT(name)
            DO UPDATE SET
                class = excluded.class,
                updated_at = excluded.updated_at
            """, (
                name,
                correct_class,
                timestamp
            ))


        db.commit()


        print(
            "🎮 Verified Legend classes loaded."
        )


    # ======================================================
    # CURRENT LEGENDS
    # ======================================================

    def get_current_legends(self):

        database_legends = (
            self.get_database_legends()
        )


        if database_legends:

            return database_legends


        return CURRENT_LEGENDS.copy()


    # ======================================================
    # SLUG TO LEGEND NAME
    #
    # Converts:
    #
    # mad-maggie -> Mad Maggie
    # bloodhound -> Bloodhound
    #
    # ======================================================

    @staticmethod
    def slug_to_name(slug):

        special_names = {

            "mad-maggie": "Mad Maggie"

        }


        slug = slug.lower().strip()


        if slug in special_names:

            return special_names[slug]


        words = slug.split("-")


        return " ".join(
            word.capitalize()
            for word in words
            if word
        )


    # ======================================================
    # EXTRACT LEGEND LINKS
    #
    # Each official class page is searched for links leading
    # to individual Legend pages.
    #
    # ======================================================

    def extract_legends_from_html(
        self,
        html,
        page_url
    ):

        legends = set()


        pattern = (
            r'href=["\']'
            r'([^"\']*characters-hub/'
            r'([a-z0-9-]+)'
            r'[^"\']*)'
            r'["\']'
        )


        matches = re.findall(
            pattern,
            html,
            flags=re.IGNORECASE
        )


        ignored_slugs = {

            "characters-hub",

            "assault-hub",
            "controller-hub",
            "recon-hub",
            "skirmisher-hub",
            "support-hub"

        }


        for href, slug in matches:

            slug = slug.lower().strip()


            if slug in ignored_slugs:

                continue


            # Make sure the URL is valid.

            full_url = urljoin(
                page_url,
                href
            )


            if "characters-hub" not in full_url:

                continue


            name = self.slug_to_name(
                slug
            )


            if name:

                legends.add(name)


        return legends


    # ======================================================
    # FETCH ONE OFFICIAL CLASS PAGE
    # ======================================================

    async def fetch_class_legends(
        self,
        session,
        legend_class,
        url
    ):

        try:

            async with session.get(
                url,
                allow_redirects=True
            ) as response:

                if response.status != 200:

                    print(
                        f"⚠️ Could not check "
                        f"{legend_class}. "
                        f"EA returned HTTP "
                        f"{response.status}."
                    )

                    return None


                html = await response.text()


        except Exception as error:

            print(
                f"⚠️ Could not check "
                f"{legend_class}: {error}"
            )

            return None


        legends = (
            self.extract_legends_from_html(
                html,
                url
            )
        )


        if not legends:

            print(
                f"⚠️ No Legends found on "
                f"EA's {legend_class} page."
            )

            return None


        return legends


    # ======================================================
    # FETCH OFFICIAL ROSTER
    #
    # IMPORTANT:
    #
    # Each class page is handled independently.
    #
    # This means a Legend found on:
    #
    # Recon page -> Recon
    #
    # Controller page -> Controller
    #
    # etc.
    #
    # ======================================================

    async def fetch_official_legends(self):

        headers = {

            "User-Agent": (
                "Mozilla/5.0 "
                "(compatible; GridGuardian/1.0)"
            ),

            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            )

        }


        timeout = aiohttp.ClientTimeout(
            total=30
        )


        official_legends = {}


        try:

            async with aiohttp.ClientSession(
                timeout=timeout,
                headers=headers
            ) as session:

                for legend_class, url in (
                    EA_CLASS_URLS.items()
                ):

                    legends = (
                        await self.fetch_class_legends(
                            session,
                            legend_class,
                            url
                        )
                    )


                    # Do not use partial official data.
                    #
                    # If even one class page fails, the
                    # existing database stays untouched.

                    if legends is None:

                        return None


                    for name in legends:

                        official_legends[
                            name
                        ] = legend_class


        except Exception as error:

            print(
                f"⚠️ Official Legend update failed: "
                f"{error}"
            )

            return None


        # --------------------------------------------------
        # VALIDATION
        # --------------------------------------------------

        # Prevent bad website parsing from overwriting the
        # database with a tiny or broken roster.

        if len(official_legends) < 20:

            print(
                "⚠️ Official roster returned too few "
                "Legends."
            )

            print(
                f"⚠️ Found "
                f"{len(official_legends)} Legends."
            )

            return None


        # Make sure all five classes were actually found.

        found_classes = set(
            official_legends.values()
        )


        required_classes = set(
            EA_CLASS_URLS.keys()
        )


        if found_classes != required_classes:

            print(
                "⚠️ Official roster did not contain "
                "all five classes."
            )

            return None


        return official_legends


    # ======================================================
    # UPDATE DATABASE
    # ======================================================

    async def update_legends(self):

        async with self.update_lock:

            official_legends = (
                await self.fetch_official_legends()
            )


            if official_legends is None:

                return False


            current_legends = (
                self.get_current_legends()
            )


            # --------------------------------------------------
            # CHECK FOR CHANGES
            # --------------------------------------------------

            if current_legends == official_legends:

                print(
                    "🎮 Apex Legends roster is already "
                    "up to date."
                )

                return False


            # --------------------------------------------------
            # DETECT NEW LEGENDS
            # --------------------------------------------------

            current_normalized = {

                self.normalize_name(name)

                for name in current_legends
            }


            official_normalized = {

                self.normalize_name(name)

                for name in official_legends
            }


            new_legends = [

                name

                for name in official_legends

                if (
                    self.normalize_name(name)
                    not in current_normalized
                )
            ]


            removed_legends = [

                name

                for name in current_legends

                if (
                    self.normalize_name(name)
                    not in official_normalized
                )
            ]


            # --------------------------------------------------
            # SAVE VERIFIED ROSTER
            # --------------------------------------------------

            self.save_legends(
                official_legends
            )


            print(
                "🎮 Apex Legends roster automatically "
                "updated!"
            )


            print(
                f"📊 Current Legends: "
                f"{len(official_legends)}"
            )


            if new_legends:

                print(
                    "➕ New Legends detected: "
                    + ", ".join(
                        sorted(new_legends)
                    )
                )


            if removed_legends:

                print(
                    "➖ Removed Legends detected: "
                    + ", ".join(
                        sorted(removed_legends)
                    )
                )


            return True


    # ======================================================
    # AUTOMATIC UPDATE LOOP
    # ======================================================

    @tasks.loop(
        minutes=UPDATE_INTERVAL_MINUTES
    )
    async def legend_update_loop(self):

        await self.update_legends()


    @legend_update_loop.before_loop
    async def before_legend_update_loop(self):

        await self.bot.wait_until_ready()


    # ======================================================
    # LEGEND LOOKUP
    # ======================================================

    @commands.command(
        name="legend",
        aliases=[
            "apexlegend",
            "legendinfo"
        ]
    )
    async def legend(
        self,
        ctx,
        *,
        legend_name=None
    ):

        if not legend_name:

            return await ctx.send(
                "❌ Please provide a Legend.\n\n"
                "**Example:** `!legend wattson`\n"
                "Use `!legends` to see every Legend."
            )


        legends = self.get_current_legends()


        search = self.normalize_name(
            legend_name
        )


        selected_name = None


        for name in legends:

            if (
                self.normalize_name(name)
                == search
            ):

                selected_name = name

                break


        if selected_name is None:

            return await ctx.send(
                f"❌ I couldn't find "
                f"**{legend_name}**.\n\n"
                "Use `!legends` to see the full roster."
            )


        legend_class = legends[
            selected_name
        ]


        ability_data = LEGEND_ABILITIES.get(
            selected_name
        )


        embed = discord.Embed(
            title=f"🎮 {selected_name}",
            color=EMBED_COLOR
        )


        embed.add_field(
            name="🏷️ Class",
            value=legend_class,
            inline=False
        )


        if ability_data:

            embed.add_field(
                name="🟢 Passive",
                value=ability_data["passive"],
                inline=False
            )


            embed.add_field(
                name="⚡ Tactical",
                value=ability_data["tactical"],
                inline=False
            )


            embed.add_field(
                name="🔴 Ultimate",
                value=ability_data["ultimate"],
                inline=False
            )


        else:

            embed.add_field(
                name="ℹ️ Ability Information",
                value=(
                    "This Legend was automatically "
                    "detected from the official roster.\n\n"
                    "Ability information has not been "
                    "added to Grid Guardian yet."
                ),
                inline=False
            )


        embed.set_footer(
            text=(
                "Grid Guardian • Apex Legends"
            )
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # LEGENDS LIST
    # ======================================================

    @commands.command(
        name="legends",
        aliases=[
            "apexlegends"
        ]
    )
    async def legends(self, ctx):

        legends = self.get_current_legends()


        classes = {

            "⚔️ Assault": [],

            "🏰 Controller": [],

            "🛰️ Recon": [],

            "💨 Skirmisher": [],

            "🛡️ Support": []

        }


        for name, legend_class in (
            legends.items()
        ):

            if legend_class == "Assault":

                classes[
                    "⚔️ Assault"
                ].append(name)


            elif legend_class == "Controller":

                classes[
                    "🏰 Controller"
                ].append(name)


            elif legend_class == "Recon":

                classes[
                    "🛰️ Recon"
                ].append(name)


            elif legend_class == "Skirmisher":

                classes[
                    "💨 Skirmisher"
                ].append(name)


            elif legend_class == "Support":

                classes[
                    "🛡️ Support"
                ].append(name)


        embed = discord.Embed(
            title="🎮 Apex Legends",

            description=(
                f"**{len(legends)} Legends Available**\n\n"
                "The official EA roster is checked "
                "automatically every hour.\n\n"
                "Use `!legend <name>` for more "
                "information.\n"
                "**Example:** `!legend wattson`"
            ),

            color=EMBED_COLOR
        )


        for class_name, legend_list in (
            classes.items()
        ):

            if not legend_list:

                continue


            embed.add_field(

                name=class_name,

                value="\n".join(

                    f"• {name}"

                    for name in sorted(
                        legend_list
                    )

                ),

                inline=False

            )


        embed.set_footer(
            text=(
                "Grid Guardian • Automatically Updated"
            )
        )


        await ctx.send(
            embed=embed
        )


    # ======================================================
    # FORCE UPDATE COMMAND
    # ======================================================

    @commands.command(
        name="updatelegends",
        aliases=[
            "refreshlegends"
        ]
    )
    @commands.has_permissions(
        administrator=True
    )
    async def updatelegends(self, ctx):

        checking_message = await ctx.send(
            "🔄 Checking the official Apex Legends roster..."
        )


        updated = await self.update_legends()


        if updated:

            await checking_message.edit(
                content=(
                    "✅ The Apex Legends roster was updated!"
                )
            )


        else:

            await checking_message.edit(
                content=(
                    "✅ No roster changes were detected, "
                    "or the official source could not be "
                    "reached."
                )
            )


# ==========================================================
# SETUP
# ==========================================================

async def setup(bot):

    await bot.add_cog(
        Legends(bot)
    )