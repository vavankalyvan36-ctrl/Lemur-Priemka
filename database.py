import aiosqlite
DB = "lemur.db"

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS services(
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT UNIQUE,
            name TEXT, price REAL DEFAULT 0, enabled INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS numbers(
            id INTEGER PRIMARY KEY AUTOINCREMENT, service_id INTEGER,
            number TEXT, sold INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            number_id INTEGER, service_id INTEGER, price REAL,
            status TEXT DEFAULT 'waiting_code',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            amount REAL, status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        services = [
            ("tg","📱 Telegram"),("max","⚡ MAX"),("vk","🔵 VK"),
            ("wa","🟢 WhatsApp"),("ya","🟡 Яндекс"),("inst","📸 Instagram"),
            ("google","🔍 Google"),("fb","🔵 Facebook"),
            ("wb","🛒 Wildberries"),("ozon","🛍 Ozon")
        ]
        for code, name in services:
            await db.execute(
                "INSERT OR IGNORE INTO services(code,name) VALUES(?,?)",
                (code,name)
            )
        await db.commit()

async def upsert_user(uid, username):
    async with aiosqlite.connect(DB) as db:
        await db.execute("INSERT OR IGNORE INTO users(id,username) VALUES(?,?)",
                         (uid, username or ""))
        await db.execute("UPDATE users SET username=? WHERE id=?",
                         (username or "", uid))
        await db.commit()

async def get_balance(uid):
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("SELECT balance FROM users WHERE id=?", (uid,))
        row = await cur.fetchone()
        return float(row[0]) if row else 0.0
