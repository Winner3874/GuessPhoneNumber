import os
import json
from datetime import datetime, timedelta
import asyncio
import random
from discord.ext import commands
import discord
from discord import ui
import re


BASE_DIR = os.path.dirname(__file__)
DATA_PATH = os.path.join(BASE_DIR, 'guess_data.json')

# 特殊用戶（無限遊玩次數）
ADMIN_USERS = {'lingyou4783'}  # Discord 用戶名稱

def load_data():
	if not os.path.exists(DATA_PATH):
		return {
			"accounts": {},
			"successful_guesses": {},
			"user_guess_counts": {},
			"user_profiles": {}
		}
	with open(DATA_PATH, 'r', encoding='utf-8') as f:
		data = json.load(f)
		# 確保所有必要的鍵都存在（相容舊資料）
		if 'user_profiles' not in data:
			data['user_profiles'] = {}
		if 'successful_guesses' not in data:
			data['successful_guesses'] = {}
		if 'user_guess_counts' not in data:
			data['user_guess_counts'] = {}
		if 'accounts' not in data:
			data['accounts'] = {}
		# 處理舊版的 user_records 格式 (舊版可能是 list)
		if 'user_records' not in data:
			data['user_records'] = {}
		else:
			# 可能的情況： data['user_records'][uid] 為 list (舊格式)
			for uid, recs in list(data['user_records'].items()):
				# 若整個 user_records 是一個 list，或單一 uid 的值是 list
				if isinstance(recs, list):
					# 轉換為 dict 以 username 為鍵
					new = {}
					for rec in recs:
						target = rec.get('target_username') or rec.get('username') or '<unknown>'
						new.setdefault(target, []).append(rec)
					data['user_records'][uid] = new
				# 若該 uid 的值不是 dict，強制轉為 dict，避免類型錯誤
				elif not isinstance(recs, dict):
					data['user_records'][uid] = {}
		return data

def save_data(data):
	with open(DATA_PATH, 'w', encoding='utf-8') as f:
		json.dump(data, f, ensure_ascii=False, indent=2)

def valid_phone(p: str) -> bool:
	return isinstance(p, str) and p.isdigit() and len(p) == 10 and p.startswith('09')

def current_hour_key():
	return datetime.now().strftime('%Y%m%d%H')

def current_date():
	return datetime.now().strftime('%Y-%m-%d')

def get_claim_period(dt: datetime):
	if dt.minute < 30:
		dt = dt - timedelta(hours=1)
	return dt.strftime('%Y%m%d%H')


def get_next_claim_reset(dt: datetime):
	reset = dt.replace(minute=30, second=0, microsecond=0)
	if dt.minute >= 30:
		reset += timedelta(hours=1)
	return reset


def get_or_create_profile(data, user_id):
	"""取得或建立玩家檔案，若需要更新種族則更新"""
	uid = str(user_id)
	if uid not in data['user_profiles']:
		data['user_profiles'][uid] = {
			'race': None,
			'coins': 0,
			'race_date': None,
			'last_claim_period': None,
			'extra_guess_chances': 0,
			'ab_feedback_uses': 0
		}
	profile = data['user_profiles'][uid]
	profile.setdefault('last_claim_period', None)
	profile.setdefault('extra_guess_chances', 0)
	profile.setdefault('ab_feedback_uses', 0)
	profile.setdefault('digit_counter_uses', 0)
	profile.setdefault('last_five_digits_uses', 0)
	profile.setdefault('divisor_remainder_uses', 0)
	profile.setdefault('lis_query_uses', 0)
	profile.setdefault('unique_digits_uses', 0)
	today = current_date()
	# 每天 00:00 重新抽籤 — 使用 user_id + 日期 作為 seed，確保同一天內在任何重啟下保持一致
	if profile.get('race_date') != today:
		races = ['主人', '寧寧', '阿尼的哥哥']
		seed = f"{uid}-{today}"
		profile['race'] = random.Random(seed).choice(races)
		profile['race_date'] = today
		profile['last_claim_period'] = None
	return profile

# ===== Modal 類定義 =====

