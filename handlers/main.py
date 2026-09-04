from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import (
    add_user, get_user, get_user_by_code, send_question,
    get_unanswered, get_question, answer_question, get_all_users, get_stats
)
from config import BOT_USERNAME, ADMIN_ID, SECRET_KEY

router = Router()

class States(StatesGroup):
    writing_question = State()
    writing_answer = State()

def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📨 Savollar")],
        [KeyboardButton(text="🔗 Mening havolam")],
        [KeyboardButton(text="📊 Statistika")]
    ], resize_keyboard=True)

def ask_again_kb(target_code):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✉️ Yana savol yozish", callback_data="ask_" + target_code)]
    ])

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    args = message.text.split()
    user = await get_user(message.from_user.id)
    if not user:
        await add_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name
        )
        user = await get_user(message.from_user.id)

    if len(args) > 1:
        code = args[1]
        target = await get_user_by_code(code)
        if target and target['telegram_id'] != message.from_user.id:
            await state.update_data(target_id=target['telegram_id'], target_code=code)
            name = target['full_name'] or "Foydalanuvchi"
            await message.answer(
                "🎭 <b>Anonim savol yuborish</b>\n\n"
                "<b>" + name + "</b> ga anonim savol yuboring.\n\n"
                "✍️ Savolingizni yozing:",
                parse_mode="HTML"
            )
            await state.set_state(States.writing_question)
            return
        elif target and target['telegram_id'] == message.from_user.id:
            await message.answer("😅 O'zingizning havolangizga kira olmaysiz!", reply_markup=main_menu())
            return

    link = "https://t.me/" + BOT_USERNAME + "?start=" + user['link_code']
    await message.answer(
        "👋 Salom, <b>" + (message.from_user.full_name or "Foydalanuvchi") + "</b>!\n\n"
        "🎭 Bu bot orqali anonim savol qabul qilishingiz mumkin.\n\n"
        "📎 <b>Shaxsiy havolangiz:</b>\n<code>" + link + "</code>\n\n"
        "Havolani ulashing va anonim savollar qabul qiling!",
        parse_mode="HTML",
        reply_markup=main_menu()
    )

@router.callback_query(F.data.startswith("ask_"))
async def ask_again(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split("_")[1]
    target = await get_user_by_code(code)
    if not target:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
    await state.update_data(target_id=target['telegram_id'], target_code=code)
    await callback.message.answer("✍️ Yangi savolingizni yozing:")
    await state.set_state(States.writing_question)
    await callback.answer()

@router.message(States.writing_question)
async def receive_question(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Faqat matn yuboring!")
        return
    data = await state.get_data()
    target_id = data.get('target_id')
    target_code = data.get('target_code', '')
    if not target_id:
        await state.clear()
        return

    from_info = "@" + message.from_user.username if message.from_user.username else message.from_user.full_name or "Noma'lum"
    q_id = await send_question(target_id, message.from_user.id, from_info, message.text)
    await state.clear()

    await message.answer(
        "✅ <b>Savolingiz yuborildi!</b>\n\nJavob kelganda sizga xabar beramiz.",
        parse_mode="HTML",
        reply_markup=ask_again_kb(target_code)
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Javob berish", callback_data="ans_" + str(q_id))]
    ])
    try:
        await message.bot.send_message(
            target_id,
            "📨 <b>Yangi anonim savol!</b>\n\n❓ " + message.text,
            parse_mode="HTML",
            reply_markup=kb
        )
    except:
        pass

@router.message(F.text == "📨 Savollar")
async def my_questions(message: Message):
    questions = await get_unanswered(message.from_user.id)
    if not questions:
        await message.answer("📭 Hozircha javobsiz savol yo'q!")
        return
    await message.answer("📨 <b>Javobsiz savollar (" + str(len(questions)) + " ta)</b>", parse_mode="HTML")
    for q in questions[:10]:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Javob berish", callback_data="ans_" + str(q['id']))]
        ])
        await message.answer(
            "❓ <b>Savol #" + str(q['id']) + "</b>\n\n" + q['question'] + "\n\n🕐 " + str(q['created_at'])[:16],
            parse_mode="HTML",
            reply_markup=kb
        )

@router.callback_query(F.data.startswith("ans_"))
async def start_answer(callback: CallbackQuery, state: FSMContext):
    q_id = int(callback.data.split("_")[1])
    q = await get_question(q_id)
    if not q or q['to_user_id'] != callback.from_user.id:
        await callback.answer("Bu savol sizniki emas!", show_alert=True)
        return
    await state.update_data(question_id=q_id)
    await callback.message.answer(
        "💬 Javobingizni yozing:\n\nSavol: <i>" + q['question'] + "</i>",
        parse_mode="HTML"
    )
    await state.set_state(States.writing_answer)
    await callback.answer()

@router.message(States.writing_answer)
async def send_answer(message: Message, state: FSMContext):
    data = await state.get_data()
    q_id = data.get('question_id')
    if not q_id:
        await state.clear()
        return
    q = await get_question(q_id)
    await answer_question(q_id, message.text)
    await state.clear()
    await message.answer("✅ Javobingiz yuborildi!")

    if q and q['from_user_id']:
        try:
            await message.bot.send_message(
                q['from_user_id'],
                "📩 <b>Savolingizga javob keldi!</b>\n\n"
                "❓ Savol: <i>" + q['question'] + "</i>\n\n"
                "💬 Javob: <b>" + message.text + "</b>",
                parse_mode="HTML"
            )
        except:
            pass

@router.message(F.text == "🔗 Mening havolam")
async def my_link(message: Message):
    user = await get_user(message.from_user.id)
    if not user:
        return
    link = "https://t.me/" + BOT_USERNAME + "?start=" + user['link_code']
    await message.answer(
        "🔗 <b>Shaxsiy havolangiz:</b>\n\n<code>" + link + "</code>\n\n"
        "Bu havolani ulashing va anonim savollar qabul qiling!",
        parse_mode="HTML"
    )

@router.message(F.text == "📊 Statistika")
async def stats(message: Message):
    total, answered = await get_stats(message.from_user.id)
    await message.answer(
        "📊 <b>Statistikangiz</b>\n\n"
        "📨 Jami: <b>" + str(total) + "</b>\n"
        "✅ Javob berilgan: <b>" + str(answered) + "</b>\n"
        "⏳ Javobsiz: <b>" + str(total - answered) + "</b>",
        parse_mode="HTML"
    )

@router.message(F.text == SECRET_KEY)
async def show_users(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    users = await get_all_users()
    if not users:
        await message.answer("Hali foydalanuvchi yo'q.")
        return
    text = "👥 <b>Foydalanuvchilar (" + str(len(users)) + " ta)</b>\n\n━━━━━━━━━━━━━\n"
    for i, u in enumerate(users, 1):
        username = "@" + u['username'] if u['username'] else "yo'q"
        text += (
            str(i) + ". <b>" + (u['full_name'] or "Noma'lum") + "</b>\n"
            "   👤 " + username + "\n"
            "   🆔 <code>" + str(u['telegram_id']) + "</code>\n"
            "   📅 " + str(u['created_at'])[:16] + "\n━━━━━━━━━━━━━\n"
        )
    for chunk in [text[i:i+4000] for i in range(0, len(text), 4000)]:
        await message.answer(chunk, parse_mode="HTML")
