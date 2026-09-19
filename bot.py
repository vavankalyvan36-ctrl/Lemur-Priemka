import asyncio, aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMIN_ID, ADMIN_PASSWORD, PAYMENT_LINK
from database import DB, init_db, upsert_user, get_balance

dp = Dispatcher()

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Каталог", callback_data="catalog")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
         InlineKeyboardButton(text="💳 Пополнить", callback_data="pay")],
        [InlineKeyboardButton(text="📱 Мои покупки", callback_data="orders")],
        [InlineKeyboardButton(text="👥 Рефералы", callback_data="ref"),
         InlineKeyboardButton(text="💬 Поддержка", callback_data="support")]
    ])

@dp.message(Command("start"))
async def start(m: Message):
    await upsert_user(m.from_user.id, m.from_user.username)
    await m.answer("🐾 Добро пожаловать в Lemur-Priemka\n\nВыберите действие:", reply_markup=menu())

@dp.callback_query(F.data == "balance")
async def balance(c: CallbackQuery):
    b = await get_balance(c.from_user.id)
    await c.message.edit_text(f"💰 Баланс: {b:.2f}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Пополнить", callback_data="pay")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]
        ]))
    await c.answer()

@dp.callback_query(F.data == "home")
async def home(c: CallbackQuery):
    await c.message.edit_text("🐾 Lemur-Priemka\n\nВыберите действие:", reply_markup=menu())
    await c.answer()

@dp.callback_query(F.data == "catalog")
async def catalog(c: CallbackQuery):
    async with aiosqlite.connect(DB) as db:
        rows = await (await db.execute(
            "SELECT code,name FROM services WHERE enabled=1 ORDER BY id")).fetchall()
    kb = [[InlineKeyboardButton(text=n, callback_data=f"service:{code}")] for code,n in rows]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="home")])
    await c.message.edit_text("📦 Каталог:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await c.answer()

@dp.callback_query(F.data.startswith("service:"))
async def service(c: CallbackQuery):
    code = c.data.split(":",1)[1]
    async with aiosqlite.connect(DB) as db:
        row = await (await db.execute(
            "SELECT id,name,price FROM services WHERE code=?", (code,))).fetchone()
        if not row:
            await c.answer("Сервис не найден", show_alert=True); return
        sid,name,price = row
        stock = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE service_id=? AND sold=0",(sid,))).fetchone())[0]
    await c.message.edit_text(
        f"{name}\n\n💰 Цена: {price:.2f}\n📦 В наличии: {stock}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Купить", callback_data=f"buy:{sid}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="catalog")]
        ]))
    await c.answer()

@dp.callback_query(F.data.startswith("buy:"))
async def buy(c: CallbackQuery):
    sid = int(c.data.split(":")[1]); uid = c.from_user.id
    async with aiosqlite.connect(DB) as db:
        s = await (await db.execute("SELECT name,price FROM services WHERE id=?",(sid,))).fetchone()
        if not s or s[1] <= 0:
            await c.answer("Цена ещё не установлена.", show_alert=True); return
        name,price = s
        bal = (await (await db.execute("SELECT balance FROM users WHERE id=?",(uid,))).fetchone())[0]
        nr = await (await db.execute(
            "SELECT id,number FROM numbers WHERE service_id=? AND sold=0 LIMIT 1",(sid,))).fetchone()
        if not nr: await c.answer("Нет номеров в наличии.", show_alert=True); return
        if bal < price: await c.answer("Недостаточно средств.", show_alert=True); return
        nid,number = nr
        await db.execute("UPDATE users SET balance=balance-? WHERE id=?",(price,uid))
        cur = await db.execute(
            "INSERT INTO orders(user_id,number_id,service_id,price) VALUES(?,?,?,?) RETURNING id",
            (uid,nid,sid,price))
        oid = (await cur.fetchone())[0]
        await db.execute("UPDATE numbers SET sold=1 WHERE id=?",(nid,))
        await db.commit()
    await c.message.edit_text(
        f"✅ Покупка #{oid}\n\n{name}\n📱 Номер: <code>{number}</code>\n\n"
        "Если нужен код, нажмите кнопку.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📩 Запросить код", callback_data=f"code:{oid}")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="home")]
        ]))
    await c.answer()

