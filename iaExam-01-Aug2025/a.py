#!/usr/bin/env python3
"""
course_student_counts.py

Count unique students scheduled per course across schedule/assignments_*.csv.

Outputs:
 - course_counts.txt  (human readable, printed)
 - course_counts.csv  (CSV: sNo,course_code,course_name,semester,student_count)
"""

import os
import glob
import csv
import re
from collections import defaultdict, OrderedDict

ASSIGNMENTS_DIR = "schedule"
PATTERN = os.path.join(ASSIGNMENTS_DIR, "assignments_*.csv")
SCHEDULE_CSV = "schedule.csv"

OUT_TXT = "course_counts.txt"
OUT_CSV = "course_counts.csv"

# ---------------- helpers ----------------

def safe_str(v):
    if v is None:
        return ""
    return str(v).strip()

def normalize_sno(x):
    s = safe_str(x)
    if not s:
        return ""
    s = s.strip()
    # keep textual sNo like "Tst08" as-is; if numeric-like convert
    if re.fullmatch(r'\d+\.\d+', s):
        try:
            s = str(int(float(s)))
        except Exception:
            pass
    return s

def read_schedule_map(path):
    """Map sNo -> {course_code, course_name, semester}"""
    mapping = {}
    if not os.path.exists(path):
        return mapping
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                reader.fieldnames = [h.strip() for h in reader.fieldnames]
            for r in reader:
                sNo = normalize_sno(r.get('sNo') or r.get('SNo') or r.get('sno') or r.get('S.No') or '')
                if not sNo:
                    continue
                course_code = safe_str(r.get('Course-Code') or r.get('Course Code') or r.get('CourseCode') or '')
                course_name = safe_str(r.get('Course-Name') or r.get('Course Name') or r.get('CourseName') or '')
                semester = safe_str(r.get('Semester') or r.get('SEM') or r.get('sem') or '')
                mapping[sNo] = {'course_code': course_code, 'course_name': course_name, 'semester': semester}
    except Exception as e:
        print(f"Warning: failed to read schedule.csv: {e}")
    return mapping

def collect_assignments(pattern):
    """Return list of rows (dicts) from matching assignment CSVs (robust header handling)."""
    files = sorted(glob.glob(pattern))
    rows = []
    for fn in files:
        try:
            with open(fn, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    # strip header names
                    reader.fieldnames = [h.strip().replace('\u00A0',' ') if h else h for h in reader.fieldnames]
                for r in reader:
                    rows.append({ (k.strip() if k else k): (v or '') for k,v in (r.items()) })
        except Exception as e:
            print(f"Warning: failed to read {fn}: {e}")
    return rows, files

# ---------------- main report logic ----------------

def build_course_counts(assign_rows):
    """
    Returns:
      course_to_usns: dict sNo -> set(USN)
      missing_sno_rows_count: number of rows that had no sNo but non-empty USN
    """
    course_to_usns = defaultdict(set)
    missing_sno_rows_count = 0
    total_rows = 0
    for r in assign_rows:
        total_rows += 1
        # robust extraction of fields
        usn = (r.get('USN') or r.get('Usn') or r.get('usn') or '').strip()
        if not usn:
            # skip blank USN
            continue
        # Try multiple variant headers for course id
        raw_sno = (r.get('Course-sNo') or r.get('Course-sno') or r.get('sNo') or r.get('sno') or r.get('Course') or '').strip()
        sNo = normalize_sno(raw_sno)
        if not sNo:
            missing_sno_rows_count += 1
            continue
        # count unique students per sNo
        course_to_usns[sNo].add(usn)
    return course_to_usns, missing_sno_rows_count, total_rows

def write_outputs(course_to_usns, schedule_map, files, total_rows, missing_sno_rows_count):
    # prepare sorted list of sNo by descending student count then sNo
    items = sorted(course_to_usns.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    # write TXT (human readable)
    lines = []
    lines.append("Course student counts report")
    lines.append("="*40)
    lines.append(f"Files scanned: {len(files)}")
    if files:
        lines.append("  " + ", ".join(os.path.basename(f) for f in files))
    lines.append(f"Total assignment rows scanned: {total_rows}")
    lines.append(f"Rows with missing or empty sNo while USN present: {missing_sno_rows_count}")
    lines.append("")
    lines.append(f"{'sNo':10}  {'Students':>8}  {'Course-Code':12}  {'Semester':8}  Course Name")
    lines.append("-"*100)
    for sNo, usn_set in items:
        meta = schedule_map.get(sNo, {})
        code = meta.get('course_code','')
        cname = meta.get('course_name','')
        sem = meta.get('semester','')
        lines.append(f"{sNo:10}  {len(usn_set):8d}  {code:12}  {sem:8}  {cname}")
    if not items:
        lines.append("No courses with student allocations found.")
    txt = "\n".join(lines)
    print(txt)
    try:
        with open(OUT_TXT, 'w', encoding='utf-8') as f:
            f.write(txt)
        print(f"\nWrote human-readable report to: {OUT_TXT}")
    except Exception as e:
        print(f"ERROR writing {OUT_TXT}: {e}")

    # write CSV
    try:
        with open(OUT_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['sNo', 'course_code', 'course_name', 'semester', 'student_count'])
            for sNo, usn_set in items:
                meta = schedule_map.get(sNo, {})
                code = meta.get('course_code','')
                cname = meta.get('course_name','')
                sem = meta.get('semester','')
                writer.writerow([sNo, code, cname, sem, len(usn_set)])
        print(f"Wrote CSV report to: {OUT_CSV}")
    except Exception as e:
        print(f"ERROR writing {OUT_CSV}: {e}")

# ---------------- entry point ----------------

def main():
    assign_rows, files = collect_assignments(PATTERN)
    if not assign_rows:
        print(f"No assignment rows found in pattern {PATTERN}. Exiting.")
        return
    schedule_map = read_schedule_map(SCHEDULE_CSV)
    course_to_usns, missing_sno_rows_count, total_rows = build_course_counts(assign_rows)
    write_outputs(course_to_usns, schedule_map, files, total_rows, missing_sno_rows_count)

if __name__ == "__main__":
    main()
