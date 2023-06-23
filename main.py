import logging
import asyncpg
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ContentType
import asyncio
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
import yookassa
from aiogram import Bot, Dispatcher, executor, types, filters
import json
from aiogram import Bot, Dispatcher, executor, types, filters
from yookassa import Configuration, Payment
import payment
import config
from aiogram.types import ReplyKeyboardRemove

API_TOKEN = '5886139783:AAEaXf8AknbHhArm9PMNTKZ7yCXmFWFsyxA'
YOUR_ADMIN_ID=716775112
YOOKASSA_SHOP_ID = '506751'
YOOKASSA_SECRET_KEY = '381764678:TEST:59902'

DB_HOST = 'localhost'
DB_PORT = 5432
DB_NAME = 'postgres'
DB_USER = 'postgres'
DB_PASSWORD = 'ALEXLOL19741978'

# Initialize the bot and state storage
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Configure logging
logging.basicConfig(level=logging.INFO)
timer_tasks = {}
# Database connection pool
db_pool = None

# Database initialization and connection
async def setup_database():
    global db_pool
    db_pool = await asyncpg.create_pool(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

# Database table creation
async def create_table():
    async with db_pool.acquire() as connection:
        await connection.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                coins INTEGER DEFAULT 0
            )
        ''')

# Class for storing user states
class UserForm(StatesGroup):
    direction = State()
    platform = State()
    budget = State()
    phone = State()

class UserForm1(StatesGroup):
    message = State()

# Keyboard markup
keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(KeyboardButton("Оставить заявку"))
keyboard.add(KeyboardButton("Купить товар"))
keyboard.add(KeyboardButton("Мой баланс"))

# Handler for the /start command
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if message.from_user.id == YOUR_ADMIN_ID:
        keyboard.add(KeyboardButton("Отправить сообщение пользователям"))

    # Add the user to the database and set their coins to 0
    await add_user_to_database(message.from_user.id)

    await message.reply("Выберите действие:", reply_markup=keyboard)

# Add a new user to the database
async def add_user_to_database(user_id):
    async with db_pool.acquire() as connection:
        await connection.execute(
            '''
            INSERT INTO users (user_id) VALUES ($1)
            ON CONFLICT (user_id) DO NOTHING
            ''',
            user_id
        )

# Get the user's coins from the database
async def get_user_coins(user_id):
    async with db_pool.acquire() as connection:
        coins = await connection.fetchval(
            '''
            SELECT coins FROM users WHERE user_id = $1
            ''',
            user_id
        )
        return coins

# Update the user's coins in the database
async def update_user_coins(user_id, coins):
    async with db_pool.acquire() as connection:
        await connection.execute(
            '''
            UPDATE users SET coins = $1 WHERE user_id = $2
            ''',
            coins,
            user_id
        )

# Handler for the "Мой баланс" button
@dp.message_handler(lambda message: message.text == "Мой баланс")
async def check_balance(message: types.Message):
    # Get the user's coins from the database
    coins = await get_user_coins(message.from_user.id)
    await message.answer(f"У вас {coins} условных единиц.")

# Handler for the "Купить товар" button
@dp.message_handler(lambda message: message.text == "Купить товар")
async def buy_item(message: types.Message):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("Купить 1 раз"))
    keyboard.add(KeyboardButton("Купить 2 раза"))
    await message.answer("Выберите количество покупок:", reply_markup=keyboard)

# Handler for the buttons to select the number of purchases
@dp.message_handler(lambda message: message.text in ["Купить 1 раз", "Купить 2 раза"])
async def process_payment(message: types.Message):
    if message.text == 'Купить 1 раз':
        await bot.send_invoice(
            message.from_user.id,
            title='Покупка 1 раза',
            description='1 раз',
            payload='1 раз',
            provider_token=YOOKASSA_SECRET_KEY,
            currency='RUB',
            start_parameter='test_bot',
            prices=[{'label': 'Руб', 'amount': '15000'}]
        )
    else:
        await bot.send_invoice(
            message.from_user.id,
            title='Покупка 2 раза',
            description='2 раза',
            payload='2 раза',
            provider_token=YOOKASSA_SECRET_KEY,
            currency='RUB',
            start_parameter='test_bot',
            prices=[{'label': 'Руб', 'amount': '30000'}]
        )

@dp.pre_checkout_query_handler()
async def process_pre_checkout_query(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def process_payment(message: types.Message):
    if message.successful_payment.invoice_payload == '1 раз':
        # Increase the user's coins by 1
        await increase_user_coins(message.from_user.id, 1)
        await bot.send_message(message.from_user.id, 'Вы успешно купили 1 раз', reply_markup=keyboard)
    else:
        # Increase the user's coins by 2
        await increase_user_coins(message.from_user.id, 2)
        await bot.send_message(message.from_user.id, 'Вы успешно купили 2 раза', reply_markup=keyboard)

# Increase the user's coins in the database
async def increase_user_coins(user_id, amount):
    current_coins = await get_user_coins(user_id)
    new_coins = current_coins + amount
    await update_user_coins(user_id, new_coins)

# Handler for the "Оставить заявку" button
@dp.message_handler(lambda message: message.text == "Оставить заявку")
async def request_form_start(message: types.Message):
    keyboard1 = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard1.add(KeyboardButton("Продажа"))
    keyboard1.add(KeyboardButton("Производство"))
    keyboard1.add(KeyboardButton("Оказание услуг"))
    await message.answer("Какое направление вашего бизнеса?", reply_markup=keyboard1)
    timer = asyncio.create_task(timer_callback(message.from_user.id))
    timer_tasks[message.from_user.id] = timer

    await UserForm.direction.set()


async def timer_callback(user_id):
    await asyncio.sleep(600)  # Ожидание 10 минут

    if user_id in timer_tasks:
        del timer_tasks[user_id]
        await bot.send_message(user_id, "Ты забыл заполнить заявку!")

# Handler for the response to the business direction question
@dp.message_handler(state=UserForm.direction)
async def request_form_direction(message: types.Message, state: FSMContext):
    keyboard2 = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard2.add(KeyboardButton("Телеграмм"))
    keyboard2.add(KeyboardButton("Ватсап"))
    keyboard2.add(KeyboardButton("Вайбер"))
    async with state.proxy() as data:
        data['direction'] = message.text
    await message.answer("На какой платформе вы хотите разработать чат-бот?", reply_markup=keyboard2)
    await UserForm.next()

# Handler for the response to the platform question
@dp.message_handler(state=UserForm.platform)
async def request_form_platform(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['platform'] = message.text
    await message.answer("Какой у вас бюджет? От ... До ...", reply_markup=ReplyKeyboardRemove())
    await UserForm.next()

# Handler for the response to the budget question
@dp.message_handler(state=UserForm.budget)
async def request_form_budget(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['budget'] = message.text
    await message.answer("Введите ваш номер телефона")
    await UserForm.next()

# Handler for the response to the phone number question
@dp.message_handler(state=UserForm.phone)
async def request_form_phone(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['phone'] = message.text
        if message.from_user.id in timer_tasks:
            timer_tasks[message.from_user.id].cancel()
            del timer_tasks[message.from_user.id]
        # Send the request to the administrator
        await bot.send_message(
            YOUR_ADMIN_ID,
            f"<b>Новая заявка:</b>\n"
            f"Направление бизнеса: {data['direction']}\n"
            f"Платформа: {data['platform']}\n"
            f"Бюджет: {data['budget']}\n"
            f"Телефон: {data['phone']}",
            parse_mode='HTML'
        )
        await message.answer("Спасибо! Ваша заявка отправлена администратору.", reply_markup=keyboard)
    # Reset the form state
    await state.finish()
async def send_message_to_all_users1(text):
    async with db_pool.acquire() as connection:
        user_ids = await connection.fetch(
            '''
            SELECT user_id FROM users
            '''
        )
        for row in user_ids:
            user_id = row['user_id']
            try:
                await bot.send_message(user_id, text)
            except Exception as e:
                print(f"Failed to send message to user {user_id}: {str(e)}")
# Handler for the administrator's response to send a message to all users
@dp.message_handler(state=UserForm1.message, user_id=YOUR_ADMIN_ID)
async def send_message_to_all_users(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        await send_message_to_all_users1(message.text)
        await message.answer("Сообщение отправлено всем пользователям.")
    # Reset the form state
    await state.finish()

# Handler for the "Отправить сообщение пользователям" button (only available to the administrator)
@dp.message_handler(lambda message: message.text == "Отправить сообщение пользователям" and message.from_user.id == YOUR_ADMIN_ID)
async def send_message_to_users(message: types.Message):
    await message.answer("Введите сообщение для отправки всем пользователям:")
    # Set the administrator's state to wait for a message
    await UserForm1.next()

# Handler for user inactivity
@dp.message_handler(lambda message: True, state='*')
async def handle_user_idle(message: types.Message, state: FSMContext):
    # Send the user a notification about inactivity
    await message.answer("Такой команды нет:(")

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(setup_database())
    loop.run_until_complete(create_table())
    executor.start_polling(dp)