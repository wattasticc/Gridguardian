"""
Grid Guardian - Daily Quest Events

Central event helpers used by other cogs to update daily quest progress.

Supported events:
    - practice
    - coach
    - setup
    - upvote
    - challenge

This module is intentionally separate from Discord commands so other
cogs can safely report progress without creating circular imports.
"""

import sqlite3
import random
from datetime import datetime, timezone

DB_PATH = "gridguardian.db"


# ============================================================
# DATABASE
# ============================================================

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ============================================================
# DAILY QUEST DEFINITIONS
# ============================================================

QUEST_POOL = [
    {
        "type": "practice",
        "name": "Grid Practice",
        "description": "Complete Wattson practice.",
        "target": 1,
        "reward_xp": 50,
    },
    {
        "type": "practice",
        "name": "Electrical Training",
        "description": "Complete Wattson practice 2 times.",
        "target": 2,
        "reward_xp": 100,
    },
    {
        "type": "coach",
        "name": "Coach's Apprentice",
        "description": "Complete a Wattson Coach lesson.",
        "target": 1,
        "reward_xp": 75,
    },
    {
        "type": "coach",
        "name": "Study the Grid",
        "description": "Complete 2 Wattson Coach lessons.",
        "target": 2,
        "reward_xp": 125,
    },
    {
        "type": "setup",
        "name": "Grid Architect",
        "description": "Create a Wattson setup.",
        "target": 1,
        "reward_xp": 75,
    },
    {
        "type": "setup",
        "name": "Master Planner",
        "description": "Create 2 Wattson setups.",
        "target": 2,
        "reward_xp": 125,
    },
    {
        "type": "upvote",
        "name": "Share the Knowledge",
        "description": "Receive an upvote on one of your Wattson setups.",
        "target": 1,
        "reward_xp": 75,
    },
    {
        "type": "upvote",
        "name": "Community Favorite",
        "description": "Receive 3 setup upvotes.",
        "target": 3,
        "reward_xp": 150,
    },
    {
        "type": "challenge",
        "name": "Challenge Accepted",
        "description": "Complete a daily or weekly challenge.",
        "target": 1,
        "reward_xp": 100,
    },
    {
        "type": "challenge",
        "name": "Challenge Grinder",
        "description": "Complete 2 challenges.",
        "target": 2,
        "reward_xp": 150,
    },
]


# ============================================================
# TABLE CHECK
# ============================================================

