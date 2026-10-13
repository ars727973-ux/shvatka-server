# -*- coding: utf-8 -*-
"""
==================================================================
  Telegram-бот «Не забудь!» — умная напоминалка
  Библиотека: aiogram 3.x          Запуск:  python reminder_bot.py
==================================================================

Что умеет:
  • Понимает обычный текст:  «завтра в 9 позвонить маме»,
    «через 20 минут выключить духовку», «каждый день в 8:00 зарядка».
  • Напоминает в нужное время и ПОВТОРЯЕТ напоминание («спамит»),
    пока не нажмёшь «✅ Готово».
  • Кнопки «Отложить»: +10 минут, +1 час, на завтра.
  • Повторяющиеся задачи: каждый день, по будням, по понедельникам,
    каждые 2 часа, каждый месяц...
  • Утренний план на день, тихие часы ночью, статистика и серия дней.
  • Все данные лежат в reminders.json рядом с этим файлом —
    после перезапуска ничего не пропадает.
"""

# ╔════════════════════════════════════════════════════════════════╗
# ║                          НАСТРОЙКИ                             ║
# ╚════════════════════════════════════════════════════════════════╝

# Токен бота от @BotFather (внутри кавычек)
import os  # токены можно передать через переменные окружения или файл .env

BOT_TOKEN = os.environ.get("REMINDER_TOKEN", "ВСТАВЬ_ТОКЕН_СЮДА")

# Владелец бота (ты). Только у владельца в «⚙️ Настройках» есть кнопка
# «🔓 Для всех / 🔒 Только я» — она решает, кто может пользоваться ботом.
# Свой ID бот покажет по команде /id.
OWNER_ID = int(os.environ.get("OWNER_ID", "6649586929"))

# Люди, которым бот доступен ВСЕГДА, даже в режиме «🔒 Только я»
# (например, семья). Пример: ALLOWED_USERS = [111111111, 222222222]
ALLOWED_USERS = []

# Часовой пояс по умолчанию (часы от UTC). Ташкент = 5, Москва = 3.
# Каждый может поменять его себе в «⚙️ Настройках».
DEFAULT_TZ_HOURS = 5

# Через сколько минут повторять напоминание, пока не нажата «✅ Готово».
# 0 = не повторять. Каждый может поменять в настройках.
DEFAULT_NAG_MINUTES = 5

# Максимум повторов одного напоминания (чтобы бот не спамил вечно)
NAG_LIMIT = 60

# Утренний план на день: время "08:00" или None (выключено)
DEFAULT_DIGEST = "08:00"

# Тихие часы: в это время бот НЕ повторяет напоминания (но сами
# напоминания, поставленные на это время, всё равно придут).
QUIET_FROM = 23
QUIET_TO = 7

# Защита от переполнения
MAX_TASKS_PER_USER = 300
MAX_TEXT_LENGTH = 300

# Как часто бот проверяет, не пора ли напомнить (секунды)
CHECK_EVERY_SECONDS = 5

# Файл с данными (создаётся автоматически)
DATA_FILE_NAME = "reminders.json"


# ╔════════════════════════════════════════════════════════════════╗
# ║                 ПОДКЛЮЧЕНИЕ БИБЛИОТЕК                          ║
# ╚════════════════════════════════════════════════════════════════╝

import sys

if sys.version_info < (3, 9):
    print("ОШИБКА: нужен Python 3.9 или новее.")
    sys.exit(1)

import asyncio
import html
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import date as date_cls
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.exceptions import (
        TelegramAPIError,
        TelegramBadRequest,
        TelegramForbiddenError,
        TelegramNetworkError,
        TelegramRetryAfter,
        TelegramUnauthorizedError,
    )
    from aiogram.filters import Command, CommandStart
    from aiogram.types import (
        BotCommand,
        CallbackQuery,
        ErrorEvent,
        InlineKeyboardButton,
        InlineKeyboardMarkup,
        KeyboardButton,
        Message,
        ReplyKeyboardMarkup,
    )
except ImportError:
    print("ОШИБКА: не установлена библиотека aiogram 3. Выполни:  pip install -U aiogram")
    sys.exit(1)


# ╔════════════════════════════════════════════════════════════════╗
# ║                     ЛОГИ И ГЛОБАЛЬНЫЕ ДАННЫЕ                   ║
# ╚════════════════════════════════════════════════════════════════╝

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
                    datefmt="%H:%M:%S")
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
log = logging.getLogger("reminder")

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / DATA_FILE_NAME
BACKUP_FILE = BASE_DIR / (DATA_FILE_NAME + ".bak")
TMP_FILE = BASE_DIR / (DATA_FILE_NAME + ".tmp")

DATA: Dict[str, Any] = {}       # все данные (то же, что в reminders.json)
STATE: Dict[int, dict] = {}     # «что бот сейчас ждёт» от каждого человека

WD_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
NAG_OPTIONS = [0, 1, 3, 5, 10, 15, 30, 60]
DIGEST_OPTIONS = [None, "07:00", "08:00", "09:00", "10:00"]

# Фразы для повторных напоминаний — чем дольше игнорируешь, тем настойчивее 😄
NAG_LINES = [
    "🔔 Напоминаю ещё раз!",
    "⏰ Эй, не забыл?",
    "👀 Я всё ещё жду…",
    "😤 Ну давай же!",
    "📢 Это важно!",
    "🚨 Я не отстану, пока не нажмёшь «✅ Готово»!",
]

# Тексты кнопок нижнего меню
BTN_NEW = "➕ Новая задача"
BTN_LIST = "📋 Мои задачи"
BTN_TODAY = "📅 Сегодня"
BTN_STATS = "📊 Статистика"
BTN_SETTINGS = "⚙️ Настройки"
BTN_HELP = "❓ Помощь"


# ╔════════════════════════════════════════════════════════════════╗
# ║                  ХРАНЕНИЕ ДАННЫХ (JSON)                        ║
# ╚════════════════════════════════════════════════════════════════╝

def empty_data() -> Dict[str, Any]:
    return {"version": 1, "next_id": 1, "users": {}, "tasks": {}, "public": True}


def load_data() -> Dict[str, Any]:
    """Читает reminders.json; если он повреждён — берёт резервную копию."""
    for path in (DATA_FILE, BACKUP_FILE):
        if not path.exists():
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for key, value in empty_data().items():
                    data.setdefault(key, value)
                if path == BACKUP_FILE:
                    log.warning("Основной файл повреждён — взял резервную копию.")
                return data
        except (OSError, json.JSONDecodeError) as error:
            broken = path.with_name(f"{path.name}.broken_{int(time.time())}")
            try:
                shutil.copy2(path, broken)
            except OSError:
                pass
            log.error("Файл %s повреждён (%s), копия: %s", path.name, error, broken.name)
    log.info("Создаю новый файл данных: %s", DATA_FILE)
    return empty_data()


