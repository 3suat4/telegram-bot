import json
import os
import datetime
import random  # Slot makinesi için gerekli
import requests  # API istekleri için
import threading
from datetime import time as dtime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
)

import logging

# Flask ile özel WebView için gerekli kütüphaneler
from flask import Flask, request, jsonify

# ------------------------------ #
#         Ayarlar & Loglama      #
# ------------------------------ #

API_TOKEN = '7870626668:AAH1CltL_ktxYaEpAid1Il47yZBOlmjKZt0'
BOT_USERNAME = 'SugattiBot'  # BotFather'dan alınan kullanıcı adı

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
USER_DATA_FILE = 'user_data.json'

# ------------------------------ #
#         Veri İşlemleri         #
# ------------------------------ #

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_user_data(user_data):
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(user_data, f, indent=4)

def initialize_user(user_data: dict, user_key: str, user_obj):
    full_name = user_obj.full_name
    if user_key not in user_data:
        user_data[user_key] = {
            'name': full_name,
            'level': 1,
            'points': 0,
            'last_bonus': 0,
            'last_mission': 0,
            'referrals': [],
            'referred_by': None,
            'investment': None,
            # Slot makinesi için günlük hak ve tarih bilgisi
            'slot_machine': {
                'spins': 0,
                'date': datetime.datetime.now().strftime("%Y-%m-%d")
            },
            # Reklam izleme kontrolü: WebView üzerinden reklam 20 sn izlendi mi?
            'ad_valid': False
        }
    else:
        user_data[user_key]['name'] = full_name
        for key in ['referrals', 'referred_by', 'investment', 'slot_machine', 'ad_valid']:
            if key not in user_data[user_key]:
                if key == 'referrals':
                    user_data[user_key][key] = []
                elif key == 'slot_machine':
                    user_data[user_key][key] = {
                        'spins': 0,
                        'date': datetime.datetime.now().strftime("%Y-%m-%d")
                    }
                elif key == 'ad_valid':
                    user_data[user_key][key] = False
                else:
                    user_data[user_key][key] = None

def get_points_per_click(level: int) -> int:
    return level

def get_level_up_cost(level: int) -> int:
    return level * (10 + (level - 1) * 5)

# ------------------------------ #
#        Inline Klavye           #
# ------------------------------ #

def get_keyboard(is_group: bool = False) -> InlineKeyboardMarkup:
    if is_group:
        keyboard = [
            [InlineKeyboardButton("🏆 Lider Tablosu", callback_data='leaderboard')]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("⚡ Tıklama Yap", callback_data='click'),
             InlineKeyboardButton("🚀 Seviye Satın Al", callback_data='buy_level')],
            [InlineKeyboardButton("🤝 Davet Et", callback_data='referral'),
             InlineKeyboardButton("📣 Ödül Bilgileri", callback_data='reward_info')],
            [InlineKeyboardButton("🎁 Günlük Bonus", callback_data='daily_bonus'),
             InlineKeyboardButton("⏰ Saatlik Bonus", callback_data='mission')],
            [InlineKeyboardButton("🎯 Görevler", callback_data='tasks')],
            [InlineKeyboardButton("🏆 Lider Tablosu", callback_data='leaderboard'),
             InlineKeyboardButton("👥 Referans Tablosu", callback_data='referral_table')],
            [InlineKeyboardButton("👤 Profil", callback_data='profile'),
             InlineKeyboardButton("🛒 Mağaza", callback_data='shop'),
             InlineKeyboardButton("❓ Yardım", callback_data='help')]
        ]
    return InlineKeyboardMarkup(keyboard)

def get_reward_info_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="back_to_main")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ------------------------------ #
#         Temel Fonksiyonlar     #
# ------------------------------ #

async def click(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)

    current_level = user_data[user_key]['level']
    points_earned = get_points_per_click(current_level)
    user_data[user_key]['points'] += points_earned
    save_user_data(user_data)

    await query.answer(text=f"{points_earned} puan kazandınız!")
    updated_message = (
        "<b>Seviye:</b> {level}\n"
        "<b>Puan:</b> {points}\n\n"
        "Yeni <i>tıklama</i> yaparak puan kazanın! 🚀"
    ).format(level=user_data[user_key]['level'], points=user_data[user_key]['points'])
    await query.edit_message_text(text=updated_message, parse_mode='HTML', reply_markup=get_keyboard())