class DigitCounterModal(ui.Modal, title='數字計數器'):
	username = ui.TextInput(label='目標 username', placeholder='輸入目標使用者名稱')
	digit = ui.TextInput(label='要查詢的數字 (0-9)', placeholder='輸入單一數字')
	
	def __init__(self):
		super().__init__()
	
	async def on_submit(self, interaction: discord.Interaction):
		data = load_data()
		uid = str(interaction.user.id)
		prof = get_or_create_profile(data, uid)
		
		# 驗證輸入
		if not self.digit.value.isdigit() or len(self.digit.value) != 1:
			await interaction.response.send_message('❌ 數字必須是 0-9 之間的單一數字。', ephemeral=True)
			return
		if self.username.value not in data['accounts']:
			await interaction.response.send_message('❌ 指定的 username 不存在。', ephemeral=True)
			return
		if prof.get('digit_counter_uses', 0) <= 0:
			await interaction.response.send_message('❌ 你沒有數字計數器次數。', ephemeral=True)
			return
		
		# 驗證通過，扣幣與使用次數
		phone = data['accounts'][self.username.value]['phone']
		count = phone.count(self.digit.value)
		prof['digit_counter_uses'] -= 1
		prof['coins'] -= 1200
		
		# 記錄 (包含輸入與結果)
		record_tool_use(data, uid, self.username.value, 'digit_counter', input_value=self.digit.value, result=f'數字 {self.digit.value} 出現 {count} 次')
		
		save_data(data)
		await interaction.response.send_message(f'🔍 數字 **{self.digit.value}** 在 `{self.username.value}` 的 phone number 中出現 **{count}** 次。', ephemeral=True)

class DivisorRemainderModal(ui.Modal, title='整除餘數'):
	username = ui.TextInput(label='目標 username', placeholder='輸入目標使用者名稱')
	
	def __init__(self):
		super().__init__()
	
	async def on_submit(self, interaction: discord.Interaction):
		data = load_data()
		uid = str(interaction.user.id)
		prof = get_or_create_profile(data, uid)
		
		# 驗證輸入
		if self.username.value not in data['accounts']:
			await interaction.response.send_message('❌ 指定的 username 不存在。', ephemeral=True)
			return
		if prof.get('divisor_remainder_uses', 0) <= 0:
			await interaction.response.send_message('❌ 你沒有整除餘數次數。', ephemeral=True)
			return
		
		# 驗證通過，扣幣與使用次數
		phone_int = int(data['accounts'][self.username.value]['phone'])
		divisor = 2 if random.random() < 0.7 else 7
		remainder = phone_int % divisor
		prof['divisor_remainder_uses'] -= 1
		prof['coins'] -= 800
		
		# 記錄 (包含輸入與結果)
		record_tool_use(data, uid, self.username.value, 'divisor_remainder', input_value=str(divisor), result=f'除以 {divisor} 的餘數是 {remainder}')
		
		save_data(data)
		await interaction.response.send_message(f'📊 `{self.username.value}` 的 phone number 除以 **{divisor}** 的餘數是 **{remainder}**。', ephemeral=True)

class LISModal(ui.Modal, title='最長遞增子序列'):
	username = ui.TextInput(label='目標 username', placeholder='輸入目標使用者名稱')
	
	def __init__(self):
		super().__init__()
	
	async def on_submit(self, interaction: discord.Interaction):
		data = load_data()
		uid = str(interaction.user.id)
		prof = get_or_create_profile(data, uid)
		
		# 驗證輸入
		if self.username.value not in data['accounts']:
			await interaction.response.send_message('❌ 指定的 username 不存在。', ephemeral=True)
			return
		if prof.get('lis_query_uses', 0) <= 0:
			await interaction.response.send_message('❌ 你沒有最長遞增子序列次數。', ephemeral=True)
			return
		
		# 驗證通過，扣幣與使用次數
		phone = data['accounts'][self.username.value]['phone']
		lis_length = compute_lis(phone)
		prof['lis_query_uses'] -= 1
		prof['coins'] -= 1200
		
		# 記錄 (包含輸入與結果)
		record_tool_use(data, uid, self.username.value, 'lis_query', input_value=None, result=f'最長遞增子序列長度是 {lis_length}')
		
		save_data(data)
		await interaction.response.send_message(f'📈 `{self.username.value}` 的 phone number 最長遞增子序列長度是 **{lis_length}**。', ephemeral=True)

