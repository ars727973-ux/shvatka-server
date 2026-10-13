# -*- coding: utf-8 -*-
"""
==================================================================
  Telegram-бот «Зеркальная комната» с Mini App
  Библиотека: aiogram 3.x          Запуск:  python mirror_bot.py
==================================================================

Бот приветствует игрока и открывает Mini App (index.html на GitHub Pages)
прямо внутри Telegram. Вся игра — лучи, зеркала, загадки — живёт в index.html.

Если рядом с ботом лежит картинка mirror_preview.jpg, бот пришлёт её
в приветствии. Нет картинки — пришлёт просто текст.
"""

# ╔════════════════════════════════════════════════════════════════╗
# ║                          НАСТРОЙКИ                             ║
# ╚════════════════════════════════════════════════════════════════╝

# Токен бота от @BotFather
import os  # токены можно передать через переменные окружения или файл .env

BOT_TOKEN = os.environ.get("MIRROR_TOKEN", "ВСТАВЬ_ТОКЕН_СЮДА")

# Ссылка на index.html в интернете (GitHub Pages), обязательно https://
WEBAPP_URL = os.environ.get("MIRROR_WEBAPP_URL", "https://ars727973-ux.github.io/mirror/")

# Надпись на кнопке меню слева от поля ввода
MENU_BUTTON_TEXT = "Зеркала"

# Картинка для приветствия (лежит в той же папке, что и бот)
PREVIEW_FILE = "mirror_preview.jpg"


# ╔════════════════════════════════════════════════════════════════╗
# ║                          ТЕКСТЫ                                ║
# ╚════════════════════════════════════════════════════════════════╝

# Описание, которое человек видит ДО нажатия «Запустить» (до 512 символов)
DESCRIPTION = (
    "🪞 Зеркальная комната — залипательная игра со светом.\n\n"
    "Все стены здесь — зеркала. Ставишь лампу, лазер или призму, и лучи отражаются "
    "бесконечно, рисуя узоры.\n\n"
    "✨ 35 комнат — от круга до бильярда Синая\n"
    "🔦 9 инструментов: лампа, лазер, призма, пульсар, зеркала, чёрные дыры…\n"
    "🧩 120 загадок в 6 главах\n"
    "🎨 Свои комнаты, нарисованные пальцем\n\n"
    "Нажми «Запустить» 👇"
)

# Короткое описание — в профиле бота и когда им делятся (до 120 символов)
SHORT_DESCRIPTION = "Зеркальные комнаты, лучи света и 120 загадок. Залипательно 🪞✨"


def start_text(name: str) -> str:
    return (
        f"👋 Привет, <b>{name}</b>!\n\n"
        "🪞 <b>Зеркальная комната</b> — здесь все стены зеркала. Поставь свет "
        "и смотри, как лучи отражаются бесконечно и рисуют узоры.\n\n"
        "✨ <b>35 комнат</b> — от круга до бильярда Синая\n"
        "🔦 <b>9 инструментов</b>: лампа, лазер, призма, пульсар, зеркала, чёрные дыры…\n"
        "🧩 <b>120 загадок</b> в 6 главах — собери все 360 ⭐\n"
        "🎨 <b>Свои комнаты</b> — рисуй стены пальцем\n\n"
        "Загадка на картинке: в комнате Пенроуза одна лампа <b>никогда</b> не осветит всё. "
        "А две — смогут? 😉\n\n"
        "Жми кнопку ниже 👇"
    )


HELP_TEXT = (
    "📖 <b>Как играть</b>\n\n"
    "<b>Свободный режим</b>\n"
    "1. Внизу выбери комнату.\n"
    "2. Выбери инструмент и нажми внутри комнаты.\n"
    "3. Смотри, как свет отражается от стен-зеркал.\n\n"
    "<b>Инструменты</b>\n"
    "💡 <b>Лампа</b> — свет во все стороны\n"
    "🔦 <b>Фонарь</b> — конус света (нажми и потяни)\n"
    "🔴 <b>Лазер</b> — один луч, сотни отражений (нажми и потяни)\n"
    "🌈 <b>Призма</b> — радужный веер лучей\n"
    "☀️ <b>Полоса</b> — параллельные лучи, как из окна\n"
    "💫 <b>Пульсар</b> — лампа, которая мигает волнами\n"
    "🪞 <b>Зеркало</b> — проведи линию пальцем\n"
    "🕳 <b>Дыра</b> — поглощает свет (потяни, чтобы увеличить)\n"
    "🧽 <b>Ластик</b> — убирает зеркала, дыры и лампы\n\n"
    "<b>Загадки</b>\n"
    "Попади лазером в мишень, освети комнату, собери свет в фокусе или нарисуй "
    "зеркало, чтобы направить луч. Чем меньше попыток — тем больше звёзд ⭐\n\n"
    "<b>Полезное</b>\n"
    "• «Нарисовать» — своя комната: обведи стены пальцем\n"
    "• «Изменить» — удалить или скрыть лишние комнаты\n"
    "• «Авто» — приложение само ставит свет, можно просто смотреть\n"
    "• «Настройки» — цвет света, число лучей, затухание следа"
)

