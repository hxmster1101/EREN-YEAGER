# --- เพิ่ม Variable ใน Railway ---
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', 0)) # ID ของแอดมินที่ตรวจสอบได้คนเดียว

# --- 3. ระบบซื้อยศ (เวอร์ชัน อนุมัติ/ยกเลิก โดยแอดมินคนเดียว) ---
class VerifyView(discord.ui.View):
    def __init__(self, buyer_id):
        super().__init__(timeout=None)
        self.buyer_id = buyer_id

    @discord.ui.button(label="✅ อนุมัติ", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ตรวจสอบว่าเป็นแอดมินที่กำหนดหรือไม่
        if interaction.user.id != ADMIN_USER_ID:
            return await interaction.response.send_message("❌ คุณไม่มีสิทธิ์กดปุ่มนี้", ephemeral=True)

        guild = interaction.guild
        member = await guild.fetch_member(self.buyer_id)
        role = discord.utils.get(guild.roles, name=ROLE_VIP_NAME)
        
        if role:
            await member.add_roles(role)
            # แจ้งสมาชิก
            try:
                await member.send(f"✅ การซื้อยศ **{ROLE_VIP_NAME}** ของคุณได้รับการอนุมัติแล้ว!")
            except: pass
            
            # แจ้งห้องประวัติ
            history_ch = bot.get_channel(ID_HISTORY_CHANNEL)
            embed = discord.Embed(title="🟢 ผลการตรวจสอบ: อนุมัติ", color=discord.Color.green())
            embed.add_field(name="ผู้ซื้อ", value=member.mention)
            embed.add_field(name="ยศที่ได้รับ", value=role.name)
            embed.add_field(name="ผู้อนุมัติ", value=interaction.user.mention)
            embed.timestamp = datetime.datetime.now()
            await history_ch.send(embed=embed)
            
            await interaction.response.send_message(f"อนุมัติยศให้ {member.display_name} เรียบร้อย", ephemeral=True)
            await interaction.message.delete()
        else:
            await interaction.response.send_message(f"❌ ไม่พบยศชื่อ {ROLE_VIP_NAME} ในเซิร์ฟเวอร์", ephemeral=True)

    @discord.ui.button(label="❌ ยกเลิก/ปฏิเสธ", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        # ตรวจสอบว่าเป็นแอดมินที่กำหนดหรือไม่
        if interaction.user.id != ADMIN_USER_ID:
            return await interaction.response.send_message("❌ คุณไม่มีสิทธิ์กดปุ่มนี้", ephemeral=True)

        member = await interaction.guild.fetch_member(self.buyer_id)
        
        # แจ้งสมาชิก
        try:
            await member.send(f"❌ การซื้อยศของคุณถูกปฏิเสธ กรุณาติดต่อแอดมินเพื่อตรวจสอบสลิปอีกครั้ง")
        except: pass
        
        # แจ้งห้องประวัติ
        history_ch = bot.get_channel(ID_HISTORY_CHANNEL)
        embed = discord.Embed(title="🔴 ผลการตรวจสอบ: ปฏิเสธ", color=discord.Color.red())
        embed.add_field(name="ผู้ส่งสลิป", value=member.mention)
        embed.add_field(name="ผู้ตรวจสอบ", value=interaction.user.mention)
        embed.timestamp = datetime.datetime.now()
        await history_ch.send(embed=embed)

        await interaction.response.send_message(f"ปฏิเสธรายการของ {member.display_name} เรียบร้อย", ephemeral=True)
        await interaction.message.delete()

# --- ส่วนรับข้อความสลิป ---
@bot.event
async def on_message(message):
    if message.author.bot: return

    # ตรวจสอบการส่งสลิปในห้องที่กำหนด
    if message.channel.id == ID_SLIP_CHANNEL and message.attachments:
        view = VerifyView(message.author.id)
        embed = discord.Embed(title="🧾 มีรายการแจ้งโอนใหม่", description=f"จากคุณ: {message.author.mention}", color=discord.Color.blue())
        embed.set_image(url=message.attachments[0].url) # แสดงรูปสลิปใน Embed
        
        # ส่งหาแอดมิน (หรือส่งในห้องเดิมแต่ระบุว่ารอแอดมินกด)
        await message.channel.send(content=f"🔔 <@{ADMIN_USER_ID}> ตรวจสอบสลิปด้วยครับ", embed=embed, view=view)

    # (ระบบ AI คุยต่อจากนี้...)
    c.execute("SELECT name, age, trait FROM ai_characters WHERE channel_id = ?", (message.channel.id,))
    ai_data = c.fetchone()
    if ai_data:
        # ... (โค้ด AI ส่วนเดิม) ...
        pass

    await bot.process_commands(message)