class UniqueDigitsModal(ui.Modal, title='查詢包含的數字'):
	username = ui.TextInput(label='目標 username', placeholder='輸入目標使用者名稱')
	
	def __init__(self):
		super().__init__()
	
	async def on_submit(self, interaction: discord.Interaction):
		data = load_data()
		uid = str(interaction.user.id)
		prof = get_or_create_profile(data, uid)
		
		# 驗證輸入
		if self.username.value not in data['accounts']:
			await interaction.response.send_message('❌ 指定的 username 不存在。', ephemeral=True)
			return
		if prof.get('unique_digits_uses', 0) <= 0:
			await interaction.response.send_message('❌ 你沒有包含數字查詢次數。', ephemeral=True)
			return
		
		# 驗證通過，扣幣與使用次數
		phone = data['accounts'][self.username.value]['phone']
		unique_digits = sorted(set(phone))
		prof['unique_digits_uses'] -= 1
		prof['coins'] -= 1000
		
		# 記錄 (包含輸入與結果)
		record_tool_use(data, uid, self.username.value, 'unique_digits', input_value=None, result=f'包含的數字有：{" ".join(unique_digits)}')
		
		save_data(data)
		await interaction.response.send_message(f'🔢 `{self.username.value}` 的 phone number 包含的數字有：**{" ".join(unique_digits)}**。', ephemeral=True)


def compute_lis(s: str) -> int:
	"""計算字符串中最長遞增子序列的長度"""
	if not s:
		return 0
	n = len(s)
	dp = [1] * n
	for i in range(1, n):
		for j in range(i):
			if s[j] < s[i]:
				dp[i] = max(dp[i], dp[j] + 1)
	return max(dp)

def record_guess(data, uid, username, phonenumber_guess, result, ab_feedback_given=False):
	"""記錄猜測"""
	if 'user_records' not in data:
		data['user_records'] = {}
	if uid not in data['user_records']:
		data['user_records'][uid] = {}
	if username not in data['user_records'][uid]:
		data['user_records'][uid][username] = []
	
	record = {
		'type': 'guess',
		'guess': phonenumber_guess,
		'result': result,
		'ab_feedback': ab_feedback_given
	}
	data['user_records'][uid][username].append(record)

def record_tool_use(data, uid, username, tool_type, input_value=None, result=None):
	"""記錄工具使用：儲存 input 與 result"""
	if 'user_records' not in data:
		data['user_records'] = {}
	if uid not in data['user_records']:
		data['user_records'][uid] = {}
	if username not in data['user_records'][uid]:
		data['user_records'][uid][username] = []

	record = {
		'type': tool_type,
		'input': input_value,
		'result': result
	}
	data['user_records'][uid][username].append(record)

def clear_user_records_for_username(data, uid, username):
	"""在猜中該 username 時，清除該用戶所有關於該 username 的記錄"""
	if 'user_records' in data and uid in data['user_records']:
		if username in data['user_records'][uid]:
			del data['user_records'][uid][username]

def is_admin():
	"""檢查是否為 admin 的裝飾器"""
	async def predicate(interaction: discord.Interaction) -> bool:
		return interaction.user.name in ADMIN_USERS
	return discord.app_commands.check(predicate)

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
	print(f'Logged in as {bot.user} (ID: {bot.user.id})')
	try:
		await bot.tree.sync()
		print('Slash commands synced.')
	except Exception as e:
		print('Failed to sync commands:', e)
	print('------')

# ===== 手機猜測遊戲 =====

@bot.tree.command(name='create_account', description='建立一個新的遊戲帳號')
@discord.app_commands.describe(username='要建立的使用者名稱', phonenumber='以 09 開頭共 10 碼')
async def create_account(interaction: discord.Interaction, username: str, phonenumber: str):
	data = load_data()
	if username in data['accounts']:
		await interaction.response.send_message(f'❌ 使用者名稱 `{username}` 已存在，請換一個。', ephemeral=True)
		return
	if not valid_phone(phonenumber):
		await interaction.response.send_message('❌ 手機號碼格式錯誤：需以 09 開頭且共 10 碼。', ephemeral=True)
		return
	data['accounts'][username] = {
		'owner': str(interaction.user.id),
		'phone': phonenumber,
		'success_count': 0
	}
	data['successful_guesses'].setdefault(username, [])
	save_data(data)
	await interaction.response.send_message(f'✅ 已為你建立遊戲帳號 `{username}`。', ephemeral=True)
	await interaction.followup.send(f'🎮 {interaction.user.mention} 創了遊戲帳號 `{username}`。')

