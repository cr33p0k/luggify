import asyncio
import logging

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from telegram_bot.config import get_bot_settings
from telegram_bot.keyboards import (
    build_ai_menu,
    build_checklist_keyboard,
    build_confirmation_keyboard,
    build_main_menu,
    build_trip_picker,
)
from telegram_bot.services import (
    build_account_debug_text,
    build_interactive_checklist_view,
    build_remaining_items_text,
    build_trip_overview_text,
    confirm_ai_actions_for_telegram,
    ensure_telegram_user,
    get_checklists_for_picker,
    get_selected_or_primary_checklist,
    link_web_account_from_telegram,
    process_ai_prompt_for_telegram,
    toggle_interactive_checklist_item,
)


router = Router()


class AIChatState(StatesGroup):
    waiting_for_question = State()


HELP_TEXT = (
    "Я могу помочь так:\n"
    "/start — открыть главное меню\n"
    "/link <код> — привязать Telegram к аккаунту с сайта\n"
    "/trip — показать ближайшую поездку\n"
    "/list — открыть чеклист кнопками\n"
    "/forgot — показать, что ещё не собрано\n"
    "/choose — выбрать конкретную поездку\n"
    "/whoami — показать Telegram-статус и привязку\n"
    "/ai — включить AI-режим\n\n"
    "Примеры:\n"
    "— добавить: добавь powerbank / закинь мне воду\n"
    "— отметить: отметь паспорт / отметь у popich фен\n"
    "— удалить: удали фен / удали у creepok свитер\n"
    "— переместить: перекинь power bank popich\n"
    "— багаж: создай багаж чемодан\n"
    "— состояние: что уже отмечено / что осталось собрать\n\n"
    "Если поездки ещё нет, AI тоже работает в формате:\n"
    "Париж | что попробовать из еды?"
)


def _format_pending_actions(actions) -> str:
    labels = {
        "add": "добавить",
        "remove": "удалить",
        "check": "отметить",
        "uncheck": "снять отметку",
    }
    lines = []
    for action in actions or []:
        label = labels.get(action.get("type"), action.get("type"))
        items = ", ".join(action.get("items") or [])
        if items:
            lines.append(f"• {label}: {items}")
    return "\n".join(lines)


async def _get_selected_slug(state: FSMContext):
    data = await state.get_data()
    return data.get("selected_checklist_slug")


async def _reset_dialog_state(state: FSMContext):
    selected_slug = await _get_selected_slug(state)
    await state.set_state(None)
    await state.update_data(
        selected_checklist_slug=selected_slug,
        pending_ai_actions=None,
        pending_ai_checklist_slug=None,
        pending_ai_language=None,
        pending_trip_prompt=None,
    )


async def _handle_ai_result(message: Message, state: FSMContext, result: dict):
    if result["mode"] == "confirm":
        await state.update_data(
            pending_ai_actions=result["actions"],
            pending_ai_checklist_slug=result["checklist_slug"],
            pending_ai_language="ru",
            pending_trip_prompt=None,
        )
        await message.answer(
            f"Подтвердите изменение для поездки {result['checklist_title']}:\n\n"
            f"{_format_pending_actions(result['actions'])}",
            reply_markup=build_confirmation_keyboard(),
        )
        return

    if result["mode"] == "pick_trip":
        await state.update_data(
            pending_trip_prompt=result["prompt"],
            pending_ai_actions=None,
            pending_ai_checklist_slug=None,
            pending_ai_language=None,
        )
        await message.answer(
            result["message"],
            reply_markup=build_trip_picker(
                result["checklists"],
                callback_prefix="pick_trip_for_prompt",
                include_cancel=True,
                cancel_callback="pick_trip_for_prompt:cancel",
            ),
        )
        return

    await state.update_data(
        pending_ai_actions=None,
        pending_ai_checklist_slug=None,
        pending_ai_language=None,
        pending_trip_prompt=None,
    )
    await message.answer(result["message"], reply_markup=build_ai_menu(get_bot_settings()))


async def _safe_edit_checklist_message(callback: CallbackQuery, text: str, reply_markup):
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


def _extract_command_argument(message: Message) -> str:
    command_text = (message.text or "").strip()
    return command_text.split(maxsplit=1)[1].strip() if " " in command_text else ""