FACTS = [
    "🧠 <b>Комната Пенроуза</b> (1958): есть комнаты с зеркальными стенами, которые невозможно осветить одной лампой, где бы она ни стояла. Её придумал Лайонел Пенроуз, отец нобелевского лауреата Роджера Пенроуза.",
    "🎯 <b>Эллипс</b>: если поставить лампу в один фокус, все лучи после отражения пройдут через второй. На этом устроены «шепчущие галереи» — шёпот у одной стены слышно у противоположной.",
    "📡 <b>Парабола</b> собирает параллельные лучи в одну точку. Поэтому так устроены спутниковые тарелки, фары и солнечные печи. Проверь инструментом «Полоса»!",
    "🌀 <b>Бильярд Синая</b> — квадрат с круглой колонной. Один из первых доказанно хаотичных бильярдов: два почти одинаковых луча быстро разлетаются в разные стороны.",
    "🏟 <b>Стадион Бунимовича</b> хаотичен, хотя в нём нет ни одной вогнутой стены. Леонид Бунимович удивил этим математиков в 1974 году.",
    "🍄 <b>Гриб Бунимовича</b> — смесь порядка и хаоса: в шляпке часть лучей вечно кружит по краю, а другие хаотично блуждают.",
    "☕ <b>Каустика</b> — яркие кривые, где собирается отражённый свет. Ты видел её на дне чашки с кофе. В приложении попробуй «Круг» с лампой у края.",
    "🔺 <b>Треугольник Фаньяно</b>: в остроугольном треугольнике есть замкнутый маршрут луча, который повторяется вечно. Найди его лазером!",
    "⚙️ <b>Треугольник Рёло</b> — фигура постоянной ширины, как круг. Такие бывают крышки люков и даже свёрла, которые сверлят почти квадратные отверстия.",
    "🔦 В 1995 году Джордж Токарский построил многоугольную зеркальную комнату, где свет из одной точки никогда не попадёт в другую. А в 2016-м доказали: в многоугольниках с «рациональными» углами таких тёмных точек может быть лишь конечное число.",
]


# ╔════════════════════════════════════════════════════════════════╗
# ║                          САМ БОТ                               ║
# ╚════════════════════════════════════════════════════════════════╝

import asyncio
import html
import logging
import random
import sys
from pathlib import Path

try:
    from aiogram import Bot, Dispatcher, F, Router
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramNetworkError, TelegramUnauthorizedError
    from aiogram.filters import Command, CommandStart
    from aiogram.types import (
        BotCommand,
        CallbackQuery,
        FSInputFile,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        MenuButtonWebApp,
        Message,
        WebAppInfo,
    )
except ImportError:
    print("ОШИБКА: не установлена библиотека aiogram 3. Выполни:  pip install -U aiogram")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
log = logging.getLogger("mirror")

BASE_DIR = Path(__file__).resolve().parent
router = Router()


def app_url(mode: str = "") -> str:
    """Ссылка на приложение; mode=levels открывает загадки, mode=draw — рисование."""
    return WEBAPP_URL + (f"?mode={mode}" if mode else "")


def main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✨ Открыть зеркальную комнату", web_app=WebAppInfo(url=app_url()))],
        [InlineKeyboardButton(text="🧩 Загадки", web_app=WebAppInfo(url=app_url("levels"))),
         InlineKeyboardButton(text="🎨 Нарисовать", web_app=WebAppInfo(url=app_url("draw")))],
        [InlineKeyboardButton(text="📖 Как играть", callback_data="help"),
         InlineKeyboardButton(text="💡 Интересный факт", callback_data="fact")],
    ])


def one_button(text: str, mode: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, web_app=WebAppInfo(url=app_url(mode)))]])


def fact_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎲 Ещё факт", callback_data="fact_more")],
        [InlineKeyboardButton(text="✨ Проверить в комнате", web_app=WebAppInfo(url=app_url()))],
    ])


def user_name(message_or_callback) -> str:
    user = message_or_callback.from_user
    return html.escape(user.first_name or "друг") if user else "друг"


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    text = start_text(user_name(message))
    photo = BASE_DIR / PREVIEW_FILE
    if photo.exists():
        try:
            await message.answer_photo(FSInputFile(photo), caption=text, reply_markup=main_keyboard())
            return
        except TelegramAPIError as error:
            log.warning("Не удалось отправить картинку: %s", error)
    await message.answer(text, reply_markup=main_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=one_button("✨ Открыть комнату"))