@bot.tree.command(name='guess', description='猜測指定遊戲帳號的手機號碼 (10碼) 或後五碼 (5碼)')
@discord.app_commands.describe(username='要猜的使用者名稱', phonenumber_guess='09 開頭共 10 碼，或任意 5 個數字')
async def guess(interaction: discord.Interaction, username: str, phonenumber_guess: str):
	data = load_data()
	uid = str(interaction.user.id)
	prof = get_or_create_profile(data, uid)
	hour = current_hour_key()
	user_counts = data.setdefault('user_guess_counts', {})
	bucket = user_counts.get(uid, {'hour': hour, 'count': 0})
	if bucket['hour'] != hour:
		bucket = {'hour': hour, 'count': 0}
	
	# 檢查 username 是否存在
	if username not in data['accounts']:
		await interaction.response.send_message('❌ 指定的 username 不存在。', ephemeral=True)
		return
	
	# 判斷是否為後五碼模式
	is_last_five = len(phonenumber_guess) == 5 and phonenumber_guess.isdigit()
	is_full_number = len(phonenumber_guess) == 10 and phonenumber_guess.startswith('09') and phonenumber_guess.isdigit()
	
	if not is_last_five and not is_full_number:
		await interaction.response.send_message('❌ 猜測格式錯誤：需要 5 個數字（後五碼）或 10 個數字（完整號碼：09 開頭）。', ephemeral=True)
		return
	
	already = data.setdefault('successful_guesses', {}).get(username, [])
	if uid in already:
		await interaction.response.send_message('⚠️ 你已經成功猜過這個帳號的手機號碼，無法再猜。', ephemeral=True)
		return
	
	# 後五碼模式
	if is_last_five:
		if prof.get('last_five_digits_uses', 0) <= 0:
			await interaction.response.send_message('❌ 你沒有後五碼猜測次數。', ephemeral=True)
			return
		
		# 檢查是否超過本小時猜測限制
		if bucket['count'] >= 8:
			await interaction.response.send_message('⛔ 本小時猜測次數已達上限（每小時最多 8 次），請等下一個整點或購買額外猜測機會。', ephemeral=True)
			return
		
		phone = data['accounts'][username]['phone']
		phone_last_five = phone[-5:]
		
		if phonenumber_guess == phone_last_five:
			# 後五碼正確：僅記錄此為一筆猜測紀錄（保存輸入與結果），不視為完整猜中
			bucket['count'] += 1
			prof['last_five_digits_uses'] -= 1
			data['user_guess_counts'][uid] = bucket
			record_guess(data, uid, username, phonenumber_guess, '✅ 後五碼猜對', ab_feedback_given=False)
			save_data(data)
			remaining = max(0, 8 - bucket['count'])
			await interaction.response.send_message(f'🎉 猜對後五碼！但這不算完整猜中。\n`{username}` 的後五碼正確。\n⏰ 還剩 **{remaining}** 次機會')
		else:
			bucket['count'] += 1
			prof['last_five_digits_uses'] -= 1
			data['user_guess_counts'][uid] = bucket
			diff = sum(1 for a, b in zip(phone_last_five, phonenumber_guess) if a != b)
			record_guess(data, uid, username, phonenumber_guess, f'差 {diff} 個', ab_feedback_given=False)
			save_data(data)
			remaining = max(0, 8 - bucket['count'])
			await interaction.response.send_message(f'🔎 猜測結果：有 {diff} 個位置與答案不一樣。\n⏰ 還剩 **{remaining}** 次機會')
		return
	
	# 正常猜測模式（10 碼）
	use_extra = False
	if bucket['count'] >= 8:
		if prof.get('extra_guess_chances', 0) <= 0:
			await interaction.response.send_message('⛔ 本小時猜測次數已達上限（每小時最多 8 次），請等下一個整點或購買額外猜測機會。', ephemeral=True)
			return
		use_extra = True
	
	answer = data['accounts'][username]['phone']
	diff = sum(1 for a, b in zip(answer, phonenumber_guess) if a != b)

	ab_feedback = prof.get('ab_feedback_uses', 0) > 0
	if ab_feedback:
		prof['ab_feedback_uses'] -= 1

	if diff == 0:
		if uid not in already:
			already.append(uid)
			data['accounts'][username]['success_count'] = data['accounts'][username].get('success_count', 0) + 1
			data['successful_guesses'][username] = already
			# 清除所有關於該 username 的記錄
			clear_user_records_for_username(data, uid, username)
		
		if use_extra:
			prof['extra_guess_chances'] -= 1
		else:
			bucket['count'] += 1
		data['user_guess_counts'][uid] = bucket
		record_guess(data, uid, username, phonenumber_guess, '✅ 猜對', ab_feedback)
		save_data(data)
		remaining = max(0, 8 - bucket['count'])
		await interaction.response.send_message(f'🎉 猜對了！`{username}` 的手機號碼正確。\n⏰ 還剩 **{remaining}** 次機會', ephemeral=True)
		await interaction.followup.send(f'🎉 恭喜 {interaction.user.mention} 猜中了 `{username}` 的手機號碼！')
	else:
		if use_extra:
			prof['extra_guess_chances'] -= 1
		else:
			bucket['count'] += 1
		data['user_guess_counts'][uid] = bucket

		if ab_feedback:
			a = sum(1 for i in range(len(answer)) if answer[i] == phonenumber_guess[i])
			common = sum(min(answer.count(d), phonenumber_guess.count(d)) for d in set(answer))
			b = common - a
			result_str = f'{a}A{b}B'
			record_guess(data, uid, username, phonenumber_guess, result_str, True)
			remaining = max(0, 8 - bucket['count'])
			save_data(data)
			await interaction.response.send_message(f'🔎 {a}A{b}B\n⏰ 還剩 **{remaining}** 次機會', ephemeral=True)
			await interaction.followup.send(f'{interaction.user.mention} 猜了 `{username}` 的手機號碼，有 {diff} 個位置與答案不一樣。')
		else:
			result_str = f'差 {diff} 個'
			record_guess(data, uid, username, result_str, False)
			remaining = max(0, 8 - bucket['count'])
			save_data(data)
			await interaction.response.send_message(f'🔎 猜測結果：有 {diff} 個位置與答案不一樣。\n⏰ 還剩 **{remaining}** 次機會', ephemeral=True)
			await interaction.followup.send(f'{interaction.user.mention} 猜了 `{username}` 的手機號碼，有 {diff} 個位置與答案不一樣。')

