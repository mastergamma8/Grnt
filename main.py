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

# Реквизиты для сделок:
# Для RUB
RECEIVER_CARD = "2204120118196936"
# Для криптовалюты
CRYPTO_WALLET_TON = "UQB-qPuyNz9Ib75AHe43Jz39HBlThp9Bnvcetb06OfCnhsi2"
CRYPTO_WALLET_USDT = "TMVBMmiQ1cci4t4K6DSbJEMSNpoUufADC6"
CRYPTOBOT_LINK = "https://t.me/send?start=IVnVvwBFGe5t"

BOT_USERNAME = "TTHGRTbot"  # без символа @

# ===== Инициализация =====
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Глобальный словарь для хранения данных по сделкам
# Структура сделки:
# {
#   "buyer_id": ...,
#   "seller_id": ...,
#   "amount": ...,
#   "currency": ...,
#   "product": ...,
#   "buyer_screenshot": ...,
#   "seller_screenshot": ...,
#   "seller_requisites": ...,
# }
deals = {}

# ===== Определяем состояния =====
class Form(StatesGroup):
    waiting_for_currency = State()
    waiting_for_amount = State()
    waiting_for_product = State()
    waiting_for_payment_screenshot = State()
    waiting_for_transfer_screenshot = State()
    waiting_for_requisites = State()  # новый: ждём реквизиты от продавца

# ===== Основное меню (покупатель) =====
@dp.message(CommandStart())
async def start_handler(message: types.Message, state: FSMContext):
    # Если команда /start содержит аргумент вида "deal_XXXX" – это вход продавца в сделку
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
        # Проверяем, чтобы создатель сделки (покупатель) не мог присоединиться в качестве продавца
        if deals[deal_id]["buyer_id"] == message.from_user.id:
            await message.answer("⚠️ Вы не можете присоединиться к своей сделке.", parse_mode="HTML")
            return
        # Если продавец уже присоединился, уведомляем пользователя
        if deals[deal_id].get("seller_id") is not None:
            await message.answer("⚠️ Продавец уже присоединился к сделке.", parse_mode="HTML")
            return

        # Регистрируем пользователя как продавца
        deals[deal_id]["seller_id"] = message.from_user.id
        await message.answer(
            f"🔹 <b>Вы зашли в сделку #{deal_id}</b>\n\n"
            "📸 Отправьте скриншот, подтверждающий передачу товара.",
            parse_mode="HTML"
        )
        # Уведомляем покупателя, что продавец присоединился
        buyer_id = deals[deal_id]["buyer_id"]
        await bot.send_message(buyer_id, f"🔔 Продавец присоединился к сделке #{deal_id}.", parse_mode="HTML")
        await state.set_state(Form.waiting_for_transfer_screenshot)
    else:
        # Главное меню – кнопка "Создать сделку"
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Создать сделку", callback_data="create_deal")]
        ])
        await message.answer(
            "🎉 <b>Добро пожаловать в TTH GRT</b> – надежный P2P-гарант!\n\n"
            "💼 <b>Покупайте и продавайте всё, что угодно – безопасно!</b>\n"
            "От Telegram-подарков и NFT до Telegram-каналов и игр – сделки проходят легко и без риска.\n\n"
            "📖 <b>Как пользоваться?</b>\n"
            "Ознакомьтесь с инструкцией — <a href=\"https://telegra.ph/Kak-polzovatsya-botom-TTH-GRT--P2P-garant-02-09\">здесь</a>.\n\n"
            "Выберите нужный раздел ниже:",
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True  # Убирает предпросмотр ссылки
        )
        
