import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import sqlite3
import datetime
import asyncio

# --- ตั้งค่า Bot ---
TOKEN = os.getenv('BOT_TOKEN')
intents = discord.Intents.all()
bot = commands.Bot(command_command_prefix="!", intents=intents)

# --- เชื่อมต่อ Database ---
conn = sqlite3.connect('database.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS birthdays (user_id INTEGER PRIMARY KEY, birthday TEXT)''')
conn.commit()

# --- 1. ระบบวันเกิด (Birthday Modal & Task) ---
class BirthdayModal(discord.ui.Modal, title="ลงทะเบียนวันเกิด"):
    date_input = discord.ui.TextInput(label="วัน/เดือน/ค.ศ. (เช่น 25/12/2000)", placeholder="DD/MM/YYYY")

    async def on_submit(self, interaction: discord.Interaction):
        c.execute("REPLACE INTO birthdays (user_id, birthday) VALUES (?, ?)", (interaction.user.id, self.date_input.value))
        conn.commit()
        await interaction.response.send_message(f"ลงทะเบียนวันเกิดเรียบร้อย: {self.date_input.value}", ephemeral=True)

@tasks.loop(hours=24)
async def check_birthdays():
    now = datetime.datetime.now().strftime("%d/%m")
    c.execute("SELECT user_id FROM birthdays WHERE birthday LIKE ?", (f"{now}%",))
    users = c.fetchall()
    channel = bot.get_channel(1234567890) # **แก้ไข: ใส่ ID ห้องแจ้งเตือนวันเกิด**
    if channel:
        for user_id in users:
            member = await channel.guild.fetch_member(user_id[0])
            if member:
                await channel.send(f"🎂 สุขสันต์วันเกิดนะ {member.mention}! ขอให้มีความสุขมากๆ ครับ 🎉")

# --- 2. ระบบติดต่อแอดมิน (Admin Sync Voice) ---
# ระบบนี้จะทำงานอัตโนมัติผ่าน Event on_voice_state_update
ID_WAITING_ROOM = 11111111  # **แก้ไข: ใส่ ID ห้องรอแอดมิน**
ID_ADMIN_ROOM = 22222222    # **แก้ไข: ใส่ ID ห้องติดต่อแอดมิน**
ROLE_ADMIN_NAME = "Admin"   # **แก้ไข: ชื่อยศแอดมิน**

@bot.event
async def on_voice_state_update(member, before, after):
    admin_room = bot.get_channel(ID_ADMIN_ROOM)
    waiting_room = bot.get_channel(ID_WAITING_ROOM)
    
    # เมื่อแอดมินเข้าห้องติดต่อแอดมิน
    if after.channel and after.channel.id == ID_ADMIN_ROOM:
        if any(role.name == ROLE_ADMIN_NAME for role in member.roles):
            for m in waiting_room.members:
                await m.move_to(admin_room)

    # เมื่อแอดมินออกจากห้องติดต่อแอดมิน
    if before.channel and before.channel.id == ID_ADMIN_ROOM:
        if any(role.name == ROLE_ADMIN_NAME for role in member.roles):
            # เตะทุกคน (ยกเว้นแอดมินคนอื่นที่อาจยังอยู่) ออกจากห้อง
            if not any(any(r.name == ROLE_ADMIN_NAME for r in m.roles) for m in admin_room.members):
                for m in admin_room.members:
                    await m.move_to(None)

# --- 3. ระบบซื้อยศ (Shop & Slip Verification) ---
ID_SLIP_CHANNEL = 33333333     # **แก้ไข: ID ห้องส่งสลิป**
ID_HISTORY_CHANNEL = 44444444  # **แก้ไข: ID ห้องประวัติ**

class ShopView(discord.ui.View):
    @discord.ui.button(label="ติดต่อซื้อยศ", style=discord.ButtonStyle.primary)
    async def buy_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.user.send(f"กรุณาส่งสลิปโอนเงินที่ห้อง <#{ID_SLIP_CHANNEL}> พร้อมระบุยศที่ต้องการ")
        await interaction.response.send_message("บอทส่งรายละเอียดไปทาง DM แล้วครับ", ephemeral=True)

class VerifyView(discord.ui.View):
    def __init__(self, buyer_id):
        super().__init__(timeout=None)
        self.buyer_id = buyer_id

    @discord.ui.button(label="อนุมัติยศ", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        member = await guild.fetch_member(self.buyer_id)
        role = discord.utils.get(guild.roles, name="Vip") # **แก้ไข: ชื่อยศที่ต้องการให้**
        await member.add_roles(role)
        
        # แจ้งสมาชิก & ประวัติ
        await member.send("✅ การซื้อยศของคุณได้รับการอนุมัติแล้ว!")
        history_ch = bot.get_channel(ID_HISTORY_CHANNEL)
        await history_ch.send(f"📦 ซื้อขายสำเร็จ: {member.mention} ได้รับยศ {role.name} โดย Admin {interaction.user}")
        await interaction.message.delete()

@bot.event
async def on_message(message):
    if message.channel.id == ID_SLIP_CHANNEL and message.attachments:
        if not message.author.bot:
            view = VerifyView(message.author.id)
            # ข้อความเห็นเฉพาะแอดมิน (ใช้วิธีส่งแล้วลบ หรือตั้ง Permission ห้องให้แอดมินเห็นคนเดียว)
            await message.channel.send(f"🔔 สลิปจาก {message.author.mention} รอแอดมินตรวจสอบ", view=view)
    await bot.process_commands(message)

# --- 4. ระบบ AI Character (Private Room) ---
class AIConfigModal(discord.ui.Modal, title="สร้างตัวละคร AI"):
    name = discord.ui.TextInput(label="ชื่อ AI", placeholder="ตั้งชื่อเล่นให้ AI")
    age = discord.ui.TextInput(label="อายุ", placeholder="เช่น 18")
    trait = discord.ui.TextInput(label="นิสัย/บุคลิก", style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        channel = await guild.create_text_channel(f"ai-{self.name.value}", overwrites=overwrites)
        await channel.send(f"🤖 **ตัวละคร AI ถูกสร้างแล้ว**\nชื่อ: {self.name.value}\nอายุ: {self.age.value}\nนิสัย: {self.trait.value}\n*ห้องนี้เป็นห้องส่วนตัวของคุณ*")
        await interaction.response.send_message(f"สร้างห้องคุยกับ AI แล้วที่ {channel.mention}", ephemeral=True)

# --- ปุ่มกดรวม (Setup Command) ---
class MainControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="ลงทะเบียนวันเกิด", style=discord.ButtonStyle.secondary)
    async def reg_bd(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BirthdayModal())

    @discord.ui.button(label="ติดต่อซื้อยศ", style=discord.ButtonStyle.success)
    async def buy_role_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(f"กรุณาส่งสลิปที่ <#{ID_SLIP_CHANNEL}>", ephemeral=True)

    @discord.ui.button(label="สร้างตัวละคร AI", style=discord.ButtonStyle.primary)
    async def create_ai(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AIConfigModal())

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    await ctx.send("=== ระบบจัดการเซิร์ฟเวอร์ ===", view=MainControlView())

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    check_birthdays.start()
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)

bot.run(TOKEN)
