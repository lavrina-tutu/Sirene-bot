#!/usr/bin/env python3
"""Push import-profile CSV (8 columns) to Google Sheets — лист «Лист1» (C2)."""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

IMPORT_COLS = 8


def import_range(data_rows: int, cols: int = IMPORT_COLS) -> str:
  """A1:H<N+1> where N = number of data rows (header is row 1)."""
  if data_rows < 0:
    raise ValueError("data_rows must be >= 0")
  end_row = data_rows + 1
  end_col = chr(ord("A") + cols - 1)
  return f"A1:{end_col}{end_row}"


def read_import_values(csv_path: Path) -> list[list[str]]:
  with csv_path.open(encoding="utf-8", newline="") as f:
    reader = csv.reader(f)
    rows = [list(row) for row in reader]
  if not rows:
    raise ValueError(f"CSV is empty: {csv_path}")
  if len(rows[0]) != IMPORT_COLS:
    raise ValueError(
      f"Expected {IMPORT_COLS} columns, got {len(rows[0])} in {csv_path}",
    )
  return rows


def _get_services():
  mpp_reader = Path.home() / "USERTOOLS" / "MppReader"
  if str(mpp_reader) not in sys.path:
    sys.path.insert(0, str(mpp_reader))
  from push_to_gs import get_services  # noqa: WPS433

  return get_services()


def resolve_sheet_title(sheets_svc, spreadsheet_id: str, preferred: str = "Лист1") -> str:
  meta = sheets_svc.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
  titles = [s["properties"]["title"] for s in meta.get("sheets", [])]
  if preferred in titles:
    return preferred
  if titles:
    return titles[0]
  return preferred


def share_spreadsheet(drive_svc, file_id: str, emails: list[str]) -> None:
  for email in emails:
    email = email.strip()
    if not email:
      continue
    drive_svc.permissions().create(
      fileId=file_id,
      body={"type": "user", "role": "writer", "emailAddress": email},
      sendNotificationEmail=False,
    ).execute()


def push_import_csv(
  csv_path: Path,
  *,
  title: str | None = None,
  spreadsheet_id: str | None = None,
  share_emails: list[str] | None = None,
  sheet_title: str = "Лист1",
) -> tuple[str, str]:
  """Create or update spreadsheet; return (spreadsheet_id, url)."""
  values = read_import_values(csv_path)
  data_rows = len(values) - 1
  cell_range = import_range(data_rows)

  sheets_svc, drive_svc = _get_services()
  ss = sheets_svc.spreadsheets()

  if spreadsheet_id:
    file_id = spreadsheet_id
    resolved_sheet = resolve_sheet_title(sheets_svc, file_id, sheet_title)
    full_range = f"{resolved_sheet}!{cell_range}"
    ss.values().update(
      spreadsheetId=file_id,
      range=full_range,
      valueInputOption="USER_ENTERED",
      body={"values": values},
    ).execute()
  else:
    doc_title = title or csv_path.stem
    spreadsheet = ss.create(body={
      "properties": {"title": doc_title},
      "sheets": [{"properties": {"title": sheet_title}}],
    }).execute()
    file_id = spreadsheet["spreadsheetId"]
    resolved_sheet = resolve_sheet_title(sheets_svc, file_id, sheet_title)
    full_range = f"{resolved_sheet}!{cell_range}"
    ss.values().update(
      spreadsheetId=file_id,
      range=full_range,
      valueInputOption="USER_ENTERED",
      body={"values": values},
    ).execute()

  if share_emails:
    share_spreadsheet(drive_svc, file_id, share_emails)

  url = f"https://docs.google.com/spreadsheets/d/{file_id}/edit"
  return file_id, url


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description="Push import CSV to Google Sheets (Лист1)")
  parser.add_argument("csv", type=Path, help="import-profile CSV (8 columns)")
  parser.add_argument("--title", help="Spreadsheet title when creating new")
  parser.add_argument("--spreadsheet-id", help="Update existing spreadsheet")
  parser.add_argument(
    "--share",
    action="append",
    default=[],
    help="Email to share (repeatable); do not hardcode in skill",
  )
  parser.add_argument("--sheet", default="Лист1", help="Sheet tab name (default: Лист1)")
  args = parser.parse_args(argv)

  if not args.csv.is_file():
    print(f"CSV not found: {args.csv}", file=sys.stderr)
    return 1

  emails: list[str] = []
  for item in args.share:
    emails.extend(e.strip() for e in item.split(",") if e.strip())

  try:
    file_id, url = push_import_csv(
      args.csv,
      title=args.title,
      spreadsheet_id=args.spreadsheet_id,
      share_emails=emails or None,
      sheet_title=args.sheet,
    )
  except Exception as exc:
    print(f"push_import_gs failed: {exc}", file=sys.stderr)
    return 1

  print(f"spreadsheet_id:{file_id}")
  print(f"READY:{url}")
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