@bot.tree.command(name='stats', description='查看指定遊戲帳號被猜中的次數')
@discord.app_commands.describe(username='要查詢的使用者名稱')
async def stats(interaction: discord.Interaction, username: str):
	data = load_data()
	if username not in data['accounts']:
		await interaction.response.send_message('❌ 指定的 username 不存在。', ephemeral=True)
		return
	suc_list = data.setdefault('successful_guesses', {}).get(username, [])
	await interaction.response.send_message(f'📊 `{username}` 的手機號碼已被正確猜到 {len(suc_list)} 次。')

@bot.tree.command(name='accounts', description='查看指定 Discord 用戶創的所有遊戲帳號（預設查自己）')
@discord.app_commands.describe(user='要查詢的 Discord 用戶（預設為自己）')
async def accounts(interaction: discord.Interaction, user: discord.User = None):
	if user is None:
		user = interaction.user
	data = load_data()
	uid = str(user.id)
	user_accounts = [acc for acc, info in data['accounts'].items() if info['owner'] == uid]
	if not user_accounts:
		await interaction.response.send_message(f'❌ {user.mention} 還沒有建立任何遊戲帳號。', ephemeral=True)
		return
	acc_list = '\n'.join([f'• `{acc}`' for acc in user_accounts])
	await interaction.response.send_message(f'👤 {user.mention} 的遊戲帳號：\n{acc_list}')

# ===== 商品功能命令 =====

@bot.tree.command(name='profile', description='查看指定 Discord 用戶的種族、金幣與剩餘猜測機會（預設查自己）')
@discord.app_commands.describe(user='要查詢的 Discord 用戶（預設為自己）')
async def profile(interaction: discord.Interaction, user: discord.User = None):
	if user is None:
		user = interaction.user
	data = load_data()
	prof = get_or_create_profile(data, user.id)
	user_counts = data.setdefault('user_guess_counts', {})
	bucket = user_counts.get(str(user.id), {'hour': current_hour_key(), 'count': 0})
	if bucket['hour'] != current_hour_key():
		bucket_count = 0
	else:
		bucket_count = bucket['count']
	remaining_guesses = max(0, 8 - bucket_count)
	save_data(data)
	
	race_emoji = {'主人': '👑', '寧寧': '✨', '阿尼的哥哥': '🔥'}.get(prof['race'], '❓')
	coins = prof['coins']
	next_reset = get_next_claim_reset(datetime.now()).strftime('%H:%M')
	
	embed = discord.Embed(
		title=f'👤 {user.display_name} 的檔案',
		color=discord.Color.blue()
	)
	embed.add_field(name='種族', value=f'{race_emoji} {prof["race"]}', inline=True)
	embed.add_field(name='金幣', value=f'💰 {coins}', inline=True)
	embed.add_field(name='本小時剩餘猜測', value=f'{remaining_guesses}', inline=False)
	embed.add_field(name='額外猜測機會', value=f'{prof["extra_guess_chances"]}', inline=True)
	embed.add_field(name='A/B 反饋次數', value=f'{prof["ab_feedback_uses"]}', inline=True)
	embed.add_field(name='後五碼猜測', value=f'{prof.get("last_five_digits_uses", 0)}', inline=True)
	embed.add_field(name='下次可領取', value=next_reset, inline=False)
	await interaction.response.send_message(embed=embed)