def save_data() -> None:
    """Сохраняет данные сразу и надёжно (временный файл + резервная копия)."""
    try:
        with open(TMP_FILE, "w", encoding="utf-8") as f:
            json.dump(DATA, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        if DATA_FILE.exists():
            shutil.copy2(DATA_FILE, BACKUP_FILE)
        os.replace(TMP_FILE, DATA_FILE)
    except OSError as error:
        log.error("Не удалось сохранить данные: %s", error)


# ╔════════════════════════════════════════════════════════════════╗
# ║                  ПОЛЬЗОВАТЕЛИ И ВРЕМЯ                          ║
# ╚════════════════════════════════════════════════════════════════╝

def get_user(uid: int, name: Optional[str] = None) -> dict:
    """Возвращает настройки человека (создаёт, если его ещё нет)."""
    key = str(uid)
    user = DATA["users"].get(key)
    if user is None:
        user = {}
        DATA["users"][key] = user
    defaults = {
        "name": "",
        "tz": DEFAULT_TZ_HOURS * 60,          # часовой пояс в минутах
        "nag": DEFAULT_NAG_MINUTES,           # повтор каждые N минут
        "digest": DEFAULT_DIGEST,             # утренний план
        "digest_last": "",                    # когда последний раз присылали план
        "quiet": True,                        # тихие часы
        "blocked": False,                     # человек заблокировал бота
        "stats": {"created": 0, "done": 0, "snoozed": 0, "nags": 0},
        "history": [],                        # выполненные задачи
    }
    for k, v in defaults.items():
        if k not in user:
            user[k] = json.loads(json.dumps(v))  # копия, чтобы списки не были общими
    if name:
        user["name"] = name
    return user


def tz_of(user: dict) -> timezone:
    return timezone(timedelta(minutes=user["tz"]))


def local_now(user: dict) -> datetime:
    return datetime.now(tz_of(user))


def to_local(ts: float, user: dict) -> datetime:
    return datetime.fromtimestamp(ts, tz_of(user))


def tz_label(user: dict) -> str:
    hours = user["tz"] / 60
    sign = "+" if hours >= 0 else "−"
    hours = abs(hours)
    return f"UTC{sign}{int(hours)}" if hours == int(hours) else f"UTC{sign}{hours}"


def fmt_when(ts: float, user: dict) -> str:
    """'сегодня в 18:30', 'завтра в 09:00', 'пт, 17.10 в 10:00'."""
    dt = to_local(ts, user)
    now = local_now(user)
    days = (dt.date() - now.date()).days
    if days == 0:
        day = "сегодня"
    elif days == 1:
        day = "завтра"
    elif days == 2:
        day = "послезавтра"
    elif days == -1:
        day = "вчера"
    else:
        day = f"{WD_SHORT[dt.weekday()]}, {dt.strftime('%d.%m')}"
        if dt.year != now.year:
            day += f".{dt.year}"
    return f"{day} в {dt.strftime('%H:%M')}"


def fmt_delta(ts: float) -> str:
    """'через 2 ч 5 мин' или 'просрочено на 10 мин'."""
    diff = int(ts - time.time())
    past = diff < 0
    diff = abs(diff)
    if diff < 60:
        return "прямо сейчас" if past else "меньше чем через минуту"
    d, rest = divmod(diff, 86400)
    h, rest = divmod(rest, 3600)
    m = rest // 60
    parts = []
    if d:
        parts.append(f"{d} дн")
    if h:
        parts.append(f"{h} ч")
    if m and not d:
        parts.append(f"{m} мин")
    text = " ".join(parts) or "1 мин"
    return f"просрочено на {text}" if past else f"через {text}"


def fmt_repeat(repeat: Optional[dict]) -> str:
    if not repeat:
        return ""
    kind = repeat["type"]
    if kind == "daily":
        return "каждый день"
    if kind == "weekly":
        days = sorted(repeat.get("days") or [])
        if days == [0, 1, 2, 3, 4]:
            return "по будням"
        if days == [5, 6]:
            return "по выходным"
        if len(days) == 7:
            return "каждый день"
        return "по " + ", ".join(WD_SHORT[d] for d in days)
    if kind == "interval":
        minutes = repeat["minutes"]
        if minutes % 1440 == 0:
            n = minutes // 1440
            return "каждый день" if n == 1 else f"каждые {n} дн"
        if minutes % 60 == 0:
            n = minutes // 60
            return "каждый час" if n == 1 else f"каждые {n} ч"
        return f"каждые {minutes} мин"
    if kind == "monthly":
        return f"каждый месяц, {repeat.get('day', 1)} числа"
    return ""


def in_quiet_hours(user: dict) -> bool:
    if not user.get("quiet"):
        return False
    hour = local_now(user).hour
    if QUIET_FROM > QUIET_TO:                       # например 23 → 7 (через полночь)
        return hour >= QUIET_FROM or hour < QUIET_TO
    return QUIET_FROM <= hour < QUIET_TO


# ╔════════════════════════════════════════════════════════════════╗
# ║          РАЗБОР ТЕКСТА: «завтра в 9 позвонить маме»            ║
# ╚════════════════════════════════════════════════════════════════╝
# Бот ищет в тексте кусочки про время, вырезает их, а то, что
# осталось, становится текстом задачи.

MONTHS = {"января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
          "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12}
MONTH_RE = "|".join(MONTHS)
WEEKDAYS = {"понедельник": 0, "вторник": 1, "среда": 2, "среду": 2, "четверг": 3,
            "пятница": 4, "пятницу": 4, "суббота": 5, "субботу": 5, "воскресенье": 6}
WD_RE = "|".join(sorted(WEEKDAYS, key=len, reverse=True))
WEEKDAYS_PLURAL = {"понедельникам": 0, "вторникам": 1, "средам": 2, "четвергам": 3,
                   "пятницам": 4, "субботам": 5, "воскресеньям": 6}
WDP_RE = "|".join(WEEKDAYS_PLURAL)
PERIODS = {"в полдень": (12, 0), "в полночь": (0, 0), "утром": (9, 0), "с утра": (9, 0), "днём": (13, 0), "днем": (13, 0),
           "в обед": (13, 0), "вечером": (19, 0), "ночью": (23, 0)}
UNIT_ALT = r"секунд\w*|сек\b|минут\w*|мин\b|месяц\w*|мес\b|м\b|час\w*|ч\b|дн\w*|день|д\b|недел\w*|год\w*|лет\b"
I = re.IGNORECASE


@dataclass
class Parsed:
    text: str                       # текст задачи
    due: Optional[float] = None     # когда напомнить (метка времени) или None
    repeat: Optional[dict] = None   # правило повтора или None
    error: str = ""                 # понятная ошибка (например, «нет такой даты»)


def unit_seconds(unit: str) -> int:
    unit = unit.lower()
    if unit.startswith("сек"):
        return 1
    if unit.startswith("мес"):
        return 30 * 86400
    if unit.startswith("год") or unit == "лет":
        return 365 * 86400
    if unit.startswith("мин") or unit == "м":
        return 60
    if unit.startswith("ч"):
        return 3600
    if unit.startswith("недел"):
        return 604800
    return 86400  # день, дн, д


def number_value(text: Optional[str]) -> float:
    if not text:
        return 1
    text = text.lower()
    if text == "пол":
        return 0.5
    if text == "полтора":
        return 1.5
    return float(text.replace(",", "."))


def clean_task_text(s: str) -> str:
    """Убирает лишние слова вроде «напомни мне» и пустые предлоги."""
    s = re.sub(r"\s+", " ", s).strip(" ,.;:-—–")
    s = re.sub(r"^(?:напомни(?:ть)?|напоминание)\b\s*(?:мне\b)?\s*,?\s*(?:что(?:бы)?\b|о\b|об\b|про\b)?\s*",
               "", s, flags=I)
    s = re.sub(r"(?:^|\s)(?:в|во|на|к|и)\s*$", "", s, flags=I)   # «Купить хлеб в» → «Купить хлеб»
    s = re.sub(r"\s+", " ", s).strip(" ,.;:-—–")
    return (s[:1].upper() + s[1:])[:MAX_TEXT_LENGTH] if s else ""


def parse_request(raw: str, user: dict, now_ts: Optional[float] = None) -> Parsed:
    """Главная функция разбора текста."""
    tz = tz_of(user)
    now = datetime.fromtimestamp(now_ts if now_ts is not None else time.time(), tz)
    s = raw

    def cut(m: "re.Match") -> None:
        """Вырезает найденный кусок (заменяет пробелами)."""
        nonlocal s
        s = s[:m.start()] + " " * (m.end() - m.start()) + s[m.end():]

    repeat: Optional[dict] = None
    period = None
    rel_seconds = None
    hh = mm = None
    minutes_given = False  # было ли «18:30», а не просто «в 7»
    explicit_day = False   # указан день/дата
    target_date: Optional[date_cls] = None
    year_given = True
    weekday_target = None

    # ---------- 1. Повторы ----------
    m = re.search(r"\b(?:каждый\s+день|ежедневно)\b", s, I)
    if m:
        repeat = {"type": "daily"}
        cut(m)
    if not repeat:
        m = re.search(r"\bкаждое\s+утро\b", s, I)
        if m:
            repeat, period = {"type": "daily"}, (9, 0)
            cut(m)
    if not repeat:
        m = re.search(r"\bкаждый\s+вечер\b", s, I)
        if m:
            repeat, period = {"type": "daily"}, (19, 0)
            cut(m)
    if not repeat:
        m = re.search(r"\bпо\s+будн\w*|\bв\s+будни\b|\bпо\s+рабочим\s+дням\b", s, I)
        if m:
            repeat = {"type": "weekly", "days": [0, 1, 2, 3, 4]}
            cut(m)
    if not repeat:
        m = re.search(r"\bпо\s+выходн\w*|\bв\s+выходные\b", s, I)
        if m:
            repeat = {"type": "weekly", "days": [5, 6]}
            cut(m)
    if not repeat:
        m = re.search(rf"\bпо\s+(?:{WDP_RE})(?:\s*(?:,|и)\s*(?:{WDP_RE}))*", s, I)
        if m:
            days = sorted({WEEKDAYS_PLURAL[w.lower()] for w in re.findall(WDP_RE, m.group(0), I)})
            repeat = {"type": "weekly", "days": days}
            cut(m)
    if not repeat:
        m = re.search(rf"\bкажд(?:ый|ую|ое)\s+({WD_RE})\b", s, I)
        if m:
            repeat = {"type": "weekly", "days": [WEEKDAYS[m.group(1).lower()]]}
            cut(m)
    if not repeat:
        m = re.search(r"\bкажд(?:ую|ая)\s+неделю\b|\bеженедельно\b", s, I)
        if m:
            repeat = {"type": "weekly", "days": None}
            cut(m)
    if not repeat:
        m = re.search(r"\bкаждый\s+месяц\b|\bежемесячно\b", s, I)
        if m:
            repeat = {"type": "monthly"}
            cut(m)
    if not repeat:
        m = re.search(r"\bкажд(?:ые|ый|ую|ое)\s+(\d+\s*)?(минут\w*|мин\b|час\w*|ч\b|дн\w*|день)", s, I)
        if m:
            n = int(m.group(1)) if m.group(1) else 1
            minutes = max(1, n * unit_seconds(m.group(2)) // 60)
            repeat = {"type": "interval", "minutes": minutes}
            cut(m)

    # ---------- 2. «через 20 минут», «через полчаса», «через 1 час 30 минут» ----------
    m = re.search(rf"\bчерез\s+((?:(?:\d+(?:[.,]\d+)?|полтора|пол)?\s*(?:{UNIT_ALT})[\s,]*(?:и\s+)?)+)", s, I)
    if m:
        total = 0.0
        for num, unit in re.findall(rf"(\d+(?:[.,]\d+)?|полтора|пол)?\s*({UNIT_ALT})", m.group(1), I):
            total += number_value(num) * unit_seconds(unit)
        if total > 0:
            rel_seconds = total
            cut(m)

    # ---------- 3. Время ----------
    m = re.search(r"\b(?:в|к)\s*(\d{1,2})(?:[:.](\d{2}))?\s*(утра|дня|вечера|ночи)\b", s, I)
    if m:
        h, mi, word = int(m.group(1)), int(m.group(2) or 0), m.group(3).lower()
        if 0 <= h <= 12 and mi < 60:
            if word == "утра" and h == 12:
                h = 0
            elif word in ("дня", "вечера") and h < 12:
                h += 12
            elif word == "ночи":
                h = 0 if h == 12 else (h + 12 if h >= 9 else h)
            hh, mm = h % 24, mi
            period = "explicit"
            cut(m)
    if hh is None:
        pattern = rf"\b(?:в|к)\s*(\d{{1,2}})(?:[:.](\d{{2}}))?(?!\d)(?:\s*(?:час\w*|ч\b))?(?!\s*(?:{MONTH_RE}))"
        for m in re.finditer(pattern, s, I):
            h, mi = int(m.group(1)), int(m.group(2) or 0)
            if h <= 23 and mi <= 59:
                hh, mm = h, mi
                minutes_given = m.group(2) is not None
                cut(m)
                break
    if hh is None:
        m = re.search(r"(?<![\d.:])(\d{1,2}):(\d{2})(?![\d:])", s)
        if m and int(m.group(1)) <= 23 and int(m.group(2)) <= 59:
            hh, mm = int(m.group(1)), int(m.group(2))
            minutes_given = True
            cut(m)
    if hh is None:
        # «18.30» — время, если это не может быть датой (минуты больше 12)
        m = re.search(r"(?<![\d.:])(\d{1,2})\.(\d{2})(?![\d.:])", s)
        if m and 12 < int(m.group(2)) <= 59 and int(m.group(1)) <= 23:
            hh, mm = int(m.group(1)), int(m.group(2))
            minutes_given = True
            cut(m)

    # ---------- 4. Дата ----------
    try:
        m = re.search(r"(?<![\d.:])(\d{1,2})\.(\d{1,2})(?:\.(\d{4}|\d{2}))?(?![\d:])", s)
        if m and 1 <= int(m.group(2)) <= 12:
            year = int(m.group(3)) if m.group(3) else now.year
            if year < 100:
                year += 2000
            year_given = bool(m.group(3))
            target_date = date_cls(year, int(m.group(2)), int(m.group(1)))
            explicit_day = True
            cut(m)
        if target_date is None:
            m = re.search(rf"\b(\d{{1,2}})\s+({MONTH_RE})(?:\s+(\d{{4}}))?(?:\s*(?:года|г\.?))?", s, I)
            if m:
                year = int(m.group(3)) if m.group(3) else now.year
                year_given = bool(m.group(3))
                target_date = date_cls(year, MONTHS[m.group(2).lower()], int(m.group(1)))
                explicit_day = True
                cut(m)
        if target_date is None:
            m = re.search(r"\b(\d{1,2})(?:-?го)?\s+числа\b", s, I)
            if m:
                d, y, mo = int(m.group(1)), now.year, now.month
                for _ in range(14):          # ближайший месяц, где есть такое число
                    try:
                        cand = date_cls(y, mo, d)
                        if cand >= now.date():
                            break
                    except ValueError:
                        pass
                    y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
                else:
                    raise ValueError
                target_date = cand
                explicit_day = True
                cut(m)
    except ValueError:
        return Parsed(text=clean_task_text(s), error="Такой даты не существует 🙂")

    if target_date is None:
        for word, shift in (("послезавтра", 2), ("завтра", 1), ("сегодня", 0)):
            m = re.search(rf"\b{word}\b", s, I)
            if m:
                target_date = now.date() + timedelta(days=shift)
                explicit_day = True
                cut(m)
                break
    if target_date is None:
        m = re.search(rf"\b(?:(?:в|во)\s+)?({WD_RE})\b", s, I)
        if m:
            weekday_target = WEEKDAYS[m.group(1).lower()]
            explicit_day = True
            cut(m)

    # ---------- 5. «утром», «вечером» ----------
    if hh is None:
        for word, value in PERIODS.items():
            m = re.search(rf"(?<!\w){word}(?!\w)", s, I)
            if m:
                hh, mm = value
                period = "word"
                cut(m)
                break
    elif period is None:
        for word in PERIODS:
            m = re.search(rf"(?<!\w){word}(?!\w)", s, I)
            if m:
                cut(m)  # «вечером в 7» — убираем слово, время уже есть
                if word in ("вечером", "днём", "днем", "в обед") and hh < 12:
                    hh += 12
                period = "word"
                break
    elif isinstance(period, tuple):
        hh, mm = period
        period = "word"

    text = clean_task_text(s) or "Напоминание"
    has_info = rel_seconds is not None or hh is not None or explicit_day or repeat is not None
    if not has_info:
        return Parsed(text=text)
    if (hh is None and rel_seconds is None and not repeat
            and target_date is not None and target_date == now.date()):
        return Parsed(text=text)        # «сегодня …» без часа — спросим время кнопками

    # ---------- 6. Собираем дату и время ----------
    if rel_seconds is not None:
        due = now + timedelta(seconds=rel_seconds)
    elif repeat and repeat["type"] == "interval" and hh is None and not explicit_day:
        due = now + timedelta(minutes=repeat["minutes"])
    else:
        h = hh if hh is not None else 9
        mi = mm or 0
        if target_date is not None:
            due = datetime(target_date.year, target_date.month, target_date.day, h, mi, tzinfo=tz)
            if not year_given and due < now - timedelta(days=1):
                due = due.replace(year=due.year + 1)
        elif weekday_target is not None:
            ahead = (weekday_target - now.weekday()) % 7
            due = (now + timedelta(days=ahead)).replace(hour=h, minute=mi, second=0, microsecond=0)
            if due <= now:
                due += timedelta(days=7)
        elif repeat and repeat["type"] == "weekly" and repeat.get("days"):
            due = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            for _ in range(8):
                if due > now and due.weekday() in repeat["days"]:
                    break
                due += timedelta(days=1)
        else:
            due = now.replace(hour=h, minute=mi, second=0, microsecond=0)
            if due <= now:
                # «в 7» в 15:00 — скорее всего имеется в виду 19:00
                if (hh is not None and period is None and not minutes_given and not repeat
                        and 1 <= hh <= 9 and due + timedelta(hours=12) > now):
                    due += timedelta(hours=12)
                else:
                    due += timedelta(days=1)

    if repeat and repeat["type"] == "weekly" and not repeat.get("days"):
        repeat["days"] = [due.weekday()]
    if repeat and repeat["type"] == "monthly":
        repeat["day"] = due.day

    return Parsed(text=text, due=due.timestamp(), repeat=repeat)


# ╔════════════════════════════════════════════════════════════════╗
# ║                     ЗАДАЧИ                                     ║
# ╚════════════════════════════════════════════════════════════════╝

def user_tasks(uid: int) -> List[dict]:
    """Активные задачи человека, отсортированные по времени."""
    tasks = [t for t in DATA["tasks"].values() if t["uid"] == uid and t["status"] == "active"]
    return sorted(tasks, key=lambda t: (not t["fired"], t["due"]))


def get_task(task_id: str) -> Optional[dict]:
    task = DATA["tasks"].get(str(task_id))
    if task and task["status"] == "active":
        return task
    return None


def create_task(uid: int, text: str, due: float, repeat: Optional[dict]) -> dict:
    user = get_user(uid)
    task_id = DATA["next_id"]
    DATA["next_id"] += 1
    task = {
        "id": task_id,
        "uid": uid,
        "text": text[:MAX_TEXT_LENGTH],
        "due": due,
        "repeat": repeat,
        "nag": user["nag"] > 0,      # повторять ли до отметки
        "status": "active",          # active / done / deleted
        "fired": False,              # напоминание уже пришло и ждёт «Готово»
        "nag_count": 0,
        "next_nag": None,
        "nag_stop": False,           # «хватит повторять» для текущего раза
        "msg_id": None,              # последнее сообщение-напоминание
        "late": False,
        "snoozes": 0,
        "created": time.time(),
    }
    DATA["tasks"][str(task_id)] = task
    user["stats"]["created"] += 1
    save_data()
    log.info("Новая задача #%s для %s: %s", task_id, uid, text)
    return task


def reset_firing(task: dict) -> None:
    """Сбрасывает состояние «напоминание сработало»."""
    task["fired"] = False
    task["nag_count"] = 0
    task["next_nag"] = None
    task["nag_stop"] = False
    task["late"] = False


def add_month(dt: datetime, day: int) -> datetime:
    year, month = (dt.year + 1, 1) if dt.month == 12 else (dt.year, dt.month + 1)
    for d in (day, 30, 29, 28):  # 31-го нет в каждом месяце
        try:
            return dt.replace(year=year, month=month, day=min(day, d))
        except ValueError:
            continue
    return dt


def next_due(task: dict, after: float) -> float:
    """Следующее время повторяющейся задачи ПОСЛЕ момента after."""
    repeat = task["repeat"]
    due = task["due"]
    if repeat["type"] == "interval":
        step = repeat["minutes"] * 60
        if after < due:
            return due
        return due + (int((after - due) // step) + 1) * step
    user = get_user(task["uid"])
    dt = to_local(due, user)
    for _ in range(2000):
        if repeat["type"] == "monthly":
            dt = add_month(dt, repeat.get("day", dt.day))
        else:
            dt += timedelta(days=1)
            if repeat["type"] == "weekly" and dt.weekday() not in (repeat.get("days") or [dt.weekday()]):
                continue
        if dt.timestamp() > after:
            return dt.timestamp()
    return after + 86400


def complete_task(task: dict) -> str:
    """«✅ Готово». Возвращает текст-результат."""
    user = get_user(task["uid"])
    user["stats"]["done"] += 1
    user["history"].append({"text": task["text"], "at": time.time(), "nags": task["nag_count"]})
    user["history"] = user["history"][-500:]
    if task["repeat"]:
        base = task.pop("anchor", task["due"])   # плановое время, даже если задачу откладывали
        task["due"] = base
        task["due"] = next_due(task, max(time.time(), base))
        reset_firing(task)
        save_data()
        return (f"✅ <b>Готово:</b> {html.escape(task['text'])}\n"
                f"🔁 Следующий раз: {fmt_when(task['due'], user)}")
    task["status"] = "done"
    task["done_at"] = time.time()
    save_data()
    return f"✅ <b>Готово:</b> <s>{html.escape(task['text'])}</s>\nМолодец! 💪"


def snooze_task(task: dict, minutes: Optional[int] = None, tomorrow: bool = False) -> str:
    """Отложить задачу."""
    user = get_user(task["uid"])
    now = time.time()
    if task["repeat"] and "anchor" not in task:
        task["anchor"] = task["due"]           # запоминаем плановое время повтора
    if tomorrow:
        old = to_local(task["due"], user)
        nxt = local_now(user) + timedelta(days=1)
        task["due"] = nxt.replace(hour=old.hour, minute=old.minute, second=0, microsecond=0).timestamp()
    else:
        base = now if (task["fired"] or task["due"] < now) else task["due"]
        task["due"] = base + minutes * 60
    reset_firing(task)
    task["snoozes"] += 1
    user["stats"]["snoozed"] += 1
    save_data()
    return f"⏰ Отложено: {html.escape(task['text'])}\n🕒 Напомню {fmt_when(task['due'], user)}"


# ╔════════════════════════════════════════════════════════════════╗
# ║                     ТЕКСТЫ И КНОПКИ                            ║
# ╚════════════════════════════════════════════════════════════════╝

def btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_NEW), KeyboardButton(text=BTN_LIST)],
            [KeyboardButton(text=BTN_TODAY), KeyboardButton(text=BTN_STATS)],
            [KeyboardButton(text=BTN_SETTINGS), KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder="завтра в 9 позвонить маме",
    )


def nag_enabled(task: dict, user: dict) -> bool:
    return bool(task["nag"]) and user["nag"] > 0


def task_card_text(task: dict, header: str = "") -> str:
    user = get_user(task["uid"])
    lines = []
    if header:
        lines += [header, ""]
    lines.append(f"📝 <b>{html.escape(task['text'])}</b>")
    lines.append("")
    lines.append(f"🕒 {fmt_when(task['due'], user)} ({fmt_delta(task['due'])})")
    if task["repeat"]:
        lines.append(f"🔁 Повтор: {fmt_repeat(task['repeat'])}")
    if nag_enabled(task, user):
        lines.append(f"📣 Напоминать каждые {user['nag']} мин, пока не нажмёшь «Готово»")
    else:
        lines.append("🔕 Напомню один раз")
    if task["fired"]:
        lines.append("🔔 <b>Уже сработало — ждёт отметки</b>")
    return "\n".join(lines)


def task_card_kb(task: dict) -> InlineKeyboardMarkup:
    tid = task["id"]
    user = get_user(task["uid"])
    nag_label = "📣 Повторы: вкл" if nag_enabled(task, user) else "🔕 Повторы: выкл"
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("✅ Готово", f"t:{tid}:done"), btn("🗑 Удалить", f"t:{tid}:del")],
        [btn("⏰ +10 мин", f"t:{tid}:s10"), btn("⏰ +1 час", f"t:{tid}:s60"), btn("🌅 Завтра", f"t:{tid}:tom")],
        [btn("🕒 Время", f"t:{tid}:edit"), btn("✏️ Текст", f"t:{tid}:rename"), btn(nag_label, f"t:{tid}:nag")],
        [btn("⬅️ К списку", "list")],
    ])


