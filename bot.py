import os
import discord
from discord.ui import Button, View

# --- Configuration ---
# You will set these in Railway, not here.
BOT_TOKEN = os.environ.get('BOT_TOKEN')
REVIEWER_ROLE_ID = 1393293811286937761 # The role ID for your reviewers
TICKET_CATEGORY_ID = 0 # <-- IMPORTANT: Replace 0 with the ID of the Discord category where tickets should be created

# Set up the bot's permissions (called "intents")
intents = discord.Intents.default()
intents.message_content = True

# Create the bot object - CHANGED THIS LINE
bot = discord.Bot(intents=intents)

# --- The Button Class ---
# This defines what happens when the "Claim" button is clicked
class ClaimButtonView(View):
    def __init__(self):
        # We don't want the button to time out
        super().__init__(timeout=None) 

    @discord.ui.button(label="Claim Application", style=discord.ButtonStyle.success, custom_id="claim_button")
    async def claim_button_callback(self, interaction: discord.Interaction, button: Button):
        # When the button is clicked, this code runs.
        # interaction.user is the staff member who clicked it.
        
        # 1. Get the original embed message to find the applicant's ID
        original_embed = interaction.message.embeds[0]
        applicant_id_field = next((field for field in original_embed.fields if field.name == "**Discord ID**"), None)
        
        if not applicant_id_field:
            await interaction.response.send_message("Error: Could not find the applicant's ID in the original message.", ephemeral=True)
            return

        applicant_id = int(applicant_id_field.value)
        applicant = interaction.guild.get_member(applicant_id)
        
        # 2. Acknowledge the button press
        await interaction.response.send_message(f"Application claimed by {interaction.user.mention}. Creating ticket...", ephemeral=True)

        # 3. Create the private ticket channel
        guild = interaction.guild
        reviewer_role = guild.get_role(REVIEWER_ROLE_ID)
        category = guild.get_channel(TICKET_CATEGORY_ID)

        # Set permissions for the new channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            reviewer_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True), # The claiming staff member
        }
        # Add the applicant to the channel if they are found
        if applicant:
            overwrites[applicant] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        # Create the channel
        channel_name = f"ticket-{applicant.name if applicant else applicant_id}"
        ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)
        
        # 4. Send a welcome message in the new ticket channel
        await ticket_channel.send(f"Ticket created for <@{applicant_id}>. Claimed by {interaction.user.mention}. <@&{REVIEWER_ROLE_ID}>")

# --- Bot Events ---
@bot.event
async def on_ready():
    # This message prints in your Railway logs when the bot starts successfully
    print(f'Logged in as {bot.user}!')
    # Make sure the bot's view is persistent so buttons work after a restart
    bot.add_view(ClaimButtonView())


# --- A Test Command ---
# This slash command lets you test the system.
@bot.slash_command(name="test_application", description="Posts a test application embed.")
async def test_application(ctx, user: discord.Member):
    # This function simulates the message your Zapier workflow would post.
    # In the final version, Zapier would call your bot's API instead of you using this command.
    
    embed = discord.Embed(
        title="Whitelist Application Review",
        description="This is a test application generated for demonstration.",
        color=5793266
    )
    # Add a field with the applicant's Discord ID so the button can find it
    embed.add_field(name="**Discord ID**", value=str(user.id))
    embed.add_field(name="**Character Name**", value="Testy McTestface")
    
    # Send the message with the embed and the "Claim" button
    await ctx.respond("Test application posted.", ephemeral=True)
    await ctx.send(embed=embed, view=ClaimButtonView())

# Run the bot
bot.run(BOT_TOKEN)