@bot.tree.command(name='coins', description='查看指定 Discord 用戶的金幣數量（預設查自己）')
@discord.app_commands.describe(user='要查詢的 Discord 用戶（預設為自己）')
async def coins(interaction: discord.Interaction, user: discord.User = None):
	if user is None:
		user = interaction.user
	data = load_data()
	prof = get_or_create_profile(data, user.id)
	save_data(data)
	await interaction.response.send_message(f'💰 {user.mention} 的金幣：**{prof["coins"]}**')

@bot.tree.command(name='shop', description='查看商店商品列表')
async def shop(interaction: discord.Interaction):
	embed = discord.Embed(title='🛒 商店商品列表', color=discord.Color.green())
	embed.add_field(name='額外猜測機會', value='10 金幣 / 1 次\n增加一筆額外猜測機會，不佔每小時 8 次限制。', inline=False)
	embed.add_field(name='A/B 反饋下次猜測', value='500 金幣 / 1 次\n下一次猜測若錯，改回傳 xA yB。', inline=False)
	embed.add_field(name='數字計數器', value='20 金幣 / 1 次\n指定一個數字，系統回傳該數字在 phone number 出現的次數。', inline=False)
	embed.add_field(name='後五碼猜測', value='400 金幣 / 1 次\n下次猜測只需輸入 5 碼數字（後五碼）。', inline=False)
	embed.add_field(name='整除餘數', value='800 金幣 / 1 次\n系統隨機選擇 2 或 7，回傳 phone number 除以該數的餘數。', inline=False)
	embed.add_field(name='最長嚴格遞增子序列', value='1200 金幣 / 1 次\n回傳指定 username 的 phone number 的最長嚴格遞增子序列長度。', inline=False)
	embed.add_field(name='包含的數字', value='100 金幣 / 1 次\n回傳指定 username 的 phone number 中包含的所有數字。', inline=False)
	await interaction.response.send_message(embed=embed)
