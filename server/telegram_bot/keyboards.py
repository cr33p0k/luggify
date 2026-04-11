from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from telegram_bot.config import TelegramBotSettings


def build_main_menu(settings: TelegramBotSettings) -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="Моя поездка"),
            KeyboardButton(text="Что я забыл?"),
        ],
        [
            KeyboardButton(text="Чеклист"),
            KeyboardButton(text="Выбрать поездку"),
        ],
        [
            KeyboardButton(text="Спросить ИИ"),
            KeyboardButton(text="Помощь"),
        ],
    ]

    if settings.mini_app_url:
        keyboard.append(
            [KeyboardButton(text="Открыть mini app", web_app=WebAppInfo(url=settings.mini_app_url))]
        )

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или напишите команду",
    )


def build_ai_menu(settings: TelegramBotSettings) -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text="Стоп AI")]]
    keyboard.append([KeyboardButton(text="Чеклист"), KeyboardButton(text="Выбрать поездку")])
    if settings.mini_app_url:
        keyboard.append(
            [KeyboardButton(text="Открыть mini app", web_app=WebAppInfo(url=settings.mini_app_url))]
        )

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Напишите вопрос про поездку",
    )


def build_trip_picker(
    checklists,
    selected_slug: str = None,
    callback_prefix: str = "pick_trip",
    include_cancel: bool = False,
    cancel_callback: str = "pick_trip_cancel",
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for checklist in checklists:
        is_selected = checklist.slug == selected_slug
        prefix = "✓ " if is_selected else ""
        title = f"{prefix}{checklist.city}"
        if checklist.start_date and checklist.end_date:
            title = f"{title} · {checklist.start_date:%d.%m} — {checklist.end_date:%d.%m}"
        builder.add(
            InlineKeyboardButton(
                text=title[:64],
                callback_data=f"{callback_prefix}:{checklist.slug}",
            )
        )
    if include_cancel:
        builder.add(InlineKeyboardButton(text="Отмена", callback_data=cancel_callback))
    builder.adjust(1)
    return builder.as_markup()


def build_confirmation_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Да", callback_data="confirm_ai:yes"),
        InlineKeyboardButton(text="Нет", callback_data="confirm_ai:no"),
    )
    return builder.as_markup()


def _trim_button_label(text: str, limit: int = 28) -> str:
    value = (text or "").strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def build_checklist_keyboard(view: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    checklist_id = view["checklist_id"]
    section_key = view["section_key"]
    page = view["page"]

    section_buttons = []
    for section in view["sections"]:
        section_buttons.append(
            InlineKeyboardButton(
                text=_trim_button_label(section["label"], 18),
                callback_data=f"cl:view:{checklist_id}:{section['key']}:{0 if not section['active'] else page}",
                style="primary" if section["active"] else None,
            )
        )
    if section_buttons:
        builder.row(*section_buttons, width=3)

    item_buttons = [
        InlineKeyboardButton(
            text=_trim_button_label(("✓ " if item["checked"] else "") + item.get("label", item["name"]), 30),
            callback_data=f"cl:toggle:{checklist_id}:{section_key}:{page}:{item_index}",
            style="success" if item["checked"] else None,
        )
        for item_index, item in enumerate(view["items"])
    ]
    for index in range(0, len(item_buttons), 2):
        builder.row(*item_buttons[index:index + 2])

    if view["page_count"] > 1:
        nav_row = []
        if view["page"] > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text="‹ Назад",
                    callback_data=f"cl:view:{checklist_id}:{section_key}:{view['page'] - 1}",
                )
            )
        nav_row.append(
            InlineKeyboardButton(
                text=f"{view['page'] + 1}/{view['page_count']}",
                callback_data="cl:noop",
            )
        )
        if view["page"] < view["page_count"] - 1:
            nav_row.append(
                InlineKeyboardButton(
                    text="Вперёд ›",
                    callback_data=f"cl:view:{checklist_id}:{section_key}:{view['page'] + 1}",
                )
            )
        builder.row(*nav_row)

    builder.row(
        InlineKeyboardButton(
            text="Обновить",
            callback_data=f"cl:view:{checklist_id}:{section_key}:{page}",
        )
    )
    return builder.as_markup()