def reminder_text(task: dict) -> str:
    user = get_user(task["uid"])
    n = task["nag_count"]
    head = "🔔 <b>НАПОМИНАНИЕ</b>" if n == 0 else f"{NAG_LINES[min(n - 1, len(NAG_LINES) - 1)]} ({n})"
    lines = [head, "", f"📝 <b>{html.escape(task['text'])}</b>",
             f"🕒 Было назначено: {fmt_when(task['due'], user)}"]
    if task["repeat"]:
        lines.append(f"🔁 {fmt_repeat(task['repeat'])}")
    if task.get("late"):
        lines.append("⚠️ Немного опоздал — бот был выключен.")
    if nag_enabled(task, user) and not task["nag_stop"]:
        lines.append(f"\n📣 Буду повторять каждые {user['nag']} мин, пока не нажмёшь «✅ Готово».")
    return "\n".join(lines)


def reminder_kb(task: dict) -> InlineKeyboardMarkup:
    tid = task["id"]
    rows = [
        [btn("✅ Готово", f"r:{tid}:done")],
        [btn("⏰ 10 мин", f"r:{tid}:s10"), btn("⏰ 1 час", f"r:{tid}:s60"), btn("🌅 Завтра", f"r:{tid}:tom")],
    ]
    user = get_user(task["uid"])
    if nag_enabled(task, user) and not task["nag_stop"]:
        rows.append([btn("🔕 Хватит повторять", f"r:{tid}:quiet")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def task_short(task: dict, user: dict) -> str:
    """Короткая строка задачи для кнопки списка."""
    dt = to_local(task["due"], user)
    days = (dt.date() - local_now(user).date()).days
    when = dt.strftime("%H:%M") if days == 0 else ("завтра " + dt.strftime("%H:%M") if days == 1
                                                     else dt.strftime("%d.%m %H:%M"))
    icon = "🔔" if task["fired"] else ("🔁" if task["repeat"] else "🕒")
    text = task["text"] if len(task["text"]) <= 28 else task["text"][:27] + "…"
    return f"{icon} {when} · {text}"


def list_view(uid: int):
    user = get_user(uid)
    tasks = user_tasks(uid)
    if not tasks:
        return ("📋 <b>Задач нет</b> 🎉\n\nНапиши, что и когда напомнить, например:\n"
                "<i>завтра в 9 позвонить маме</i>"), None
    fired = sum(1 for t in tasks if t["fired"])
    text = f"📋 <b>Мои задачи</b>: {len(tasks)}"
    if fired:
        text += f"\n🔔 Ждут отметки: {fired}"
    text += "\n\nНажми на задачу, чтобы открыть её."
    rows = [[btn(task_short(t, user), f"t:{t['id']}:view")] for t in tasks[:40]]
    if len(tasks) > 40:
        text += f"\n\nПоказаны первые 40 из {len(tasks)}."
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def today_text(uid: int, morning: bool = False) -> Optional[str]:
    user = get_user(uid)
    today = local_now(user).date()
    fired = [t for t in user_tasks(uid) if t["fired"]]
    todays = [t for t in user_tasks(uid) if not t["fired"] and to_local(t["due"], user).date() == today]
    if morning and not fired and not todays:
        return None
    lines = ["🌅 <b>Доброе утро! План на сегодня:</b>" if morning else
             f"📅 <b>Сегодня, {today.strftime('%d.%m')}</b>", ""]
    if not todays and not fired:
        lines.append("Задач на сегодня нет 🎉")
    for t in todays:
        icon = "🔁" if t["repeat"] else "•"
        lines.append(f"{icon} {to_local(t['due'], user).strftime('%H:%M')} — {html.escape(t['text'])}")
    if fired:
        lines += ["", "🔔 <b>Ждут отметки:</b>"]
        lines += [f"• {html.escape(t['text'])}" for t in fired]
    return "\n".join(lines)


def stats_text(uid: int) -> str:
    user = get_user(uid)
    st = user["stats"]
    tz = tz_of(user)
    today = local_now(user).date()
    done_days = {datetime.fromtimestamp(h["at"], tz).date() for h in user["history"]}
    done_today = sum(1 for h in user["history"] if datetime.fromtimestamp(h["at"], tz).date() == today)
    done_week = sum(1 for h in user["history"]
                    if (today - datetime.fromtimestamp(h["at"], tz).date()).days < 7)
    # Серия: сколько дней подряд есть хотя бы одна выполненная задача
    streak = 0
    day = today if today in done_days else today - timedelta(days=1)
    while day in done_days:
        streak += 1
        day -= timedelta(days=1)
    nags = [h["nags"] for h in user["history"]]
    avg_nags = sum(nags) / len(nags) if nags else 0
    on_first = sum(1 for n in nags if n == 0)
    tasks = user_tasks(uid)
    lines = [
        "📊 <b>Твоя статистика</b>", "",
        f"✅ Выполнено сегодня: <b>{done_today}</b>",
        f"📆 За 7 дней: <b>{done_week}</b>",
        f"🏁 Всего выполнено: <b>{st['done']}</b> из {st['created']} созданных",
        f"🔥 Серия: <b>{streak}</b> дн. подряд",
        "",
        f"📋 Активных задач: {len(tasks)} (повторяющихся: {sum(1 for t in tasks if t['repeat'])})",
        f"⏰ Переносов: {st['snoozed']}",
        f"📣 Повторных напоминаний отправлено: {st['nags']}",
    ]
    if nags:
        lines.append(f"🎯 С первого раза: {round(on_first * 100 / len(nags))}% "
                     f"(в среднем {avg_nags:.1f} повтора до «Готово»)")
    if streak >= 3:
        lines += ["", "🏆 Отличная серия, так держать!"]
    return "\n".join(lines)


def settings_text(uid: int) -> str:
    user = get_user(uid)
    nag = f"каждые {user['nag']} мин" if user["nag"] else "выкл (напомню один раз)"
    digest = f"в {user['digest']}" if user["digest"] else "выкл"
    quiet = f"вкл ({QUIET_FROM:02d}:00–{QUIET_TO:02d}:00 не повторяю)" if user["quiet"] else "выкл"
    return ("⚙️ <b>Настройки</b>\n\n"
            f"🌍 Часовой пояс: <b>{tz_label(user)}</b> (у тебя сейчас {local_now(user).strftime('%H:%M')})\n"
            f"📣 Повторять до отметки: <b>{nag}</b>\n"
            f"🌅 Утренний план: <b>{digest}</b>\n"
            f"🌙 Тихие часы: <b>{quiet}</b>\n"
            + owner_settings_line(uid) +
            "\n<i>Нажимай на кнопки, чтобы менять значения.</i>")


def owner_settings_line(uid: int) -> str:
    """Строка про доступ — видна только владельцу."""
    if uid != OWNER_ID:
        return ""
    users = len(DATA["users"])
    mode = "🔓 для всех" if DATA.get("public", True) else "🔒 только я"
    return f"\n👑 Доступ к боту: <b>{mode}</b> (пользователей: {users})\n"


def settings_kb(uid: int) -> InlineKeyboardMarkup:
    user = get_user(uid)
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("🌍 −1 час", "s:tz-"), btn(tz_label(user), "s:none"), btn("🌍 +1 час", "s:tz+")],
        [btn(f"📣 Повтор: {user['nag']} мин" if user["nag"] else "📣 Повтор: выкл", "s:nag")],
        [btn(f"🌅 План: {user['digest'] or 'выкл'}", "s:dig")],
        [btn("🌙 Тихие часы: " + ("вкл" if user["quiet"] else "выкл"), "s:quiet")],
    ] + ([[btn("🔓 Доступ: для всех" if DATA.get("public", True) else "🔒 Доступ: только я",
               "s:public")]] if uid == OWNER_ID else []))


