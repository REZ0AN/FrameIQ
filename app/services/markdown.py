from collections.abc import Sequence

import mistune

from app.models.analysis import BatchSynthesis, EvidencePoint, ResearchReport


class MarkdownRenderer:
    def __init__(self) -> None:
        self._markdown = mistune.create_markdown(
            escape=True,
            plugins=["strikethrough", "table", "task_lists"],
        )

    def render(self, markdown_text: str) -> str:
        return str(self._markdown(markdown_text))

    def from_report(
        self,
        report: ResearchReport | None,
        source: str,
        error: str | None,
    ) -> str:
        if report is None:
            lines = ["# Research canvas", "", f"Source: {source}"]
            if error:
                lines.extend(["", "## Run error", "", error])
            return "\n".join(lines)

        lines = ["# Research canvas"]
        if report.batch_synthesis:
            _append_synthesis(lines, report.batch_synthesis)
        for video in report.videos:
            lines.extend(
                [
                    "",
                    f"## {video.title}",
                    "",
                    f"Video ID: `{video.video_id}`",
                    "",
                    video.executive_summary,
                ]
            )
            _append_list(lines, "Key takeaways", video.key_takeaways)
            _append_evidence(lines, "Highlights", video.highlights)
            _append_list(lines, "Discussion themes", video.discussion_themes)
            _append_list(lines, "Likely impacts", video.impacts)
            _append_list(lines, "Strengths", video.strengths)
            _append_list(lines, "Weaknesses", video.weaknesses)
            lines.extend(["", "### Reasoning assessment", "", video.reasoning.overall])
            _append_evidence(lines, "Claims", video.reasoning.claims, level=4)
            _append_list(lines, "Assumptions", video.reasoning.assumptions, level=4)
            _append_list(lines, "Logical gaps", video.reasoning.logical_gaps, level=4)
        return "\n".join(lines)


def _append_synthesis(lines: list[str], synthesis: BatchSynthesis) -> None:
    lines.extend(["", "## Combined perspective", "", synthesis.executive_summary])
    _append_list(lines, "Common ground", synthesis.common_ground)
    _append_list(lines, "Disagreements", synthesis.disagreements)
    _append_list(lines, "Unique contributions", synthesis.unique_contributions)
    _append_list(lines, "Combined implications", synthesis.combined_implications)
    _append_list(lines, "Questions to pursue", synthesis.follow_up_questions)


def _append_list(
    lines: list[str],
    heading: str,
    values: Sequence[str],
    level: int = 3,
) -> None:
    lines.extend(["", f"{'#' * level} {heading}", ""])
    lines.extend(f"- {value}" for value in values)
    if not values:
        lines.append("- None identified.")


def _append_evidence(
    lines: list[str],
    heading: str,
    values: Sequence[EvidencePoint],
    level: int = 3,
) -> None:
    lines.extend(["", f"{'#' * level} {heading}", ""])
    for value in values:
        timestamp = f" `{value.timestamp}`" if value.timestamp else ""
        lines.append(f"- **{value.statement}**{timestamp} — {value.evidence}")
    if not values:
        lines.append("- None identified.")
