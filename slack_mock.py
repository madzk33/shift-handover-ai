"""Formatters for Slack-style and Markdown handover output."""

from schema import EquipmentStatus, Handover, Severity

SEVERITY_EMOJI = {
    Severity.high: "🔴",
    Severity.medium: "🟡",
    Severity.low: "🟢",
}

EQUIPMENT_EMOJI = {
    EquipmentStatus.ok: "✅",
    EquipmentStatus.degraded: "⚠️",
    EquipmentStatus.down: "🛑",
}


def format_for_slack(handover: Handover) -> str:
    """Produce a Slack-style formatted string with emoji severity indicators.

    Args:
        handover: Validated Handover instance.

    Returns:
        Slack-ready plain text with emoji and section headers.
    """
    lines: list[str] = []

    lines.append(f"📋 *Shift Handover — {handover.shift_date} ({handover.shift_type} Shift)*")
    lines.append(f"👤 Operative: {handover.operative}  |  📍 {handover.line_or_area}")
    lines.append("")
    lines.append(f"*Summary:* {handover.summary}")
    lines.append("")

    if handover.issues_raised:
        lines.append("*🚨 Issues Raised*")
        for issue in handover.issues_raised:
            emoji = SEVERITY_EMOJI[issue.severity]
            lines.append(f"  {emoji} [{issue.severity.value.upper()}] {issue.description}")
            lines.append(f"      ↳ Action: {issue.action_needed}")
        lines.append("")

    if handover.pending_items:
        lines.append("*📌 Pending Items*")
        for item in handover.pending_items:
            lines.append(f"  • {item.item}")
            lines.append(f"      Owner: {item.owner_next_shift}  |  Deadline: {item.deadline}")
        lines.append("")

    if handover.equipment_status:
        lines.append("*🔧 Equipment Status*")
        for eq in handover.equipment_status:
            emoji = EQUIPMENT_EMOJI[eq.status]
            lines.append(f"  {emoji} {eq.equipment} — {eq.status.value.upper()}: {eq.notes}")
        lines.append("")

    if handover.stock_or_ingredient_notes:
        lines.append("*📦 Stock / Ingredients*")
        for note in handover.stock_or_ingredient_notes:
            lines.append(f"  • {note}")
        lines.append("")

    if handover.safety_or_compliance_flags:
        lines.append("*⚠️ Safety / Compliance Flags*")
        for flag in handover.safety_or_compliance_flags:
            lines.append(f"  • {flag}")
        lines.append("")

    if handover.next_shift_priorities:
        lines.append("*🎯 Next Shift Priorities*")
        for i, priority in enumerate(handover.next_shift_priorities, 1):
            lines.append(f"  {i}. {priority}")
        lines.append("")

    return "\n".join(lines).rstrip()


def format_as_markdown(handover: Handover) -> str:
    """Produce a clean Markdown handover document suitable for export.

    Args:
        handover: Validated Handover instance.

    Returns:
        Markdown string.
    """
    lines: list[str] = []

    lines.append(f"# Shift Handover — {handover.shift_date}")
    lines.append("")
    lines.append(f"| Field | Value |")
    lines.append(f"|-------|-------|")
    lines.append(f"| **Shift** | {handover.shift_type} |")
    lines.append(f"| **Operative** | {handover.operative} |")
    lines.append(f"| **Line / Area** | {handover.line_or_area} |")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(handover.summary)
    lines.append("")

    if handover.issues_raised:
        lines.append("## Issues Raised")
        lines.append("")
        lines.append("| Severity | Description | Action Needed |")
        lines.append("|----------|-------------|---------------|")
        for issue in handover.issues_raised:
            emoji = SEVERITY_EMOJI[issue.severity]
            lines.append(
                f"| {emoji} {issue.severity.value.upper()} | {issue.description} | {issue.action_needed} |"
            )
        lines.append("")

    if handover.pending_items:
        lines.append("## Pending Items")
        lines.append("")
        lines.append("| Item | Owner (Next Shift) | Deadline |")
        lines.append("|------|--------------------|----------|")
        for item in handover.pending_items:
            lines.append(f"| {item.item} | {item.owner_next_shift} | {item.deadline} |")
        lines.append("")

    if handover.equipment_status:
        lines.append("## Equipment Status")
        lines.append("")
        lines.append("| Equipment | Status | Notes |")
        lines.append("|-----------|--------|-------|")
        for eq in handover.equipment_status:
            emoji = EQUIPMENT_EMOJI[eq.status]
            lines.append(f"| {eq.equipment} | {emoji} {eq.status.value.upper()} | {eq.notes} |")
        lines.append("")

    if handover.stock_or_ingredient_notes:
        lines.append("## Stock / Ingredient Notes")
        lines.append("")
        for note in handover.stock_or_ingredient_notes:
            lines.append(f"- {note}")
        lines.append("")

    if handover.safety_or_compliance_flags:
        lines.append("## Safety / Compliance Flags")
        lines.append("")
        for flag in handover.safety_or_compliance_flags:
            lines.append(f"- ⚠️ {flag}")
        lines.append("")

    if handover.next_shift_priorities:
        lines.append("## Next Shift Priorities")
        lines.append("")
        for i, priority in enumerate(handover.next_shift_priorities, 1):
            lines.append(f"{i}. {priority}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by Shift Handover AI*")

    return "\n".join(lines)
