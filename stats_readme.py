from __future__ import annotations

from datetime import datetime
from pathlib import Path

TABLE_HEADER = "| Saved at | Component | Node | Found | Saved | Output file | Status |"
TABLE_SEPARATOR = "| --- | --- | --- | ---: | ---: | --- | --- |"

INTRO = """# Scraping Wro stats

Auto-generated run log for scraper and processor.

## Run history
"""


def _clean(value: object) -> str:
    text = str(value) if value is not None else ""
    return text.replace("|", "/").replace("\n", " ").strip()


def _ensure_layout(path: Path) -> None:
    if not path.exists():
        path.write_text(
            f"{INTRO}{TABLE_HEADER}\n{TABLE_SEPARATOR}\n",
            encoding="utf-8",
        )
        return

    content = path.read_text(encoding="utf-8", errors="ignore")
    if TABLE_HEADER in content:
        return

    if not content.endswith("\n"):
        content += "\n"

    content += f"\n## Run history\n{TABLE_HEADER}\n{TABLE_SEPARATOR}\n"
    path.write_text(content, encoding="utf-8")


def append_run_log(
    *,
    component: str,
    found: int,
    saved: int,
    output_file: str,
    status: str,
    node: str = "-",
    saved_at: datetime | None = None,
    readme_path: str = "readme.md",
) -> None:
    path = Path(readme_path)
    _ensure_layout(path)

    stamp = (saved_at or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    row = (
        f"| {_clean(stamp)} | {_clean(component)} | {_clean(node)} | "
        f"{_clean(found)} | {_clean(saved)} | {_clean(output_file)} | {_clean(status)} |\n"
    )

    with path.open("a", encoding="utf-8") as handle:
        handle.write(row)