@router.message(Command("levels"))
async def cmd_levels(message: Message) -> None:
    await message.answer(
        "🧩 <b>120 загадок в 6 главах</b>\n\n"
        "1. Первые лучи — лазер и мишень\n"
        "2. Рикошеты — нужное число отражений и несколько мишеней\n"
        "3. Свет и тень — освети комнату, собери свет в фокусе\n"
        "4. Чёрные дыры — найди обход\n"
        "5. Зеркальщик — нарисуй зеркало, чтобы направить луч\n"
        "6. Мастер — всё вместе, а в конце загадка Пенроуза\n\n"
        "Чем меньше попыток, тем больше звёзд. Максимум — 360 ⭐",
        reply_markup=one_button("🧩 Открыть загадки", "levels"),
    )


@router.message(Command("draw"))
async def cmd_draw(message: Message) -> None:
    await message.answer(
        "🎨 <b>Своя комната</b>\n\n"
        "Обведи пальцем замкнутую линию — это стены. Линии внутри станут колоннами. "
        "Потом поставь свет и смотри, что получится.\n\n"
        "Своих комнат может быть до 20. Лишние удаляются кнопкой «Изменить».",
        reply_markup=one_button("🎨 Нарисовать комнату", "draw"),
    )


@router.message(Command("fact"))
async def cmd_fact(message: Message) -> None:
    await message.answer(random.choice(FACTS), reply_markup=fact_keyboard())


@router.callback_query(F.data == "help")
async def cb_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(HELP_TEXT, reply_markup=one_button("✨ Открыть комнату"))


@router.callback_query(F.data.in_({"fact", "fact_more"}))
async def cb_fact(callback: CallbackQuery) -> None:
    await callback.answer()
    text = random.choice(FACTS)
    if callback.data == "fact_more":
        try:
            await callback.message.edit_text(text, reply_markup=fact_keyboard())
            return
        except TelegramBadRequest:
            pass  # тот же факт выпал второй раз или сообщение слишком старое
    await callback.message.answer(text, reply_markup=fact_keyboard())


@router.message()
async def any_message(message: Message) -> None:
    await message.answer(
        "Я понимаю только кнопки и команды 🙂\n\n"
        "/start — главное меню\n/levels — загадки\n/draw — нарисовать комнату\n"
        "/fact — интересный факт\n/help — как играть",
        reply_markup=one_button("✨ Открыть зеркальную комнату"),
    )


async def setup_profile(bot: Bot) -> None:
    """Описание, короткое описание, команды и кнопка меню. Ошибки не мешают запуску."""
    steps = [
        ("описание", bot.set_my_description(description=DESCRIPTION)),
        ("короткое описание", bot.set_my_short_description(short_description=SHORT_DESCRIPTION)),
        ("команды", bot.set_my_commands([
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="levels", description="120 загадок"),
            BotCommand(command="draw", description="Нарисовать свою комнату"),
            BotCommand(command="fact", description="Интересный факт о свете"),
            BotCommand(command="help", description="Как играть"),
        ])),
        ("кнопка меню", bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text=MENU_BUTTON_TEXT, web_app=WebAppInfo(url=app_url())))),
    ]
    for name, coro in steps:
        try:
            await coro
        except TelegramAPIError as error:
            print(f"  Не удалось обновить {name}: {error}")


async def main() -> None:
    bot = Bot(token=BOT_TOKEN.strip(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)

    try:
        me = await bot.get_me()
    except TelegramUnauthorizedError:
        print("ОШИБКА: Telegram не принял токен. Скопируй его заново у @BotFather.")
        await bot.session.close()
        return
    except TelegramNetworkError as error:
        print("ОШИБКА: нет связи с Telegram. Проверь интернет.", error)
        await bot.session.close()
        return

    await setup_profile(bot)
    photo = BASE_DIR / PREVIEW_FILE
    print("=" * 60)
    print(f"  Бот @{me.username} запущен! Остановить: Ctrl + C")
    print(f"  Приложение: {WEBAPP_URL}")
    print(f"  Картинка в приветствии: {'есть' if photo.exists() else 'нет (положи ' + PREVIEW_FILE + ' рядом с ботом)'}")
    print(f"  Ссылка на бота: https://t.me/{me.username}")
    print("=" * 60)
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    token = BOT_TOKEN.strip()
    if not token or token == "ВСТАВЬ_ТОКЕН_СЮДА" or ":" not in token:
        print('ОШИБКА: вставь токен бота в строку BOT_TOKEN = "..."')
        sys.exit(1)
    if not WEBAPP_URL.startswith("https://"):
        print('ОШИБКА: вставь ссылку на index.html в WEBAPP_URL = "https://..."')
        sys.exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
