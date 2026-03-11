import discord
from discord import app_commands
from discord.ext import commands
from database import Database
from ai_analysis import get_risk_score
from datetime import datetime, timezone


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(name="flag", description="Flag a user as suspicious across all Guardian servers")
    @app_commands.describe(
        user="The user to flag",
        reason="Why are you flagging this user?",
        evidence="Any message content, links, or context (optional)"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def flag(self, interaction: discord.Interaction, user: discord.User,
                   reason: str, evidence: str = "None provided"):
        await interaction.response.defer(ephemeral=True)

        # Build signal profile for AI
        account_age = (datetime.now(timezone.utc) - user.created_at).days
        signals = {
            "username": str(user),
            "account_age_days": account_age,
            "has_avatar": user.avatar is not None,
            "reported_reason": reason,
            "evidence": evidence
        }

        risk = await get_risk_score(signals)
        score = risk.get("score", 5)
        summary = risk.get("summary", "No summary available.")
        action = risk.get("recommended_action", "review")

        # Save to database
        self.db.flag_user(
            user_id=str(user.id),
            reason=reason,
            confidence=score,
            reported_by_guild=str(interaction.guild_id),
            reported_by_user=str(interaction.user.id)
        )

        # If score is high enough, also add to review queue
        if score >= 7:
            self.db.add_to_review(
                user_id=str(user.id),
                guild_id=str(interaction.guild_id),
                submitted_by=str(interaction.user.id),
                evidence=f"{reason} | {evidence}"
            )

        embed = discord.Embed(
            title="🚩 User Flagged",
            color=discord.Color.orange() if score < 8 else discord.Color.red()
        )
        embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="AI Risk Score", value=f"{score}/10", inline=True)
        embed.add_field(name="Recommended Action", value=action.upper(), inline=True)
        embed.add_field(name="AI Summary", value=summary, inline=False)

        if score >= 7:
            embed.set_footer(text="⚡ Added to human review queue due to high risk score")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="check", description="Check if a user is flagged in the Guardian database")
    @app_commands.describe(user="The user to check")
    async def check(self, interaction: discord.Interaction, user: discord.User):
        flag = self.db.get_flag(str(user.id))

        if not flag:
            embed = discord.Embed(
                title="✅ User Not Flagged",
                description=f"{user.mention} has no flags in the Guardian database.",
                color=discord.Color.green()
            )
        else:
            color = discord.Color.red() if flag["confidence"] >= 7 else discord.Color.orange()
            embed = discord.Embed(title="⚠️ Flagged User", color=color)
            embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=False)
            embed.add_field(name="Reason", value=flag["reason"], inline=False)
            embed.add_field(name="Confidence Score", value=f"{flag['confidence']}/10", inline=True)
            embed.add_field(name="Status", value=flag["status"].upper(), inline=True)
            embed.add_field(name="Flagged At", value=flag["flagged_at"][:10], inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="unflag", description="Remove a flag from a user")
    @app_commands.describe(user="The user to unflag")
    @app_commands.checks.has_permissions(administrator=True)
    async def unflag(self, interaction: discord.Interaction, user: discord.User):
        flag = self.db.get_flag(str(user.id))
        if not flag:
            await interaction.response.send_message(
                f"{user.mention} is not flagged.", ephemeral=True
            )
            return

        self.db.unflag_user(str(user.id))
        await interaction.response.send_message(
            f"✅ Removed flag for {user.mention}.", ephemeral=True
        )

    @app_commands.command(name="flaglist", description="View all flagged users in the database")
    @app_commands.checks.has_permissions(administrator=True)
    async def flaglist(self, interaction: discord.Interaction):
        flags = self.db.get_all_flags()
        if not flags:
            await interaction.response.send_message("No flagged users.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🚩 Flagged Users ({len(flags)} total)",
            color=discord.Color.red()
        )

        for f in flags[:10]:  # Show top 10
            embed.add_field(
                name=f"ID: {f['user_id']}",
                value=f"Score: {f['confidence']}/10 | {f['reason'][:50]}",
                inline=False
            )

        if len(flags) > 10:
            embed.set_footer(text=f"Showing 10 of {len(flags)} flags")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="setup", description="Set the Guardian alert channel for this server")
    @app_commands.describe(channel="Channel to send Guardian alerts to")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel):
        self.db.set_alert_channel(str(interaction.guild_id), channel.name)
        await interaction.response.send_message(
            f"✅ Guardian alerts will be sent to {channel.mention}", ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Moderation(bot))