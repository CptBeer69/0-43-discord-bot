import os
import discord
from discord.ui import Button, View
from flask import Flask, request, jsonify
import threading

# --- Discord Bot Configuration ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
REVIEWER_ROLE_ID = 1393293811286937761
TICKET_CATEGORY_ID = 1393576700352401460
APP_LOG_CHANNEL_ID = 1393288154986975263

# Set up the bot's permissions (called "intents")
intents = discord.Intents.default()
intents.members = True # This is a privileged intent
bot = discord.Bot(intents=intents)

# --- Flask Web Server Setup ---
# This creates the API endpoint for Zapier
app = Flask(__name__)

@app.route('/new_application', methods=['POST'])
def new_application():
    data = request.json
    print(f"[FLASK] Received data from Zapier: {data}")
    # We pass the data to the bot to handle the Discord message
    bot.loop.create_task(post_application_message(data))
    return jsonify({"status": "success", "message": "Data received"}), 200

async def post_application_message(data):
    """This function builds and sends the final, detailed embed message."""
    print("[BOT] post_application_message function started.")
    channel = bot.get_channel(APP_LOG_CHANNEL_ID)
    if not channel:
        print(f"[ERROR] Could not find APP_LOG_CHANNEL_ID: {APP_LOG_CHANNEL_ID}")
        return

    # --- Get all the data from the JSON payload sent by Zapier ---
    user_id = data.get('user_id')
    summary = data.get('ai_summary', 'N/A')
    decision = data.get('ai_decision', 'N/A')
    context = data.get('ai_context', 'N/A')
    red_flags = data.get('ai_red_flags', 'N/A')
    char_name = data.get('char_name', 'N/A')
    real_age = data.get('real_age', 'N/A')
    steam_link = data.get('steam_link', 'N/A')
    sheet_row = data.get('sheet_row', '')
    avatar = data.get('avatar_url')

    # Construct the direct link to the spreadsheet row
    application_link = f"https://docs.google.com/spreadsheets/d/1h-EZmoI_SYzkwhLEoE3yB6hZd6mfvW7mZh6FDfYpdJA/edit?range=A{sheet_row}"

    # --- Build the final embed object to match your desired layout ---
    embed = discord.Embed(
        title="Whitelist Application Review",
        color=5793266
    )
    embed.set_thumbnail(url=avatar)
    
    # Adding all the detailed fields
    embed.add_field(name="**AI Whitelister Summary**", value=summary, inline=False)
    embed.add_field(name="**AI Whitelister Decision**", value=decision, inline=False)
    embed.add_field(name="**AI Whitelister Context**", value=context, inline=False)
    embed.add_field(name="**AI Whitelister Red Flags**", value=red_flags, inline=False)
    embed.add_field(name="--- Application Details ---", value="\u200b", inline=False)
    embed.add_field(name="**Character Name**", value=char_name, inline=True)
    embed.add_field(name="**Real Age**", value=real_age, inline=True)
    embed.add_field(name="**Discord ID**", value=str(user_id), inline=False) # This field is required for the button to work
    embed.add_field(name="**Steam Account Link**", value=steam_link, inline=False)
    embed.add_field(name="**Application Link**", value=f"[Click here to view Row {sheet_row}]({application_link})", inline=False)

    # The main message content with the pings
    content_message = f"New application from <@{user_id}>. Review required: <@&{REVIEWER_ROLE_ID}>"
    
    try:
        # Send the message with the pings, the embed, and the Claim button
        await channel.send(content=content_message, embed=embed, view=ClaimButtonView())
        print("[BOT] Successfully sent final application message to Discord.")
    except Exception as e:
        print(f"[ERROR] Failed to send final message to Discord: {e}")

# --- The "Claim" Button Logic ---
class ClaimButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Application", style=discord.ButtonStyle.success, custom_id="claim_button_final_v4")
    async def claim_button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        print(f"[BUTTON] Claim button pressed by: {interaction.user.name}")
        await interaction.response.defer(ephemeral=True) # Acknowledge the click privately
        
        log_channel = bot.get_channel(APP_LOG_CHANNEL_ID)

        try:
            original_embed = interaction.message.embeds[0]
            applicant_id_field = next((field for field in original_embed.fields if field.name == "**Discord ID**"), None)
            
            if not applicant_id_field:
                await interaction.followup.send("Error: Could not find Discord ID in the message.", ephemeral=True)
                return

            applicant_id = int(applicant_id_field.value)
            applicant = await interaction.guild.fetch_member(applicant_id)

            guild = interaction.guild
            reviewer_role = guild.get_role(REVIEWER_ROLE_ID)
            category = guild.get_channel(TICKET_CATEGORY_ID)
            
            if not category:
                print(f"[ERROR] Could not find TICKET_CATEGORY_ID: {TICKET_CATEGORY_ID}")
                await interaction.followup.send("Error: Ticket category not found. Please check configuration.", ephemeral=True)
                return

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                reviewer_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            if applicant:
                overwrites[applicant] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            channel_name = f"ticket-{applicant.name}" if applicant else f"ticket-id-{applicant_id}"
            ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)
            
            await ticket_channel.send(f"Ticket created for <@{applicant_id}> by {interaction.user.mention}. <@&{REVIEWER_ROLE_ID}>", embed=original_embed)
            await interaction.message.delete()
            print("[BOT] Successfully created ticket and deleted original message.")
            await interaction.followup.send(f"Success! Ticket created: {ticket_channel.mention}", ephemeral=True)

        except Exception as e:
            print(f"[ERROR] An exception occurred during ticket creation: {e}")
            error_embed = discord.Embed(
                title="Button Interaction Failed - Detailed Error",
                description=f"An error occurred when `{interaction.user.name}` tried to claim a ticket.",
                color=15158332
            )
            error_embed.add_field(name="Error Details", value=f"```\n{e}\n```")
            if log_channel:
                await log_channel.send(embed=error_embed)
            await interaction.followup.send("An unexpected error occurred. The details have been logged.", ephemeral=True)

# --- Bot Start-up Logic ---
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}!')
    bot.add_view(ClaimButtonView())

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# Start Flask in a separate thread and then run the bot
flask_thread = threading.Thread(target=run_flask)
flask_thread.start()
bot.run(BOT_TOKEN)