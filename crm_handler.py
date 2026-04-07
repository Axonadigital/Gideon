"""
CRM Handler - Kopplar Gideon till Axona CRM via discord_bot edge function.

Kommunicerar med: supabase/functions/discord_bot (autentiseras via X-Bot-Secret).
"""
import aiohttp


class CRMError(Exception):
    pass


class CRMHandler:
    def __init__(self, url: str, secret: str):
        self.url = url
        self.secret = secret

    async def call_action(self, action: str, **params) -> dict:
        """Anropa en action i CRM edge function och returnera data."""
        payload = {"action": action, **params}
        headers = {
            "x-bot-secret": self.secret,
            "Content-Type": "application/json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                body = await resp.json()
                if not resp.ok or not body.get("success"):
                    raise CRMError(body.get("error", f"HTTP {resp.status}"))
                return body["data"]

    # ── Formattering ──────────────────────────────────────────────

    def format_pipeline(self, data: dict) -> str:
        lines = ["📊 **Pipeline-sammanfattning**"]
        lines.append(f"Totalt: **{data['total_deals']} deals** · {data['total_amount']:,.0f} kr\n".replace(",", " "))
        for stage, s in sorted(data["stages"].items()):
            lines.append(f"  `{stage}` → {s['count']} deals · {s['total_amount']:,.0f} kr".replace(",", " "))
        return "\n".join(lines)

    def format_weekly_report(self, data: dict) -> str:
        lines = [
            "📅 **Veckans rapport**",
            f"🏢 Nya företag: **{data['new_companies']}**",
            f"💼 Nya deals: **{data['new_deals']}** ({data['deals_total_amount']:,.0f} kr)".replace(",", " "),
            f"🏆 Deals vunna: **{data['deals_won']}**",
            f"📄 Offerter: skapade **{data['quotes_created']}** · skickade **{data['quotes_sent']}** · signerade **{data['quotes_signed']}**",
            f"📞 Samtal: **{data['calls_made']}**",
        ]
        return "\n".join(lines)

    def format_tasks(self, tasks: list) -> str:
        if not tasks:
            return "✅ Inga försenade tasks!"
        lines = [f"⚠️ **Försenade tasks ({len(tasks)} st)**"]
        for t in tasks[:15]:
            contact = t.get("contacts") or {}
            name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
            due = (t.get("due_date") or "")[:10]
            lines.append(f"  • **{t['type']}** – {t['text'][:70]} _{name}_ ({due})")
        if len(tasks) > 15:
            lines.append(f"  _…och {len(tasks) - 15} till_")
        return "\n".join(lines)

    def format_followups(self, followups: list) -> str:
        if not followups:
            return "✅ Inga försenade followups!"
        lines = [f"📞 **Försenade followups ({len(followups)} st)**"]
        for f in followups[:15]:
            company = f.get("name") or "okänt företag"
            due = (f.get("next_followup_date") or "")[:10]
            note = f.get("next_action_note") or f.get("next_action_type") or "–"
            lines.append(f"  • **{company}** – {note[:70]} ({due})")
        if len(followups) > 15:
            lines.append(f"  _…och {len(followups) - 15} till_")
        return "\n".join(lines)

    def format_performance(self, data: dict) -> str:
        lines = ["🏆 **Säljprestanda (senaste 30 dagarna)**"]
        for sp in data["salespeople"]:
            name = sp["name"] or "Okänd"
            val = (f"{sp['total_value']:,.0f} kr").replace(",", " ")
            lines.append(
                f"\n**{name}**\n"
                f"  Aktiva: {sp['active_deals']} · Vunna: {sp['won_deals']} · Förlorade: {sp['lost_deals']}\n"
                f"  Värde: {val} · Samtal: {sp['calls_last_30_days']}"
            )
        return "\n".join(lines)

    def format_ai_analysis(self, data: dict) -> str:
        a = data.get("analysis", {})
        snap = data.get("data_snapshot", {})

        score = a.get("health_score")
        bar = "🟢" if score and score >= 70 else ("🟡" if score and score >= 40 else "🔴")

        lines = [
            "🤖 **AI-säljanalys**",
            f"{bar} Säljhälsa: **{score}/100**" if score is not None else "",
            "",
            f"**Status:** {a.get('status_summary', '–')}",
            "",
        ]

        risks = a.get("top_risks", [])
        if risks:
            lines.append("**🚨 Topprisker:**")
            lines.extend(f"  • {r}" for r in risks)
            lines.append("")

        steps = a.get("next_steps", [])
        if steps:
            lines.append("**✅ Nästa steg:**")
            lines.extend(f"  {i+1}. {s}" for i, s in enumerate(steps))
            lines.append("")

        opps = a.get("opportunities", [])
        if opps:
            lines.append("**💡 Möjligheter:**")
            lines.extend(f"  • {o}" for o in opps)
            lines.append("")

        lines.append(
            f"_Pipeline: {snap.get('total_deals','–')} deals · "
            f"{snap.get('total_pipeline_value', 0):,.0f} kr · "
            f"Försenade tasks: {snap.get('overdue_tasks','–')} · "
            f"Followups: {snap.get('overdue_followups','–')}_".replace(",", " ")
        )

        return "\n".join(line for line in lines if line is not None)
