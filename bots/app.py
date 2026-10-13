# -*- coding: utf-8 -*-
"""
==================================================================
  Запуск ВСЕХ ботов одной программой:  python app.py
==================================================================

Зачем: каждый бот, запущенный отдельно, занимает ~150 МБ памяти.
Вместе в одной программе они делят библиотеки, и каждый следующий
бот добавляет лишь 10–20 МБ. Поэтому все боты помещаются даже
на маленьких бесплатных серверах.

Токены берутся из файла .env рядом с этим файлом или из переменных
окружения (на облачных площадках их задают в панели управления).
Бот без токена просто пропускается.
"""

import asyncio
import importlib
import logging
import os
import signal
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# ---------- Список ботов: (файл без .py, переменная с токеном, название) ----------
BOTS = [
    ("mirror_bot", "MIRROR_TOKEN", "Зеркальная комната"),
    ("reminder_bot", "REMINDER_TOKEN", "Напоминалка «Не забудь!»"),
]


def load_env_file(path: Path) -> None:
    """Читает файл .env (строки вида КЛЮЧ=значение). Переменные из панели площадки главнее."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S")
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
log = logging.getLogger("app")

try:
    from aiogram import Dispatcher, Router
except ImportError:
    print("ОШИБКА: не установлена библиотека aiogram 3. Выполни:  pip install -r requirements.txt")
    sys.exit(1)

# Несколько ботов в одной программе: сигнал остановки обрабатывает app.py, а не каждый бот.
_original_start_polling = Dispatcher.start_polling


async def _start_polling_without_signals(self, *bots, **kwargs):
    kwargs["handle_signals"] = False
    return await _original_start_polling(self, *bots, **kwargs)


Dispatcher.start_polling = _start_polling_without_signals


def token_ok(token: str) -> bool:
    return bool(token) and token != "ВСТАВЬ_ТОКЕН_СЮДА" and ":" in token


def use_data_dir(module) -> None:
    """Если задан DATA_DIR (постоянный диск на площадке), храним данные ботов там."""
    data_dir = os.environ.get("DATA_DIR")
    if not data_dir or not hasattr(module, "DATA_FILE"):
        return
    folder = Path(data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("DATA_FILE", "BACKUP_FILE", "TMP_FILE"):
        if hasattr(module, name):
            setattr(module, name, folder / getattr(module, name).name)


def detach_routers(module) -> None:
    """Перед перезапуском отцепляем обработчики бота от старого диспетчера."""
    for value in vars(module).values():
        if isinstance(value, Router) and not isinstance(value, Dispatcher):
            value._parent_router = None


async def keep_running(title: str, module) -> None:
    """Запускает бота и перезапускает его, если он упал (пауза растёт до 5 минут)."""
    pause = 10
    while True:
        detach_routers(module)
        started = time.monotonic()
        try:
            await module.main()
            log.warning("«%s» остановился.", title)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("«%s» упал с ошибкой.", title)
        pause = 10 if time.monotonic() - started > 600 else min(pause * 2, 300)
        log.info("Перезапуск «%s» через %s с.", title, pause)
        await asyncio.sleep(pause)


async def health_server(port: int) -> None:
    """Некоторые площадки ждут, что программа отвечает на порту. Отвечаем «OK»."""
    from aiohttp import web
    app = web.Application()
    app.router.add_get("/", lambda request: web.Response(text="OK: боты работают"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    log.info("Проверка работы доступна на порту %s", port)
    await asyncio.Event().wait()


# ---------- Резервная копия данных напоминалки в Telegram ----------
# На бесплатных площадках без постоянного диска (Render) файл reminders.json
# пропадает при каждом перезапуске. Поэтому, если включено TG_BACKUP=1,
# копия файла хранится закреплённым сообщением в чате владельца с ботом
# и восстанавливается оттуда при запуске.
TG_API = os.environ.get("TG_API", "https://api.telegram.org")
BACKUP_CAPTION = "#backup Резервная копия напоминаний (не открепляй это сообщение)"


async def tg_call(session, token, method, data=None, files=None):
    url = f"{TG_API}/bot{token}/{method}"
    if files:
        from aiohttp import FormData
        form = FormData()
        for k, v in (data or {}).items():
            form.add_field(k, v if isinstance(v, str) else __import__("json").dumps(v))
        for k, (name, content) in files.items():
            form.add_field(k, content, filename=name, content_type="application/json")
        async with session.post(url, data=form) as r:
            j = await r.json()
    else:
        async with session.post(url, json=data or {}) as r:
            j = await r.json()
    if not j.get("ok"):
        raise RuntimeError(f"{method}: {j.get('description')}")
    return j["result"]


async def restore_backup(token: str, owner: int, data_file: Path) -> None:
    import aiohttp
    if data_file.exists():
        return
    try:
        async with aiohttp.ClientSession() as s:
            chat = await tg_call(s, token, "getChat", {"chat_id": owner})
            msg = chat.get("pinned_message") or {}
            doc = msg.get("document") or {}
            if not (msg.get("caption", "").startswith("#backup") and doc.get("file_id")):
                log.info("Резервной копии в Telegram пока нет — начинаю с пустого файла.")
                return
            f = await tg_call(s, token, "getFile", {"file_id": doc["file_id"]})
            async with s.get(f"{TG_API}/file/bot{token}/{f['file_path']}") as r:
                raw = await r.read()
            __import__("json").loads(raw.decode("utf-8"))  # проверка, что файл целый
            data_file.write_bytes(raw)
            log.info("Данные напоминалки восстановлены из Telegram (%s байт).", len(raw))
    except Exception as error:
        log.warning("Не удалось восстановить копию из Telegram: %s", error)


async def backup_loop(token: str, owner: int, data_file: Path) -> None:
    import aiohttp
    last = data_file.stat().st_mtime if data_file.exists() else 0
    msg_id = None
    async with aiohttp.ClientSession() as s:
        try:
            chat = await tg_call(s, token, "getChat", {"chat_id": owner})
            pm = chat.get("pinned_message") or {}
            if pm.get("caption", "").startswith("#backup"):
                msg_id = pm["message_id"]
        except Exception:
            pass
        while True:
            await asyncio.sleep(30)
            try:
                if not data_file.exists() or data_file.stat().st_mtime == last:
                    continue
                last = data_file.stat().st_mtime
                content = data_file.read_bytes()
                media = {"type": "document", "media": "attach://file", "caption": BACKUP_CAPTION}
                if msg_id:
                    try:
                        await tg_call(s, token, "editMessageMedia", {"chat_id": str(owner), "message_id": str(msg_id), "media": media}, {"file": ("reminders.json", content)})
                        continue
                    except Exception as error:
                        if "not modified" in str(error):
                            continue
                        msg_id = None
                m = await tg_call(s, token, "sendDocument", {"chat_id": str(owner), "caption": BACKUP_CAPTION, "disable_notification": "true"}, {"document": ("reminders.json", content)})
                msg_id = m["message_id"]
                await tg_call(s, token, "pinChatMessage", {"chat_id": owner, "message_id": msg_id, "disable_notification": True})
            except asyncio.CancelledError:
                raise
            except Exception as error:
                log.warning("Резервная копия в Telegram не сохранилась: %s", error)


async def main() -> None:
    tasks = []
    print("=" * 60)
    for module_name, env_name, title in BOTS:
        if not (BASE_DIR / f"{module_name}.py").exists():
            continue
        if not token_ok(os.environ.get(env_name, "")):
            print(f"  –  {title}: пропущен (нет токена {env_name} в .env)")
            continue
        try:
            module = importlib.import_module(module_name)
        except Exception as error:
            print(f"  ✗  {title}: не удалось загрузить ({error})")
            continue
        use_data_dir(module)
        if os.environ.get("TG_BACKUP") == "1" and hasattr(module, "DATA_FILE") and os.environ.get("OWNER_ID", "").isdigit():
            token, owner = os.environ[env_name], int(os.environ["OWNER_ID"])
            await restore_backup(token, owner, module.DATA_FILE)
            tasks.append(asyncio.create_task(backup_loop(token, owner, module.DATA_FILE), name=title + " backup"))
        tasks.append(asyncio.create_task(keep_running(title, module), name=title))
        print(f"  ✓  {title}: запускается")
    if not tasks:
        print("  Нет ни одного бота с токеном. Впиши токены в файл .env")
        print("=" * 60)
        return
    print(f"  Ботов в работе: {sum(1 for t in tasks if not t.get_name().endswith(' backup'))}. Остановить: Ctrl + C")
    print("=" * 60)

    port = os.environ.get("PORT")
    if port and port.isdigit():
        tasks.append(asyncio.create_task(health_server(int(port)), name="health"))

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass  # Windows: Ctrl + C обрабатывается через KeyboardInterrupt

    waiter = asyncio.create_task(stop.wait())
    await asyncio.wait([waiter, *tasks], return_when=asyncio.FIRST_COMPLETED)
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    print("Все боты остановлены.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Все боты остановлены.")