def ask_time_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn("⏱ 15 мин", "q:15"), btn("⏱ 30 мин", "q:30"), btn("⏱ 1 час", "q:60")],
        [btn("⏱ 3 часа", "q:180"), btn("🌆 Сегодня в 19:00", "q:eve")],
        [btn("🌅 Завтра в 9:00", "q:tom"), btn("❌ Отмена", "q:cancel")],
    ])


HELP_TEXT = (
    "❓ <b>Как пользоваться</b>\n\n"
    "Просто напиши, <b>что</b> и <b>когда</b> напомнить:\n"
    "• <i>через 20 минут выключить духовку</i>\n"
    "• <i>через полтора часа забрать посылку</i>\n"
    "• <i>завтра в 9 позвонить маме</i>\n"
    "• <i>в 18:30 тренировка</i>\n"
    "• <i>в пятницу в 7 вечера кино</i>\n"
    "• <i>25 октября в 10:00 к врачу</i>   или   <i>25.10 в 10:00 к врачу</i>\n"
    "• <i>сегодня вечером купить хлеб</i>\n\n"
    "🔁 <b>Повторяющиеся:</b>\n"
    "• <i>каждый день в 8:00 зарядка</i>\n"
    "• <i>по будням в 7:30 будильник для кота</i>\n"
    "• <i>по понедельникам и средам в 18 бассейн</i>\n"
    "• <i>каждые 2 часа пить воду</i>\n"
    "• <i>каждый месяц 5 числа в 10 оплатить интернет</i>\n"
    "• <i>через полтора часа забрать посылку</i>, <i>в полдень обед</i>\n\n"
    "Если время не указано — бот предложит кнопки.\n\n"
    "📣 Когда придёт напоминание, бот будет <b>повторять его</b>, пока не нажмёшь «✅ Готово». "
    "Можно отложить: +10 мин, +1 час, на завтра.\n\n"
    "<b>Команды:</b> /list — задачи, /today — сегодня, /stats — статистика, "
    "/settings — настройки, /cancel — отменить ввод, /id — твой ID"
)