@bot.tree.command(name='buy', description='在商店購買商品')
@discord.app_commands.describe(item='要購買的商品', quantity='購買數量')
@discord.app_commands.choices(item=[
	discord.app_commands.Choice(name='額外猜測機會', value='extra_guess'),
	discord.app_commands.Choice(name='A/B 反饋下次猜測', value='ab_feedback'),
	discord.app_commands.Choice(name='數字計數器', value='digit_counter'),
	discord.app_commands.Choice(name='後五碼猜測', value='last_five_digits'),
	discord.app_commands.Choice(name='整除餘數', value='divisor_remainder'),
	discord.app_commands.Choice(name='最長嚴格遞增子序列', value='lis_query'),
	discord.app_commands.Choice(name='包含的數字', value='unique_digits')
])
async def buy(interaction: discord.Interaction, item: str, quantity: int = 1):
	if quantity <= 0:
		await interaction.response.send_message('❌ 購買數量必須大於 0。', ephemeral=True)
		return
	data = load_data()
	uid = str(interaction.user.id)
	prof = get_or_create_profile(data, uid)
	price = 0
	if item == 'extra_guess':
		price = 10 * quantity
		if prof['coins'] < price:
			await interaction.response.send_message(f'❌ 你的金幣不足，需 {price}，但你只有 {prof["coins"]}。', ephemeral=True)
			return
		prof['coins'] -= price
		prof['extra_guess_chances'] += quantity
		message = f'✅ 購買成功：額外猜測機會 +{quantity}。'
	elif item == 'ab_feedback':
		price = 500 * quantity
		if prof['coins'] < price:
			await interaction.response.send_message(f'❌ 你的金幣不足，需 {price}，但你只有 {prof["coins"]}。', ephemeral=True)
			return
		prof['coins'] -= price
		prof['ab_feedback_uses'] += quantity
		message = f'✅ 購買成功：A/B 反饋次數 +{quantity}。'
	elif item == 'digit_counter':
		price = 20 * quantity
		if prof['coins'] < price:
			await interaction.response.send_message(f'❌ 你的金幣不足，需 {price}，但你只有 {prof["coins"]}。', ephemeral=True)
			return
		prof['coins'] -= price
		prof['digit_counter_uses'] += quantity
		save_data(data)
		if quantity == 1:
			await interaction.response.send_modal(DigitCounterModal())
			return
		message = f'✅ 購買成功：數字計數器 +{quantity}。'
	elif item == 'last_five_digits':
		price = 400 * quantity
		if prof['coins'] < price:
			await interaction.response.send_message(f'❌ 你的金幣不足，需 {price}，但你只有 {prof["coins"]}。', ephemeral=True)
			return
		prof['coins'] -= price
		prof['last_five_digits_uses'] += quantity
		message = f'✅ 購買成功：後五碼猜測 +{quantity}。\n💡 下次 /guess 時輸入 5 個數字即可使用。'
	elif item == 'divisor_remainder':
		price = 800 * quantity
		if prof['coins'] < price:
			await interaction.response.send_message(f'❌ 你的金幣不足，需 {price}，但你只有 {prof["coins"]}。', ephemeral=True)
			return
		prof['coins'] -= price
		prof['divisor_remainder_uses'] += quantity
		save_data(data)
		if quantity == 1:
			await interaction.response.send_modal(DivisorRemainderModal())
			return
		message = f'✅ 購買成功：整除餘數 +{quantity}。'
	elif item == 'lis_query':
		price = 1200 * quantity
		if quantity != 1:
			await interaction.response.send_message('❌ 最長嚴格遞增子序列商品一次只能買 1 次。', ephemeral=True)
			return
		if prof['coins'] < price:
			await interaction.response.send_message(f'❌ 你的金幣不足，需 {price}，但你只有 {prof["coins"]}。', ephemeral=True)
			return
		prof['coins'] -= price
		prof['lis_query_uses'] += 1
		save_data(data)
		await interaction.response.send_modal(LISModal())
		return
	elif item == 'unique_digits':
		price = 100 * quantity
		if quantity != 1:
			await interaction.response.send_message('❌ 包含的數字商品一次只能買 1 次。', ephemeral=True)
			return
		if prof['coins'] < price:
			await interaction.response.send_message(f'❌ 你的金幣不足，需 {price}，但你只有 {prof["coins"]}。', ephemeral=True)
			return
		prof['coins'] -= price
		prof['unique_digits_uses'] += 1
		save_data(data)
		await interaction.response.send_modal(UniqueDigitsModal())
		return
	else:
		await interaction.response.send_message('❌ 不支援的商品。', ephemeral=True)
		return
	save_data(data)
	await interaction.response.send_message(message, ephemeral=True)
	await interaction.response.send_message(f'{message} 你剩下 **{prof["coins"]}** 金幣。')

@bot.tree.command(name='claim', description='每小時領取金幣，30 分重置，並有機率中大獎。')
async def claim(interaction: discord.Interaction):
	data = load_data()
	uid = str(interaction.user.id)
	prof = get_or_create_profile(data, uid)
	is_admin = interaction.user.name in ADMIN_USERS

	now = datetime.now()
	period = get_claim_period(now)
	if not is_admin and prof.get('last_claim_period') == period:
		next_reset = get_next_claim_reset(now).strftime('%H:%M')
		await interaction.response.send_message(
			f'⛔ 你本期已經領取過了，請於 {next_reset} 後再領取。',
			ephemeral=True
		)
		return

	jackpot = random.random() < 0.01
	if jackpot:
		base_amount = 1000
		message = '🎉 你中大獎了！'
	else:
		base_amount = random.randint(0, 200)
		message = '💰 領取成功！'

	multiplier = {'主人': 1.5, '寧寧': 1.0, '阿尼的哥哥': 0.5}[prof['race']]
	reward = int(base_amount * multiplier)
	prof['coins'] += reward
	prof['last_claim_period'] = period
	save_data(data)

	next_reset = get_next_claim_reset(now).strftime('%H:%M')
	await interaction.response.send_message(
		f'{message} 你獲得 **{reward}** 金幣。\n'
		f'基礎金額：{base_amount}，種族倍率：{multiplier}。\n'
		f'總金幣：**{prof["coins"]}**\n'
		f'下次可於 {next_reset} 再領取。'
	)