async def buy_level(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)

    current_level = user_data[user_key]['level']
    points = user_data[user_key]['points']
    required_points = get_level_up_cost(current_level)
    
    if points >= required_points:
        user_data[user_key]['level'] += 1
        user_data[user_key]['points'] -= required_points
        await query.answer(text="Seviyeniz yükseldi!", show_alert=True)
    else:
        points_needed = required_points - points
        await query.answer(text=f"{points_needed} puan daha gerekiyor.", show_alert=True)
    
    save_user_data(user_data)
    updated_message = (
        "<b>Seviye:</b> {level}\n"
        "<b>Puan:</b> {points}\n\n"
        "Yeni <i>tıklama</i> yaparak puan kazanın!"
    ).format(level=user_data[user_key]['level'], points=user_data[user_key]['points'])
    await query.edit_message_text(text=updated_message, parse_mode='HTML', reply_markup=get_keyboard())

async def daily_bonus(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    
    now = datetime.datetime.now().timestamp()
    last_bonus = user_data[user_key].get('last_bonus', 0)
    bonus_cooldown = 86400
    if now - last_bonus >= bonus_cooldown:
        bonus_points = user_data[user_key]['level'] * 10
        user_data[user_key]['points'] += bonus_points
        user_data[user_key]['last_bonus'] = now
        save_user_data(user_data)
        await query.answer(text=f"Günlük bonus: {bonus_points} puan", show_alert=True)
    else:
        remaining = bonus_cooldown - (now - last_bonus)
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        seconds = int(remaining % 60)
        await query.answer(text=f"{hours} saat, {minutes} dk, {seconds} sn bekleyin.", show_alert=True)
    
    updated_message = (
        "<b>Seviye:</b> {level}\n"
        "<b>Puan:</b> {points}\n\n"
        "Yeni <i>tıklama</i> yaparak puan kazanın!"
    ).format(level=user_data[user_key]['level'], points=user_data[user_key]['points'])
    await query.edit_message_text(text=updated_message, parse_mode='HTML', reply_markup=get_keyboard())

async def mission(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    
    now = datetime.datetime.now().timestamp()
    last_bonus_time = user_data[user_key].get('last_mission', 0)
    bonus_cooldown = 3600
    if now - last_bonus_time >= bonus_cooldown:
        bonus = user_data[user_key]['level'] * 8
        user_data[user_key]['points'] += bonus
        user_data[user_key]['last_mission'] = now
        save_user_data(user_data)
        await query.answer(text=f"Saatlik bonus: {bonus} puan", show_alert=True)
    else:
        remaining = bonus_cooldown - (now - last_bonus_time)
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        await query.answer(text=f"{minutes} dk, {seconds} sn bekleyin.", show_alert=True)
    
    updated_message = (
        "<b>Seviye:</b> {level}\n"
        "<b>Puan:</b> {points}\n\n"
        "Yeni <i>tıklama</i> yaparak puan kazanın!"
    ).format(level=user_data[user_key]['level'], points=user_data[user_key]['points'])
    await query.edit_message_text(text=updated_message, parse_mode='HTML', reply_markup=get_keyboard())

# ------------------------------ #
#         Tablo Fonksiyonları    #
# ------------------------------ #

async def leaderboard_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_data = load_user_data()
    if not user_data:
        await query.answer(text="Oyuncu kaydı bulunamadı.", show_alert=True)
        return
    sorted_users = sorted(user_data.items(), key=lambda x: x[1].get('points', 0), reverse=True)
    message = "<b>🏆 En İyi Oyuncular 🏆</b>\n\n"
    for rank, (uid, data) in enumerate(sorted_users[:10], start=1):
        message += f"{rank}. {data.get('name', 'Bilinmeyen')} - Seviye: {data.get('level', 1)}, Puan: {data.get('points', 0)}\n"
    await query.answer()
    await query.message.reply_text(message, parse_mode='HTML')

async def referral_table_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_data = load_user_data()
    if not user_data:
        await query.answer(text="Referans kaydı bulunamadı.", show_alert=True)
        return
    sorted_users = sorted(user_data.items(), key=lambda x: len(x[1].get('referrals', [])), reverse=True)
    message = "<b>👥 En İyi Referanslar 👥</b>\n\n"
    for rank, (uid, data) in enumerate(sorted_users[:10], start=1):
        ref_count = len(data.get('referrals', []))
        message += f"{rank}. {data.get('name', 'Bilinmeyen')} - Referans: {ref_count}\n"
    await query.answer()
    await query.message.reply_text(message, parse_mode='HTML')

# ------------------------------ #
#    Davet & Ödül Bilgileri      #
# ------------------------------ #

async def referral_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    referral_link = f"https://t.me/{BOT_USERNAME}?start={user_key}"
    text = (
        "🤝 <b>Davet Et</b>\n\n"
        "Arkadaşlarını davet ederek bonus kazanabilirsin!\n"
        f"<b>Davet Linkin:</b>\n<a href='{referral_link}'>{referral_link}</a>\n\n"
        "Linki paylaş ve bonusunu al!"
    )
    await query.answer()
    await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=get_keyboard())

async def reward_info_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    info_text = (
        "<b>📣 Haftalık Ödül Bilgileri:</b>\n\n"
        "<u>Lider Tablosu</u> (Her Pazartesi 00:00):\n"
        "1. <b>500</b> puan\n"
        "2. <b>400</b> puan\n"
        "3. <b>300</b> puan\n"
        "4. <b>200</b> puan\n"
        "5. <b>100</b> puan\n\n"
        "<u>Referans Tablosu</u> (Her Pazartesi 00:00):\n"
        "1. <b>300</b> puan\n"
        "2. <b>250</b> puan\n"
        "3. <b>200</b> puan\n"
        "4. <b>150</b> puan\n"
        "5. <b>100</b> puan\n\n"
        "Ödüller otomatik olarak dağıtılır."
    )
    await query.answer()
    await query.edit_message_text(text=info_text, parse_mode='HTML', reply_markup=get_reward_info_keyboard())

# ------------------------------ #
#         Görevler & Reklam      #
# ------------------------------ #

async def tasks_callback(update: Update, context: CallbackContext):
    """
    Görevler bölümünde, kullanıcı reklamı izlemek üzere özel WebView açacaktır.
    WebView üzerinden reklam 20 saniye izlendikten sonra kullanıcı veritabanında
    'ad_valid' alanı True olarak işaretlenecektir.
    """
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    
    text = (
        "<b>🎯 Görevler</b>\n\n"
        "Aşağıdaki butona tıklayarak reklamı görüntüleyin.\n"
        "Reklamı tam olarak izleyin; en az 20 saniye geçtikten sonra ödül alabilirsiniz."
    )
    keyboard = [
        [InlineKeyboardButton("Reklamı Başlat", url=f"https://reklamtelegram.netlify.app/advert?user_id={user_key}")],
        [InlineKeyboardButton("Ödül Al", callback_data="claim_ad_reward")],
        [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="back_to_main")]
    ]

    await query.answer()
    await query.edit_message_text(text=text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def claim_ad_reward(update: Update, context: CallbackContext):
    """
    Kullanıcı 'Ödül Al' butonuna tıkladığında, veritabanındaki 'ad_valid' bayrağı kontrol edilir.
    Eğer reklam en az 20 saniye izlendi ise ödül verilir ve bayrak sıfırlanır.
    """
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    
    if not user_data[user_key].get('ad_valid'):
        await query.answer(text="Lütfen reklamı tam olarak izleyin.", show_alert=True)
        return
    
    reward = 20  # Reklam izleme ödülü
    user_data[user_key]['points'] += reward
    user_data[user_key]['ad_valid'] = False  # Ödül alındıktan sonra bayrak sıfırlanır
    save_user_data(user_data)
    
    await query.answer(text=f"Reklam ödülünüz: {reward} puan kazandınız!", show_alert=True)
    
    message_text = (
        f"<b>🎯 Görevler</b>\n\n"
        f"Reklam ödülünüz alındı! Şu anki puanınız: {user_data[user_key]['points']}\n\n"
        "Diğer işlemler için aşağıdaki menüyü kullanın."
    )
    await query.edit_message_text(text=message_text, parse_mode='HTML', reply_markup=get_keyboard())

# ------------------------------ #
#         Start & Profil         #
# ------------------------------ #

async def start(update: Update, context: CallbackContext):
    user_key = str(update.message.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, update.message.from_user)
    args = update.message.text.split()
    if len(args) > 1:
        referrer_id = args[1]
        if referrer_id != user_key and user_data[user_key].get('referred_by') is None:
            user_data[user_key]['referred_by'] = referrer_id
            if referrer_id in user_data:
                user_data[referrer_id]['points'] += 50
                user_data[referrer_id]['referrals'].append(user_key)
    save_user_data(user_data)
    is_group = update.message.chat.type in ['group', 'supergroup']
    message = (
        "<b>Profil Bilgileriniz</b>\n"
        f"Seviye: {user_data[user_key]['level']}\n"
        f"Puan: {user_data[user_key]['points']}\n\n"
        "Yeni <i>tıklama</i> yaparak puan kazanın!"
    )
    await update.message.reply_text(message, parse_mode='HTML', reply_markup=get_keyboard(is_group))

async def profile_command(update: Update, context: CallbackContext):
    user_key = str(update.message.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, update.message.from_user)
    referrals_count = len(user_data[user_key].get('referrals', []))
    message = (
        "<b>👤 Profil Bilgileriniz</b>\n\n"
        f"Ad: {user_data[user_key]['name']}\n"
        f"Seviye: {user_data[user_key]['level']}\n"
        f"Puan: {user_data[user_key]['points']}\n"
        f"Referans: {referrals_count}\n"
    )
    await update.message.reply_text(message, parse_mode='HTML')

async def help_command(update: Update, context: CallbackContext):
    help_text = (
        "<b>🤖 Bot Komutları:</b>\n\n"
        "<b>/start</b> - Botu başlatır ve profil oluşturur\n"
        "<b>/leaderboard</b> - En iyi oyuncuları gösterir\n"
        "<b>/profile</b> - Profil bilgilerini gösterir\n"
        "<b>/help</b> - Yardım mesajı\n\n"
        "<b>İnline Butonlar:</b>\n"
        "• ⚡ Tıklama Yap\n"
        "• 🚀 Seviye Satın Al\n"
        "• 🤝 Davet Et\n"
        "• 📣 Ödül Bilgileri\n"
        "• 🎁 Günlük Bonus\n"
        "• ⏰ Saatlik Bonus\n"
        "• 🎯 Görevler\n"
        "• 🏆 Lider Tablosu\n"
        "• 👥 Referans Tablosu\n"
        "• 👤 Profil / 🛒 Mağaza / ❓ Yardım"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')

async def profile_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    referrals_count = len(user_data[user_key].get('referrals', []))
    message = (
        "<b>👤 Profil Bilgileriniz</b>\n\n"
        f"Ad: {user_data[user_key]['name']}\n"
        f"Seviye: {user_data[user_key]['level']}\n"
        f"Puan: {user_data[user_key]['points']}\n"
        f"Referans: {referrals_count}\n"
    )
    await query.answer()
    await query.edit_message_text(text=message, parse_mode='HTML', reply_markup=get_keyboard())

# ------------------------------ #
#         Mağaza Sistemi         #
# ------------------------------ #

async def shop_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    
    shop_message = (
        "<b>🛒 Mağaza</b>\n\n"
        "Lütfen bir seçenek belirleyin."
    )
    keyboard = [
        [InlineKeyboardButton("Yatırım / Kazanç", callback_data="investment")],
        [InlineKeyboardButton("Slot Makinesi", callback_data="slot_machine")],
        [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="back_to_main")]
    ]
    await query.answer()
    await query.edit_message_text(text=shop_message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def investment_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    
    if user_data[user_key].get('investment') is not None:
        message = (
            "<b>Aktif Yatırım:</b>\n"
            "Zaten aktif yatırımınız var. Lütfen kazancınızı talep edin."
        )
        keyboard = [
            [InlineKeyboardButton("💰 Kazanç Talep Et", callback_data="claim_investment")],
            [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="back_to_main")]
        ]
    else:
        message = (
            "<b>Yatırım Seçenekleri:</b>\n"
            "1. <b>Küçük</b>: 100 puan, 10 dk sonra, %5 kâr\n"
            "2. <b>Orta</b>: 300 puan, 20 dk sonra, %5 kâr\n"
            "3. <b>Büyük</b>: 1000 puan, 30 dk sonra, %5 kâr"
        )
        keyboard = [
            [InlineKeyboardButton("Küçük", callback_data="invest_small"),
             InlineKeyboardButton("Orta", callback_data="invest_medium")],
            [InlineKeyboardButton("Büyük", callback_data="invest_large")],
            [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="back_to_main")]
        ]
    await query.answer()
    await query.edit_message_text(text=message, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def invest_points_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    
    investment_type = query.data
    if user_data[user_key].get('investment') is not None:
        await query.answer(text="Mevcut yatırımı kapatın.", show_alert=True)
        return

    if investment_type == "invest_small":
        cost, wait_time = 100, 600
    elif investment_type == "invest_medium":
        cost, wait_time = 300, 1200
    elif investment_type == "invest_large":
        cost, wait_time = 1000, 1800
    else:
        await query.answer(text="Geçersiz seçenek.", show_alert=True)
        return

    if user_data[user_key]['points'] < cost:
        await query.answer(text="Yeterli puan yok.", show_alert=True)
        return

    user_data[user_key]['points'] -= cost
    user_data[user_key]['investment'] = {
        'amount': cost,
        'start_time': datetime.datetime.now().timestamp(),
        'wait_time': wait_time,
        'type': investment_type
    }
    save_user_data(user_data)
    await query.answer(text=f"{investment_type.replace('invest_', '').capitalize()} yatırımı başladı!", show_alert=True)
    await query.edit_message_text(
        text="Yatırım başladı! Süre dolduğunda <b>Kazanç Talep Et</b> butonuna tıklayın.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Kazanç Talep Et", callback_data="claim_investment")],
            [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="back_to_main")]
        ])
    )

