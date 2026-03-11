import os
from groq import Groq

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT = """You are a threat analysis AI for a Discord moderation bot called Guardian.
Your job is to analyze user behavior signals and assign a risk score from 1-10.

Scoring guide:
1-3: Low risk, likely safe
4-6: Moderate risk, worth watching
7-8: High risk, recommend human review
9-10: Critical risk, recommend immediate action

You must respond in this exact JSON format (no markdown, no explanation):
{
  "score": <integer 1-10>,
  "summary": "<one sentence reason>",
  "recommended_action": "<none|alert|review|kick|ban>"
}"""

async def get_risk_score(signals: dict) -> dict:
    """
    Analyze behavioral signals and return a risk score.
    
    signals dict can include:
    - username: str
    - account_age_days: int
    - has_avatar: bool
    - message_sample: str (recent messages, optional)
    - join_pattern: str (e.g. "joined 5 servers in 1 day")
    - reported_reason: str
    """
    signal_text = "\n".join([f"- {k}: {v}" for k, v in signals.items()])
    
    prompt = f"""Analyze this Discord user's risk profile based on the following signals:

{signal_text}

Respond with a JSON risk assessment."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=200
        )
        
        import json
        content = response.choices[0].message.content.strip()
        return json.loads(content)
    
    except Exception as e:
        print(f"AI analysis error: {e}")
        return {
            "score": 5,
            "summary": "AI analysis unavailable, defaulting to manual review.",
            "recommended_action": "review"
        }


async def analyze_message(message: str) -> dict:
    """
    Scan a message for red flags.
    Returns a risk dict same format as get_risk_score.
    """
    prompt = f"""Analyze this Discord message for harmful content, illegal material promotion, or suspicious behavior:

Message: "{message}"

Respond with a JSON risk assessment."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=200
        )

        import json
        content = response.choices[0].message.content.strip()
        return json.loads(content)

    except Exception as e:
        print(f"Message analysis error: {e}")
        return {
            "score": 5,
            "summary": "AI analysis unavailable.",
            "recommended_action": "review"
        }