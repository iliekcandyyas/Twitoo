import discord
from discord import app_commands
from discord.ext import commands
from database import Database


class Review(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = Database()

    @app_commands.command(name="review", description="View the human review queue")
    @app_commands.checks.has_permissions(administrator=True)
    async def review(self, interaction: discord.Interaction):
        queue = self.db.get_review_queue(status="pending")

        if not queue:
            await interaction.response.send_message(
                "✅ Review queue is empty.", ephemeral=True
            )
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="promote", description="Manually promote a user to human review")
    @app_commands.describe(
        user="User to escalate for review",
        evidence="What did you observe?"
    )
    @app_commands.checks.has_permissions(manage_messages=True)
    async def promote(self, interaction: discord.Interaction, user: discord.User, evidence: str):
        self.db.add_to_review(
            user_id=str(user.id),
            guild_id=str(interaction.guild_id),
            submitted_by=str(interaction.user.id),
            evidence=evidence
        )

        embed = discord.Embed(
            title="👤 Promoted to Human Review",
            description=f"{user.mention} has been added to the review queue.",
            color=discord.Color.yellow()
        )
        embed.add_field(name="Evidence", value=evidence, inline=False)
        embed.set_footer(text="A moderator will review this case shortly.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="resolve", description="Resolve a case in the review queue")
    @app_commands.describe(
        case_id="The case ID from /review",
        action="What action to take",
        notes="Optional notes"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Dismiss (false positive)", value="dismissed"),
        app_commands.Choice(name="Confirm flag (keep in DB)", value="confirmed"),
        app_commands.Choice(name="Escalate further", value="escalated"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def resolve(self, interaction: discord.Interaction, case_id: int,
                      action: app_commands.Choice[str], notes: str = "None"):
        queue = self.db.get_review_queue(status="pending")
        case = next((c for c in queue if c["id"] == case_id), None)

        if not case:
            await interaction.response.send_message(
                f"Case #{case_id} not found or already resolved.", ephemeral=True
            )
            return

        self.db.update_review_status(case_id, action.value)

        if action.value == "dismissed":
            self.db.unflag_user(case["user_id"])
            result_msg = f"🟢 Case #{case_id} dismissed. Flag removed for user `{case['user_id']}`."
        elif action.value == "confirmed":
            self.db.update_flag_status(case["user_id"], "confirmed")
            result_msg = f"🔴 Case #{case_id} confirmed. Flag locked for user `{case['user_id']}`."
        else:
            result_msg = f"🟡 Case #{case_id} escalated."

        await interaction.response.send_message(result_msg, ephemeral=True)

    @app_commands.command(name="report", description="Report a user to Guardian (available to all members)")
    @app_commands.describe(
        user="Who are you reporting?",
        reason="What did they do?"
    )
    async def report(self, interaction: discord.Interaction, user: discord.User, reason: str):
        """Anyone can report — this goes straight to the review queue, not the flag DB."""
        self.db.add_to_review(
            user_id=str(user.id),
            guild_id=str(interaction.guild_id),
            submitted_by=str(interaction.user.id),
            evidence=f"[Member report] {reason}"
        )

        await interaction.response.send_message(
            f"✅ Report submitted. A moderator will review your report for {user.mention}.",
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(Review(bot))