# ===== Создание сделки (покупатель) =====
@dp.callback_query(F.data == "create_deal")
async def create_deal(callback: types.CallbackQuery, state: FSMContext):
    # Доступны только RUB, Crypto и CryptoBot (USD убран)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💴 RUB", callback_data="currency_rub")],
        [InlineKeyboardButton(text="💎 Crypto", callback_data="currency_crypto")],
        [InlineKeyboardButton(text="🤖 CryptoBot", callback_data="currency_cryptobot")]
    ])
    await bot.send_message(callback.from_user.id, "Выберите валюту для сделки:", reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(Form.waiting_for_currency)
    await callback.answer()

@dp.callback_query(F.data.startswith("currency_"))
async def process_currency(callback: types.CallbackQuery, state: FSMContext):
    currency = callback.data.split('_')[1]  # rub, crypto, cryptobot
    # Генерируем уникальный номер сделки
    deal_id = f"{random.randint(1000, 9999)}"
    deal_link = f"https://t.me/{BOT_USERNAME}?start=deal_{deal_id}"
    await state.update_data(currency=currency, deal_id=deal_id, deal_link=deal_link)
    await bot.send_message(callback.from_user.id,
        f"🔹 <b>Сделка #{deal_id}</b>\n\n"
        f"Вы выбрали валюту: {currency.upper()}.\nВведите сумму сделки.",
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
    
    # Сохраняем данные сделки
    deals[deal_id] = {
        "buyer_id": message.from_user.id,
        "seller_id": None,
        "amount": amount,
        "currency": currency,
        "product": product,
        "buyer_screenshot": None,
        "seller_screenshot": None,
        "seller_requisites": None
    }
    
    await state.update_data(product=product)
    
    # Кнопка отмены сделки для покупателя
    cancel_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить сделку", callback_data=f"cancel_{deal_id}")]
    ])
    
    # Инструкции по оплате зависят от валюты
    if currency.lower() == "rub":
        instructions = f"💳 Отправьте {amount} RUB на карту <b>{RECEIVER_CARD}</b>."
    elif currency.lower() == "crypto":
        instructions = (f"💳 Отправьте {amount} USDT на кошелек:\n"
                        f"TON: <code>{CRYPTO_WALLET_TON}</code>\n"
                        f"USDT TRC20: <code>{CRYPTO_WALLET_USDT}</code>")
    elif currency.lower() == "cryptobot":
        instructions = f"💳 Отправьте {amount} USDT через <a href=\"{CRYPTOBOT_LINK}\">CryptoBot</a>."
    else:
        instructions = ""
    
    await message.answer(
        f"✅ <b>Сделка #{deal_id} создана!</b>\n\n"
        f"📌 <b>Товар:</b> {product}\n"
        f"💰 <b>Сумма:</b> {amount} {currency.upper()}\n\n"
        f"{instructions}\n\n"
        f"🔗 Передайте продавцу эту ссылку для участия в сделке: <a href=\"{deal_link}\">Войти в сделку</a>\n\n"
        "📸 После оплаты отправьте скриншот оплаты.",
        reply_markup=cancel_keyboard,
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_payment_screenshot)

@dp.message(Form.waiting_for_payment_screenshot, F.photo)
async def process_payment_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    deal_id = data["deal_id"]
    deals[deal_id]["buyer_screenshot"] = message.photo[-1].file_id
    # Формируем информацию о пользователе: если есть username, то выводим его, иначе ссылку на чат
    buyer = message.from_user
    if buyer.username:
        user_info = f"@{buyer.username}"
    else:
        user_info = f"<a href='tg://user?id={buyer.id}'>Ссылка на чат</a>"
    await message.answer("📸 Скриншот оплаты получен! Ожидаем, когда продавец отправит скриншот передачи товара.", parse_mode="HTML")
    await bot.send_photo(
        ADMIN_ID,
        message.photo[-1].file_id,
        caption=f"📩 <b>Сделка #{deal_id}</b>\n\n✅ Покупатель {user_info} отправил скриншот оплаты.",
        parse_mode="HTML"
    )
    await state.clear()

# ===== Продавец: отправка скриншота передачи и реквизитов =====
@dp.message(Form.waiting_for_transfer_screenshot, F.photo)
async def process_transfer_screenshot(message: types.Message, state: FSMContext):
    # Ищем сделку по seller_id
    seller_deal_id = None
    for d_id, deal in deals.items():
        if deal.get("seller_id") == message.from_user.id and deal.get("seller_screenshot") is None:
            seller_deal_id = d_id
            break
    if seller_deal_id is None:
        await message.answer("⚠️ Сделка не найдена или уже обработана.", parse_mode="HTML")
        return
    deals[seller_deal_id]["seller_screenshot"] = message.photo[-1].file_id
    await message.answer(
        "📸 Скриншот передачи товара получен!\n\nПожалуйста, отправьте ваши реквизиты для получения средств.",
        parse_mode="HTML"
    )
    await state.set_state(Form.waiting_for_requisites)