def _daily_quests_table_exists(cursor: sqlite3.Cursor) -> bool:
    cursor.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'daily_quests'
        """
    )

    return cursor.fetchone() is not None


# ============================================================
# COLUMN CHECK
# ============================================================

def _get_columns(cursor: sqlite3.Cursor) -> set[str]:
    cursor.execute("PRAGMA table_info(daily_quests)")
    return {row["name"] for row in cursor.fetchall()}


# ============================================================
# CREATE TODAY'S QUESTS
# ============================================================

def _ensure_daily_quests(
    cursor: sqlite3.Cursor,
    guild_id: int,
    user_id: int,
) -> bool:
    """
    Make sure the user has today's daily quests.

    If today's quests already exist, nothing happens.

    If the user has no quests for today, three quests are generated.
    """

    today = _today()

    cursor.execute(
        """
        SELECT COUNT(*) AS count
        FROM daily_quests
        WHERE guild_id = ?
          AND user_id = ?
          AND quest_date = ?
        """,
        (guild_id, user_id, today),
    )

    row = cursor.fetchone()

    if row and row["count"] >= 3:
        return True

    # Remove incomplete/partial generation from today so we don't
    # accidentally leave a user with an incorrect number of quests.
    cursor.execute(
        """
        DELETE FROM daily_quests
        WHERE guild_id = ?
          AND user_id = ?
          AND quest_date = ?
        """,
        (guild_id, user_id, today),
    )

    selected = random.sample(
        QUEST_POOL,
        min(3, len(QUEST_POOL)),
    )

    columns = _get_columns(cursor)

    for quest in selected:
        # Support the expected schema used by the daily quest system.
        if {
            "guild_id",
            "user_id",
            "quest_date",
            "quest_type",
            "name",
            "description",
            "target",
            "progress",
            "claimed",
        }.issubset(columns):
            cursor.execute(
                """
                INSERT INTO daily_quests (
                    guild_id,
                    user_id,
                    quest_date,
                    quest_type,
                    name,
                    description,
                    target,
                    progress,
                    claimed
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0)
                """,
                (
                    guild_id,
                    user_id,
                    today,
                    quest["type"],
                    quest["name"],
                    quest["description"],
                    quest["target"],
                ),
            )

        else:
            # Fall back to the simpler schema if the table contains
            # reward_xp or other fields from an older version.
            available_columns = {
                "guild_id",
                "user_id",
                "quest_date",
                "quest_type",
                "name",
                "description",
                "target",
                "progress",
                "reward_xp",
                "claimed",
            }

            insert_columns = [
                column
                for column in [
                    "guild_id",
                    "user_id",
                    "quest_date",
                    "quest_type",
                    "name",
                    "description",
                    "target",
                    "progress",
                    "reward_xp",
                    "claimed",
                ]
                if column in columns and column in available_columns
            ]

            values = []

            for column in insert_columns:
                if column == "guild_id":
                    values.append(guild_id)
                elif column == "user_id":
                    values.append(user_id)
                elif column == "quest_date":
                    values.append(today)
                elif column == "quest_type":
                    values.append(quest["type"])
                elif column == "name":
                    values.append(quest["name"])
                elif column == "description":
                    values.append(quest["description"])
                elif column == "target":
                    values.append(quest["target"])
                elif column == "progress":
                    values.append(0)
                elif column == "reward_xp":
                    values.append(quest["reward_xp"])
                elif column == "claimed":
                    values.append(0)

            if insert_columns:
                placeholders = ", ".join(["?"] * len(insert_columns))

                cursor.execute(
                    f"""
                    INSERT INTO daily_quests (
                        {", ".join(insert_columns)}
                    )
                    VALUES ({placeholders})
                    """,
                    values,
                )

    return True


# ============================================================
# UPDATE QUEST PROGRESS
# ============================================================

def update_daily_quest(
    guild_id: int,
    user_id: int,
    quest_type: str,
    amount: int = 1,
) -> bool:
    """
    Update today's daily quest progress for a user.

    Returns:
        True  -> progress was updated
        False -> nothing was updated
    """

    if not guild_id or not user_id:
        return False

    if amount <= 0:
        return False

    valid_types = {
        "practice",
        "coach",
        "setup",
        "upvote",
        "challenge",
    }

    if quest_type not in valid_types:
        return False

    conn = _connect()

    try:
        cursor = conn.cursor()

        # If the daily quest table doesn't exist yet, don't crash
        # the main bot feature that triggered the event.
        if not _daily_quests_table_exists(cursor):
            return False

        # Make sure today's quests exist before trying to update them.
        if not _ensure_daily_quests(
            cursor,
            guild_id,
            user_id,
        ):
            return False

        today = _today()

        cursor.execute(
            """
            UPDATE daily_quests
            SET progress = MIN(target, progress + ?)
            WHERE guild_id = ?
              AND user_id = ?
              AND quest_date = ?
              AND quest_type = ?
              AND claimed = 0
            """,
            (
                amount,
                guild_id,
                user_id,
                today,
                quest_type,
            ),
        )

        changed = cursor.rowcount > 0

        conn.commit()

        return changed

    except sqlite3.Error:
        conn.rollback()
        return False

    finally:
        conn.close()


# ============================================================
# EVENT HELPERS
# ============================================================

def record_practice(
    guild_id: int,
    user_id: int,
) -> bool:
    """
    Record one completed Wattson practice session.
    """

    return update_daily_quest(
        guild_id,
        user_id,
        "practice",
        1,
    )


def record_coach_completion(
    guild_id: int,
    user_id: int,
) -> bool:
    """
    Record one completed Wattson Coach lesson.
    """

    return update_daily_quest(
        guild_id,
        user_id,
        "coach",
        1,
    )


def record_setup(
    guild_id: int,
    user_id: int,
) -> bool:
    """
    Record one newly-created Wattson setup.
    """

    return update_daily_quest(
        guild_id,
        user_id,
        "setup",
        1,
    )


def record_upvote(
    guild_id: int,
    user_id: int,
) -> bool:
    """
    Record one upvote received by a user's setup.
    """

    return update_daily_quest(
        guild_id,
        user_id,
        "upvote",
        1,
    )


def record_challenge_completion(
    guild_id: int,
    user_id: int,
) -> bool:
    """
    Record one completed challenge.
    """

    return update_daily_quest(
        guild_id,
        user_id,
        "challenge",
        1,
    )


# ============================================================
# GENERIC EVENT HELPER
# ============================================================

def record_event(
    guild_id: int,
    user_id: int,
    event_type: str,
    amount: int = 1,
) -> bool:
    """
    Generic helper for future integrations.
    """

    return update_daily_quest(
        guild_id,
        user_id,
        event_type,
        amount,
    )