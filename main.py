import discord
from discord.ext import commands, tasks
import os
import sqlite3
import datetime
import asyncio
import aiohttp

# --- Load Environment Variables ---
TOKEN = os.getenv('BOT_TOKEN')
AI_API_KEY = os.getenv('AI_API_KEY')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0))
ID_BIRTHDAY_CH = int(os.getenv('ID_BIRTHDAY_CH', 0))
ID_SLIP_CHANNEL = int(os.getenv('ID_SLIP_CHANNEL', 0))
ID_HISTORY_CHANNEL = int(os.getenv('ID_HISTORY_CHANNEL', 0))
ID_WAIT_VOICE = int(os.getenv('ID_WAIT_VOICE', 0))
ID_ADMIN_VOICE = int(os.getenv('ID_ADMIN_VOICE', 0))
ROLE_VIP_NAME = os.getenv('ROLE_VIP_NAME', 'Vip')

# --- Bot & DB Setup ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

conn = sqlite3.connect('database.db')
c = conn.cursor()
c.execute('CREATE TABLE IF NOT EXISTS birthdays (user_id INTEGER PRIMARY KEY, birthday TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS ai_chars (channel_id INTEGER PRIMARY KEY, name TEXT, age TEXT, trait TEXT)')
conn.commit()

# --- [ Helper Functions ] ---
async def ask_ai(prompt, system_instruction):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={AI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": f"{system_instruction}\n\nUser: {prompt}\nAI:"}]}]}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data['candidates'][0]['content']['parts'][0]['text']
            return "❌ AI ไม่ตอบสนอง (เช็ก API Key)"

# --- [ 1. Birthday System ] ---
class BirthdayModal(discord.ui.Modal, title="ลงทะเบียนวันเกิด"):
    date_in = discord.ui.TextInput(label="วัน/เดือน/ค.ศ. (เช่น 25/12/2000)", placeholder="DD/MM/YYYY")
    async def on_submit(self, itn: discord.Interaction):
        c.execute("REPLACE INTO birthdays VALUES (?, ?)", (itn.user.id, self.date_in.value))
        conn.commit()
        await itn.response.send_message(f"บันทึกวันเกิดเรียบร้อย: {self.date_in.value}", ephemeral=True)

class BirthdayView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="ลงทะเบียนวันเกิด", style=discord.ButtonStyle.primary, emoji="🎂")
    async def btn(self, itn, btn): await itn.response.send_modal(BirthdayModal())

@tasks.loop(hours=24)
async def check_bdays():
    now = datetime.datetime.now().strftime("%d/%m")
    c.execute("SELECT user_id FROM birthdays WHERE birthday LIKE ?", (f"{now}%",))
    users = c.fetchall()
    ch = bot.get_channel(ID_BIRTHDAY_CH)
    if ch:
        for u in users:
            m = await ch.guild.fetch_member(u[0])
            if m: await ch.send(f"🎂 สุขสันต์วันเกิดนะ {m.mention}! ขอให้มีความสุขมากๆ 🎉")

# --- [ 2. Admin Voice System ] ---
class CallAdminView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="📞 ติดต่อแอดมิน (ย้ายเข้าห้องรอ)", style=discord.ButtonStyle.danger)
    async def btn(self, itn, btn):
        if itn.user.voice:
            await itn.user.move_to(bot.get_channel(ID_WAIT_VOICE))
            await itn.response.send_message("✅ ย้ายคุณไปห้องรอแล้ว!", ephemeral=True)
        else:
            await itn.response.send_message("⚠️ กรุณาเข้าห้องเสียงใดห้องหนึ่งก่อนกดปุ่มครับ", ephemeral=True)

@bot.event
async def on_voice_state_update(member, before, after):
    adm_v = bot.get_channel(ID_ADMIN_VOICE)
    wait_v = bot.get_channel(ID_WAIT_VOICE)
    if after.channel and after.channel.id == ID_ADMIN_VOICE and member.id == ADMIN_USER_ID:
        for m in wait_v.members: await m.move_to(adm_v)
    if before.channel and before.channel.id == ID_ADMIN_VOICE and member.id == ADMIN_USER_ID:
        for m in adm_v.members: 
            if m.id != ADMIN_USER_ID: await m.move_to(None)

