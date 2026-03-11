import discord
from discord.ext import commands
from database import Database
from ai_analysis import get_risk_score
from datetime import datetime, timezone


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @discord.slash_command(name="flag", description="Flag a user as suspicious across all Guardian servers")
    @discord.option("user", discord.User, description="The user to flag")
    @discord.option("reason", str, description="Why are you flagging this user?")
    @discord.option("evidence", str, description="Any message content, links, or context (optional)", required=False)
    @commands.has_permissions(manage_messages=True)
    async def flag(self, ctx: discord.ApplicationContext, user: discord.User,
                   reason: str, evidence: str = "None provided"):
        await ctx.defer(ephemeral=True)

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

        self.db.flag_user(
            user_id=str(user.id),
            reason=reason,
            confidence=score,
            reported_by_guild=str(ctx.guild_id),
            reported_by_user=str(ctx.user.id)
        )

        if score >= 7:
            self.db.add_to_review(
                user_id=str(user.id),
                guild_id=str(ctx.guild_id),
                submitted_by=str(ctx.user.id),
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

        await ctx.followup.send(embed=embed, ephemeral=True)

    @discord.slash_command(name="check", description="Check if a user is flagged in the Guardian database")
    @discord.option("user", discord.User, description="The user to check")
    async def check(self, ctx: discord.ApplicationContext, user: discord.User):
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

        await ctx.respond(embed=embed)

    @discord.slash_command(name="unflag", description="Remove a flag from a user")
    @discord.option("user", discord.User, description="The user to unflag")
    @commands.has_permissions(administrator=True)
    async def unflag(self, ctx: discord.ApplicationContext, user: discord.User):
        flag = self.db.get_flag(str(user.id))
        if not flag:
            await ctx.respond(f"{user.mention} is not flagged.", ephemeral=True)
            return

        self.db.unflag_user(str(user.id))
        await ctx.respond(f"✅ Removed flag for {user.mention}.", ephemeral=True)

    @discord.slash_command(name="flaglist", description="View all flagged users in the database")
    @commands.has_permissions(administrator=True)
    async def flaglist(self, ctx: discord.ApplicationContext):
        flags = self.db.get_all_flags()
        if not flags:
            await ctx.respond("No flagged users.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🚩 Flagged Users ({len(flags)} total)",
            color=discord.Color.red()
        )
        for f in flags[:10]:
            embed.add_field(
                name=f"ID: {f['user_id']}",
                value=f"Score: {f['confidence']}/10 | {f['reason'][:50]}",
                inline=False
            )
        if len(flags) > 10:
            embed.set_footer(text=f"Showing 10 of {len(flags)} flags")

        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name="setup", description="Set the Guardian alert channel for this server")
    @discord.option("channel", discord.TextChannel, description="Channel to send Guardian alerts to")
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        self.db.set_alert_channel(str(ctx.guild_id), channel.name)
        await ctx.respond(f"✅ Guardian alerts will be sent to {channel.mention}", ephemeral=True)


def setup(bot):
    bot.add_cog(Moderation(bot))