@dp.callback_query(F.data.startswith("code:"))
async def code(c: CallbackQuery):
    oid = int(c.data.split(":")[1])
    async with aiosqlite.connect(DB) as db:
        row = await (await db.execute(
            "SELECT user_id FROM orders WHERE id=?",(oid,))).fetchone()
    if not row or row[0] != c.from_user.id:
        await c.answer("Заказ не найден.", show_alert=True); return
    await c.bot.send_message(ADMIN_ID, f"📩 Запрос кода\nЗаказ: #{oid}\nПользователь ID: {c.from_user.id}")
    await c.answer("Запрос отправлен администратору.")

@dp.callback_query(F.data == "pay")
async def pay(c: CallbackQuery):
    await c.message.edit_text(
        "💳 Пополнение\n\nОплатите через @send, затем нажмите «Я оплатил».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=PAYMENT_LINK)],
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data="payment_request")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="home")]
        ]))
    await c.answer()

@dp.callback_query(F.data == "payment_request")
async def payment_request(c: CallbackQuery):
    await c.message.answer("Введите сумму оплаты числом, например: 10")
    await c.answer()

@dp.message(F.text.regexp(r"^\d+(?:[.,]\d{1,2})?$"))
async def payment_amount(m: Message):
    amount = float(m.text.replace(",", "."))
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            "INSERT INTO payments(user_id,amount) VALUES(?,?) RETURNING id",
            (m.from_user.id,amount))
        pid = (await cur.fetchone())[0]
        await db.commit()
    await m.answer("✅ Заявка отправлена администратору.")
    await m.bot.send_message(ADMIN_ID,
        f"🔔 Пополнение #{pid}\nID: {m.from_user.id}\nСумма: {amount:.2f}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"payok:{pid}"),
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"payno:{pid}")
        ]]))

@dp.callback_query(F.data.startswith("payok:"))
async def payok(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    pid=int(c.data.split(":")[1])
    async with aiosqlite.connect(DB) as db:
        row=await (await db.execute(
            "SELECT user_id,amount FROM payments WHERE id=? AND status='pending'",(pid,))).fetchone()
        if not row: await c.answer("Уже обработано."); return
        uid,amount=row
        await db.execute("UPDATE payments SET status='approved' WHERE id=?",(pid,))
        await db.execute("UPDATE users SET balance=balance+? WHERE id=?",(amount,uid))
        await db.commit()
    await c.message.edit_text(f"✅ Пополнение #{pid} подтверждено.")
    await c.bot.send_message(uid,f"💰 Баланс пополнен на {amount:.2f}.")
    await c.answer()

@dp.callback_query(F.data.startswith("payno:"))
async def payno(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID: return
    pid=int(c.data.split(":")[1])
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE payments SET status='rejected' WHERE id=? AND status='pending'",(pid,))
        await db.commit()
    await c.message.edit_text(f"❌ Пополнение #{pid} отклонено.")
    await c.answer()

@dp.message(Command("admin"))
async def admin(m: Message):
    if m.from_user.id == ADMIN_ID:
        await m.answer("🔐 Введите пароль администратора.")

@dp.message()
async def admin_password(m: Message):
    if m.from_user.id == ADMIN_ID and m.text == ADMIN_PASSWORD:
        await m.answer(
    "🛠 Админка открыта.\n\nВыберите действие:",
    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Номера", callback_data="admin_numbers")],
        [InlineKeyboardButton(text="💰 Цены", callback_data="admin_prices")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ])
)
@dp.callback_query(F.data == "admin_numbers")
async def admin_numbers(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB) as db:
        rows = await (await db.execute("""
            SELECT numbers.number, services.name, numbers.sold
            FROM numbers
            LEFT JOIN services ON services.id = numbers.service_id
            ORDER BY numbers.id DESC
        """)).fetchall()

    if not rows:
        text = "📱 Номера\n\nНомеров пока нет."
    else:
        text = "📱 Номера:\n\n"
        for number, service, sold in rows:
            status = "🔴 Продан" if sold else "🟢 Свободен"
            text += f"{number} — {service or 'Без услуги'} — {status}\n"

    await c.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
        ])
    )
    await c.answer()


