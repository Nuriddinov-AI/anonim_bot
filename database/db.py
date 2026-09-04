import aiosqlite
import random
import string

DB = "anon.db"

async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                full_name TEXT,
                phone TEXT,
                link_code TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                to_user_id INTEGER NOT NULL,
                from_info TEXT,
                question TEXT NOT NULL,
                answer TEXT,
                is_answered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (to_user_id) REFERENCES users(telegram_id)
            );
        """)
        await db.commit()

async def add_user(telegram_id, username, full_name, phone=None):
    code = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (telegram_id, username, full_name, phone, link_code) VALUES (?,?,?,?,?)",
            (telegram_id, username, full_name, phone, code)
        )
        await db.commit()

async def get_user(telegram_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,)) as cur:
            return await cur.fetchone()

async def get_user_by_code(code):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE link_code=?", (code,)) as cur:
            return await cur.fetchone()

async def send_question(to_user_id, from_user_id, from_info, question):
    async with aiosqlite.connect(DB) as db:
        cursor = await db.execute(
            "INSERT INTO questions (to_user_id, from_user_id, from_info, question) VALUES (?,?,?,?)",
            (to_user_id, from_user_id, from_info, question)
        )
        await db.commit()
        return cursor.lastrowid

async def get_unanswered(user_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM questions WHERE to_user_id=? AND is_answered=0 ORDER BY created_at DESC",
            (user_id,)
        ) as cur:
            return await cur.fetchall()

async def get_question(question_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM questions WHERE id=?", (question_id,)) as cur:
            return await cur.fetchone()

async def answer_question(question_id, answer):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE questions SET answer=?, is_answered=1 WHERE id=?",
            (answer, question_id)
        )
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        ) as cur:
            return await cur.fetchall()

async def get_stats(user_id):
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT COUNT(*) as total FROM questions WHERE to_user_id=?", (user_id,)
        ) as cur:
            total = (await cur.fetchone())['total']
        async with db.execute(
            "SELECT COUNT(*) as answered FROM questions WHERE to_user_id=? AND is_answered=1", (user_id,)
        ) as cur:
            answered = (await cur.fetchone())['answered']
        return total, answered