@dp.message(Form.waiting_for_requisites)
async def process_requisites(message: types.Message, state: FSMContext):
    seller_deal_id = None
    for d_id, deal in deals.items():
        if deal.get("seller_id") == message.from_user.id and deal.get("seller_requisites") is None:
            seller_deal_id = d_id
            break
    if seller_deal_id is None:
        await message.answer("⚠️ Сделка не найдена или реквизиты уже отправлены.", parse_mode="HTML")
        return
    deals[seller_deal_id]["seller_requisites"] = message.text
    # Формируем информацию о продавце
    seller = message.from_user
    if seller.username:
        user_info = f"@{seller.username}"
    else:
        user_info = f"<a href='tg://user?id={seller.id}'>Ссылка на чат</a>"
    # Формируем клавиатуру для подтверждения сделки администратором
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить сделку", callback_data=f"confirm_{seller_deal_id}")],
        [InlineKeyboardButton(text="❌ Вернуть деньги покупателю", callback_data=f"refund_{seller_deal_id}")]
    ])
    caption = (
        f"📩 <b>Сделка #{seller_deal_id}</b> ожидает подтверждения.\n\n"
        f"✅ Продавец {user_info} отправил скриншот передачи товара.\n\n"
        f"Реквизиты продавца: {message.text}\n\n"
        "Проверьте скриншоты оплаты и передачи товара."
    )
    await bot.send_photo(
        ADMIN_ID,
        deals[seller_deal_id]["seller_screenshot"],
        caption=caption,
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await message.answer("Ваши реквизиты получены. Ожидайте подтверждения сделки.", parse_mode="HTML")
    await state.clear()

# ===== Отмена сделки (инициатор – покупатель) =====
@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_deal(callback: types.CallbackQuery):
    deal_id = callback.data.split("_")[1]
    deal = deals.get(deal_id)
    if not deal:
        await callback.message.answer("⚠️ Сделка не найдена или уже завершена.", parse_mode="HTML")
        return
    if callback.from_user.id != deal.get("buyer_id"):
        await callback.answer("Вы не можете отменить эту сделку.", show_alert=True)
        return
    await bot.send_message(ADMIN_ID, f"❌ Сделка #{deal_id} отменена покупателем (ID: {callback.from_user.id}).", parse_mode="HTML")
    await callback.message.answer(f"❌ Сделка #{deal_id} отменена.", parse_mode="HTML")
    seller_id = deal.get("seller_id")
    if seller_id:
        await bot.send_message(seller_id, f"❌ Сделка #{deal_id} отменена покупателем.", parse_mode="HTML")
    del deals[deal_id]
    await callback.answer()

# ===== Админ: подтверждение или возврат сделки =====
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

# ===== Команда для отправки сообщения от администратора =====
@dp.message(Command("msg"))
async def admin_send_message(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return

    # Получаем аргументы команды вручную:
    command_args = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else ""    
    if not args:
        await message.reply("Использование:\n/msg buyer <deal_id> <сообщение>\n/msg seller <deal_id> <сообщение>")
        return

    split_args = args.split(maxsplit=2)
    if len(split_args) < 3:
        await message.reply("Использование:\n/msg buyer <deal_id> <сообщение>\n/msg seller <deal_id> <сообщение>")
        return

        role, deal_id, msg_text = split_args
        await message.reply("Сделка не найдена.")
        return

    if role.lower() == "buyer":
        target_id = deals[deal_id]["buyer_id"]
    elif role.lower() == "seller":
        target_id = deals[deal_id].get("seller_id")
        if not target_id:
            await message.reply("Продавец еще не присоединился к сделке.")
            return
    else:
        await message.reply("Неверный тип получателя. Используйте buyer или seller.")
        return

    try:
        await bot.send_message(target_id, f"Сообщение от администратора:\n\n{msg_text}", parse_mode="HTML")
        await message.reply("Сообщение отправлено.")
    except Exception as e:
        await message.reply(f"Ошибка при отправке сообщения: {e}")

# ===== Запуск бота =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
