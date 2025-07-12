import os
import discord
from discord.ui import Button, View
from flask import Flask, request, jsonify
import threading

# --- Discord Bot Configuration ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
REVIEWER_ROLE_ID = 1393293811286937761
TICKET_CATEGORY_ID = 1393576700352401460  # <-- IMPORTANT: Replace 0 with your Ticket Category ID
APP_LOG_CHANNEL_ID = 1393288154986975263  # <-- IMPORTANT: Replace 0 with your Application Log Channel ID

intents = discord.Intents.default()
bot = discord.Bot(intents=intents)

# --- Flask Web Server Setup ---
# This creates the API endpoint for Zapier
app = Flask(__name__)

@app.route('/new_application', methods=['POST'])
def new_application():
    # This function runs when Zapier sends data to your bot's URL
    data = request.json
    bot.loop.create_task(post_application_message(data))
    return jsonify({"status": "success", "message": "Data received"}), 200

async def post_application_message(data):
    # This coroutine posts the actual message in Discord
    channel = bot.get_channel(APP_LOG_CHANNEL_ID)
    if not channel:
        print(f"Error: Could not find channel with ID {APP_LOG_CHANNEL_ID}")
        return

    # Build the embed from the data sent by Zapier
    embed = discord.Embed(
        title="Whitelist Application Review",
        color=5793266
    )
    # Add all the fields from our previous script...
    embed.add_field(name="**AI Whitelister Summary**", value=data.get('summary', 'N/A'), inline=False)
    embed.add_field(name="**AI Whitelister Decision**", value=data.get('decision', 'N/A'), inline=False)
    # ... and so on for all your other fields ...
    embed.add_field(name="**Character Name**", value=data.get('char_name', 'N/A'))
    embed.add_field(name="**Discord ID**", value=str(data.get('user_id', 'N/A'))) # Store the user_id here

    # Send the message with the Claim button
    await channel.send(embed=embed, view=ClaimButtonView())

# --- The "Claim" Button Logic ---
class ClaimButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Application", style=discord.ButtonStyle.success, custom_id="claim_button_v2")
    async def claim_button_callback(self, interaction: discord.Interaction, button: Button):
        # 1. Acknowledge the claim
        await interaction.response.send_message(f"Claimed by {interaction.user.mention}. Creating ticket...", ephemeral=True)

        # 2. Get info from the original embed
        original_embed = interaction.message.embeds[0]
        applicant_id_field = next((field for field in original_embed.fields if field.name == "**Discord ID**"), None)
        applicant_id = int(applicant_id_field.value)
        applicant = interaction.guild.get_member(applicant_id)

        # 3. Create the private ticket channel
        guild = interaction.guild
        reviewer_role = guild.get_role(REVIEWER_ROLE_ID)
        category = guild.get_channel(TICKET_CATEGORY_ID)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            reviewer_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if applicant:
            overwrites[applicant] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_channel = await guild.create_text_channel(f"ticket-{applicant.name if applicant else applicant_id}", overwrites=overwrites, category=category)

        # 4. Copy the embed content to the new channel
        await ticket_channel.send(f"Ticket created for <@{applicant_id}> by {interaction.user.mention}. <@&{REVIEWER_ROLE_ID}>", embed=original_embed)

        # 5. Delete the original message from the log channel
        await interaction.message.delete()

# --- Bot Start-up Logic ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    bot.add_view(ClaimButtonView())

def run_flask():
    # This runs the Flask web server
    # Note: Railway provides the PORT environment variable.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# Start Flask in a separate thread and then run the bot
flask_thread = threading.Thread(target=run_flask)
flask_thread.start()
bot.run(BOT_TOKEN)