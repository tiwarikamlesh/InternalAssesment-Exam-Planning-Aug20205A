#!/usr/bin/env python3
"""
Generate LaTeX where sections = Program -- Semester -- Section,
each student has an enumerate entry with their subjects (itemize),
and each subject entry includes assigned Date, Slot, Room and Block (A/B)
if an assignment exists in schedule/assignments_*.csv.

Outputs: students_schedule.tex
"""

import os
import re
import glob
import csv
from collections import defaultdict, OrderedDict
import pandas as pd

SCHEDULE_CSV = 'schedule.csv'
STUDENTS_CSV = 'students.csv'
ASSIGNMENTS_DIR = 'schedule'   # reads schedule/assignments_*.csv
OUTPUT_TEX = 'students_schedule.tex'

LATEX_ESCAPES = {
    '&': r'\&',
    '%': r'\%',
    '$': r'\$',
    '#': r'\#',
    '_': r'\_',
    '{': r'\{',
    '}': r'\}',
    '~': r'\textasciitilde{}',
    '^': r'\textasciicircum{}',
    '\\': r'\textbackslash{}',
}

def escape_latex(s: str) -> str:
    """Escape LaTeX special characters and collapse whitespace."""
    if s is None:
        return ''
    if not isinstance(s, str):
        s = str(s)
    # replace backslash first
    s = s.replace('\\', LATEX_ESCAPES['\\'])
    for ch, esc in LATEX_ESCAPES.items():
        if ch == '\\':
            continue
        s = s.replace(ch, esc)
    s = re.sub(r"\s+", ' ', s).strip()
    return s

def title_case_name(name: str) -> str:
    """Simple title-casing for student names."""
    if not isinstance(name, str):
        name = str(name)
    return ' '.join([w.capitalize() for w in name.strip().lower().split()])

def get_cell(row, col_name: str) -> str:
    """Safely get a cell value from a pandas row (Series). Return '' for NaN/missing."""
    val = row.get(col_name, '')
    if pd.isna(val):
        return ''
    return str(val).strip()

def sanity_check(df: pd.DataFrame, file_name: str):
    """Check for missing (NaN/empty) values and print details."""
    print(f"\nSanity check for {file_name}:")
    issues_found = False
    for col in df.columns:
        mask = df[col].isna() | (df[col].astype(str).str.strip() == '')
        bad_rows = df[mask]
        if not bad_rows.empty:
            issues_found = True
            print(f"  Column '{col}' has {len(bad_rows)} missing/empty values at rows: {bad_rows.index.tolist()}")
    if not issues_found:
        print("  No missing values found.")

# --- schedule map (sNo -> code,name) ---------------------------------------

def read_schedule_map(csv_path: str) -> dict:
    df = pd.read_csv(csv_path, dtype=str)
    sanity_check(df, csv_path)
    mapping = {}
    for _, row in df.iterrows():
        sno = (row.get('sNo') or '').strip()
        code = (row.get('Course-Code') or '').strip()
        name = (row.get('Course-Name') or '').strip()
        # also keep Test-Date and Test-Slot here for convenience
        date_raw = (row.get('Test-Date') or '').strip()
        slot = (row.get('Test-Slot') or '').strip()
        if sno:
            mapping[sno] = {'code': code, 'name': name, 'date_raw': date_raw, 'slot': slot}
    return mapping

