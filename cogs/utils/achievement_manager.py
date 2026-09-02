import sqlite3


DB_NAME = "gridguardian.db"


def unlock(user_id: int, achievement: str) -> bool:
    """
    Unlock an achievement for a user.

    Returns:
        True  -> achievement was newly unlocked
        False -> user already had the achievement
    """

    db = sqlite3.connect(DB_NAME)
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS achievements (
        user_id INTEGER,
        achievement TEXT,
        PRIMARY KEY(user_id, achievement)
    )
    """)

    cursor.execute("""
    INSERT OR IGNORE INTO achievements
    (user_id, achievement)
    VALUES (?, ?)
    """, (
        user_id,
        achievement
    ))

    newly_unlocked = cursor.rowcount > 0

    db.commit()
    db.close()

    return newly_unlocked


def get_achievements(user_id: int):
    """
    Returns all achievements unlocked by a user.
    """

    db = sqlite3.connect(DB_NAME)
    cursor = db.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS achievements (
        user_id INTEGER,
        achievement TEXT,
        PRIMARY KEY(user_id, achievement)
    )
    """)

    cursor.execute("""
    SELECT achievement
    FROM achievements
    WHERE user_id=?
    ORDER BY achievement
    """, (user_id,))

    achievements = [
        row[0]
        for row in cursor.fetchall()
    ]

    db.close()

    return achievements