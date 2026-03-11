import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

COGS = [
    "cogs.moderation",
    "cogs.review",
]

@bot.command()
async def sync(ctx):
    if await bot.is_owner(ctx.author):
        await bot.tree.sync()
        await ctx.send("Commands synced globally!")
    else:
        await ctx.send("You must be daddy to use this command.")

@bot.event
async def on_ready():
    print(f"Guardian is online as {bot.user}")
    print(f"Watching {len(bot.guilds)} server(s)")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.event
async def on_member_join(member: discord.Member):
    """Check new members against the flag database on join."""
    from database import Database
    from ai_analysis import get_risk_score

    db = Database()
    flag = db.get_flag(str(member.id))

    if flag:
        channel = discord.utils.get(member.guild.text_channels, name="guardian-alerts")
        if channel:
            embed = discord.Embed(
                title="⚠️ Flagged User Joined",
                color=discord.Color.red()
            )
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
                await bot.load_extension(cog)
                print(f"Loaded: {cog}")
            except Exception as e:
                print(f"Failed to load {cog}: {e}")
        await bot.start(os.getenv("DISCORD_TOKEN"))

if __name__ == "__main__":
    asyncio.run(main())