async def _process_link_request(message: Message, state: FSMContext) -> bool:
    await _reset_dialog_state(state)
    settings = get_bot_settings()
    raw_text = (message.text or "").strip()
    payload = _extract_command_argument(message)

    if raw_text.startswith("/start ") and payload.startswith("link_"):
        payload = payload.removeprefix("link_")
    elif raw_text.startswith("/link@"):
        parts = raw_text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else ""
    elif payload.startswith("link_"):
        payload = payload.removeprefix("link_")

    if not raw_text.startswith("/link") and not raw_text.startswith("/start link_"):
        return False

    if not payload:
        await message.answer(
            "Откройте привязку Telegram на сайте ещё раз. Я жду команду вида /link <код>.",
            reply_markup=build_main_menu(settings),
        )
        return True

    link_message = await link_web_account_from_telegram(message.from_user, payload)
    await message.answer(link_message, reply_markup=build_main_menu(settings))
    return True


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    await _reset_dialog_state(state)
    settings = get_bot_settings()
    start_payload = _extract_command_argument(message)

    if start_payload.startswith("link_"):
        link_message = await link_web_account_from_telegram(
            message.from_user,
            start_payload.removeprefix("link_"),
        )
        await message.answer(link_message, reply_markup=build_main_menu(settings))
        return

    await ensure_telegram_user(message.from_user)
    welcome = (
        f"Привет, {message.from_user.first_name or 'путешественник'}!\n\n"
        "Я Telegram-помощник Luggify. Могу показать ближайшую поездку, напомнить, "
        "что ещё не собрано, отвечать через AI и даже менять чеклист по вашей фразе."
    )
    await message.answer(welcome, reply_markup=build_main_menu(settings))


@router.message(Command("link"))
async def handle_link(message: Message, state: FSMContext):
    await _process_link_request(message, state)


@router.message(Command("help"))
@router.message(F.text == "Помощь")
async def handle_help(message: Message, state: FSMContext):
    await _reset_dialog_state(state)
    await message.answer(HELP_TEXT, reply_markup=build_main_menu(get_bot_settings()))


@router.message(Command("trip"))
@router.message(F.text == "Моя поездка")
async def handle_trip(message: Message, state: FSMContext):
    await _reset_dialog_state(state)
    await ensure_telegram_user(message.from_user)
    selected_slug = await _get_selected_slug(state)
    await message.answer(
        await build_trip_overview_text(message.from_user, selected_slug),
        reply_markup=build_main_menu(get_bot_settings()),
    )


@router.message(Command("list"))
@router.message(F.text == "Чеклист")
async def handle_checklist(message: Message, state: FSMContext):
    await _reset_dialog_state(state)
    await ensure_telegram_user(message.from_user)
    selected_slug = await _get_selected_slug(state)
    view = await build_interactive_checklist_view(message.from_user, selected_slug=selected_slug)
    if not view["ok"]:
        await message.answer(view["message"], reply_markup=build_main_menu(get_bot_settings()))
        return

    await message.answer(
        view["text"],
        reply_markup=build_checklist_keyboard(view),
    )


@router.message(Command("forgot"))
@router.message(F.text == "Что я забыл?")
async def handle_forgot(message: Message, state: FSMContext):
    await _reset_dialog_state(state)
    await ensure_telegram_user(message.from_user)
    selected_slug = await _get_selected_slug(state)
    await message.answer(
        await build_remaining_items_text(message.from_user, selected_slug),
        reply_markup=build_main_menu(get_bot_settings()),
    )


@router.message(Command("choose"))
@router.message(F.text == "Выбрать поездку")
async def handle_choose_trip(message: Message, state: FSMContext):
    await ensure_telegram_user(message.from_user)
    await state.update_data(
        pending_ai_actions=None,
        pending_ai_checklist_slug=None,
        pending_ai_language=None,
        pending_trip_prompt=None,
    )
    checklists = await get_checklists_for_picker(message.from_user)
    if not checklists:
        await message.answer(
            "Пока не вижу поездок для выбора. Сначала создайте чеклист в приложении.",
            reply_markup=build_main_menu(get_bot_settings()),
        )
        return

    selected_slug = await _get_selected_slug(state)
    await message.answer(
        "Выберите поездку, с которой я буду работать по умолчанию:",
        reply_markup=build_trip_picker(checklists, selected_slug),
    )


