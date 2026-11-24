import asyncio, random
from typing import Optional
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMIN_IDS, CHECK_INTERVAL, PROXY_URL
import database as db
from parser import fetch_ads, ParserDiagnosticError

from aiogram.types import User
bot = Bot(token=BOT_TOKEN)
bot._me = User(id=9224558424, is_bot=True, first_name="Test", username="ilona_avito_test_bot")
dp = Dispatcher()

class AddLinkState(StatesGroup):
    waiting_for_url = State()
    waiting_for_title = State()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ссылку", callback_data="add_link")],
        [InlineKeyboardButton(text="📋 Мои ссылки", callback_data="list_links")],
        [InlineKeyboardButton(text="🔄 Проверить сейчас", callback_data="check_now")],
        [InlineKeyboardButton(text="🩺 Диагностика", callback_data="diagnostics")]
    ])

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer("👋 **Мониторинг Авито запущен!**\n\nВыбери действие:", reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "add_link")
async def start_add_link(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AddLinkState.waiting_for_url)
    await cb.message.answer("🔗 Пришли поисковую ссылку с Авито:")
    await cb.answer()

@dp.message(AddLinkState.waiting_for_url)
async def process_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith("http"):
        return await message.answer("❌ Пришли ссылку, начинающуюся с https://")
    await state.update_data(url=url)
    await state.set_state(AddLinkState.waiting_for_title)
    await message.answer("📝 Как назовем этот поиск?")

@dp.message(AddLinkState.waiting_for_title)
async def process_title(message: Message, state: FSMContext):
    data = await state.get_data()
    url, title = data["url"], message.text.strip()
    await state.clear()
    wait_msg = await message.answer("⏳ Добавляю ссылку и запоминаю текущие объявления...")
    await db.add_link(title, url)
    try:
        ads = await fetch_ads(url)
        for ad in ads:
            await db.mark_ad_seen(ad["id"])
        await wait_msg.edit_text(f"✅ Ссылка **{title}** добавлена! Запомнил {len(ads)} объявлений.", reply_markup=main_menu(), parse_mode="Markdown")
    except Exception as e:
        await wait_msg.edit_text(f"⚠️ Ссылка **{title}** добавлена, но при проверке возникла проблема:\n\n{e}", reply_markup=main_menu(), parse_mode="Markdown")

@dp.callback_query(F.data == "list_links")
async def show_links(cb: CallbackQuery):
    links = await db.get_links()
    if not links:
        await cb.message.answer("📭 Список ссылок пуст.", reply_markup=main_menu())
        return await cb.answer()
    for link_id, title, url, is_active in links:
        status = "🟢 Активна" if is_active else "⏸ На паузе"
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="⏯ Пауза / Старт", callback_data=f"toggle_{link_id}"),
            InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{link_id}")
        ]])
        await cb.message.answer(f"**{title}**\nСтатус: {status}\n{url}", reply_markup=kb, parse_mode="Markdown")
    await cb.answer()

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_link_cb(cb: CallbackQuery):
    _, raw_id = cb.data.split("_", 1)
    await db.toggle_link(int(raw_id))
    await cb.message.edit_text("🔄 Статус изменен! Нажми «Мои ссылки».")
    await cb.answer()

@dp.callback_query(F.data.startswith("del_"))
async def delete_link_cb(cb: CallbackQuery):
    _, raw_id = cb.data.split("_", 1)
    await db.delete_link(int(raw_id))
    await cb.message.edit_text("🗑 Ссылка удалена.")
    await cb.answer()

@dp.callback_query(F.data == "diagnostics")
async def run_diagnostics(cb: CallbackQuery):
    await cb.answer("Проверяю...")
    msg = await cb.message.answer("🩺 **Запускаю диагностику...**", parse_mode="Markdown")
    all_links = await db.get_links(only_active=False)
    active_links = await db.get_links(only_active=True)
    proxy_status = "🟢 Подключен" if PROXY_URL else "🟡 Не задан (прямое подключение)"
    report = f"🩺 **Отчет диагностики**\n\n🖥 **Сервер и бот:** 🟢 Работают\n🌐 **Прокси:** {proxy_status}\n🔗 **Ссылок:** {len(all_links)} (активных: {len(active_links)})\n\n"
    if active_links:
        _, t_title, t_url, _ = active_links.pop(0)
        try:
            ads = await fetch_ads(t_url)
            report += f"✅ **Доступ к Авито («{t_title}»):** ОК! Найдено {len(ads)} объявлений."
        except Exception as e:
            report += f"❌ **Доступ к Авито («{t_title}»):**\n{e}"
    else:
        report += "ℹ️ *Добавьте активную ссылку для проверки Авито.*"
    await msg.edit_text(report, reply_markup=main_menu(), parse_mode="Markdown")

async def run_check(notify_chat_id: Optional[int] = None):
    links = await db.get_links(only_active=True)
    new_count = 0
    for _, title, url, _ in links:
        try:
            ads = await fetch_ads(url)
            for ad in reversed(ads):
                if not await db.is_ad_seen(ad["id"]):
                    await db.mark_ad_seen(ad["id"])
                    new_count += 1
                    caption = f"🆕 **Новое по поиску «{title}»**\n\n📦 {ad['title']}\n💰 **{ad['price']}**"
                    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔗 Открыть на Авито", url=ad["url"])]])
                    recipients = ADMIN_IDS if ADMIN_IDS else ([notify_chat_id] if notify_chat_id else [])
                    for cid in recipients:
                        if ad["photo"]:
                            await bot.send_photo(cid, photo=ad["photo"], caption=caption, reply_markup=kb, parse_mode="Markdown")
                        else:
                            await bot.send_message(cid, text=caption, reply_markup=kb, parse_mode="Markdown")
            await asyncio.sleep(random.uniform(2.0, 4.0))
        except Exception as e:
            print(f"[Error] {title}: {e}")
    if notify_chat_id:
        await bot.send_message(notify_chat_id, f"✅ Проверка завершена. Новых объявлений: {new_count}")

@dp.callback_query(F.data == "check_now")
async def manual_check(cb: CallbackQuery):
    await cb.answer("Проверяю...")
    await run_check(notify_chat_id=cb.from_user.id)

async def scheduler():
    while True:
        await asyncio.sleep(CHECK_INTERVAL)
        await run_check()

async def main():
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    asyncio.create_task(scheduler())
    print("🚀 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