async def claim_investment(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    
    investment = user_data[user_key].get('investment')
    if investment is None:
        await query.answer(text="Aktif yatırım bulunamadı.", show_alert=True)
        return
    
    now = datetime.datetime.now().timestamp()
    wait_time = investment.get('wait_time', 600)
    if now - investment['start_time'] < wait_time:
        remaining = wait_time - (now - investment['start_time'])
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        await query.answer(text=f"Lütfen {minutes} dk {seconds} sn sonra tekrar deneyin.", show_alert=True)
        return

    profit = int(investment['amount'] * 0.05)
    total_return = investment['amount'] + profit
    user_data[user_key]['points'] += total_return
    user_data[user_key]['investment'] = None
    save_user_data(user_data)
    await query.answer(text=f"Yatırımdan {total_return} puan kazandınız!", show_alert=True)
    await query.edit_message_text(text=f"<b>Yatırım tamamlandı.</b>\nGüncel Puan: {user_data[user_key]['points']}", parse_mode='HTML', reply_markup=get_keyboard())

# ------------------------------ #
#     Slot Makinesi Sistemi     #
# ------------------------------ #

async def slot_machine_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    if user_data[user_key]['slot_machine']['date'] != today:
        user_data[user_key]['slot_machine']['date'] = today
        user_data[user_key]['slot_machine']['spins'] = 0

    spins = user_data[user_key]['slot_machine']['spins']
    if spins >= 3:
        await query.answer(text="Günlük slot hakkınız doldu.", show_alert=True)
        return
    
    symbols = ["🍒", "🍋", "🍊", "🍇", "⭐"]
    result = [random.choice(symbols) for _ in range(3)]
    result_str = " | ".join(result)
    
    if result[0] == result[1] == result[2]:
        reward = 100
        outcome = "Büyük kazanç! Üç aynı sembol."
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        reward = 50
        outcome = "Orta kazanç! İki aynı sembol."
    else:
        reward = 10
        outcome = "Küçük kazanç. Eşleşme yok."
    
    user_data[user_key]['points'] += reward
    user_data[user_key]['slot_machine']['spins'] += 1
    save_user_data(user_data)
    
    remaining = 3 - user_data[user_key]['slot_machine']['spins']
    message_text = (
        f"<b>Slot Makinesi Sonucu</b>\n\n"
        f"{result_str}\n"
        f"{outcome}\n\n"
        f"<b>Kazandığınız Puan:</b> {reward}\n"
        f"Kalan slot hakkı: {remaining}"
    )
    
    if remaining > 0:
        keyboard = [
            [InlineKeyboardButton("Slot Çevir", callback_data="slot_machine")],
            [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="back_to_main")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="back_to_main")]
        ]
    
    await query.answer()
    await query.edit_message_text(text=message_text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

# ------------------------------ #
#         Yardım & Geri          #
# ------------------------------ #

async def help_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    help_text = (
        "<b>🤖 Yardım</b>\n\n"
        "<b>/start</b> - Botu başlatır ve profil oluşturur\n"
        "<b>/leaderboard</b> - En iyi oyuncuları gösterir\n"
        "<b>/profile</b> - Profil bilgilerini gösterir\n"
        "<b>/help</b> - Yardım mesajı\n\n"
        "<b>Butonlar:</b>\n"
        "⚡ Tıklama Yap, 🚀 Seviye Satın Al, 🤝 Davet Et, 📣 Ödül Bilgileri,\n"
        "🎁 Günlük Bonus, ⏰ Saatlik Bonus, 🎯 Görevler, 🏆 Lider Tablosu, 👥 Referans Tablosu,\n"
        "👤 Profil, 🛒 Mağaza, ❓ Yardım"
    )
    keyboard = [[InlineKeyboardButton("🔙 Ana Menüye Dön", callback_data="back_to_main")]]
    await query.answer()
    await query.edit_message_text(text=help_text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(keyboard))

async def back_to_main(update: Update, context: CallbackContext):
    query = update.callback_query
    user_key = str(query.from_user.id)
    user_data = load_user_data()
    initialize_user(user_data, user_key, query.from_user)
    message_text = (
        "<b>Profil Bilgileriniz</b>\n"
        f"Seviye: {user_data[user_key]['level']}\n"
        f"Puan: {user_data[user_key]['points']}\n\n"
        "Lütfen menüden bir seçenek belirleyin."
    )
    await query.answer()
    await query.edit_message_text(text=message_text, parse_mode='HTML', reply_markup=get_keyboard())

async def no_action(update: Update, context: CallbackContext):
    await update.callback_query.answer()

# ------------------------------ #
#         Haftalık Ödüller       #
# ------------------------------ #

async def weekly_reward(context: CallbackContext):
    user_data = load_user_data()
    if not user_data:
        return

    sorted_leaderboard = sorted(user_data.items(), key=lambda x: x[1].get('points', 0), reverse=True)
    leaderboard_rewards = [500, 400, 300, 200, 100]
    for i, (uid, data) in enumerate(sorted_leaderboard[:5]):
        bonus = leaderboard_rewards[i]
        data['points'] += bonus
        logger.info(f"Lider Ödülü: {data.get('name')} (ID: {uid}) - {bonus} puan verildi.")

    sorted_referrals = sorted(user_data.items(), key=lambda x: len(x[1].get('referrals', [])), reverse=True)
    referral_rewards = [300, 250, 200, 150, 100]
    for i, (uid, data) in enumerate(sorted_referrals[:5]):
        bonus = referral_rewards[i]
        data['points'] += bonus
        logger.info(f"Referans Ödülü: {data.get('name')} (ID: {uid}) - {bonus} puan verildi.")

    save_user_data(user_data)
    logger.info("Haftalık ödüller dağıtıldı.")

# ------------------------------ #
#   Tıklama Sayısını Göster (API)  #
# ------------------------------ #

async def clickcount_command(update: Update, context: CallbackContext):
    today = datetime.date.today().strftime("%Y-%m-%d")

    params = {
        "start_date": today,
        "finish_date": today,
        "group_by": "date"
    }
    
    headers = {
        "X-API-Key": "7ec3aed6161c9e7271f91d10c4771300"
    }
    
    try:
        response = requests.get("https://api3.adsterratools.com/publisher/stats.json", params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            stats = data.get("items", [])

            if stats and isinstance(stats, list):
                click_count = sum(item.get("clicks", 0) for item in stats)
                await update.message.reply_text(f"Bugünkü toplam tıklama sayısı: {click_count}")
            else:
                await update.message.reply_text("Bugün için veri bulunamadı.")
        
        elif response.status_code == 401:
            await update.message.reply_text("API Hatası: Yetkilendirme başarısız. API anahtarınızı kontrol edin.")
        elif response.status_code == 403:
            await update.message.reply_text("API Hatası: Erişim reddedildi.")
        else:
            await update.message.reply_text(f"API Hatası: {response.status_code} - {response.text}")

    except Exception as e:
        await update.message.reply_text(f"Hata oluştu: {str(e)}")

# ------------------------------ #
#           Komutlar             #
# ------------------------------ #

async def start_command(update: Update, context: CallbackContext):
    logger.info("Start komutu alındı!")
    await start(update, context)

# ------------------------------ #
#       Flask WebView Kısmı      #
# ------------------------------ #

flask_app = Flask(__name__)

@flask_app.route('/advert')
def advert():
    user_id = request.args.get('user_id')
    # Reklamı izleme sayfası (JavaScript ile 20 sn geri sayım yapar)
    html_content = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Reklam İzleme</title>
    </head>
    <body>
        <h1>Reklam İzleniyor</h1>
        <p>Lütfen reklamı sonuna kadar izleyin...</p>
        <div id="timer">20</div>
        <script>
            var seconds = 20;
            var timer = document.getElementById('timer');
            var interval = setInterval(function(){{
                seconds--;
                timer.textContent = seconds;
                if(seconds <= 0) {{
                    clearInterval(interval);
                    // 20 saniye tamamlandıktan sonra sunucuya bildir
                    fetch('/ad_watched?user_id={user_id}')
                      .then(response => response.json())
                      .then(data => {{
                          document.body.innerHTML = "<h2>" + data.message + "</h2>";
                      }});
                }}
            }}, 1000);
        </script>
    </body>
    </html>
    '''
    return html_content

@flask_app.route('/ad_watched')
def ad_watched():
    user_id = request.args.get('user_id')
    user_data = load_user_data()
    if user_id in user_data:
        user_data[user_id]['ad_valid'] = True
        save_user_data(user_data)
        return jsonify({"message": "Reklamı izlediniz, artık ödül alabilirsiniz."})
    else:
        return jsonify({"message": "Kullanıcı bulunamadı."}), 404

# ------------------------------ #
#            Main                #
# ------------------------------ #

def run_flask():
    flask_app.run(host="0.0.0.0", port=5000)

def main():
    application = Application.builder().token(API_TOKEN).build()

    # Mesaj Komutları
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("leaderboard", leaderboard_callback))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("clickcount", clickcount_command))

    # Callback Query Handler'ları
    application.add_handler(CallbackQueryHandler(click, pattern='^click$'))
    application.add_handler(CallbackQueryHandler(buy_level, pattern='^buy_level$'))
    application.add_handler(CallbackQueryHandler(daily_bonus, pattern='^daily_bonus$'))
    application.add_handler(CallbackQueryHandler(mission, pattern='^mission$'))
    application.add_handler(CallbackQueryHandler(leaderboard_callback, pattern='^leaderboard$'))
    application.add_handler(CallbackQueryHandler(profile_callback, pattern='^profile$'))
    application.add_handler(CallbackQueryHandler(shop_callback, pattern='^shop$'))
    application.add_handler(CallbackQueryHandler(help_callback, pattern='^help$'))
    application.add_handler(CallbackQueryHandler(invest_points_handler, pattern='^invest_small$|^invest_medium$|^invest_large$'))
    application.add_handler(CallbackQueryHandler(claim_investment, pattern='^claim_investment$'))
    application.add_handler(CallbackQueryHandler(back_to_main, pattern='^back_to_main$'))
    application.add_handler(CallbackQueryHandler(no_action, pattern='^no_action$'))
    application.add_handler(CallbackQueryHandler(referral_callback, pattern='^referral$'))
    application.add_handler(CallbackQueryHandler(referral_table_callback, pattern='^referral_table$'))
    application.add_handler(CallbackQueryHandler(reward_info_callback, pattern='^reward_info$'))
    application.add_handler(CallbackQueryHandler(investment_handler, pattern='^investment$'))
    application.add_handler(CallbackQueryHandler(slot_machine_handler, pattern='^slot_machine$'))
    # Yeni görevler ve reklam butonları için Handler
    application.add_handler(CallbackQueryHandler(tasks_callback, pattern='^tasks$'))
    application.add_handler(CallbackQueryHandler(claim_ad_reward, pattern='^claim_ad_reward$'))

    application.job_queue.run_daily(weekly_reward, time=dtime(hour=0, minute=0, second=0), days=(0,))
    
    application.run_polling()

if __name__ == '__main__':
    # Flask uygulamasını ayrı bir thread'de başlatıyoruz
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    # Telegram Bot'u başlatıyoruz
    main()