@router.message(Command("whoami"))
async def handle_whoami(message: Message, state: FSMContext):
    await ensure_telegram_user(message.from_user)
    selected_slug = await _get_selected_slug(state)
    await message.answer(
        await build_account_debug_text(message.from_user, selected_slug),
        reply_markup=build_main_menu(get_bot_settings()),
    )


@router.callback_query(F.data.startswith("pick_trip:"))
async def handle_pick_trip(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 1)[1]
    checklist = await get_selected_or_primary_checklist(callback.from_user, slug)
    if not checklist or checklist.slug != slug:
        await callback.answer("Не удалось выбрать поездку", show_alert=True)
        return

    await state.update_data(
        selected_checklist_slug=slug,
        pending_ai_actions=None,
        pending_ai_checklist_slug=None,
        pending_ai_language=None,
        pending_trip_prompt=None,
    )
    await callback.answer("Поездка выбрана")
    await callback.message.edit_text(
        "Теперь работаю с поездкой по умолчанию:\n\n"
        + await build_trip_overview_text(callback.from_user, slug)
    )


@router.callback_query(F.data.startswith("pick_trip_for_prompt:"))
async def handle_pick_trip_for_prompt(callback: CallbackQuery, state: FSMContext):
    slug = callback.data.split(":", 1)[1]
    if slug == "cancel":
        await state.update_data(pending_trip_prompt=None)
        await callback.answer("Отменено")
        await callback.message.edit_text("Окей, ничего не меняю.")
        return

    data = await state.get_data()
    prompt = data.get("pending_trip_prompt")
    if not prompt:
        await callback.answer("Запрос уже устарел", show_alert=True)
        return

    checklist = await get_selected_or_primary_checklist(callback.from_user, slug)
    if not checklist or checklist.slug != slug:
        await callback.answer("Не удалось выбрать поездку", show_alert=True)
        return

    await state.update_data(selected_checklist_slug=slug, pending_trip_prompt=None)
    await callback.answer("Поездка выбрана")
    result = await process_ai_prompt_for_telegram(callback.from_user, prompt, slug)
    await callback.message.edit_text(
        f"Работаю с поездкой {checklist.city}.\n\n{result['message']}"
        if result["mode"] != "confirm"
        else f"Работаю с поездкой {checklist.city}."
    )
    if result["mode"] == "confirm":
        await state.update_data(
            pending_ai_actions=result["actions"],
            pending_ai_checklist_slug=result["checklist_slug"],
            pending_ai_language="ru",
        )
        await callback.message.answer(
            f"Подтвердите изменение для поездки {result['checklist_title']}:\n\n"
            f"{_format_pending_actions(result['actions'])}",
            reply_markup=build_confirmation_keyboard(),
        )


@router.message(Command("ai"))
@router.message(F.text == "Спросить ИИ")
async def handle_ai_entry(message: Message, state: FSMContext):
    await ensure_telegram_user(message.from_user)
    command_text = (message.text or "").strip()
    parts = command_text.split(maxsplit=1)
    direct_prompt = parts[1].strip() if len(parts) > 1 and command_text.startswith("/ai") else ""
    selected_slug = await _get_selected_slug(state)

    if direct_prompt:
        result = await process_ai_prompt_for_telegram(message.from_user, direct_prompt, selected_slug)
        await state.set_state(AIChatState.waiting_for_question)
        await _handle_ai_result(message, state, result)
        return

    await state.set_state(AIChatState.waiting_for_question)
    await message.answer(
        "Напиши вопрос или команду.\n\n"
        "— добавить: закинь мне воду\n"
        "— отметить: отметь у popich паспорт\n"
        "— удалить: удали у creepok свитер\n"
        "— переместить: перекинь power bank popich\n"
        "— состояние: что уже отмечено\n\n"
        "Без чеклиста тоже можно: Город | вопрос",
        reply_markup=build_ai_menu(get_bot_settings()),
    )


@router.message(F.text == "Стоп AI")
async def handle_ai_stop(message: Message, state: FSMContext):
    await _reset_dialog_state(state)
    await message.answer(
        "AI-режим остановлен. Можно вернуться к меню.",
        reply_markup=build_main_menu(get_bot_settings()),
    )