# ╔════════════════════════════════════════════════════════════════╗
# ║                 ОТПРАВКА И ПЛАНИРОВЩИК                         ║
# ╚════════════════════════════════════════════════════════════════╝

async def safe_send(bot: Bot, chat_id: int, text: str, kb=None) -> Optional[int]:
    """Отправляет сообщение. Возвращает его ID или None."""
    for _ in range(2):
        try:
            msg = await bot.send_message(chat_id, text, reply_markup=kb)
            return msg.message_id
        except TelegramRetryAfter as error:
            await asyncio.sleep(error.retry_after + 1)
        except TelegramForbiddenError:
            get_user(chat_id)["blocked"] = True   # человек заблокировал бота
            save_data()
            log.info("Пользователь %s заблокировал бота", chat_id)
            return None
        except TelegramAPIError as error:
            log.warning("Не удалось отправить %s: %s", chat_id, error)
            return None
    return None


async def safe_delete(bot: Bot, chat_id: int, message_id: Optional[int]) -> None:
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramAPIError:
        pass  # старое сообщение (старше 48 ч) удалить нельзя — не страшно


async def fire(bot: Bot, task: dict, is_nag: bool) -> None:
    """Отправляет напоминание (первое или повторное)."""
    user = get_user(task["uid"])
    if is_nag:
        task["nag_count"] += 1
        user["stats"]["nags"] += 1
        await safe_delete(bot, task["uid"], task["msg_id"])  # убираем прошлое, чтобы не было каши
    else:
        task["fired"] = True
        task["nag_count"] = 0
        task["late"] = time.time() - task["due"] > 120
    msg_id = await safe_send(bot, task["uid"], reminder_text(task), reminder_kb(task))
    task["msg_id"] = msg_id
    task["next_nag"] = time.time() + user["nag"] * 60 if user["nag"] else None
    save_data()