@dp.callback_query(F.data == "admin_numbers")
async def admin_numbers(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB) as db:
        cur = await db.execute("""
            SELECT numbers.number, services.name, numbers.sold
            FROM numbers
            LEFT JOIN services ON numbers.service_id = services.id
            ORDER BY numbers.id DESC
        """)
        rows = await cur.fetchall()

    text = "📱 Номера:\n\n"

    if not rows:
        text += "Номеров пока нет."
    else:
        for number, service, sold in rows:
            status = "🔴 Продан" if sold else "🟢 Свободен"
            text += f"• {number} — {service or 'Без сервиса'} — {status}\n"

    await c.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
        ])
    )
    await c.answer()
@dp.callback_query(F.data == "admin_prices")
async def admin_prices(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB) as db:
        rows = await (await db.execute("""
            SELECT id, name, price
            FROM services
            ORDER BY id
        """)).fetchall()

    kb = []

    for service_id, name, price in rows:
        kb.append([
            InlineKeyboardButton(
                text=f"{name}: {price:.2f} ₽",
                callback_data=f"admin_price:{service_id}"
            )
        ])

    kb.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="admin_back"
        )
    ])

    await c.message.edit_text(
        "💰 Цены:\n\nВыберите услугу, чтобы изменить цену:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

    await c.answer()
admin_price_waiting = {}

@dp.callback_query(F.data.startswith("admin_price:"))
async def admin_price(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return

    service_id = int(c.data.split(":")[1])

    async with aiosqlite.connect(DB) as db:
        row = await (await db.execute(
            "SELECT name, price FROM services WHERE id=?",
            (service_id,)
        )).fetchone()

    if not row:
        await c.answer("❌ Услуга не найдена", show_alert=True)
        return

    admin_price_waiting[c.from_user.id] = service_id

    await c.message.answer(
        f"💰 {row[0]}\n\n"
        f"Текущая цена: {row[1]:.2f} ₽\n\n"
        "Введите новую цену, например: 25 или 25.50"
    )

    await c.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB) as db:
        users = (await (await db.execute(
            "SELECT COUNT(*) FROM users"
        )).fetchone())[0]

        numbers = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers"
        )).fetchone())[0]

        free_numbers = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE sold = 0"
        )).fetchone())[0]

        sold_numbers = (await (await db.execute(
            "SELECT COUNT(*) FROM numbers WHERE sold = 1"
        )).fetchone())[0]

        orders = (await (await db.execute(
            "SELECT COUNT(*) FROM orders"
        )).fetchone())[0]

    text = (
        "📊 Статистика\n\n"
        f"👥 Пользователей: {users}\n"
        f"📱 Всего номеров: {numbers}\n"
        f"🟢 Свободных: {free_numbers}\n"
        f"🔴 Проданных: {sold_numbers}\n"
        f"🛒 Заказов: {orders}"
    )

    await c.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_back")]
        ])
    )
    await c.answer()


@dp.callback_query(F.data == "admin_back")
async def admin_back(c: CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        return

    await c.message.edit_text(
        "🛠 Админка открыта.\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Номера", callback_data="admin_numbers")],
            [InlineKeyboardButton(text="💰 Цены", callback_data="admin_prices")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
        ])
    )
    await c.answer()


async def main():
    if not BOT_TOKEN: raise RuntimeError("BOT_TOKEN не задан в .env")
    await init_db()
    await dp.start_polling(Bot(BOT_TOKEN))

if __name__ == "__main__":
    asyncio.run(main())
