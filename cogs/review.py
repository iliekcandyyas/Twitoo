import discord
from discord.ext import commands
from database import Database


class Review(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @discord.slash_command(name="review", description="View the human review queue")
    @commands.has_permissions(administrator=True)
    async def review(self, ctx: discord.ApplicationContext):
        queue = self.db.get_review_queue(status="pending")

        if not queue:
            await ctx.respond("✅ Review queue is empty.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📋 Human Review Queue ({len(queue)} pending)",
            color=discord.Color.yellow()
        )

        for item in queue[:5]:
            embed.add_field(
                name=f"Case #{item['id']} — User {item['user_id']}",
                value=(
                    f"**Evidence:** {item['evidence'][:80]}\n"
                    f"**Submitted by:** <@{item['submitted_by']}>\n"
                    f"**Date:** {item['submitted_at'][:10]}\n"
                    f"Use `/resolve {item['id']} <action>` to handle"
                ),
                inline=False
            )

        if len(queue) > 5:
            embed.set_footer(text=f"Showing 5 of {len(queue)} pending cases")

        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name="promote", description="Manually promote a user to human review")
    @discord.option("user", discord.User, description="User to escalate for review")
    @discord.option("evidence", str, description="What did you observe?")
    @commands.has_permissions(manage_messages=True)
    async def promote(self, ctx: discord.ApplicationContext, user: discord.User, evidence: str):
        self.db.add_to_review(
            user_id=str(user.id),
            guild_id=str(ctx.guild_id),
            submitted_by=str(ctx.user.id),
            evidence=evidence
        )

        embed = discord.Embed(
            title="👤 Promoted to Human Review",
            description=f"{user.mention} has been added to the review queue.",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Evidence", value=evidence, inline=False)
        embed.set_footer(text="A moderator will review this case shortly.")

        await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(name="resolve", description="Resolve a case in the review queue")
    @discord.option("case_id", int, description="The case ID from /review")
    @discord.option("action", str, description="What action to take",
                    choices=["dismissed", "confirmed", "escalated"])
    @discord.option("notes", str, description="Optional notes", required=False)
    @commands.has_permissions(administrator=True)
    async def resolve(self, ctx: discord.ApplicationContext, case_id: int,
                      action: str, notes: str = "None"):
        queue = self.db.get_review_queue(status="pending")
        case = next((c for c in queue if c["id"] == case_id), None)

        if not case:
            await ctx.respond(f"Case #{case_id} not found or already resolved.", ephemeral=True)
            return

        self.db.update_review_status(case_id, action)

        if action == "dismissed":
            self.db.unflag_user(case["user_id"])
            result_msg = f"🟢 Case #{case_id} dismissed. Flag removed for user `{case['user_id']}`."
        elif action == "confirmed":
            self.db.update_flag_status(case["user_id"], "confirmed")
            result_msg = f"🔴 Case #{case_id} confirmed. Flag locked for user `{case['user_id']}`."
        else:
            result_msg = f"🟡 Case #{case_id} escalated."

        await ctx.respond(result_msg, ephemeral=True)

    @discord.slash_command(name="report", description="Report a user to Guardian (available to all members)")
    @discord.option("user", discord.User, description="Who are you reporting?")
    @discord.option("reason", str, description="What did they do?")
    async def report(self, ctx: discord.ApplicationContext, user: discord.User, reason: str):
        self.db.add_to_review(
            user_id=str(user.id),
            guild_id=str(ctx.guild_id),
            submitted_by=str(ctx.user.id),
            evidence=f"[Member report] {reason}"
        )

        await ctx.respond(
            f"✅ Report submitted. A moderator will review your report for {user.mention}.",
            ephemeral=True
        )


def setup(bot):
    bot.add_cog(Review(bot))