async def tick(bot: Bot) -> None:
    """Одна проверка: кому пора напомнить."""
    now = time.time()
    for task in list(DATA["tasks"].values()):
        if task["status"] != "active":
            continue
        user = get_user(task["uid"])
        if user.get("blocked") or not has_access(task["uid"]):
            continue

        if not task["fired"]:
            if now >= task["due"]:
                await fire(bot, task, is_nag=False)
            continue

        # Напоминание уже пришло, но «Готово» не нажали.
        # У повторяющейся задачи подошёл следующий раз — переходим к нему.
        if task["repeat"]:
            planned = task.get("anchor", task["due"])
            following = next_due(dict(task, due=planned), planned)
            if now >= following:
                await safe_delete(bot, task["uid"], task["msg_id"])
                task["due"] = following
                task.pop("anchor", None)
                reset_firing(task)
                save_data()
                continue

        # Повторяем («спамим»), если включено
        if (nag_enabled(task, user) and not task["nag_stop"] and task["next_nag"]
                and now >= task["next_nag"] and task["nag_count"] < NAG_LIMIT
                and not in_quiet_hours(user)):
            await fire(bot, task, is_nag=True)

    # Утренний план
    for key, user in DATA["users"].items():
        if not user.get("digest") or user.get("blocked") or not has_access(int(key)):
            continue
        local = local_now(user)
        today = local.strftime("%Y-%m-%d")
        if user.get("digest_last") == today:
            continue
        digest_dt = local.replace(hour=int(user["digest"][:2]), minute=int(user["digest"][3:]),
                                  second=0, microsecond=0)
        if digest_dt <= local < digest_dt + timedelta(hours=3):
            user["digest_last"] = today
            save_data()
            text = today_text(int(key), morning=True)
            if text:
                await safe_send(bot, int(key), text)


async def scheduler(bot: Bot) -> None:
    """Бесконечный цикл: каждые несколько секунд проверяем задачи."""
    log.info("Планировщик запущен")
    while True:
        try:
            await tick(bot)
        except Exception as error:  # планировщик не должен падать никогда
            log.exception("Ошибка в планировщике: %s", error)
        await asyncio.sleep(CHECK_EVERY_SECONDS)


# ╔════════════════════════════════════════════════════════════════╗
# ║                 ДОСТУП И АНТИСПАМ                              ║
# ╚════════════════════════════════════════════════════════════════╝

def has_access(user_id: int) -> bool:
    """Можно ли этому человеку пользоваться ботом."""
    if user_id == OWNER_ID or user_id in ALLOWED_USERS:
        return True
    return bool(DATA.get("public", True))


class AccessMiddleware(BaseMiddleware):
    """Если владелец включил «🔒 Только я» — пускает только владельца и ALLOWED_USERS."""

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is None or not has_access(user.id):
            if isinstance(event, Message):
                if event.text and event.text.startswith("/id"):
                    await event.answer(f"🆔 Твой ID: <code>{event.from_user.id}</code>")
                else:
                    await event.answer("⛔ Это личный бот.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Это личный бот.", show_alert=True)
            return None
        return await handler(event, data)


class ThrottleMiddleware(BaseMiddleware):
    """Слишком частые нажатия/сообщения игнорируются."""

    def __init__(self, seconds: float):
        self.seconds = seconds
        self.last: Dict[int, float] = {}

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user is not None:
            now = time.monotonic()
            if now - self.last.get(user.id, 0.0) < self.seconds:
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer("⏳ Не так быстро!")
                    except TelegramAPIError:
                        pass
                return None
            self.last[user.id] = now
        return await handler(event, data)


