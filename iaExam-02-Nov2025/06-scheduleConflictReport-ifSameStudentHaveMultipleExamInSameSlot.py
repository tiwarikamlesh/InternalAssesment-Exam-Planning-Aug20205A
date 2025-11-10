#!/usr/bin/env python3
"""
conflicts_report_by_session.py

Produce a session-grouped conflict report:
 For each (Date, Slot) where at least one student is scheduled for >1 tests,
 print the conflicting course list (with IC details, semester) followed by
 the list of students with conflicts (comma-separated paragraph).

Output: printed to console and saved to conflicts_by_session.txt.
"""

import os
import glob
import csv
from collections import defaultdict, OrderedDict

ASSIGNMENTS_DIR = "schedule"
PATTERN = os.path.join(ASSIGNMENTS_DIR, "assignments_*.csv")
SCHEDULE_CSV = "schedule.csv"
OUT_TXT = "conflicts_by_session.txt"

# ---------- small helpers ----------

def safe_str(v):
    if v is None:
        return ""
    return str(v).strip()

def normalize_usn(u):
    return safe_str(u).upper()

def normalize_date(d):
    return safe_str(d)

def normalize_slot(s):
    return safe_str(s)

def normalize_sno(x):
    s = safe_str(x)
    if not s:
        return ""
    return s.strip()

# ---------- read schedule.csv to map sNo -> course info ----------

def load_schedule(schedule_csv_path):
    sched = {}
    if not os.path.exists(schedule_csv_path):
        print(f"Warning: {schedule_csv_path} not found. Course info will be missing.")
        return sched
    try:
        with open(schedule_csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                reader.fieldnames = [h.strip() for h in reader.fieldnames]
            for r in reader:
                sNo = normalize_sno(
                    r.get('sNo') or r.get('SNo') or r.get('sno') or
                    r.get('S.No') or r.get('S.No.') or r.get('Test-Code') or ''
                )
                if not sNo:
                    continue
                course_name = safe_str(r.get('Course-Name') or r.get('Course Name') or r.get('CourseName'))
                ic = safe_str(r.get('Course-Coordinator-Name') or r.get('Course Coordinator Name') or r.get('Course-Coordinator') or r.get('Coordinator'))
                ic_mobile = safe_str(r.get('Contact-No') or r.get('Contact No') or r.get('Contact'))
                semester = safe_str(r.get('Semester') or r.get('SEM') or r.get('sem'))
                sched[sNo] = {
                    'course_name': course_name,
                    'ic': ic,
                    'ic_mobile': ic_mobile,
                    'semester': semester
                }
    except Exception as e:
        print(f"Warning: failed to read {schedule_csv_path}: {e}")
    return sched

# ---------- read assignments ----------

def read_assignments(pattern):
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"No assignment files matched pattern '{pattern}'")
        return [], files
    rows = []
    for fn in files:
        try:
            with open(fn, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    reader.fieldnames = [h.strip().replace('\u00A0',' ') for h in reader.fieldnames]
                for r in reader:
                    usn_raw = (r.get('USN') or r.get('Usn') or r.get('usn') or '').strip()
                    if not usn_raw:
                        continue
                    date = (r.get('Date') or r.get('Test-Date') or '').strip()
                    slot = (r.get('Slot') or r.get('Test-Slot') or '').strip()
                    sNo = (r.get('Course-sNo') or r.get('sNo') or r.get('Course') or '').strip()
                    room = (r.get('Room') or '').strip()
                    block = (r.get('Block') or '').strip()
                    rows.append({
                        'source_file': os.path.basename(fn),
                        'USN': normalize_usn(usn_raw),
                        'Date': normalize_date(date),
                        'Slot': normalize_slot(slot),
                        'sNo': normalize_sno(sNo),
                        'Room': room,
                        'Block': block
                    })
        except Exception as e:
            print(f"Warning: failed to read '{fn}': {e}")
    return rows, files

# ---------- find conflicts ----------

def find_student_conflicts(rows):
    per_student_session = defaultdict(list)
    for r in rows:
        key = (r['USN'], r['Date'], r['Slot'])
        per_student_session[key].append(r)

    conflicts = []
    for key, assigns in per_student_session.items():
        if len(assigns) > 1:
            usn, date, slot = key
            conflicts.append((usn, date, slot, assigns))
    return conflicts

def group_conflicts_by_session(conflicts):
    by_session = defaultdict(list)
    for usn, date, slot, assigns in conflicts:
        by_session[(date, slot)].append((usn, assigns))
    ordered = OrderedDict()
    for key in sorted(by_session.keys(), key=lambda k: (k[0], k[1])):
        ordered[key] = by_session[key]
    return ordered

# ---------- report ----------

def build_session_report(grouped_conflicts, schedule_map):
    lines = []
    if not grouped_conflicts:
        lines.append("No student conflicts found in same Date+Slot.")
        return lines

    for (date, slot), conflicts_list in grouped_conflicts.items():
        lines.append("-" * 60)
        lines.append(f"Date: {date or '(blank)'} | Slot: {slot or '(blank)'}")
        sNo_set = set()
        usn_set = set()
        for usn, assigns in conflicts_list:
            usn_set.add(usn)
            for a in assigns:
                if a.get('sNo'):
                    sNo_set.add(a['sNo'])
        if not sNo_set:
            lines.append("Conflicting courses: (no sNo values found)")
        else:
            lines.append("Conflicting courses:")
            for sNo in sorted(sNo_set):
                info = schedule_map.get(sNo, {})
                cname = info.get('course_name', '')
                ic = info.get('ic', '')
                ic_m = info.get('ic_mobile', '')
                sem = info.get('semester', '')
                part = f"  - {sNo}"
                if cname:
                    part += f": {cname}"
                if sem:
                    part += f" (Semester: {sem})"
                if ic:
                    part += f" | IC: {ic}"
                    if ic_m:
                        part += f" (Mobile: {ic_m})"
                lines.append(part)
        if usn_set:
            sorted_usns = sorted(usn_set)
            paragraph = ", ".join(sorted_usns)
            lines.append("")
            lines.append("Students with conflicts:")
            lines.append(paragraph)
        else:
            lines.append("Students with conflicts: (none)")
        lines.append("")
    lines.append("-" * 60)
    return lines

# ---------- main ----------

def main():
    rows, _ = read_assignments(PATTERN)
    if not rows:
        print("No assignment rows with USN found.")
        return

    conflicts = find_student_conflicts(rows)
    grouped = group_conflicts_by_session(conflicts)
    schedule_map = load_schedule(SCHEDULE_CSV)
    report_lines = build_session_report(grouped, schedule_map)

    for ln in report_lines:
        print(ln)
    with open(OUT_TXT, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))
    print(f"\nWrote report to {OUT_TXT}")

if __name__ == "__main__":
    main()
