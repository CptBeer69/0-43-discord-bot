import os
import discord
from discord.ui import Button, View
from flask import Flask, request, jsonify
import threading

# --- Discord Bot Configuration ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
# REVIEWER_ROLE_ID is no longer needed for channel creation but can be kept for other uses if you want
REVIEWER_ROLE_ID = 1393293811286937761 
TICKET_CATEGORY_ID = 1393576700352401460
APP_LOG_CHANNEL_ID = 1393288154986975263

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

# --- Flask Web Server Setup ---
app = Flask(__name__)

@app.route('/new_application', methods=['POST'])
def new_application():
    data = request.json
    bot.loop.create_task(post_application_message(data))
    return jsonify({"status": "success", "message": "Data received"}), 200

async def post_application_message(data):
    channel = bot.get_channel(APP_LOG_CHANNEL_ID)
    if not channel:
        print(f"Error: Could not find channel with ID {APP_LOG_CHANNEL_ID}")
        return
    
    embed = discord.Embed(
        title="Whitelist Application Review",
        color=5793266
    )
    embed.add_field(name="**AI Whitelister Summary**", value=f"**Decision:** {data.get('decision', 'N/A')}\n{data.get('summary', 'N/A')}", inline=False)
    embed.add_field(name="**Character Name**", value=data.get('char_name', 'N/A'), inline=True)
    embed.add_field(name="**Discord ID**", value=str(data.get('user_id', 'N/A')), inline=True)
    
    await channel.send(embed=embed, view=ClaimButtonView())

# --- The "Claim" Button Logic ---
class ClaimButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Application", style=discord.ButtonStyle.success, custom_id="claim_button_v4")
    async def claim_button_callback(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message(f"Claimed by {interaction.user.mention}. Creating ticket...", ephemeral=True)
        
        original_embed = interaction.message.embeds[0]
        applicant_id_field = next((field for field in original_embed.fields if field.name == "**Discord ID**"), None)
        
        if not applicant_id_field:
            return

        applicant_id = int(applicant_id_field.value)
        applicant = interaction.guild.get_member(applicant_id)

        guild = interaction.guild
        category = guild.get_channel(TICKET_CATEGORY_ID)
        
        # --- PERMISSIONS CHANGED HERE ---
        # The reviewer_role is no longer added automatically
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if applicant:
            overwrites[applicant] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        ticket_channel = await guild.create_text_channel(f"ticket-{applicant.name if applicant else applicant_id}", overwrites=overwrites, category=category)
        
        # --- MESSAGE CHANGED HERE ---
        # The reviewer_role ping has been removed
        await ticket_channel.send(f"Ticket created for <@{applicant_id}>. Claimed by {interaction.user.mention}.", embed=original_embed)
        
        await interaction.message.delete()

# --- Bot Start-up Logic ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    bot.add_view(ClaimButtonView())

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

flask_thread = threading.Thread(target=run_flask)
flask_thread.start()
bot.run(BOT_TOKEN)