@router.message(AIChatState.waiting_for_question)
async def handle_ai_question(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Лучше отправьте текстовый вопрос.")
        return

    data = await state.get_data()
    if data.get("pending_ai_actions"):
        await message.answer(
            "Сначала подтвердите предыдущее изменение кнопками Да или Нет.",
            reply_markup=build_confirmation_keyboard(),
        )
        return
    if data.get("pending_trip_prompt"):
        await message.answer("Сначала выберите поездку кнопками ниже или нажмите Отмена.")
        return

    result = await process_ai_prompt_for_telegram(
        message.from_user,
        message.text,
        data.get("selected_checklist_slug"),
    )
    await _handle_ai_result(message, state, result)


@router.callback_query(F.data == "confirm_ai:yes")
async def handle_confirm_ai_yes(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    pending_actions = data.get("pending_ai_actions")
    checklist_slug = data.get("pending_ai_checklist_slug")
    language = data.get("pending_ai_language") or "ru"

    if not pending_actions or not checklist_slug:
        await callback.answer("Подтверждение устарело", show_alert=True)
        return

    result = await confirm_ai_actions_for_telegram(
        callback.from_user,
        checklist_slug,
        pending_actions,
        language,
    )
    await state.update_data(
        pending_ai_actions=None,
        pending_ai_checklist_slug=None,
        pending_ai_language=None,
        pending_trip_prompt=None,
    )
    await callback.answer("Готово")
    await callback.message.edit_text(result["message"])


@router.callback_query(F.data == "confirm_ai:no")
async def handle_confirm_ai_no(callback: CallbackQuery, state: FSMContext):
    await state.update_data(
        pending_ai_actions=None,
        pending_ai_checklist_slug=None,
        pending_ai_language=None,
    )
    await callback.answer("Отменено")
    await callback.message.edit_text("Окей, ничего не меняю.")


@router.callback_query(F.data == "cl:noop")
async def handle_checklist_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("cl:view:"))
async def handle_checklist_view(callback: CallbackQuery, state: FSMContext):
    await _reset_dialog_state(state)
    parts = (callback.data or "").split(":")
    if len(parts) != 5:
        await callback.answer("Не удалось открыть чеклист", show_alert=True)
        return

    _, _, checklist_id_raw, section_key, page_raw = parts
    try:
        checklist_id = int(checklist_id_raw)
        page = int(page_raw)
    except ValueError:
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return

    view = await build_interactive_checklist_view(
        callback.from_user,
        checklist_id=checklist_id,
        section_key=section_key,
        page=page,
    )
    if not view["ok"]:
        await callback.answer(view["message"], show_alert=True)
        return

    await callback.answer()
    await _safe_edit_checklist_message(callback, view["text"], build_checklist_keyboard(view))


@router.callback_query(F.data.startswith("cl:toggle:"))
async def handle_checklist_toggle(callback: CallbackQuery):
    parts = (callback.data or "").split(":")
    if len(parts) != 6:
        await callback.answer("Не удалось переключить вещь", show_alert=True)
        return

    _, _, checklist_id_raw, section_key, page_raw, item_index_raw = parts
    try:
        checklist_id = int(checklist_id_raw)
        page = int(page_raw)
        item_index = int(item_index_raw)
    except ValueError:
        await callback.answer("Некорректные данные кнопки", show_alert=True)
        return

    result = await toggle_interactive_checklist_item(
        callback.from_user,
        checklist_id=checklist_id,
        section_key=section_key,
        page=page,
        item_index=item_index,
    )
    if not result["ok"]:
        await callback.answer(result["message"], show_alert=True)
        return

    await callback.answer(result["message"])
    await _safe_edit_checklist_message(
        callback,
        result["view"]["text"],
        build_checklist_keyboard(result["view"]),
    )


@router.message()
async def handle_fallback(message: Message, state: FSMContext):
    if await _process_link_request(message, state):
        return

    await message.answer(
        "Пока я понимаю команды меню, /trip, /list, /forgot и /ai. "
        "Если хотите живой AI-диалог, нажмите «Спросить ИИ».",
        reply_markup=build_main_menu(get_bot_settings()),
    )


async def main():
    settings = get_bot_settings()
    if not settings.token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не задан. Бот не может стартовать.")

    logging.basicConfig(level=logging.INFO)
    bot = Bot(token=settings.token)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