# ╔════════════════════════════════════════════════════════════════╗
# ║                 ОБРАБОТЧИКИ КОМАНД И КНОПОК                    ║
# ╚════════════════════════════════════════════════════════════════╝

router = Router()
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")
router.message.outer_middleware(AccessMiddleware())
router.callback_query.outer_middleware(AccessMiddleware())
router.callback_query.middleware(ThrottleMiddleware(0.5))


async def show(callback: CallbackQuery, text: str, kb=None) -> None:
    """Обновляет сообщение с кнопкой (или присылает новое)."""
    msg = callback.message
    if isinstance(msg, Message):
        try:
            await msg.edit_text(text, reply_markup=kb)
            return
        except TelegramBadRequest as error:
            if "not modified" in str(error).lower():
                return
    await callback.bot.send_message(callback.from_user.id, text, reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = get_user(message.from_user.id, message.from_user.first_name)
    user["blocked"] = False
    save_data()
    STATE.pop(message.from_user.id, None)
    await message.answer(
        f"👋 Привет, <b>{html.escape(message.from_user.first_name or 'друг')}</b>!\n\n"
        "Я — напоминалка «Не забудь!». Напиши, <b>что</b> и <b>когда</b> напомнить:\n\n"
        "• <i>через 20 минут выключить духовку</i>\n"
        "• <i>завтра в 9 позвонить маме</i>\n"
        "• <i>каждый день в 8:00 зарядка</i>\n\n"
        "Я буду напоминать снова и снова, пока не нажмёшь «✅ Готово» 😉\n\n"
        f"🌍 Часовой пояс: {tz_label(user)} (у тебя сейчас {local_now(user).strftime('%H:%M')}). "
        "Если время не совпадает — поправь в «⚙️ Настройках».",
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
@router.message(F.text == BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu())


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"🆔 Твой Telegram ID: <code>{message.from_user.id}</code>")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message) -> None:
    STATE.pop(message.from_user.id, None)
    await message.answer("👌 Отменено.", reply_markup=main_menu())


@router.message(Command("new"))
@router.message(F.text == BTN_NEW)
async def cmd_new(message: Message) -> None:
    STATE.pop(message.from_user.id, None)
    await message.answer("✍️ Напиши задачу и время одним сообщением, например:\n"
                         "<i>через 30 минут проверить почту</i>\n\n"
                         "Можно и без времени — тогда я предложу кнопки.")


