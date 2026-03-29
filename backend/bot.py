from aiogram import Bot, Dispatcher, types, executor
import json
import requests

TOKEN = "8769949339:AAFwvdkPFgj7l4BQwGfmcljauMWXRx7qves"
ADMIN_ID = 7545540622 

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# кнопка открытия сайта
keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(
    types.KeyboardButton(
        text="🍽 Бронирование",
        web_app=types.WebAppInfo(url="https://danil776-7.github.io/dubrovka-webapp/")
    )
)

@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Открыть бронирование:", reply_markup=keyboard)

# получение данных с сайта
@dp.message_handler(content_types=types.ContentType.WEB_APP_DATA)
async def web_app(message: types.Message):

    data = json.loads(message.web_app_data.data)

    # отправка в API
    res = requests.post("https://dubrovka-webapp-9.onrender.com", json=data)
    result = res.json()

    if result.get("error"):
        await message.answer("❌ Этот стол уже занят")
        return

    booking_id = result.get("id")

    text = f"""
✅ Бронь создана

📅 {data['date']} {data['time']}
🪑 Стол {data['table']}
👥 {data['guests']}
"""

    # кнопка отмены
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            "❌ Отменить бронь",
            callback_data=f"cancel|{booking_id}"
        )
    )

    # клиенту
    await message.answer(text, reply_markup=kb)

    # админу
    await bot.send_message(ADMIN_ID, f"🔥 Новая бронь\n{text}")

# отмена брони
@dp.callback_query_handler(lambda c: c.data.startswith("cancel"))
async def cancel_booking(call: types.CallbackQuery):

    _, booking_id = call.data.split("|")

    res = requests.delete(
        f"https://dubrovka-webapp-9.onrender.com/booking/{booking_id}"
    )

    result = res.json()

    if result.get("ok"):
        await call.message.edit_text("❌ Бронь отменена")
    else:
        await call.answer("Ошибка отмены", show_alert=True)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)