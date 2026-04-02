from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_FILE = ROOT / "README.base.md"
README_FILE = ROOT / "README.md"
FEED_FILE = ROOT / "public" / "profile-feed.json"

MAIN_TAGS = ["研究", "学習", "就活", "PJ"]
PERSONAL_TAGS = ["運動", "興味"]
ALL_TAGS = MAIN_TAGS + PERSONAL_TAGS
TAG_META = {
    "研究": {"icon": "🧪"},
    "学習": {"icon": "📘"},
    "就活": {"icon": "💼"},
    "PJ": {"icon": "🛠️"},
    "運動": {"icon": "🏃"},
    "興味": {"icon": "🌿"},
}

SECTION_ALIASES = {
    "Tracks": "Tracks",
    "Today's Focus": "Tracks",
    "Done": "Done",
    "What I Did": "Done",
    "Experiment / Code Update": "Done",
    "Notes": "Notes",
    "Problems": "Notes",
    "What I Learned": "Notes",
    "Next": "Next",
    "Next Step": "Next",
}


def parse_date_from_path(path: Path):
    try:
        return datetime.strptime(path.stem, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_tagged_text(text: str):
    tags = []
    rest = text.strip()

    while True:
        m = re.match(r"^\[(.+?)\]\s*", rest)
        if not m:
            break
        tags.append(m.group(1).strip())
        rest = rest[m.end():].strip()

    return tags, rest


def parse_log_file(path: Path):
    log_date = parse_date_from_path(path)
    if log_date is None:
        return None

    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()

    sections = {
        "Tracks": [],
        "Done": [],
        "Notes": [],
        "Next": [],
    }

    current_section = None

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## "):
            title = stripped[3:].strip()
            current_section = SECTION_ALIASES.get(title)
            continue

        if current_section and stripped.startswith("- "):
            item_text = stripped[2:].strip()
            tags, text = parse_tagged_text(item_text)
            sections[current_section].append(
                {
                    "raw": item_text,
                    "tags": tags,
                    "text": text,
                }
            )

    return {
        "date": log_date,
        "path": path,
        "sections": sections,
    }


def collect_entries():
    entries = []
    for path in sorted(ROOT.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9][0-9][0-9]-[0-9][0-9]/*.md")):
        parsed = parse_log_file(path)
        if parsed:
            entries.append(parsed)

    entries.sort(key=lambda x: x["date"])
    return entries


def day_tags(entry):
    done_tags = set()
    for item in entry["sections"]["Done"]:
        done_tags.update(item["tags"])

    if done_tags:
        return done_tags

    track_tags = set()
    for item in entry["sections"]["Tracks"]:
        track_tags.update(item["tags"])

    return track_tags


def count_days_by_tag(entries, days, ref_date):
    start_date = ref_date - timedelta(days=days - 1)
    counts = {tag: 0 for tag in ALL_TAGS}

    for entry in entries:
        if not (start_date <= entry["date"] <= ref_date):
            continue

        tags = day_tags(entry)
        for tag in tags:
            if tag in counts:
                counts[tag] += 1

    return counts


def latest_focuses(entry, limit=3):
    focuses = [item["text"] for item in entry["sections"]["Tracks"] if item["text"]]
    if not focuses:
        focuses = [item["text"] for item in entry["sections"]["Done"] if item["text"]]
    return focuses[:limit]


def latest_active_tracks(entry):
    active = []
    for item in entry["sections"]["Tracks"]:
        for tag in item["tags"]:
            if tag not in active:
                active.append(tag)
    return active


def recent_interest_topics(entries, days, ref_date, limit=3):
    start_date = ref_date - timedelta(days=days - 1)
    topics = []

    for entry in sorted(entries, key=lambda x: x["date"], reverse=True):
        if not (start_date <= entry["date"] <= ref_date):
            continue

        for section_name in ["Tracks", "Done", "Notes"]:
            for item in entry["sections"][section_name]:
                if "興味" in item["tags"] and item["text"] and item["text"] not in topics:
                    topics.append(item["text"])
                    if len(topics) >= limit:
                        return topics

    return topics


def make_summary(main_counts):
    nonzero = [(tag, count) for tag, count in main_counts.items() if count > 0]

    if not nonzero:
        return "統計用のタグがまだ少ないため、傾向はこれから見えてくる。"

    nonzero.sort(key=lambda x: x[1], reverse=True)

    if len(nonzero) == 1:
        return f"最近30日では「{nonzero[0][0]}」が中心。"

    first_tag, first_count = nonzero[0]
    second_tag, second_count = nonzero[1]

    if first_count - second_count <= 1:
        return f"最近30日では「{first_tag}」と「{second_tag}」が中心。"

    return f"最近30日では「{first_tag}」が中心。"


def format_day_count(n):
    return "1 day" if n == 1 else f"{n} days"


def escape_readme_text(text):
    return html.escape(text, quote=False).replace("|", "\\|").strip()


def tag_icon(tag):
    return TAG_META.get(tag, {}).get("icon", "•")


def render_tag_chip(tag):
    return f"<code>{tag_icon(tag)} {escape_readme_text(tag)}</code>"


def render_bar(count, max_count, width=8):
    if max_count <= 0 or count <= 0:
        return "░" * width

    filled = max(1, round((count / max_count) * width))
    filled = min(width, filled)
    return "█" * filled + "░" * (width - filled)


def render_snapshot_block(last_update, active_tracks, focuses):
    active_text = " ".join(render_tag_chip(tag) for tag in active_tracks) if active_tracks else "none"
    focus_text = " / ".join(escape_readme_text(x) for x in focuses) if focuses else "none"

    return "\n".join(
        [
            f"- **Last update:** `{last_update}`",
            f"- **Current focuses:** {focus_text}",
            f"- **Active tracks:** {active_text}",
        ]
    )


def render_count_block(tags, counts):
    max_count = max((counts[tag] for tag in tags), default=0)
    lines = []

    for tag in tags:
        lines.append(
            f"- **{tag_icon(tag)} {tag}**: `{format_day_count(counts[tag])}`  `{render_bar(counts[tag], max_count)}`"
        )

    return "\n".join(lines)


def render_personal_block(counts, interest_text):
    max_count = max(counts["運動"], 0)
    return "\n".join(
        [
            f"- **{tag_icon('運動')} 運動**: `{format_day_count(counts['運動'])}`  `{render_bar(counts['運動'], max_count)}`",
            f"- **{tag_icon('興味')} 興味**: {escape_readme_text(interest_text)}",
        ]
    )


def render_recent_entry(entry, limit=3):
    done_items = entry["sections"]["Done"]
    if not done_items:
        done_items = entry["sections"]["Tracks"]

    pieces = []
    for item in done_items[:limit]:
        if item["tags"]:
            pieces.append(f"{tag_icon(item['tags'][0])} [{item['tags'][0]}] {item['text']}")
        else:
            pieces.append(item["text"])

    joined = " / ".join(pieces) if pieces else "(no details)"
    rel_path = entry["path"].relative_to(ROOT).as_posix()
    return f"- [{entry['date'].isoformat()}]({rel_path}) | {joined}"


def collect_archive_links(entries, limit=6):
    seen = []
    for entry in sorted(entries, key=lambda x: x["date"], reverse=True):
        folder = entry["path"].parent.relative_to(ROOT).as_posix()
        label = entry["path"].parent.name
        pair = (label, folder)
        if pair not in seen:
            seen.append(pair)

    return seen[:limit]


def build_auto_block(entries):
    if not entries:
        return "\n".join(
            [
                "## 📌 Snapshot",
                render_snapshot_block("none", [], []),
                "",
                "## 📚 Main Tracks (Last 30 Days)",
                render_count_block(MAIN_TAGS, {tag: 0 for tag in ALL_TAGS}),
                "",
                "## 🌱 Personal Rhythm (Last 30 Days)",
                render_personal_block({tag: 0 for tag in ALL_TAGS}, "none recently"),
                "",
                "## 🗂️ Monthly Summary",
                "> まだログがない。",
                "",
                "## 🕒 Recent Entries",
                "- none",
            ]
        )

    latest = entries[-1]
    ref_date = latest["date"]

    counts_30 = count_days_by_tag(entries, 30, ref_date)

    active_tracks = latest_active_tracks(latest)
    focuses = latest_focuses(latest, limit=3)

    interest_topics = recent_interest_topics(entries, 30, ref_date, limit=3)
    interest_text = " / ".join(interest_topics) if interest_topics else "none recently"

    summary = make_summary({tag: counts_30[tag] for tag in MAIN_TAGS})

    recent_entries = "\n".join(render_recent_entry(e) for e in entries[-5:][::-1])

    archive_links = collect_archive_links(entries)
    archive_block = "\n".join([f"- [{label}]({folder})" for label, folder in archive_links])

    lines = [
        "## 📌 Snapshot",
        render_snapshot_block(latest["date"].isoformat(), active_tracks, focuses),
        "",
        "## 📚 Main Tracks (Last 30 Days)",
        render_count_block(MAIN_TAGS, counts_30),
        "",
        "## 🌱 Personal Rhythm (Last 30 Days)",
        render_personal_block(counts_30, interest_text),
        "",
        "## 🗂️ Monthly Summary",
        f"> {summary}",
        "",
        "## 🕒 Recent Entries",
        recent_entries,
    ]

    if archive_block:
        lines.extend(
            [
                "",
                "<details>",
                "<summary><strong>📁 Archive</strong></summary>",
                "",
                archive_block,
                "</details>",
            ]
        )

    return "\n".join(lines)


def write_readme(auto_block: str):
    if BASE_FILE.exists():
        base_text = BASE_FILE.read_text(encoding="utf-8")
    else:
        base_text = (
            "# Daily Research Log\n\n"
            "A quiet record of research, study, projects, fitness, and daily life.\n\n"
            "<!-- AUTO:START -->\n"
            "<!-- AUTO:END -->\n"
        )

    pattern = re.compile(r"<!-- AUTO:START -->.*?<!-- AUTO:END -->", re.DOTALL)
    replacement = f"<!-- AUTO:START -->\n{auto_block}\n<!-- AUTO:END -->"

    if pattern.search(base_text):
        output = pattern.sub(replacement, base_text)
    else:
        output = base_text.rstrip() + "\n\n" + replacement + "\n"

    README_FILE.write_text(output.rstrip() + "\n", encoding="utf-8")


def write_profile_feed(entries):
    FEED_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not entries:
        payload = {
            "last_update": None,
            "active_tracks": [],
            "current_focuses": [],
            "last14": {tag: 0 for tag in ALL_TAGS},
            "last30": {tag: 0 for tag in ALL_TAGS},
            "interest_topics": [],
            "summary": "まだログがない。",
            "recent_entries": [],
        }
        FEED_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return

    latest = entries[-1]
    ref_date = latest["date"]

    counts_14 = count_days_by_tag(entries, 14, ref_date)
    counts_30 = count_days_by_tag(entries, 30, ref_date)

    payload = {
        "last_update": latest["date"].isoformat(),
        "active_tracks": latest_active_tracks(latest),
        "current_focuses": latest_focuses(latest, limit=3),
        "last14": counts_14,
        "last30": counts_30,
        "interest_topics": recent_interest_topics(entries, 30, ref_date, limit=3),
        "summary": make_summary({tag: counts_30[tag] for tag in MAIN_TAGS}),
        "recent_entries": [
            {
                "date": entry["date"].isoformat(),
                "summary": render_recent_entry(entry, limit=3)[2:],  # remove "- "
            }
            for entry in entries[-5:][::-1]
        ],
    }

    FEED_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    entries = collect_entries()
    auto_block = build_auto_block(entries)
    write_readme(auto_block)
    write_profile_feed(entries)
    print("README.md and public/profile-feed.json updated.")


if __name__ == "__main__":
    main()
