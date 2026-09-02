import sqlite3

DB_NAME = "gridguardian.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def setup_database():
    db = get_connection()
    cursor = db.cursor()

    # -------------------------
    # SETTINGS
    # -------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        guild_id INTEGER PRIMARY KEY,
        welcome_channel_id INTEGER,
        log_channel_id INTEGER,
        suggestion_channel_id INTEGER,
        autorole_id INTEGER
    )
    """)

    # Add missing columns to older databases
    cursor.execute("PRAGMA table_info(settings)")
    columns = [row[1] for row in cursor.fetchall()]

    if "suggestion_channel_id" not in columns:
        cursor.execute("""
        ALTER TABLE settings
        ADD COLUMN suggestion_channel_id INTEGER
        """)

    if "autorole_id" not in columns:
        cursor.execute("""
        ALTER TABLE settings
        ADD COLUMN autorole_id INTEGER
        """)

    # -------------------------
    # WARNINGS
    # -------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        moderator_id INTEGER NOT NULL,
        reason TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # -------------------------
    # LEVELS
    # -------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS levels (
        user_id INTEGER PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1
    )
    """)

    # -------------------------
    # LEVEL ROLES
    # -------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS level_roles (
        guild_id INTEGER,
        level INTEGER,
        role_id INTEGER,
        PRIMARY KEY (guild_id, level)
    )
    """)

    # -------------------------
    # ECONOMY
    # -------------------------

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS economy (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0
    )
    """)

    db.commit()
    db.close()

    print("✅ Database initialized successfully.")


if __name__ == "__main__":
    setup_database()
    grep -R "process_commands" -n .