def read_students(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    sanity_check(df, csv_path)
    return df

# --- read assignments to find student-room-block allocations ---------------

def load_student_assignments(assignments_dir: str):
    """
    Read schedule/assignments_*.csv and produce:
      assign_by_usn[(USN, sNo)] -> list of dicts: {'Date','Slot','Course-sNo','Room','Block'}
    Counting only rows with a non-empty USN.
    """
    assign_by_usn = defaultdict(list)
    pattern = os.path.join(assignments_dir, "assignments_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"Warning: no assignment CSVs found in '{assignments_dir}'. Student-room fields will be empty.")
        return assign_by_usn

    for fn in files:
        try:
            with open(fn, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for r in reader:
                    usn = (r.get('USN') or r.get('Usn') or r.get('usn') or '').strip()
                    sNo = (r.get('Course-sNo') or r.get('sNo') or '').strip()
                    date = (r.get('Date') or '').strip()
                    slot = (r.get('Slot') or '').strip()
                    room = (r.get('Room') or '').strip()
                    block = (r.get('Block') or '').strip()
                    # accept even if some fields missing, store what we have
                    if usn and sNo:
                        assign_by_usn[(usn, sNo)].append({'Date': date, 'Slot': slot, 'Room': room, 'Block': block})
        except Exception as e:
            print(f"Warning: failed to read assignments file {fn}: {e}")
    return assign_by_usn

# --- grouping students -----------------------------------------------------

def build_groups(df_students: pd.DataFrame) -> OrderedDict:
    """
    Group students by BRANCH -- Semester -- Section.
    Each group contains list of dicts: {'usn','name','tests'}
    """
    groups = defaultdict(list)
    for _, row in df_students.iterrows():
        eligible = get_cell(row, 'eligible') or '1'
        if eligible not in ('1', 'True', 'TRUE', 'true'):
            continue

        branch = get_cell(row, 'BRANCH')
        sem = get_cell(row, 'SEM')
        sec = get_cell(row, 'SEC')  # section included
        usn = get_cell(row, 'USN')
        name = title_case_name(get_cell(row, 'NAME'))
        tests_raw = get_cell(row, 'tests')
        tests = [t.strip() for t in tests_raw.split(',') if t.strip()]

        key = f"{branch} -- Semester {sem} -- Section {sec}"
        groups[key].append({'usn': usn, 'name': name, 'tests': tests})

    ordered = OrderedDict()
    for k in sorted(groups.keys()):
        ordered[k] = sorted(groups[k], key=lambda s: s['usn'])
    return ordered

# --- LaTeX builder ---------------------------------------------------------

def build_latex(groups: dict, schedule_map: dict, assign_by_usn: dict) -> str:
    header = r"""\documentclass[a4paper,11pt]{article}
\usepackage[margin=0.8in]{geometry}
\usepackage{enumitem}
\usepackage{parskip}
\begin{document}
\begin{center}
\LARGE{Students' Test Schedules (with Rooms)}\\
\vspace{6pt}
\end{center}
\tableofcontents
\newpage
"""
    body = [header]

    for group_name, students in groups.items():
        body.append(f"\\section*{{{escape_latex(group_name)}}}")
        body.append(f"\\addcontentsline{{toc}}{{section}}{{{escape_latex(group_name)}}}")
        body.append("\\begin{enumerate}[leftmargin=*]")
        for s in students:
            usn = escape_latex(s['usn'])
            name = escape_latex(s['name'])
            body.append(f"  \\item {usn} -- \\textbf{{{name}}}")
            tests = s.get('tests', [])
            body.append("    \\begin{itemize}[leftmargin=*,noitemsep]")
            if not tests:
                body.append("      \\item No tests assigned")
            else:
                # show each test (de-duplicated in order)
                seen = set()
                for t in tests:
                    if t in seen:
                        continue
                    seen.add(t)
                    info = schedule_map.get(t, {'code': t, 'name': ''})
                    code = escape_latex(info.get('code', t))
                    cname = escape_latex(info.get('name', ''))
                    # find assignment(s) for this student and this sNo
                    assigns = assign_by_usn.get((s['usn'], t), [])
                    if assigns:
                        # show each assignment row (usually only one)
                        for a in assigns:
                            date = escape_latex(a.get('Date', info.get('date_raw','')))
                            slot = escape_latex(a.get('Slot', info.get('slot','')))
                            room = escape_latex(a.get('Room', ''))
                            block = escape_latex(a.get('Block', ''))
                            # pretty render: Course -- Name  [Date, Slot] Room X (A/B)
                            course_part = f"{code}" if not cname else f"{code} -- {cname}"
                            loc_part = f"{date}, {slot}"
                            room_part = f"Room {room}" if room else "Room N/A"
                            block_part = f"(Block {block})" if block else ""
                            body.append(f"      \\item {course_part} — [{loc_part}] \\ {room_part} {block_part}")
                    else:
                        # no individual assignment found for this student
                        course_part = f"{code}" if not cname else f"{code} -- {cname}"
                        body.append(f"      \\item {course_part} \\ (no room assignment found)")
            body.append("    \\end{itemize}")
        body.append("\\end{enumerate}")
        body.append("\\vspace{6pt}")
    body.append("\\end{document}")
    return "\n".join(body)

# --- main ------------------------------------------------------------------

def main():
    if not os.path.exists(SCHEDULE_CSV):
        print(f"Error: '{SCHEDULE_CSV}' not found.")
        return
    if not os.path.exists(STUDENTS_CSV):
        print(f"Error: '{STUDENTS_CSV}' not found.")
        return

    schedule_map = read_schedule_map(SCHEDULE_CSV)
    df_students = read_students(STUDENTS_CSV)
    assign_by_usn = load_student_assignments(ASSIGNMENTS_DIR)
    groups = build_groups(df_students)
    latex = build_latex(groups, schedule_map, assign_by_usn)

    with open(OUTPUT_TEX, 'w', encoding='utf-8') as f:
        f.write(latex)
    print(f"\nWrote LaTeX file to '{OUTPUT_TEX}'. Compile with pdflatex or lualatex.")

if __name__ == '__main__':
    main()