@router.message(Command("list"))
@router.message(F.text == BTN_LIST)
async def cmd_list(message: Message) -> None:
    text, kb = list_view(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.message(Command("today"))
@router.message(F.text == BTN_TODAY)
async def cmd_today(message: Message) -> None:
    await message.answer(today_text(message.from_user.id))


@router.message(Command("stats"))
@router.message(F.text == BTN_STATS)
async def cmd_stats(message: Message) -> None:
    await message.answer(stats_text(message.from_user.id))


@router.message(Command("settings"))
@router.message(F.text == BTN_SETTINGS)
async def cmd_settings(message: Message) -> None:
    uid = message.from_user.id
    await message.answer(settings_text(uid), reply_markup=settings_kb(uid))


@router.message(F.text)
async def on_text(message: Message) -> None:
    """Любой текст: разбираем как новую задачу (или как ответ на вопрос бота)."""
    uid = message.from_user.id
    user = get_user(uid, message.from_user.first_name)
    text = message.text.strip()
    state = STATE.get(uid)

    if text.startswith("/"):
        await message.answer("Не знаю такой команды. Посмотри /help")
        return

    # --- Ждём новый текст задачи ---
    if state and state["mode"] == "rename":
        task = get_task(state["task_id"])
        STATE.pop(uid, None)
        if not task:
            await message.answer("Задача не найдена.")
            return
        task["text"] = text[:MAX_TEXT_LENGTH]
        save_data()
        await message.answer(task_card_text(task, "✏️ Текст изменён"), reply_markup=task_card_kb(task))
        return

    parsed = parse_request(text, user)

    # --- Ждём время (для новой задачи или для изменения) ---
    if state and state["mode"] in ("await_time", "edit_time"):
        if parsed.error:
            await message.answer(f"⚠️ {parsed.error}")
            return
        if parsed.due is None:
            await message.answer("🤔 Не понял время. Напиши, например: <i>в 18:30</i>, "
                                 "<i>через 2 часа</i>, <i>завтра в 9</i>.\nИли /cancel",
                                 reply_markup=ask_time_kb() if state["mode"] == "await_time" else None)
            return
        if parsed.due < time.time() - 60:
            await message.answer("⚠️ Это время уже прошло. Укажи время в будущем или /cancel")
            return
        STATE.pop(uid, None)
        if state["mode"] == "edit_time":
            task = get_task(state["task_id"])
            if not task:
                await message.answer("Задача не найдена.")
                return
            task["due"] = parsed.due
            task.pop("anchor", None)
            if parsed.repeat:
                task["repeat"] = parsed.repeat
            reset_firing(task)
            save_data()
            await message.answer(task_card_text(task, "🕒 Время изменено"), reply_markup=task_card_kb(task))
            return
        task = create_task(uid, state["text"], parsed.due, parsed.repeat)
        await message.answer(task_card_text(task, "✅ <b>Готово! Напомню:</b>"), reply_markup=task_card_kb(task))
        return

    # --- Обычное сообщение = новая задача ---
    if parsed.error:
        await message.answer(f"⚠️ {parsed.error}")
        return
    if len(user_tasks(uid)) >= MAX_TASKS_PER_USER:
        await message.answer(f"⚠️ У тебя уже {MAX_TASKS_PER_USER} задач. Удали лишние в «📋 Мои задачи».")
        return
    if parsed.due is None:
        STATE[uid] = {"mode": "await_time", "text": parsed.text or text[:MAX_TEXT_LENGTH]}
        await message.answer(f"📝 <b>{html.escape(STATE[uid]['text'])}</b>\n\n"
                             "⏰ Когда напомнить? Нажми кнопку или напиши время "
                             "(<i>в 18:30</i>, <i>через 2 часа</i>, <i>завтра в 9</i>).",
                             reply_markup=ask_time_kb())
        return
    if parsed.due < time.time() - 60:
        await message.answer("⚠️ Это время уже прошло. Укажи время в будущем.")
        return
    task = create_task(uid, parsed.text, parsed.due, parsed.repeat)
    await message.answer(task_card_text(task, "✅ <b>Готово! Напомню:</b>"), reply_markup=task_card_kb(task))


@router.message()
async def on_other(message: Message) -> None:
    await message.answer("Я понимаю только текст 🙂 Напиши задачу, например: <i>через час позвонить</i>")


# ----------------------- Быстрый выбор времени -----------------------

@router.callback_query(F.data.startswith("q:"))
async def cb_quick_time(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    user = get_user(uid)
    state = STATE.get(uid)
    code = callback.data[2:]
    if code == "cancel":
        STATE.pop(uid, None)
        await callback.answer("Отменено")
        await show(callback, "👌 Отменено.")
        return
    if not state or state["mode"] != "await_time":
        await callback.answer("Напиши задачу ещё раз 🙂", show_alert=True)
        return
    now = local_now(user)
    if code == "eve":
        due = now.replace(hour=19, minute=0, second=0, microsecond=0)
        if due <= now:
            due += timedelta(days=1)
    elif code == "tom":
        due = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        due = now + timedelta(minutes=int(code))
    STATE.pop(uid, None)
    task = create_task(uid, state["text"], due.timestamp(), None)
    await callback.answer("✅ Сохранено")
    await show(callback, task_card_text(task, "✅ <b>Готово! Напомню:</b>"), task_card_kb(task))


# ----------------------- Список -----------------------

@router.callback_query(F.data == "list")
async def cb_list(callback: CallbackQuery) -> None:
    text, kb = list_view(callback.from_user.id)
    await callback.answer()
    await show(callback, text, kb)


# ----------------------- Действия с задачей -----------------------

@router.callback_query(F.data.startswith("t:") | F.data.startswith("r:"))
async def cb_task(callback: CallbackQuery) -> None:
    """t:<id>:<действие> — карточка задачи;  r:<id>:<действие> — сообщение-напоминание."""
    uid = callback.from_user.id
    try:
        source, tid, action = callback.data.split(":", 2)
    except ValueError:
        await callback.answer()
        return
    task = get_task(tid)
    if not task or task["uid"] != uid:
        await callback.answer("Эта задача уже выполнена или удалена.", show_alert=True)
        if source == "r" and isinstance(callback.message, Message):
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except TelegramAPIError:
                pass
        return

    from_reminder = source == "r"
    result = None
    if from_reminder and action in ("done", "s10", "s60", "tom", "quiet") and not task["fired"]:
        await callback.answer("Это напоминание уже обработано 👍", show_alert=True)
        if isinstance(callback.message, Message):
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except TelegramAPIError:
                pass
        return
    # Если задачу закрывают из карточки, у висящего напоминания убираем кнопки
    stale_msg = task.get("msg_id") if task["fired"] and not from_reminder and action in ("done", "s10", "s60", "tom", "delyes") else None
    if stale_msg:
        task["msg_id"] = None
        try:
            await callback.bot.edit_message_reply_markup(chat_id=uid, message_id=stale_msg, reply_markup=None)
        except TelegramAPIError:
            pass

    if action == "view":
        await callback.answer()
        await show(callback, task_card_text(task), task_card_kb(task))
        return
    if action == "done":
        result = complete_task(task)
        await callback.answer("✅ Отлично!")
    elif action in ("s10", "s60"):
        result = snooze_task(task, minutes=10 if action == "s10" else 60)
        await callback.answer("⏰ Отложено")
    elif action == "tom":
        result = snooze_task(task, tomorrow=True)
        await callback.answer("🌅 На завтра")
    elif action == "quiet":
        task["nag_stop"] = True
        save_data()
        await callback.answer("🔕 Больше не повторяю это напоминание")
        await show(callback, reminder_text(task), reminder_kb(task))
        return
    elif action == "nag":
        user = get_user(uid)
        if user["nag"] == 0:
            await callback.answer("Повторы выключены в ⚙️ Настройках", show_alert=True)
            return
        task["nag"] = not task["nag"]
        task["nag_stop"] = False
        save_data()
        await callback.answer("📣 Повторы включены" if task["nag"] else "🔕 Повторы выключены")
        await show(callback, task_card_text(task), task_card_kb(task))
        return
    elif action == "del":
        await callback.answer()
        await show(callback, f"🗑 Удалить задачу?\n\n📝 <b>{html.escape(task['text'])}</b>",
                   InlineKeyboardMarkup(inline_keyboard=[[
                       btn("🗑 Да, удалить", f"t:{tid}:delyes"), btn("⬅️ Нет", f"t:{tid}:view")]]))
        return
    elif action == "delyes":
        task["status"] = "deleted"
        task["done_at"] = time.time()
        save_data()
        await callback.answer("🗑 Удалено")
        text, kb = list_view(uid)
        await show(callback, "🗑 Задача удалена.\n\n" + text, kb)
        return
    elif action == "edit":
        STATE[uid] = {"mode": "edit_time", "task_id": tid}
        await callback.answer()
        await callback.bot.send_message(uid, "🕒 Напиши новое время: <i>в 18:30</i>, <i>через 2 часа</i>, "
                                      "<i>завтра в 9</i>, <i>каждый день в 8</i>.\n/cancel — отмена")
        return
    elif action == "rename":
        STATE[uid] = {"mode": "rename", "task_id": tid}
        await callback.answer()
        await callback.bot.send_message(uid, "✏️ Напиши новый текст задачи.\n/cancel — отмена")
        return
    else:
        await callback.answer()
        return

    # Результат «Готово» / «Отложить»
    if from_reminder:
        await show(callback, result)          # сообщение-напоминание превращается в итог
    elif get_task(tid):
        await show(callback, task_card_text(task, result), task_card_kb(task))
    else:
        text, kb = list_view(uid)
        await show(callback, result + "\n\n" + text, kb)


# ----------------------- Настройки -----------------------

@router.callback_query(F.data.startswith("s:"))
async def cb_settings(callback: CallbackQuery) -> None:
    uid = callback.from_user.id
    user = get_user(uid)
    action = callback.data[2:]
    if action == "tz-":
        user["tz"] = max(-12 * 60, user["tz"] - 60)
    elif action == "tz+":
        user["tz"] = min(14 * 60, user["tz"] + 60)
    elif action == "nag":
        idx = NAG_OPTIONS.index(user["nag"]) if user["nag"] in NAG_OPTIONS else 0
        user["nag"] = NAG_OPTIONS[(idx + 1) % len(NAG_OPTIONS)]
    elif action == "dig":
        idx = DIGEST_OPTIONS.index(user["digest"]) if user["digest"] in DIGEST_OPTIONS else 0
        user["digest"] = DIGEST_OPTIONS[(idx + 1) % len(DIGEST_OPTIONS)]
        user["digest_last"] = local_now(user).strftime("%Y-%m-%d")  # не присылать прямо сейчас
    elif action == "quiet":
        user["quiet"] = not user["quiet"]
    elif action == "public":
        if uid != OWNER_ID:
            await callback.answer("⛔ Только для владельца", show_alert=True)
            return
        DATA["public"] = not DATA.get("public", True)
        save_data()
        await callback.answer("🔓 Теперь ботом пользуются все" if DATA["public"]
                              else "🔒 Теперь бот только твой", show_alert=True)
        await show(callback, settings_text(uid), settings_kb(uid))
        return
    save_data()
    await callback.answer()
    await show(callback, settings_text(uid), settings_kb(uid))


@router.callback_query()
async def cb_unknown(callback: CallbackQuery) -> None:
    await callback.answer("Кнопка устарела 🙂")


# ╔════════════════════════════════════════════════════════════════╗
# ║                        ЗАПУСК                                  ║
# ╚════════════════════════════════════════════════════════════════╝

async def on_error(event: ErrorEvent) -> bool:
    log.error("Ошибка: %r", event.exception, exc_info=event.exception)
    return True


async def main() -> None:
    global DATA
    DATA = load_data()
    cutoff = time.time() - 30 * 86400          # выполненные и удалённые храним 30 дней
    for key in [k for k, t in DATA["tasks"].items()
                if t.get("status") != "active" and t.get("done_at", t.get("created", 0)) < cutoff]:
        del DATA["tasks"][key]
    save_data()

    bot = Bot(token=BOT_TOKEN.strip(), default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_router(router)
    dp.errors.register(on_error)

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

    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Начать"),
            BotCommand(command="list", description="Мои задачи"),
            BotCommand(command="today", description="Что на сегодня"),
            BotCommand(command="stats", description="Статистика"),
            BotCommand(command="settings", description="Настройки"),
            BotCommand(command="help", description="Как пользоваться"),
            BotCommand(command="cancel", description="Отменить ввод"),
        ])
    except TelegramAPIError:
        pass

    active = sum(1 for t in DATA["tasks"].values() if t["status"] == "active")
    print("=" * 60)
    print(f"Бот @{me.username} запущен! Остановить: Ctrl + C")
    print(f"Активных напоминаний: {active}")
    print(f"Файл данных: {DATA_FILE}")
    print("=" * 60)

    scheduler_task = asyncio.create_task(scheduler(bot))
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()


if __name__ == "__main__":
    token = BOT_TOKEN.strip()
    if not token or token == "ВСТАВЬ_ТОКЕН_СЮДА" or ":" not in token:
        print("ОШИБКА: вставь токен бота в строку BOT_TOKEN = \"...\" (внутри кавычек).")
        sys.exit(1)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен.")
