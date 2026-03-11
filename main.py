import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Bot(intents=intents)

COGS = [
    "cogs.moderation",
    "cogs.review",
]

@bot.event
async def on_ready():
    print(f"Guardian is online as {bot.user}")
    print(f"Watching {len(bot.guilds)} server(s)")

@bot.event
async def on_member_join(member: discord.Member):
    from database import Database

    db = Database()
    flag = db.get_flag(str(member.id))

    if flag:
        channel = discord.utils.get(member.guild.text_channels, name="guardian-alerts")
        if channel:
            embed = discord.Embed(title="⚠️ Flagged User Joined", color=discord.Color.red())
            embed.add_field(name="User", value=f"{member.mention} (`{member.id}`)", inline=False)
            embed.add_field(name="Flag Reason", value=flag["reason"], inline=False)
            embed.add_field(name="Confidence Score", value=f"{flag['confidence']}/10", inline=False)
            embed.add_field(name="Reported By", value=f"Server ID: {flag['reported_by_guild']}", inline=False)
            embed.set_footer(text="Use /review to take action")
            await channel.send(embed=embed)

async def main():
    async with bot:
        for cog in COGS:
            try:
                bot.load_extension(cog)
                print(f"Loaded: {cog}")
            except Exception as e:
                print(f"Failed to load {cog}: {e}")
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())
