import discord
from discord.ext import commands, tasks
import os
import sqlite3
import datetime
import asyncio

# --- ดึงค่าจาก Railway Environment Variables ---
TOKEN = os.getenv('BOT_TOKEN')
ID_BIRTHDAY_CH = int(os.getenv('ID_BIRTHDAY_CH', 0))
ID_WAITING_ROOM = int(os.getenv('ID_WAITING_ROOM', 0))
ID_ADMIN_ROOM = int(os.getenv('ID_ADMIN_ROOM', 0))
ID_SLIP_CHANNEL = int(os.getenv('ID_SLIP_CHANNEL', 0))
ID_HISTORY_CHANNEL = int(os.getenv('ID_HISTORY_CHANNEL', 0))
ROLE_ADMIN_NAME = os.getenv('ROLE_ADMIN_NAME', 'Admin')
ROLE_VIP_NAME = os.getenv('ROLE_VIP_NAME', 'Vip')

# --- ตั้งค่า Bot ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# --- Database Setup ---
conn = sqlite3.connect('database.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS birthdays (user_id INTEGER PRIMARY KEY, birthday TEXT)''')
conn.commit()

# --- 1. ระบบวันเกิด ---
class BirthdayModal(discord.ui.Modal, title="ลงทะเบียนวันเกิด"):
    date_input = discord.ui.TextInput(label="วัน/เดือน/ค.ศ. (เช่น 25/12/2000)", placeholder="DD/MM/YYYY")
    async def on_submit(self, interaction: discord.Interaction):
        c.execute("REPLACE INTO birthdays (user_id, birthday) VALUES (?, ?)", (interaction.user.id, self.date_input.value))
        conn.commit()
        await interaction.response.send_message(f"บันทึกวันเกิดเรียบร้อย: {self.date_input.value}", ephemeral=True)

@tasks.loop(hours=24)
async def check_birthdays():
    now = datetime.datetime.now().strftime("%d/%m")
    c.execute("SELECT user_id FROM birthdays WHERE birthday LIKE ?", (f"{now}%",))
    users = c.fetchall()
    channel = bot.get_channel(ID_BIRTHDAY_CH)
    if channel:
        for user_id in users:
            try:
                member = await channel.guild.fetch_member(user_id[0])
                await channel.send(f"🎂 สุขสันต์วันเกิดนะ {member.mention}! ขอให้มีความสุขมากๆ 🎉")
            except: continue

# --- 2. ระบบดึงเข้าห้องเสียงแอดมิน ---
@bot.event
async def on_voice_state_update(member, before, after):
    admin_room = bot.get_channel(ID_ADMIN_ROOM)
    waiting_room = bot.get_channel(ID_WAITING_ROOM)
    if not admin_room or not waiting_room: return

    if after.channel and after.channel.id == ID_ADMIN_ROOM:
        if any(role.name == ROLE_ADMIN_NAME for role in member.roles):
            for m in waiting_room.members:
                await m.move_to(admin_room)

    if before.channel and before.channel.id == ID_ADMIN_ROOM:
        if any(role.name == ROLE_ADMIN_NAME for role in member.roles):
            if not any(any(r.name == ROLE_ADMIN_NAME for r in m.roles) for m in admin_room.members):
                for m in admin_room.members:
                    await m.move_to(None)

# --- 3. ระบบซื้อยศ ---
class VerifyView(discord.ui.View):
    def __init__(self, buyer_id):
        super().__init__(timeout=None)
        self.buyer_id = buyer_id

    @discord.ui.button(label="อนุมัติยศ", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        member = await interaction.guild.fetch_member(self.buyer_id)
        role = discord.utils.get(interaction.guild.roles, name=ROLE_VIP_NAME)
        await member.add_roles(role)
        await member.send(f"✅ ยินดีด้วย! คุณได้รับยศ {ROLE_VIP_NAME} เรียบร้อยแล้ว")
        await bot.get_channel(ID_HISTORY_CHANNEL).send(f"📦 {member.mention} ซื้อยศสำเร็จโดย {interaction.user}")
        await interaction.message.delete()

@bot.event
async def on_message(message):
    if message.channel.id == ID_SLIP_CHANNEL and message.attachments and not message.author.bot:
        view = VerifyView(message.author.id)
        await message.channel.send(f"🔔 สลิปจาก {message.author.mention} (เฉพาะแอดมินที่เห็นปุ่มนี้)", view=view)
    await bot.process_commands(message)

# --- 4. ระบบ AI Character ---
class AIConfigModal(discord.ui.Modal, title="สร้างตัวละคร AI"):
    name = discord.ui.TextInput(label="ชื่อ AI")
    trait = discord.ui.TextInput(label="นิสัย", style=discord.TextStyle.paragraph)
    async def on_submit(self, interaction: discord.Interaction):
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await interaction.guild.create_text_channel(f"ai-{self.name.value}", overwrites=overwrites)
        await channel.send(f"🤖 AI: {self.name.value} พร้อมคุยกับคุณแล้ว!\nนิสัย: {self.trait.value}")
        await interaction.response.send_message(f"สร้างห้องแล้วที่ {channel.mention}", ephemeral=True)

# --- เมนูหลัก ---
class MainView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="ลงทะเบียนวันเกิด", style=discord.ButtonStyle.gray)
    async def b_day(self, itn, btn): await itn.response.send_modal(BirthdayModal())
    @discord.ui.button(label="ติดต่อซื้อยศ", style=discord.ButtonStyle.green)
    async def buy(self, itn, btn): await itn.response.send_message(f"ส่งสลิปที่ <#{ID_SLIP_CHANNEL}>", ephemeral=True)
    @discord.ui.button(label="สร้างตัวละคร AI", style=discord.ButtonStyle.blurple)
    async def ai(self, itn, btn): await itn.response.send_modal(AIConfigModal())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("⚙️ **ระบบจัดการเซิร์ฟเวอร์**", view=MainView())

@bot.event
async def on_ready():
    check_birthdays.start()
    print(f'Online: {bot.user}')

bot.run(TOKEN)
