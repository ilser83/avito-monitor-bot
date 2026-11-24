import aiosqlite

DB_NAME = "bot.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS seen_ads (
                ad_id TEXT PRIMARY KEY
            )
        """)
        await db.commit()

async def add_link(title: str, url: str) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO links (title, url, is_active) VALUES (?, ?, 1)",
            (title, url)
        )
        await db.commit()
        return cursor.lastrowid

async def get_links(only_active: bool = False):
    async with aiosqlite.connect(DB_NAME) as db:
        query = "SELECT id, title, url, is_active FROM links"
        if only_active:
            query += " WHERE is_active = 1"
        async with db.execute(query) as cursor:
            return await cursor.fetchall()

async def toggle_link(link_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE links SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (link_id,)
        )
        await db.commit()

async def delete_link(link_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM links WHERE id = ?", (link_id,))
        await db.commit()

async def is_ad_seen(ad_id: str) -> bool:
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT 1 FROM seen_ads WHERE ad_id = ?", (ad_id,)) as cursor:
            return await cursor.fetchone() is not None

async def mark_ad_seen(ad_id: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO seen_ads (ad_id) VALUES (?)", (ad_id,))
        await db.commit()
