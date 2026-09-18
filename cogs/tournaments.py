"""
Grid Guardian - Apex Tournament Manager

Features:
    - Create Apex tournaments
    - Team registration
    - Team member management
    - Single-elimination bracket generation
    - Automatic byes
    - Match result reporting
    - Automatic team advancement
    - Tournament standings
    - Tournament cancellation/closing
    - Persistent SQLite storage

Commands:
    !tournament
    !tournament create <name> | <team size> | <max teams> | <description>
    !tournament list
    !tournament view <id>
    !tournament register <id> <team name>
    !tournament join <id> <team id>
    !tournament leave <id>
    !tournament teams <id>
    !tournament start <id>
    !tournament bracket <id>
    !tournament matches <id>
    !tournament report <id> <match id> <score A> <score B>
    !tournament close <id>
    !tournament cancel <id>
    !tournament help

Notes:
    - Team size must be 1-3.
    - Maximum teams must be between 2 and 32.
    - A team captain creates the team.
    - The captain can add members with !tournament join.
    - Only the captain can leave/change their team.
    - Once a tournament starts, registration is locked.
    - Single-elimination brackets are generated automatically.
"""

import math
import random
import sqlite3
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands


DB_PATH = "gridguardian.db"

MIN_TEAMS = 2
MAX_TEAMS = 32
MIN_TEAM_SIZE = 1
MAX_TEAM_SIZE = 3


# ============================================================
# DATABASE
# ============================================================

def connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = connect_db()
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS apex_tournaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER NOT NULL,
                creator_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                team_size INTEGER NOT NULL DEFAULT 3,
                max_teams INTEGER NOT NULL DEFAULT 8,
                status TEXT NOT NULL DEFAULT 'registration',
                created_at TEXT NOT NULL,
                started_at TEXT,
                closed_at TEXT,
                winner_team_id INTEGER
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tournament_teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                captain_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(tournament_id, name),
                FOREIGN KEY(tournament_id)
                    REFERENCES apex_tournaments(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tournament_members (
                team_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                joined_at TEXT NOT NULL,
                PRIMARY KEY(team_id, user_id),
                FOREIGN KEY(team_id)
                    REFERENCES tournament_teams(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS tournament_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                round_number INTEGER NOT NULL,
                match_number INTEGER NOT NULL,
                team_a_id INTEGER,
                team_b_id INTEGER,
                score_a INTEGER,
                score_b INTEGER,
                winner_team_id INTEGER,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                completed_at TEXT,
                UNIQUE(tournament_id, round_number, match_number),
                FOREIGN KEY(tournament_id)
                    REFERENCES apex_tournaments(id)
                    ON DELETE CASCADE
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tournament_guild
            ON apex_tournaments(guild_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tournament_teams
            ON tournament_teams(tournament_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_tournament_matches
            ON tournament_matches(tournament_id)
            """
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# HELPERS
# ============================================================

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_tournament(
    tournament_id: int,
    guild_id: int
) -> Optional[sqlite3.Row]:
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM apex_tournaments
            WHERE id = ?
              AND guild_id = ?
            """,
            (tournament_id, guild_id),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def get_team(
    team_id: int,
    guild_id: int
) -> Optional[sqlite3.Row]:
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.*
            FROM tournament_teams t
            JOIN apex_tournaments tr
                ON tr.id = t.tournament_id
            WHERE t.id = ?
              AND t.guild_id = ?
            """,
            (team_id, guild_id),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def get_team_members(team_id: int) -> list[sqlite3.Row]:
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, joined_at
            FROM tournament_members
            WHERE team_id = ?
            ORDER BY joined_at ASC
            """,
            (team_id,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def team_has_user(team_id: int, user_id: int) -> bool:
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM tournament_members
            WHERE team_id = ?
              AND user_id = ?
            """,
            (team_id, user_id),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def user_team_in_tournament(
    tournament_id: int,
    user_id: int
) -> Optional[sqlite3.Row]:
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT t.*
            FROM tournament_teams t
            JOIN tournament_members tm
                ON tm.team_id = t.id
            WHERE t.tournament_id = ?
              AND tm.user_id = ?
            """,
            (tournament_id, user_id),
        )
        return cursor.fetchone()
    finally:
        conn.close()


def get_teams(tournament_id: int) -> list[sqlite3.Row]:
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM tournament_teams
            WHERE tournament_id = ?
            ORDER BY id ASC
            """,
            (tournament_id,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def get_matches(tournament_id: int) -> list[sqlite3.Row]:
    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM tournament_matches
            WHERE tournament_id = ?
            ORDER BY round_number ASC, match_number ASC
            """,
            (tournament_id,),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def team_name(team_id: Optional[int]) -> str:
    if not team_id:
        return "BYE"

    conn = connect_db()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name
            FROM tournament_teams
            WHERE id = ?
            """,
            (team_id,),
        )
        row = cursor.fetchone()
        return row["name"] if row else "Unknown Team"
    finally:
        conn.close()


def format_status(status: str) -> str:
    return {
        "registration": "🟢 Registration",
        "active": "🟡 In Progress",
        "completed": "🏆 Completed",
        "closed": "⚪ Closed",
        "cancelled": "🔴 Cancelled",
    }.get(status, status.title())


def format_team(team: sqlite3.Row, member_count: int) -> str:
    return (
        f"**#{team['id']} — {team['name']}**\n"
        f"Captain: <@{team['captain_id']}>\n"
        f"Players: `{member_count}`"
    )


# ============================================================
# BRACKET ENGINE
# ============================================================

def next_power_of_two(number: int) -> int:
    return 1 if number <= 1 else 2 ** math.ceil(math.log2(number))


def bracket_round_name(round_number: int, total_rounds: int) -> str:
    distance = total_rounds - round_number

    if distance == 0:
        return "Final"

    if distance == 1:
        return "Semifinals"

    if distance == 2:
        return "Quarterfinals"

    return f"Round {round_number}"


def generate_bracket(tournament_id: int) -> tuple[int, int]:
    """
    Generates the initial single-elimination bracket.

    Returns:
        (total_rounds, number_of_matches)
    """

    teams = get_teams(tournament_id)

    if len(teams) < 2:
        raise ValueError("At least 2 teams are required.")

    random.shuffle(teams)

    bracket_size = next_power_of_two(len(teams))
    total_rounds = int(math.log2(bracket_size))

    slots: list[Optional[int]] = [team["id"] for team in teams]

    while len(slots) < bracket_size:
        slots.append(None)

    conn = connect_db()

    try:
        cursor = conn.cursor()

        # Clear old bracket if necessary.
        cursor.execute(
            """
            DELETE FROM tournament_matches
            WHERE tournament_id = ?
            """,
            (tournament_id,),
        )

        # Create every match for every round.
        round_match_counts = {}

        for round_number in range(1, total_rounds + 1):
            matches_this_round = bracket_size // (2 ** round_number)
            round_match_counts[round_number] = matches_this_round

            for match_number in range(1, matches_this_round + 1):
                cursor.execute(
                    """
                    INSERT INTO tournament_matches (
                        tournament_id,
                        round_number,
                        match_number,
                        team_a_id,
                        team_b_id,
                        status,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        tournament_id,
                        round_number,
                        match_number,
                        None,
                        None,
                        now_iso(),
                    ),
                )

        # Populate round 1.
        for index in range(0, bracket_size, 2):
            match_number = (index // 2) + 1

            team_a = slots[index]
            team_b = slots[index + 1]

            cursor.execute(
                """
                UPDATE tournament_matches
                SET team_a_id = ?,
                    team_b_id = ?
                WHERE tournament_id = ?
                  AND round_number = 1
                  AND match_number = ?
                """,
                (
                    team_a,
                    team_b,
                    tournament_id,
                    match_number,
                ),
            )

        conn.commit()

    finally:
        conn.close()

    resolve_byes(tournament_id)

    return total_rounds, bracket_size - 1


def resolve_byes(tournament_id: int) -> None:
    """
    Automatically advances teams when a bracket slot contains a BYE.
    """

    changed = True

    while changed:
        changed = False

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM tournament_matches
                WHERE tournament_id = ?
                  AND status = 'pending'
                ORDER BY round_number ASC, match_number ASC
                """,
                (tournament_id,),
            )

            matches = cursor.fetchall()

            for match in matches:
                team_a = match["team_a_id"]
                team_b = match["team_b_id"]

                if team_a is None and team_b is None:
                    continue

                # One team is present, one slot is empty.
                if (team_a is None) != (team_b is None):
                    winner = team_a or team_b

                    cursor.execute(
                        """
                        UPDATE tournament_matches
                        SET winner_team_id = ?,
                            status = 'completed',
                            score_a = ?,
                            score_b = ?,
                            completed_at = ?
                        WHERE id = ?
                          AND status = 'pending'
                        """,
                        (
                            winner,
                            1 if team_a else 0,
                            1 if team_b else 0,
                            now_iso(),
                            match["id"],
                        ),
                    )

                    if cursor.rowcount:
                        changed = True

            conn.commit()

        finally:
            conn.close()

        if changed:
            advance_completed_matches(tournament_id)


def advance_completed_matches(tournament_id: int) -> None:
    """
    Moves completed winners into the next round.
    """

    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM tournament_matches
            WHERE tournament_id = ?
              AND status = 'completed'
              AND winner_team_id IS NOT NULL
            ORDER BY round_number ASC, match_number ASC
            """,
            (tournament_id,),
        )

        completed = cursor.fetchall()

        for match in completed:
            next_round = match["round_number"] + 1

            cursor.execute(
                """
                SELECT id, team_a_id, team_b_id
                FROM tournament_matches
                WHERE tournament_id = ?
                  AND round_number = ?
                  AND match_number = ?
                """,
                (
                    tournament_id,
                    next_round,
                    ((match["match_number"] - 1) // 2) + 1,
                ),
            )

            next_match = cursor.fetchone()

            if not next_match:
                continue

            next_match_number = ((match["match_number"] - 1) // 2) + 1

            if match["match_number"] % 2 == 1:
                cursor.execute(
                    """
                    UPDATE tournament_matches
                    SET team_a_id = ?
                    WHERE id = ?
                      AND team_a_id IS NULL
                    """,
                    (
                        match["winner_team_id"],
                        next_match["id"],
                    ),
                )
            else:
                cursor.execute(
                    """
                    UPDATE tournament_matches
                    SET team_b_id = ?
                    WHERE id = ?
                      AND team_b_id IS NULL
                    """,
                    (
                        match["winner_team_id"],
                        next_match["id"],
                    )
                )

        conn.commit()

    finally:
        conn.close()

    # Resolve newly-created BYEs.
    resolve_pending_final(tournament_id)


def resolve_pending_final(tournament_id: int) -> None:
    """
    Handles newly populated matches and automatic BYEs.
    """

    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM tournament_matches
            WHERE tournament_id = ?
              AND status = 'pending'
            """,
            (tournament_id,),
        )

        pending = cursor.fetchall()

        for match in pending:
            team_a = match["team_a_id"]
            team_b = match["team_b_id"]

            if team_a and team_b:
                continue

            if team_a is None and team_b is None:
                continue

            winner = team_a or team_b

            cursor.execute(
                """
                UPDATE tournament_matches
                SET winner_team_id = ?,
                    status = 'completed',
                    score_a = ?,
                    score_b = ?,
                    completed_at = ?
                WHERE id = ?
                  AND status = 'pending'
                """,
                (
                    winner,
                    1 if team_a else 0,
                    1 if team_b else 0,
                    now_iso(),
                    match["id"],
                ),
            )

        conn.commit()

    finally:
        conn.close()

    # Continue advancing automatic winners.
    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM tournament_matches
            WHERE tournament_id = ?
              AND status = 'pending'
              AND team_a_id IS NOT NULL
              AND team_b_id IS NOT NULL
            """,
            (tournament_id,),
        )

        playable_matches = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM tournament_matches
            WHERE tournament_id = ?
              AND status = 'completed'
              AND round_number = (
                  SELECT MAX(round_number)
                  FROM tournament_matches
                  WHERE tournament_id = ?
              )
              AND winner_team_id IS NOT NULL
            """,
            (tournament_id, tournament_id),
        )

        final_completed = cursor.fetchone()[0]

    finally:
        conn.close()

    if playable_matches == 0 and final_completed == 1:
        complete_tournament(tournament_id)
    else:
        advance_completed_matches(tournament_id)


def complete_tournament(tournament_id: int) -> None:
    conn = connect_db()

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT winner_team_id
            FROM tournament_matches
            WHERE tournament_id = ?
            ORDER BY round_number DESC, match_number ASC
            LIMIT 1
            """,
            (tournament_id,),
        )

        final = cursor.fetchone()

        if not final or not final["winner_team_id"]:
            return

        cursor.execute(
            """
            UPDATE apex_tournaments
            SET status = 'completed',
                winner_team_id = ?,
                closed_at = ?
            WHERE id = ?
              AND status = 'active'
            """,
            (
                final["winner_team_id"],
                now_iso(),
                tournament_id,
            ),
        )

        conn.commit()

    finally:
        conn.close()


# ============================================================
# COG
# ============================================================

class TournamentManager(commands.Cog):
    """Apex single-elimination tournament manager."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        init_db()

    # ========================================================
    # ROOT
    # ========================================================

    @commands.group(
        name="tournament",
        aliases=["tourney", "tourny"],
        invoke_without_command=True,
    )
    @commands.guild_only()
    async def tournament(self, ctx: commands.Context):
        """Apex tournament manager."""

        embed = discord.Embed(
            title="🏆 Apex Tournament Manager",
            description=(
                "Create and manage Apex Legends team tournaments.\n\n"
                "**Quick start**\n"
                "`!tournament create Name | 3 | 8 | Description`\n"
                "`!tournament register 1 Team Name`\n"
                "`!tournament join 1 1`\n"
                "`!tournament start 1`\n"
                "`!tournament bracket 1`"
            ),
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="Commands",
            value=(
                "`!tournament create`\n"
                "`!tournament list`\n"
                "`!tournament view`\n"
                "`!tournament register`\n"
                "`!tournament join`\n"
                "`!tournament leave`\n"
                "`!tournament teams`\n"
                "`!tournament start`\n"
                "`!tournament bracket`\n"
                "`!tournament matches`\n"
                "`!tournament report`\n"
                "`!tournament close`\n"
                "`!tournament cancel`\n"
                "`!tournament help`"
            ),
            inline=False,
        )

        await ctx.send(embed=embed)

    # ========================================================
    # HELP
    # ========================================================

    @tournament.command(name="help")
    async def tournament_help(self, ctx: commands.Context):
        """Show tournament help."""

        embed = discord.Embed(
            title="🏆 Tournament Commands",
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="Create",
            value=(
                "`!tournament create Name | Team Size | Max Teams | Description`\n"
                "Example:\n"
                "`!tournament create Grid Cup | 3 | 8 | Community Apex tournament`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Registration",
            value=(
                "`!tournament register <id> <team name>`\n"
                "`!tournament join <id> <team id>`\n"
                "`!tournament leave <id>`\n"
                "`!tournament teams <id>`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Tournament",
            value=(
                "`!tournament start <id>`\n"
                "`!tournament view <id>`\n"
                "`!tournament bracket <id>`\n"
                "`!tournament matches <id>`"
            ),
            inline=False,
        )

        embed.add_field(
            name="Results",
            value=(
                "`!tournament report <id> <match id> <score A> <score B>`\n"
                "`!tournament close <id>`\n"
                "`!tournament cancel <id>`"
            ),
            inline=False,
        )

        embed.set_footer(
            text="Team size: 1-3 • Max teams: 2-32 • Format: Single Elimination"
        )

        await ctx.send(embed=embed)

    # ========================================================
    # CREATE
    # ========================================================

    @tournament.command(name="create")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def tournament_create(
        self,
        ctx: commands.Context,
        *,
        data: str,
    ):
        """
        Create a tournament.

        Format:
        Name | Team Size | Max Teams | Description
        """

        parts = [part.strip() for part in data.split("|", 3)]

        if len(parts) != 4:
            await ctx.send(
                "❌ Use:\n"
                "`!tournament create Name | Team Size | Max Teams | Description`"
            )
            return

        name, team_size_text, max_teams_text, description = parts

        if not name:
            await ctx.send("❌ Tournament name cannot be empty.")
            return

        try:
            team_size = int(team_size_text)
            max_teams = int(max_teams_text)
        except ValueError:
            await ctx.send(
                "❌ Team size and maximum teams must be numbers."
            )
            return

        if not MIN_TEAM_SIZE <= team_size <= MAX_TEAM_SIZE:
            await ctx.send(
                f"❌ Team size must be between `{MIN_TEAM_SIZE}` and "
                f"`{MAX_TEAM_SIZE}`."
            )
            return

        if not MIN_TEAMS <= max_teams <= MAX_TEAMS:
            await ctx.send(
                f"❌ Maximum teams must be between `{MIN_TEAMS}` and "
                f"`{MAX_TEAMS}`."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO apex_tournaments (
                    guild_id,
                    creator_id,
                    name,
                    description,
                    team_size,
                    max_teams,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'registration', ?)
                """,
                (
                    ctx.guild.id,
                    ctx.author.id,
                    name[:100],
                    description[:1000],
                    team_size,
                    max_teams,
                    now_iso(),
                ),
            )

            tournament_id = cursor.lastrowid

            conn.commit()

        finally:
            conn.close()

        embed = discord.Embed(
            title="🏆 Tournament Created",
            color=discord.Color.green(),
        )

        embed.add_field(
            name="Tournament",
            value=f"**#{tournament_id} — {name}**",
            inline=False,
        )

        embed.add_field(
            name="Format",
            value="Single Elimination",
            inline=True,
        )

        embed.add_field(
            name="Team Size",
            value=str(team_size),
            inline=True,
        )

        embed.add_field(
            name="Max Teams",
            value=str(max_teams),
            inline=True,
        )

        embed.add_field(
            name="Description",
            value=description or "No description provided.",
            inline=False,
        )

        embed.set_footer(
            text=f"Created by {ctx.author.display_name}"
        )

        await ctx.send(embed=embed)

    # ========================================================
    # LIST
    # ========================================================

    @tournament.command(name="list")
    @commands.guild_only()
    async def tournament_list(self, ctx: commands.Context):
        """List tournaments."""

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM apex_tournaments
                WHERE guild_id = ?
                ORDER BY id DESC
                LIMIT 15
                """,
                (ctx.guild.id,),
            )

            tournaments = cursor.fetchall()

        finally:
            conn.close()

        if not tournaments:
            await ctx.send("🏆 There are no tournaments yet.")
            return

        embed = discord.Embed(
            title="🏆 Apex Tournaments",
            color=discord.Color.gold(),
        )

        lines = []

        for tournament in tournaments:
            teams = len(get_teams(tournament["id"]))

            lines.append(
                f"**#{tournament['id']} — {tournament['name']}**\n"
                f"{format_status(tournament['status'])} • "
                f"`{teams}/{tournament['max_teams']}` teams"
            )

        embed.description = "\n\n".join(lines)

        await ctx.send(embed=embed)

    # ========================================================
    # VIEW
    # ========================================================

    @tournament.command(name="view")
    @commands.guild_only()
    async def tournament_view(
        self,
        ctx: commands.Context,
        tournament_id: int,
    ):
        """View tournament details."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        teams = get_teams(tournament_id)

        creator = ctx.guild.get_member(tournament["creator_id"])

        embed = discord.Embed(
            title=f"🏆 #{tournament['id']} — {tournament['name']}",
            description=tournament["description"] or "No description.",
            color=discord.Color.gold(),
        )

        embed.add_field(
            name="Status",
            value=format_status(tournament["status"]),
            inline=True,
        )

        embed.add_field(
            name="Teams",
            value=f"`{len(teams)}/{tournament['max_teams']}`",
            inline=True,
        )

        embed.add_field(
            name="Team Size",
            value=str(tournament["team_size"]),
            inline=True,
        )

        embed.add_field(
            name="Format",
            value="Single Elimination",
            inline=True,
        )

        embed.add_field(
            name="Creator",
            value=creator.mention if creator else f"<@{tournament['creator_id']}>",
            inline=True,
        )

        if tournament["winner_team_id"]:
            embed.add_field(
                name="🏆 Winner",
                value=f"**{team_name(tournament['winner_team_id'])}**",
                inline=True,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # REGISTER
    # ========================================================

    @tournament.command(name="register")
    @commands.guild_only()
    async def tournament_register(
        self,
        ctx: commands.Context,
        tournament_id: int,
        *,
        team_name_input: str,
    ):
        """Create and register a team."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        if tournament["status"] != "registration":
            await ctx.send(
                "❌ Registration for this tournament is closed."
            )
            return

        team_name_input = team_name_input.strip()

        if not team_name_input:
            await ctx.send("❌ Team name cannot be empty.")
            return

        teams = get_teams(tournament_id)

        if len(teams) >= tournament["max_teams"]:
            await ctx.send("❌ This tournament is already full.")
            return

        existing_team = user_team_in_tournament(
            tournament_id,
            ctx.author.id,
        )

        if existing_team:
            await ctx.send(
                f"❌ You're already registered with "
                f"**{existing_team['name']}**."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO tournament_teams (
                    tournament_id,
                    guild_id,
                    name,
                    captain_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    tournament_id,
                    ctx.guild.id,
                    team_name_input[:80],
                    ctx.author.id,
                    now_iso(),
                ),
            )

            team_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO tournament_members (
                    team_id,
                    user_id,
                    joined_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    team_id,
                    ctx.author.id,
                    now_iso(),
                ),
            )

            conn.commit()

        except sqlite3.IntegrityError:
            conn.rollback()
            await ctx.send(
                "❌ A team with that name already exists in this tournament."
            )
            return

        finally:
            conn.close()

        await ctx.send(
            f"✅ **{team_name_input}** has been registered!\n"
            f"Team ID: `#{team_id}`\n"
            f"Captain: {ctx.author.mention}\n\n"
            f"Players can join with:\n"
            f"`!tournament join {tournament_id} {team_id}`"
        )

    # ========================================================
    # JOIN
    # ========================================================

    @tournament.command(name="join")
    @commands.guild_only()
    async def tournament_join(
        self,
        ctx: commands.Context,
        tournament_id: int,
        team_id: int,
    ):
        """Join an existing team."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        if tournament["status"] != "registration":
            await ctx.send(
                "❌ You can't join a team after the tournament starts."
            )
            return

        team = get_team(
            team_id,
            ctx.guild.id,
        )

        if not team or team["tournament_id"] != tournament_id:
            await ctx.send("❌ Team not found in that tournament.")
            return

        existing_team = user_team_in_tournament(
            tournament_id,
            ctx.author.id,
        )

        if existing_team:
            await ctx.send(
                f"❌ You're already on **{existing_team['name']}**."
            )
            return

        members = get_team_members(team_id)

        if len(members) >= tournament["team_size"]:
            await ctx.send("❌ That team is already full.")
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO tournament_members (
                    team_id,
                    user_id,
                    joined_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    team_id,
                    ctx.author.id,
                    now_iso(),
                ),
            )

            conn.commit()

        except sqlite3.IntegrityError:
            conn.rollback()
            await ctx.send("❌ You're already on this team.")
            return

        finally:
            conn.close()

        await ctx.send(
            f"✅ {ctx.author.mention} joined **{team['name']}**!"
        )

    # ========================================================
    # LEAVE
    # ========================================================

    @tournament.command(name="leave")
    @commands.guild_only()
    async def tournament_leave(
        self,
        ctx: commands.Context,
        tournament_id: int,
    ):
        """Leave a tournament team."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        if tournament["status"] != "registration":
            await ctx.send(
                "❌ You can't leave after the tournament starts."
            )
            return

        team = user_team_in_tournament(
            tournament_id,
            ctx.author.id,
        )

        if not team:
            await ctx.send(
                "❌ You're not registered for this tournament."
            )
            return

        if team["captain_id"] == ctx.author.id:
            await ctx.send(
                "❌ Captains cannot leave their team. "
                "The team must be deleted by tournament staff."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM tournament_members
                WHERE team_id = ?
                  AND user_id = ?
                """,
                (
                    team["id"],
                    ctx.author.id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"✅ You left **{team['name']}**."
        )

    # ========================================================
    # TEAMS
    # ========================================================

    @tournament.command(name="teams")
    @commands.guild_only()
    async def tournament_teams(
        self,
        ctx: commands.Context,
        tournament_id: int,
    ):
        """List tournament teams."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        teams = get_teams(tournament_id)

        if not teams:
            await ctx.send("🏆 No teams have registered yet.")
            return

        embed = discord.Embed(
            title=f"🏆 Teams — {tournament['name']}",
            color=discord.Color.gold(),
        )

        for team in teams:
            members = get_team_members(team["id"])

            member_text = ", ".join(
                f"<@{member['user_id']}>"
                for member in members
            )

            embed.add_field(
                name=f"#{team['id']} — {team['name']}",
                value=(
                    f"Captain: <@{team['captain_id']}>\n"
                    f"Players: {member_text or 'None'}\n"
                    f"Size: `{len(members)}/{tournament['team_size']}`"
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    # ========================================================
    # START
    # ========================================================

    @tournament.command(name="start")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def tournament_start(
        self,
        ctx: commands.Context,
        tournament_id: int,
    ):
        """Start a tournament."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        if tournament["status"] != "registration":
            await ctx.send(
                "❌ This tournament cannot be started."
            )
            return

        teams = get_teams(tournament_id)

        if len(teams) < 2:
            await ctx.send(
                "❌ At least 2 teams are required to start."
            )
            return

        incomplete = []

        for team in teams:
            members = get_team_members(team["id"])

            if len(members) != tournament["team_size"]:
                incomplete.append(
                    f"**{team['name']}** "
                    f"(`{len(members)}/{tournament['team_size']}`)"
                )

        if incomplete:
            await ctx.send(
                "❌ Every team must be full before the tournament starts.\n\n"
                + "\n".join(incomplete)
            )
            return

        try:
            total_rounds, match_count = generate_bracket(
                tournament_id
            )
        except ValueError as exc:
            await ctx.send(f"❌ {exc}")
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE apex_tournaments
                SET status = 'active',
                    started_at = ?
                WHERE id = ?
                """,
                (
                    now_iso(),
                    tournament_id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        # Handle any automatic byes.
        resolve_byes(tournament_id)

        await ctx.send(
            f"🏆 **{tournament['name']} has started!**\n\n"
            f"Teams: `{len(teams)}`\n"
            f"Rounds: `{total_rounds}`\n"
            f"Total bracket matches: `{match_count}`\n\n"
            f"Use `!tournament bracket {tournament_id}` "
            f"to view the bracket."
        )

    # ========================================================
    # BRACKET
    # ========================================================

    @tournament.command(name="bracket")
    @commands.guild_only()
    async def tournament_bracket(
        self,
        ctx: commands.Context,
        tournament_id: int,
    ):
        """Display the tournament bracket."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        matches = get_matches(tournament_id)

        if not matches:
            await ctx.send(
                "❌ The bracket hasn't been generated yet."
            )
            return

        max_round = max(
            match["round_number"]
            for match in matches
        )

        embed = discord.Embed(
            title=f"🏆 Bracket — {tournament['name']}",
            color=discord.Color.gold(),
        )

        for round_number in range(1, max_round + 1):
            round_matches = [
                match
                for match in matches
                if match["round_number"] == round_number
            ]

            lines = []

            for match in round_matches:
                a = team_name(match["team_a_id"])
                b = team_name(match["team_b_id"])

                if match["status"] == "completed":
                    if match["winner_team_id"] == match["team_a_id"]:
                        a = f"**{a}**"
                    elif match["winner_team_id"] == match["team_b_id"]:
                        b = f"**{b}**"

                    score_a = (
                        match["score_a"]
                        if match["score_a"] is not None
                        else "-"
                    )

                    score_b = (
                        match["score_b"]
                        if match["score_b"] is not None
                        else "-"
                    )

                    lines.append(
                        f"`#{match['id']}` {a} `{score_a}` — "
                        f"`{score_b}` {b}"
                    )

                else:
                    lines.append(
                        f"`#{match['id']}` {a} — {b}"
                    )

            embed.add_field(
                name=bracket_round_name(
                    round_number,
                    max_round,
                ),
                value="\n".join(lines) or "No matches",
                inline=False,
            )

        embed.set_footer(
            text="Bold team = winner • Match IDs are used for reporting"
        )

        await ctx.send(embed=embed)

    # ========================================================
    # MATCHES
    # ========================================================

    @tournament.command(name="matches")
    @commands.guild_only()
    async def tournament_matches(
        self,
        ctx: commands.Context,
        tournament_id: int,
    ):
        """Show active matches."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        matches = get_matches(tournament_id)

        active = [
            match
            for match in matches
            if match["status"] == "pending"
            and match["team_a_id"]
            and match["team_b_id"]
        ]

        if not active:
            await ctx.send(
                "🏆 There are no active matches right now."
            )
            return

        embed = discord.Embed(
            title=f"🎮 Active Matches — {tournament['name']}",
            color=discord.Color.orange(),
        )

        lines = []

        for match in active:
            lines.append(
                f"**Match #{match['id']}**\n"
                f"{team_name(match['team_a_id'])} vs "
                f"{team_name(match['team_b_id'])}"
            )

        embed.description = "\n\n".join(lines)

        await ctx.send(embed=embed)

    # ========================================================
    # REPORT
    # ========================================================

    @tournament.command(name="report")
    @commands.guild_only()
    async def tournament_report(
        self,
        ctx: commands.Context,
        tournament_id: int,
        match_id: int,
        score_a: int,
        score_b: int,
    ):
        """Report a match result."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        if tournament["status"] != "active":
            await ctx.send(
                "❌ This tournament is not currently active."
            )
            return

        if score_a < 0 or score_b < 0:
            await ctx.send(
                "❌ Scores cannot be negative."
            )
            return

        if score_a == score_b:
            await ctx.send(
                "❌ Ties are not allowed in single elimination. "
                "Report a winning score."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT *
                FROM tournament_matches
                WHERE id = ?
                  AND tournament_id = ?
                """,
                (
                    match_id,
                    tournament_id,
                ),
            )

            match = cursor.fetchone()

        finally:
            conn.close()

        if not match:
            await ctx.send("❌ Match not found.")
            return

        if match["status"] != "pending":
            await ctx.send(
                "❌ That match has already been completed."
            )
            return

        if not match["team_a_id"] or not match["team_b_id"]:
            await ctx.send(
                "❌ That match isn't ready to be played."
            )
            return

        # Determine winner.
        if score_a > score_b:
            winner = match["team_a_id"]
        else:
            winner = match["team_b_id"]

        # Permission:
        # staff can report anything.
        # Otherwise, only a member of either team can report.
        is_staff = ctx.author.guild_permissions.manage_guild

        if not is_staff:
            allowed = (
                team_has_user(
                    match["team_a_id"],
                    ctx.author.id,
                )
                or
                team_has_user(
                    match["team_b_id"],
                    ctx.author.id,
                )
            )

            if not allowed:
                await ctx.send(
                    "❌ Only tournament staff or players "
                    "in this match can report the result."
                )
                return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE tournament_matches
                SET score_a = ?,
                    score_b = ?,
                    winner_team_id = ?,
                    status = 'completed',
                    completed_at = ?
                WHERE id = ?
                  AND status = 'pending'
                """,
                (
                    score_a,
                    score_b,
                    winner,
                    now_iso(),
                    match_id,
                ),
            )

            if cursor.rowcount == 0:
                conn.rollback()
                await ctx.send(
                    "❌ That match was already updated."
                )
                return

            conn.commit()

        finally:
            conn.close()

        # Advance winner.
        advance_completed_matches(tournament_id)

        updated = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if updated and updated["status"] == "completed":
            await ctx.send(
                f"🏆 **Tournament complete!**\n"
                f"Winner: **{team_name(updated['winner_team_id'])}**"
            )
            return

        await ctx.send(
            f"✅ Match `#{match_id}` recorded.\n"
            f"Winner: **{team_name(winner)}**"
        )

    # ========================================================
    # CLOSE
    # ========================================================

    @tournament.command(name="close")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def tournament_close(
        self,
        ctx: commands.Context,
        tournament_id: int,
    ):
        """Close a tournament."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        if tournament["status"] in {
            "closed",
            "cancelled",
        }:
            await ctx.send(
                "❌ This tournament is already closed."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE apex_tournaments
                SET status = 'closed',
                    closed_at = ?
                WHERE id = ?
                """,
                (
                    now_iso(),
                    tournament_id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"⚪ Tournament **#{tournament_id}** has been closed."
        )

    # ========================================================
    # CANCEL
    # ========================================================

    @tournament.command(name="cancel")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_guild=True)
    async def tournament_cancel(
        self,
        ctx: commands.Context,
        tournament_id: int,
    ):
        """Cancel a tournament."""

        tournament = get_tournament(
            tournament_id,
            ctx.guild.id,
        )

        if not tournament:
            await ctx.send("❌ Tournament not found.")
            return

        if tournament["status"] in {
            "completed",
            "cancelled",
        }:
            await ctx.send(
                "❌ This tournament cannot be cancelled."
            )
            return

        conn = connect_db()

        try:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE apex_tournaments
                SET status = 'cancelled',
                    closed_at = ?
                WHERE id = ?
                """,
                (
                    now_iso(),
                    tournament_id,
                ),
            )

            conn.commit()

        finally:
            conn.close()

        await ctx.send(
            f"🔴 Tournament **#{tournament_id}** has been cancelled."
        )

    # ========================================================
    # ERROR HANDLING
    # ========================================================

    @tournament.error
    async def tournament_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError,
    ):
        if isinstance(
            error,
            commands.MissingPermissions,
        ):
            await ctx.send(
                "❌ You need **Manage Server** permission to do that."
            )
            return

        if isinstance(
            error,
            commands.MissingRequiredArgument,
        ):
            await ctx.send(
                "❌ You're missing a required argument.\n"
                "Use `!tournament help` for the command format."
            )
            return

        if isinstance(
            error,
            commands.BadArgument,
        ):
            await ctx.send(
                "❌ One of the values you entered isn't valid.\n"
                "Use `!tournament help` for the command format."
            )
            return

        raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(TournamentManager(bot))