@bot.tree.command(name='records', description='查看自己的猜測和工具使用紀錄')
@discord.app_commands.describe(username='[可選] 查看特定 username 的記錄')
async def records(interaction: discord.Interaction, username: str = None):
	data = load_data()
	uid = str(interaction.user.id)
	user_records_dict = data.get('user_records', {}).get(uid, {})
	
	if not user_records_dict:
		await interaction.response.send_message('📋 你還沒有任何紀錄。', ephemeral=True)
		return
	
	# 如果指定了 username，只顯示該 username 的記錄
	if username:
		if username not in user_records_dict:
			await interaction.response.send_message(f'📋 你還沒有關於 `{username}` 的任何紀錄。', ephemeral=True)
			return
		username_records = user_records_dict[username]
		embed = discord.Embed(title=f'📋 {interaction.user.display_name} 關於 `{username}` 的紀錄', color=discord.Color.purple())
		
		# 顯示最近 15 筆記錄
		recent = username_records[-15:]
		for i, rec in enumerate(recent, 1):
			rec_type = rec.get('type', '未知')
			
			if rec_type == 'guess':
				guess = rec.get('guess', '?')
				result = rec.get('result', '?')
				ab = ' (A/B反饋)' if rec.get('ab_feedback') else ''
				field_value = f'猜測: `{guess}`\n結果: {result}{ab}'
				field_name = f'{i}. 猜測'
			elif rec_type == 'digit_counter':
				result = rec.get('result', '?')
				field_value = f'結果: {result}'
				field_name = f'{i}. 數字計數器'
			elif rec_type == 'divisor_remainder':
				inp = rec.get('input', '?')
				result = rec.get('result', '?')
				field_value = f'輸入(除數): `{inp}`\n結果: {result}'
				field_name = f'{i}. 整除餘數'
			elif rec_type == 'lis_query':
				result = rec.get('result', '?')
				field_value = f'結果: {result}'
				field_name = f'{i}. 最長遞增子序列'
			elif rec_type == 'unique_digits':
				result = rec.get('result', '?')
				field_value = f'結果: {result}'
				field_name = f'{i}. 包含的數字'
			else:
				# 其他類型（含用 record_guess 記錄的後五碼與普通猜測）
				if 'guess' in rec:
					guess = rec.get('guess', '?')
					result = rec.get('result', '?')
					ab = ' (A/B反饋)' if rec.get('ab_feedback') else ''
					field_value = f'猜測: `{guess}`\n結果: {result}{ab}'
					field_name = f'{i}. 猜測'
				else:
					# fallback
					field_value = rec.get('result', '?')
					field_name = f'{i}. 其他'

			
			embed.add_field(name=field_name, value=field_value, inline=False)
		
		await interaction.response.send_message(embed=embed, ephemeral=True)
		return
	
	# 顯示所有 username 的記錄統計
	embed = discord.Embed(title=f'📋 {interaction.user.display_name} 的所有紀錄', color=discord.Color.purple())
	embed.description = '你對以下 username 進行了猜測或工具查詢：\n使用 `/records username:xxx` 查看特定 username 的記錄。'
	
	for target_username, records_list in list(user_records_dict.items())[:10]:
		record_count = len(records_list)
		success = '✅' if any(r.get('type') == 'guess' and r.get('result') == '✅ 猜對' for r in records_list) else '❌'
		embed.add_field(name=f'{success} `{target_username}` ({record_count} 筆)', value=' ', inline=True)
	
	await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name='admin_give_money', description='[Admin Only] 獲得 10000 金幣')
@is_admin()
async def admin_give_money(interaction: discord.Interaction):
	data = load_data()
	uid = str(interaction.user.id)
	prof = get_or_create_profile(data, uid)
	prof['coins'] += 10000
	save_data(data)
	
	await interaction.response.send_message(f'✨ Admin 指令：已為 {interaction.user.mention} 增加 10000 金幣。\n目前金幣：**{prof["coins"]}**', ephemeral=True)

if __name__ == '__main__':
	token = os.environ.get('DISCORD_TOKEN')
	if not token:
		token = input('請輸入 DISCORD bot token: ').strip()
	bot.run(token)

