from __future__ import annotations

from datetime import datetime
from pathlib import Path

SCRAPER_SECTION = "## Scraper run history"
PROCESSOR_SECTION = "## Processor run history"

SCRAPER_HEADER = "| Saved at | Found | Saved | Output file | Status |"
SCRAPER_SEPARATOR = "| --- | ---: | ---: | --- | --- |"

PROCESSOR_HEADER = "| Saved at | Node | Found | Saved | Output file | Status |"
PROCESSOR_SEPARATOR = "| --- | --- | ---: | ---: | --- | --- |"

LEGACY_HEADER = "| Saved at | Component | Node | Found | Saved | Output file | Status |"

INTRO = """# Scraping Wro stats

Auto-generated run logs for scraper and processor.
"""


def _clean(value: object) -> str:
    text = str(value) if value is not None else ""
    return text.replace("|", "/").replace("\n", " ").strip()


def _default_layout() -> str:
    return (
        f"{INTRO}\n"
        f"{SCRAPER_SECTION}\n"
        f"{SCRAPER_HEADER}\n"
        f"{SCRAPER_SEPARATOR}\n\n"
        f"{PROCESSOR_SECTION}\n"
        f"{PROCESSOR_HEADER}\n"
        f"{PROCESSOR_SEPARATOR}\n"
    )


def _legacy_to_sections(content: str) -> str | None:
    if LEGACY_HEADER not in content:
        return None

    scraper_rows: list[str] = []
    processor_rows: list[str] = []

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        if line in {LEGACY_HEADER, "| --- | --- | --- | ---: | ---: | --- | --- |"}:
            continue

        parts = [part.strip() for part in line.split("|")[1:-1]]
        if len(parts) != 7:
            continue

        stamp, component, node, found, saved, output_file, status = parts
        component_key = component.lower()

        if component_key == "processor":
            processor_rows.append(
                f"| {_clean(stamp)} | {_clean(node)} | {_clean(found)} | "
                f"{_clean(saved)} | {_clean(output_file)} | {_clean(status)} |"
            )
        elif component_key == "scraper":
            scraper_rows.append(
                f"| {_clean(stamp)} | {_clean(found)} | {_clean(saved)} | "
                f"{_clean(output_file)} | {_clean(status)} |"
            )

    scraper_block = "\n".join(scraper_rows)
    processor_block = "\n".join(processor_rows)
    if scraper_block:
        scraper_block = f"{scraper_block}\n"
    if processor_block:
        processor_block = f"{processor_block}\n"

    return (
        f"{INTRO}\n"
        f"{SCRAPER_SECTION}\n"
        f"{SCRAPER_HEADER}\n"
        f"{SCRAPER_SEPARATOR}\n"
        f"{scraper_block}\n"
        f"{PROCESSOR_SECTION}\n"
        f"{PROCESSOR_HEADER}\n"
        f"{PROCESSOR_SEPARATOR}\n"
        f"{processor_block}"
    )


def _ensure_layout(path: Path) -> None:
    if not path.exists():
        path.write_text(_default_layout(), encoding="utf-8")
        return

    content = path.read_text(encoding="utf-8", errors="ignore")
    if (
        SCRAPER_SECTION in content
        and PROCESSOR_SECTION in content
        and SCRAPER_HEADER in content
        and PROCESSOR_HEADER in content
    ):
        return

    migrated = _legacy_to_sections(content)
    if migrated is not None:
        path.write_text(migrated, encoding="utf-8")
        return

    extra_blocks: list[str] = []
    if SCRAPER_SECTION not in content:
        extra_blocks.append(f"{SCRAPER_SECTION}\n{SCRAPER_HEADER}\n{SCRAPER_SEPARATOR}")
    if PROCESSOR_SECTION not in content:
        extra_blocks.append(f"{PROCESSOR_SECTION}\n{PROCESSOR_HEADER}\n{PROCESSOR_SEPARATOR}")

    if extra_blocks:
        suffix = "\n\n".join(extra_blocks) + "\n"
        content = content.rstrip() + "\n\n" + suffix
        path.write_text(content, encoding="utf-8")


def _append_row_to_section(path: Path, section_name: str, row: str) -> None:
    content = path.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()

    section_index = None
    for index, line in enumerate(lines):
        if line.strip() == section_name:
            section_index = index
            break

    if section_index is None:
        raise RuntimeError(f"Section not found: {section_name}")

    next_section_index = len(lines)
    for index in range(section_index + 1, len(lines)):
        if lines[index].startswith("## "):
            next_section_index = index
            break

    insert_index = next_section_index
    while insert_index > section_index and not lines[insert_index - 1].strip():
        insert_index -= 1

    lines.insert(insert_index, row)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


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
    component_key = _clean(component).lower()

    if component_key == "processor":
        row = (
            f"| {_clean(stamp)} | {_clean(node)} | {_clean(found)} | "
            f"{_clean(saved)} | {_clean(output_file)} | {_clean(status)} |"
        )
        _append_row_to_section(path, PROCESSOR_SECTION, row)
        return

    row = (
        f"| {_clean(stamp)} | {_clean(found)} | "
        f"{_clean(saved)} | {_clean(output_file)} | {_clean(status)} |"
    )
    _append_row_to_section(path, SCRAPER_SECTION, row)
