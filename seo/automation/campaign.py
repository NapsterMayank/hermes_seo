#!/usr/bin/env python3
"""Deterministic queue and Excel export for the Hermes SEO campaign.

CSV files are the source of truth. The XLSX file is a review artifact and should not
be edited as the authoritative copy.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "seo" / "data"
REPORT = ROOT / "seo" / "reports" / "backlink-review.xlsx"

PROSPECT_COLUMNS = [
    "prospect_id", "domain", "opportunity_url", "prospect_type",
    "discovery_query", "target_market", "topic_relevance", "audience_fit",
    "editorial_quality", "spam_risk", "quality_score", "policy_url",
    "contact_url", "registration_required", "account_status",
    "approval_status", "story_angle", "draft_path", "submission_status",
    "live_link_url", "link_rel", "last_checked", "next_action", "notes",
]

TASK_COLUMNS = [
    "task_id", "prospect_id", "domain", "stage", "status", "attempts",
    "last_attempt", "next_attempt", "checkpoint_type", "checkpoint_status",
    "owner_approval", "evidence_path", "error", "notes",
]

ACTIVITY_COLUMNS = [
    "timestamp", "prospect_id", "task_id", "event", "from_status",
    "to_status", "evidence", "notes",
]

ACCOUNT_COLUMNS = [
    "prospect_id", "domain", "login_url", "email_alias", "account_status",
    "verified_at", "last_login", "notes",
]

OUTREACH_COLUMNS = [
    "domain", "contact_name", "contact_address", "prospect_type", "draft_path",
    "approved_by", "sent_at", "follow_up_at", "status", "response", "link_url",
    "notes",
]

FILES = {
    "Prospects": (DATA / "backlink-prospects.csv", PROSPECT_COLUMNS),
    "Browser Queue": (DATA / "browser-task-queue.csv", TASK_COLUMNS),
    "Activity": (DATA / "campaign-activity.csv", ACTIVITY_COLUMNS),
    "Accounts": (DATA / "account-register.csv", ACCOUNT_COLUMNS),
    "Outreach": (DATA / "outreach-log.csv", OUTREACH_COLUMNS),
}


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize_domain(value: str) -> str:
    value = clean(value).lower()
    if not value:
        return ""
    candidate = value if "://" in value else f"https://{value}"
    host = (urlsplit(candidate).hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def numeric(value: str, default: float = 0.0) -> float:
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return default


def calculated_score(row: dict[str, str]) -> str:
    fields = ("topic_relevance", "audience_fit", "editorial_quality", "spam_risk")
    if not all(clean(row.get(field, "")) for field in fields):
        return clean(row.get("quality_score", ""))
    score = (
        numeric(row["topic_relevance"]) * 0.30
        + numeric(row["audience_fit"]) * 0.25
        + numeric(row["editorial_quality"]) * 0.25
        + (100 - numeric(row["spam_risk"])) * 0.20
    )
    return str(round(score))


def ensure_csv(path: Path, columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        write_csv(path, columns, [])
        return
    with path.open(newline="", encoding="utf-8-sig") as handle:
        header = next(csv.reader(handle), [])
    if header != columns:
        raise SystemExit(
            f"Unexpected columns in {path.relative_to(ROOT)}. "
            "Back it up and migrate it before syncing."
        )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({column: clean(row.get(column, "")) for column in columns} for row in rows)
    temporary.replace(path)


def append_activity(
    rows: list[dict[str, str]], prospect_id: str, event: str,
    before: str = "", after: str = "", notes: str = "",
) -> None:
    rows.append({
        "timestamp": now(), "prospect_id": prospect_id, "task_id": "",
        "event": event, "from_status": before, "to_status": after,
        "evidence": "", "notes": notes,
    })


def next_number(values: list[str], prefix: str) -> int:
    numbers = []
    for value in values:
        match = re.fullmatch(rf"{re.escape(prefix)}-(\d+)", value or "")
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers, default=0) + 1


def task_stage(row: dict[str, str], minimum_score: int) -> tuple[str, str, str, str]:
    score = numeric(row.get("quality_score", ""), -1)
    approval = row.get("approval_status") or "unreviewed"
    account = row.get("account_status") or "not-created"
    submission = row.get("submission_status") or "not-started"
    registration = row.get("registration_required", "").lower()

    if score < 0 or not row.get("policy_url"):
        return "qualification", "queued", "", ""
    if score < minimum_score:
        return "owner-review", "rejected", "quality-threshold", "not-required"
    if approval == "rejected":
        return "owner-review", "rejected", "owner-review", "rejected"
    if approval != "approved":
        return "owner-review", "waiting", "owner-review", "required"
    if registration in {"yes", "true", "required"} and account != "created":
        return "account", "waiting", "account-approval", "required"
    if submission == "not-started":
        return "draft", "queued", "", ""
    if submission == "drafted":
        return "submission", "waiting", "payload-approval", "required"
    if submission in {"submitted", "published", "rejected"}:
        return "verification", "complete", "", ""
    return "qualification", "queued", "", ""


def normalize_and_dedupe(
    prospects: list[dict[str, str]], activities: list[dict[str, str]], minimum_score: int,
) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    by_domain: dict[str, dict[str, str]] = {}
    next_id = next_number([row.get("prospect_id", "") for row in prospects], "P")

    for incoming in prospects:
        row = {column: clean(incoming.get(column, "")) for column in PROSPECT_COLUMNS}
        row["domain"] = normalize_domain(row["domain"] or row["opportunity_url"])
        if not row["domain"]:
            continue
        row["quality_score"] = calculated_score(row)
        row["approval_status"] = row["approval_status"] or "unreviewed"
        row["account_status"] = row["account_status"] or "not-created"
        row["submission_status"] = row["submission_status"] or "not-started"
        if row["domain"] in by_domain:
            existing = by_domain[row["domain"]]
            for column in PROSPECT_COLUMNS:
                if not existing[column] and row[column]:
                    existing[column] = row[column]
            append_activity(activities, existing["prospect_id"], "duplicate-merged", notes=row["domain"])
            continue
        if not row["prospect_id"]:
            row["prospect_id"] = f"P-{next_id:04d}"
            next_id += 1
            append_activity(activities, row["prospect_id"], "prospect-id-assigned", notes=row["domain"])
        stage, _, _, _ = task_stage(row, minimum_score)
        row["next_action"] = stage
        by_domain[row["domain"]] = row
        output.append(row)
    return output


def rebuild_queue(
    prospects: list[dict[str, str]], old_tasks: list[dict[str, str]], minimum_score: int,
) -> list[dict[str, str]]:
    old = {(row["prospect_id"], row["stage"]): row for row in old_tasks}
    next_id = next_number([row.get("task_id", "") for row in old_tasks], "T")
    tasks: list[dict[str, str]] = []
    for prospect in prospects:
        stage, status, checkpoint, checkpoint_status = task_stage(prospect, minimum_score)
        key = (prospect["prospect_id"], stage)
        row = dict(old.get(key, {}))
        if not row.get("task_id"):
            row["task_id"] = f"T-{next_id:04d}"
            next_id += 1
        row.update({
            "prospect_id": prospect["prospect_id"], "domain": prospect["domain"],
            "stage": stage, "status": status, "checkpoint_type": checkpoint,
            "checkpoint_status": checkpoint_status,
        })
        row.setdefault("attempts", "0")
        row.setdefault("owner_approval", "")
        if status == "waiting" and checkpoint in {"account-approval", "payload-approval"}:
            if row["owner_approval"] == "approved":
                row["status"] = "queued"
                row["checkpoint_status"] = "approved"
        tasks.append({column: clean(row.get(column, "")) for column in TASK_COLUMNS})
    return tasks


def excel_column(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def xml_text(value: object) -> str:
    text = clean(value)
    # Neutralize spreadsheet formula injection while retaining readable text.
    if text.startswith(("=", "+", "-", "@")):
        text = "'" + text
    return escape(text)


def sheet_xml(rows: list[list[object]]) -> str:
    row_xml: list[str] = []
    for row_index, values in enumerate(rows, 1):
        cells = []
        style = ' s="1"' if row_index == 1 else ""
        for column_index, value in enumerate(values, 1):
            ref = f"{excel_column(column_index)}{row_index}"
            cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t>{xml_text(value)}</t></is></c>')
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    last_column = excel_column(max((len(row) for row in rows), default=1))
    last_row = max(len(rows), 1)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<sheetFormatPr defaultRowHeight="15"/>'
        '<sheetData>' + "".join(row_xml) + '</sheetData>'
        f'<autoFilter ref="A1:{last_column}{last_row}"/>'
        '</worksheet>'
    )


def export_xlsx(sheets: list[tuple[str, list[list[object]]]]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
    ]
    for index in range(1, len(sheets) + 1):
        content_types.append(f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    content_types.append('</Types>')

    workbook_sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, (name, _) in enumerate(sheets, 1)
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<sheets>{workbook_sheets}</sheets></workbook>'
    )
    relations = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">',
    ]
    for index in range(1, len(sheets) + 1):
        relations.append(f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>')
    relations.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    relations.append('</Relationships>')

    styles = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts>'
        '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/></cellXfs>'
        '</styleSheet>'
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        '</Relationships>'
    )
    temporary = REPORT.with_suffix(".xlsx.tmp")
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", "".join(content_types))
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", "".join(relations))
        archive.writestr("xl/styles.xml", styles)
        for index, (_, rows) in enumerate(sheets, 1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", sheet_xml(rows))
    temporary.replace(REPORT)


def load_all() -> dict[str, list[dict[str, str]]]:
    for path, columns in FILES.values():
        ensure_csv(path, columns)
    return {name: read_csv(path) for name, (path, _) in FILES.items()}


def sync(minimum_score: int = 65, target: int = 500) -> None:
    data = load_all()
    prospects = normalize_and_dedupe(data["Prospects"], data["Activity"], minimum_score)
    tasks = rebuild_queue(prospects, data["Browser Queue"], minimum_score)
    data["Prospects"] = prospects
    data["Browser Queue"] = tasks
    for name, (path, columns) in FILES.items():
        write_csv(path, columns, data[name])

    qualified = sum(numeric(row["quality_score"], -1) >= minimum_score for row in prospects)
    approved = sum(row["approval_status"] == "approved" for row in prospects)
    summary_rows = [
        ["Metric", "Value"],
        ["Generated UTC", now()],
        ["Target unique domains", target],
        ["Unique domains", len(prospects)],
        ["Remaining", max(target - len(prospects), 0)],
        [f"Qualified (score >= {minimum_score})", qualified],
        ["Owner approved", approved],
        ["Drafted", sum(row["submission_status"] == "drafted" for row in prospects)],
        ["Published", sum(row["submission_status"] == "published" for row in prospects)],
        ["Source of truth", "seo/data/*.csv (do not edit this XLSX as the master)"],
    ]
    sheets: list[tuple[str, list[list[object]]]] = [("Dashboard", summary_rows)]
    for name, (_, columns) in FILES.items():
        sheets.append((name, [columns] + [[row.get(column, "") for column in columns] for row in data[name]]))
    export_xlsx(sheets)
    print(f"Synced {len(prospects)} unique domains; {qualified} qualified; {approved} approved.")
    print(f"Review workbook: {REPORT.relative_to(ROOT)}")


def update_approval(ids: list[str], decision: str, note: str) -> None:
    data = load_all()
    requested = set(ids)
    found: set[str] = set()
    for row in data["Prospects"]:
        if row["prospect_id"] in requested or row["domain"] in requested:
            before = row["approval_status"]
            row["approval_status"] = decision
            append_activity(data["Activity"], row["prospect_id"], "owner-review", before, decision, note)
            found.update({row["prospect_id"], row["domain"]} & requested)
    missing = requested - found
    if missing:
        raise SystemExit("Unknown prospect IDs/domains: " + ", ".join(sorted(missing)))
    for name in ("Prospects", "Activity"):
        path, columns = FILES[name]
        write_csv(path, columns, data[name])
    sync()


def approve_tasks(ids: list[str], note: str) -> None:
    data = load_all()
    requested = set(ids)
    found: set[str] = set()
    for row in data["Browser Queue"]:
        if row["task_id"] not in requested:
            continue
        if row["checkpoint_type"] not in {"account-approval", "payload-approval"}:
            raise SystemExit(f"{row['task_id']} is not an account or payload checkpoint.")
        row["owner_approval"] = "approved"
        row["checkpoint_status"] = "approved"
        row["status"] = "queued"
        append_activity(
            data["Activity"], row["prospect_id"], "task-approved",
            before="waiting", after="queued", notes=f"{row['task_id']}: {note}".rstrip(),
        )
        found.add(row["task_id"])
    missing = requested - found
    if missing:
        raise SystemExit("Unknown task IDs: " + ", ".join(sorted(missing)))
    for name in ("Browser Queue", "Activity"):
        path, columns = FILES[name]
        write_csv(path, columns, data[name])
    sync()


def print_summary(minimum_score: int = 65) -> None:
    data = load_all()
    prospects = data["Prospects"]
    print(f"Unique domains: {len({normalize_domain(row['domain']) for row in prospects if row['domain']})}")
    print(f"Qualified: {sum(numeric(row['quality_score'], -1) >= minimum_score for row in prospects)}")
    for label, values in (("Approval", [row["approval_status"] or "blank" for row in prospects]),
                          ("Submission", [row["submission_status"] or "blank" for row in prospects])):
        print(label + ": " + ", ".join(f"{key}={value}" for key, value in sorted(Counter(values).items())))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage the resumable Hermes backlink campaign.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync_parser = subparsers.add_parser("sync", help="Normalize CSV queues and generate the Excel workbook.")
    sync_parser.add_argument("--minimum-score", type=int, default=65)
    sync_parser.add_argument("--target", type=int, default=500)
    subparsers.add_parser("summary", help="Print campaign counts.")
    for command, decision in (("approve", "approved"), ("reject", "rejected")):
        item = subparsers.add_parser(command, help=f"Mark exact prospects {decision} and resync.")
        item.add_argument("prospects", nargs="+", help="Prospect IDs or normalized domains.")
        item.add_argument("--note", default="")
        item.set_defaults(decision=decision)
    task_parser = subparsers.add_parser(
        "approve-task", help="Approve exact account or submission checkpoint task IDs."
    )
    task_parser.add_argument("tasks", nargs="+", help="Exact task IDs from the Browser Queue sheet.")
    task_parser.add_argument("--note", default="")

    args = parser.parse_args()
    if args.command == "sync":
        sync(args.minimum_score, args.target)
    elif args.command == "summary":
        print_summary()
    elif args.command == "approve-task":
        approve_tasks(args.tasks, args.note)
    else:
        update_approval(args.prospects, args.decision, args.note)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