# --- [ 3. Shop & Verify System ] ---
class VerifyView(discord.ui.View):
    def __init__(self, buyer_id):
        super().__init__(timeout=None)
        self.buyer_id = buyer_id

    @discord.ui.button(label="✅ อนุมัติ", style=discord.ButtonStyle.success)
    async def approve(self, itn, btn):
        if itn.user.id != ADMIN_USER_ID: return
        m = await itn.guild.fetch_member(self.buyer_id)
        r = discord.utils.get(itn.guild.roles, name=ROLE_VIP_NAME)
        await m.add_roles(r)
        await m.send(f"✅ ยศ {ROLE_VIP_NAME} ของคุณได้รับการอนุมัติ!")
        await bot.get_channel(ID_HISTORY_CHANNEL).send(f"📦 {m.mention} ซื้อยศสำเร็จโดย {itn.user.mention}")
        await itn.message.delete()

    @discord.ui.button(label="❌ ปฏิเสธ", style=discord.ButtonStyle.danger)
    async def deny(self, itn, btn):
        if itn.user.id != ADMIN_USER_ID: return
        m = await itn.guild.fetch_member(self.buyer_id)
        await m.send("❌ การซื้อยศถูกปฏิเสธ")
        await itn.message.delete()

class ShopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="💰 ติดต่อซื้อยศ", style=discord.ButtonStyle.success)
    async def btn(self, itn, btn):
        await itn.user.send(f"ส่งสลิปที่ห้อง <#{ID_SLIP_CHANNEL}>")
        await itn.response.send_message("เช็ก DM ของคุณด้วยครับ", ephemeral=True)

# --- [ 4. AI System ] ---
class AIModal(discord.ui.Modal, title="สร้างตัวละคร AI"):
    name = discord.ui.TextInput(label="ชื่อ AI")
    age = discord.ui.TextInput(label="อายุ")
    trait = discord.ui.TextInput(label="นิสัย", style=discord.TextStyle.paragraph)
    async def on_submit(self, itn: discord.Interaction):
        ov = {itn.guild.default_role: discord.PermissionOverwrite(read_messages=False), itn.user: discord.PermissionOverwrite(read_messages=True)}
        ch = await itn.guild.create_text_channel(f"ai-{self.name.value}", overwrites=ov)
        c.execute("INSERT INTO ai_chars VALUES (?,?,?,?)", (ch.id, self.name.value, self.age.value, self.trait.value))
        conn.commit()
        await ch.send(f"🤖 **AI {self.name.value} พร้อมคุยแล้ว!**")
        await itn.response.send_message(f"สร้างห้องแล้วที่ {ch.mention}", ephemeral=True)

class AIView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="🤖 สร้างตัวละคร AI", style=discord.ButtonStyle.secondary)
    async def btn(self, itn, btn): await itn.response.send_modal(AIModal())

# --- [ Events & Commands ] ---
@bot.event
async def on_message(msg):
    if msg.author.bot: return
    if msg.channel.id == ID_SLIP_CHANNEL and msg.attachments:
        await msg.channel.send(f"🔔 <@{ADMIN_USER_ID}> สลิปจาก {msg.author.mention}", view=VerifyView(msg.author.id))
    
    c.execute("SELECT name, age, trait FROM ai_chars WHERE channel_id=?", (msg.channel.id,))
    ai = c.fetchone()
    if ai:
        instr = f"Name: {ai[0]}, Age: {ai[1]}, Traits: {ai[2]}. Respond naturally."
        async with msg.channel.typing():
            res = await ask_ai(msg.content, instr)
            await msg.channel.send(res)
    await bot.process_commands(msg)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup_all(ctx):
    await ctx.send("🎂 **วันเกิด**", view=BirthdayView())
    await ctx.send("📞 **ติดต่อแอดมิน**", view=CallAdminView())
    await ctx.send("💰 **ร้านค้า**", view=ShopView())
    await ctx.send("🤖 **ระบบ AI**", view=AIView())

@bot.event
async def on_ready():
    check_bdays.start()
    print(f"Logged in as {bot.user}")

bot.run(TOKEN)
