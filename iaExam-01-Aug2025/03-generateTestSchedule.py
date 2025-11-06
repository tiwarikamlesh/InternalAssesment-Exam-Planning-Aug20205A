#!/usr/bin/env python3
"""
generate_schedule_sections_with_prog_counts_and_room_list_and_grids.py

Same as previous, but the 8x8 room allocation grid uses your exact LaTeX template
(with {\tiny ... } and the same minipage cells). For each session (date+slot) the
script fills A/B assigned counts from schedule/assignments_*.csv; if an A/B count is
zero or missing that A/B line is omitted entirely from the cell.

Difference from previous version: **the 8x8 grid DOES NOT show invigilator names**.
(Inline room lists under each course still may show invigilator names.)
Outputs: schedule_sections.tex
"""

import re
import os
import glob
import csv
from collections import defaultdict
from datetime import datetime
import pandas as pd

# --- Configuration ---
SCHEDULE_CSV = 'schedule.csv'
STUDENTS_CSV = 'students.csv'
ROOMS_CSV = 'rooms.csv'        # used to populate A/B capacities in the 8x8 table
ASSIGNMENTS_DIR = 'schedule'   # Code03 output folder
OUTPUT_TEX = 'schedule_sections.tex'
SLOT_ORDER = ['Slot-1', 'Slot-2', 'Slot-3', 'Slot-4']
SLOT_HEADINGS = [
    '8:50--10:20 (Slot-1)',
    '10:40--12:10 (Slot-2)',
    '12:30--14:00 (Slot-3)',
    '14:15--15:45 (Slot-4)',
]

GRID_ROWS = 8
GRID_COLS = 8

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


# ---- helpers ---------------------------------------------------------------

def escape_latex(s: str) -> str:
    if s is None:
        return ''
    if not isinstance(s, str):
        s = str(s)
    s = s.replace('\\', LATEX_ESCAPES['\\'])
    for ch, esc in LATEX_ESCAPES.items():
        if ch == '\\':
            continue
        s = s.replace(ch, esc)
    s = re.sub(r"\s+", ' ', s).strip()
    return s


def normalise_month_spellings(s: str) -> str:
    return s.replace('Sept', 'Sep').replace('SEPT', 'Sep').replace('.', '')


def parse_date_string(s: str):
    if pd.isna(s):
        return None
    s0 = str(s).strip()
    s0 = normalise_month_spellings(s0)
    formats = ['%d-%b-%y', '%d-%b-%Y', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y']
    for fmt in formats:
        try:
            return datetime.strptime(s0, fmt).date()
        except Exception:
            pass
    try:
        dt = pd.to_datetime(s0, dayfirst=True, errors='coerce')
        if pd.notna(dt):
            return dt.date()
    except Exception:
        pass
    return s0


def get_cell(row, col_name: str) -> str:
    val = row.get(col_name, '')
    if pd.isna(val):
        return ''
    return str(val).strip()


# ---- student counts per program/section -----------------------------------

def compute_test_counts_by_prog_sec(students_csv_path: str):
    counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    totals = defaultdict(int)
    if not os.path.exists(students_csv_path):
        print(f"Warning: '{students_csv_path}' not found — all counts will be zero.")
        return counts, totals

    df = pd.read_csv(students_csv_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    for _, row in df.iterrows():
        eligible = get_cell(row, 'eligible') or '1'
        if eligible not in ('1', 'True', 'TRUE', 'true'):
            continue
        branch = get_cell(row, 'BRANCH')
        sec = get_cell(row, 'SEC') or ''
        tests_raw = get_cell(row, 'tests')
        if not tests_raw:
            continue
        tests = [t.strip() for t in tests_raw.split(',') if t.strip()]
        for t in tests:
            counts[t][branch][sec] += 1
            totals[t] += 1
    return counts, totals


# ---- schedule reading -----------------------------------------------------

def read_schedule(csv_path: str):
    df = pd.read_csv(csv_path, dtype=str)
    required = ['sNo', 'Course-Code', 'Course-Name', 'Test-Date', 'Test-Slot',
                'Course-Coordinator-Name', 'Contact-No', 'RoomNumber', 'CabinNumber', 'Common for Programs']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column '{col}' in {csv_path}")
    df['parsed_date'] = df['Test-Date'].apply(parse_date_string)
    mapping = defaultdict(lambda: defaultdict(list))
    for _, row in df.iterrows():
        date_parsed = row['parsed_date']
        slot = row.get('Test-Slot', '')
        course_info = {
            'sNo': row.get('sNo', ''),
            'code': row.get('Course-Code', ''),
            'name': row.get('Course-Name', ''),
            'faculty': row.get('Course-Coordinator-Name', ''),
            'mobile': row.get('Contact-No', ''),
            'room': row.get('RoomNumber', ''),
            'cabin': row.get('CabinNumber', ''),
            'programs': row.get('Common for Programs', ''),
            'date_raw': row.get('Test-Date', ''),   # store original text for lookup
        }
        if pd.isna(slot) or slot == '':
            continue
        mapping[date_parsed][slot].append(course_info)
    return mapping


def split_programs_list(programs_field: str) -> list:
    if not programs_field or pd.isna(programs_field):
        return []
    return [p.strip() for p in str(programs_field).split(',') if p.strip()]


# ---- assignments map from Code03 outputs ---------------------------------

def load_assignments_map(assignments_dir: str):
    """
    Parse assignments CSV files produced by Code03 and return:
      assignments_map[(date_string, slot, sNo)] = list of { 'room':..., 'block': 'A'/'B', 'count': n }
    Counting includes only rows with a non-empty USN.
    """
    assignments_map = defaultdict(list)
    if not os.path.isdir(assignments_dir):
        return assignments_map

    pattern = os.path.join(assignments_dir, "assignments_*.csv")
    files = sorted(glob.glob(pattern))
    counts = defaultdict(int)
    for fn in files:
        try:
            with open(fn, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for r in reader:
                    date = r.get('Date', '').strip()
                    slot = r.get('Slot', '').strip()
                    sNo = r.get('Course-sNo', '').strip()
                    room = r.get('Room', '').strip()
                    block = r.get('Block', '').strip()
                    usn = r.get('USN', '').strip()
                    if usn and sNo and room:
                        key = (date, slot, sNo, room, block)
                        counts[key] += 1
        except Exception as e:
            print(f"Warning: failed to read assignments file {fn}: {e}")
    for (date, slot, sNo, room, block), cnt in counts.items():
        assignments_map[(date, slot, sNo)].append({'room': room, 'block': block, 'count': cnt})
    return assignments_map


def load_invig_map(assignments_dir: str):
    """
    Read schedule/invigilation_assignments.csv and return a map:
      invig_map[(date_string, slot, room, block)] = assigned_faculty_name
    If file missing, return empty map. (This map will still be used for inline lists,
    but it will NOT be printed in the 8x8 grid cells.)
    """
    invig_map = {}
    invig_fn = os.path.join(assignments_dir, 'invigilation_assignments.csv')
    if not os.path.exists(invig_fn):
        # no invig assignments yet
        return invig_map
    try:
        with open(invig_fn, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                date = (r.get('Date') or '').strip()
                slot = (r.get('Slot') or '').strip()
                room = (r.get('Room') or '').strip()
                block = (r.get('Block') or '').strip()
                fac = (r.get('Assigned-Faculty') or '').strip()
                if date and slot and room and block and fac:
                    invig_map[(date, slot, room, block)] = fac
    except Exception as e:
        print(f"Warning: failed to read invigilation assignments {invig_fn}: {e}")
    return invig_map


# ---- rooms list and 8x8 template-based grid generator -----------------------

def load_rooms_list(rooms_csv_path: str):
    """
    Return list of rooms as list of dicts: [{'room': '101', 'A': 31, 'B': 28}, ...]
    preserves CSV order.
    """
    rooms = []
    if not os.path.exists(rooms_csv_path):
        print(f"Warning: '{rooms_csv_path}' not found — room allocation grid will be mostly empty.")
        return rooms
    df = pd.read_csv(rooms_csv_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    for _, r in df.iterrows():
        room_name = (r.get('Class room') or r.get('Classroom') or r.get('Class') or '').strip()
        try:
            a_seats = int(float((r.get('A-seats') or r.get('A_seats') or 0)))
        except Exception:
            a_seats = 0
        try:
            b_seats = int(float((r.get('B-seats') or r.get('B_seats') or 0)))
        except Exception:
            b_seats = 0
        if room_name:
            rooms.append({'room': room_name, 'A': a_seats, 'B': b_seats})
    return rooms


def room_cell_from_template(room_entry, session_counts_map):
    """
    Build a cell using the exact template you provided.
    ONLY show A/B numeric lines when assigned count > 0.
    **This function does NOT show invigilator names** — it prints only "A: x/cap" and/or "B: y/cap".
    """
    if room_entry is None:
        return r"\ "  # empty cell

    room_raw = room_entry['room']            # raw room name like '101'
    room = escape_latex(room_raw)            # escaped for LaTeX in bold
    a_cap = room_entry['A']
    b_cap = room_entry['B']
    # raw counts from session map
    a_cnt_raw = session_counts_map.get((room_raw, 'A'))
    b_cnt_raw = session_counts_map.get((room_raw, 'B'))

    # treat None or zero as "no value" -> do not show the A/B line
    def positive_int_or_none(x):
        try:
            if x is None:
                return None
            xi = int(x)
            return xi if xi > 0 else None
        except Exception:
            try:
                xi = int(float(x))
                return xi if xi > 0 else None
            except Exception:
                return None

    a_cnt = positive_int_or_none(a_cnt_raw)
    b_cnt = positive_int_or_none(b_cnt_raw)

    # Build minipage lines conditionally (no invigilator names here)
    lines = []
    lines.append(f"\\textbf{{{room}}}")  # room bold always shown

    if a_cnt is not None:
        lines.append(f"A: {a_cnt}/{a_cap}")
    if b_cnt is not None:
        lines.append(f"B: {b_cnt}/{b_cap}")

    body = r"\\[4pt] ".join(lines) if len(lines) > 1 else lines[0]

    cell = (r"\begin{minipage}[t]{\linewidth}\centering"
            f"{body}"
            r"\end{minipage}")
    return cell


def room_grid_for_session_template(rooms_list, session_counts_map):
    """
    Build LaTeX for the 8x8 table using the exact provided template and with {\tiny ... } wrapper.
    Cells beyond available rooms are left blank; those blanks are the same as in your template.
    This function will not show invigilator names in the cells.
    """
    # create up to 64 cells
    cells = []
    for idx in range(GRID_ROWS * GRID_COLS):
        if idx < len(rooms_list):
            cells.append(room_cell_from_template(rooms_list[idx], session_counts_map))
        else:
            cells.append(r"\ ")  # empty cell (keeps the table layout)

    lines = []
    lines.append(r"{\tiny ") 
    lines.append(r"\begin{tabular}{|*{8}{p{1.6cm}|}}")
    lines.append(r"\hline")
    # build the 8 rows exactly like your template: each row joined by " & " and ending with \\
    for row_idx in range(GRID_ROWS):
        row_cells = cells[row_idx*GRID_COLS:(row_idx+1)*GRID_COLS]
        line = " & ".join(row_cells) + r" \\"
        lines.append(line)
        lines.append(r"\hline")
    lines.append(r"\end{tabular}")
    lines.append(r"}")  # closing {\tiny ... }
    return "\n".join(lines)


# ---- helper: aggregate session counts from assignments_map -----------------

def aggregate_session_counts_from_assignments_map(assignments_map, date_raw_candidates, slot):
    """
    Given assignments_map where keys are (date_raw, slot, sNo) -> list of recs,
    aggregate and return a dict mapping (room,block) -> total count for any of the
    provided date_raw_candidates and the given slot.
    """
    session_counts = defaultdict(int)
    for (akey_date, akey_slot, akey_sno), recs in assignments_map.items():
        if akey_slot != slot:
            continue
        if akey_date not in date_raw_candidates:
            continue
        for rec in recs:
            room = rec.get('room')
            block = rec.get('block')
            cnt = rec.get('count', 0) or 0
            if room and block:
                session_counts[(room, block)] += int(cnt)
    return session_counts


# ---- LaTeX builder --------------------------------------------------------

def build_latex_sections(mapping, counts_by_test, totals_per_test, assignments_map, rooms_list, invig_map) -> str:
    dates = list(mapping.keys())

    def date_key(d):
        return (1, d) if not isinstance(d, str) else (2, d)

    dates_sorted = sorted(dates, key=date_key)

    header = r"""\documentclass[a4paper,11pt]{article}
\usepackage[margin=0.8in]{geometry}
\usepackage{enumitem}
\usepackage{parskip}
\usepackage{hyperref}
\begin{document}
\begin{center}
\LARGE{Exam Schedule: Subjects by Date and Slot}\\
\vspace{6pt}
\end{center}
\tableofcontents
\newpage
"""

    body_lines = [header]

    for d in dates_sorted:
        date_str = d if isinstance(d, str) else d.strftime('%d %b %Y')
        date_cell = escape_latex(date_str)
        body_lines.append(f"\\section*{{{date_cell}}}")
        body_lines.append(f"\\addcontentsline{{toc}}{{section}}{{{date_cell}}}")
        for slot_idx, slot in enumerate(SLOT_ORDER):
            slot_heading = escape_latex(SLOT_HEADINGS[slot_idx])
            body_lines.append(f"\\subsection*{{{slot_heading}}}")
            body_lines.append(f"\\addcontentsline{{toc}}{{subsection}}{{{slot_heading}}}")
            items = mapping[d].get(slot, [])
            if not items:
                body_lines.append('No exams scheduled.\\\\')
                # Build date_raw candidates and aggregate session counts for the empty session
                date_raw_candidates = set()
                if hasattr(d, 'strftime'):
                    date_raw_candidates.add(d.strftime('%d-%b-%y'))
                    date_raw_candidates.add(d.strftime('%d-%b-%Y'))
                    date_raw_candidates.add(d.strftime('%d-%B-%Y'))
                date_raw_candidates.add(date_str)
                session_counts_map = aggregate_session_counts_from_assignments_map(assignments_map, date_raw_candidates, slot)
                # Insert the template-based grid (fills only occupied cells) — no invigilator names here
                body_lines.append('\\vspace{6pt}')
                body_lines.append(room_grid_for_session_template(rooms_list, session_counts_map))
                body_lines.append('\\vspace{12pt}')
                continue

            body_lines.append('\\begin{itemize}[leftmargin=*]')
            for course in items:
                sNo = (course.get('sNo') or '').strip()
                total = totals_per_test.get(sNo, 0)
                code = escape_latex(course.get('code', ''))
                name = escape_latex(course.get('name', ''))
                faculty = escape_latex(course.get('faculty', ''))
                mobile = escape_latex(course.get('mobile', ''))
                room = escape_latex(course.get('room', ''))
                cabin = escape_latex(course.get('cabin', ''))
                programs_list = split_programs_list(course.get('programs', '') or '')
                date_raw = (course.get('date_raw') or '').strip()  # original date string to match assignments

                # Course heading with consolidated total
                body_lines.append(f"  \\item \\textbf{{{code}}} -- {name} \\hfill (Total: {total})\\\\")
                body_lines.append(f"    Faculty: \\textbf{{{faculty}}}, Mobile: {mobile}, Room: {room}, Cabin: {cabin}\\\\")
                # Programs block as before
                if not programs_list:
                    body_lines.append("    Programs: None specified.\\\\")
                else:
                    body_lines.append("    Programs:")
                    body_lines.append("    \\begin{itemize}[leftmargin=*,noitemsep]")
                    per_test_counts = counts_by_test.get(sNo, {})
                    for prog in programs_list:
                        prog_clean = prog.strip()
                        prog_counts = per_test_counts.get(prog_clean, {})
                        if not prog_counts:
                            body_lines.append(f"      \\item {escape_latex(prog_clean)} (no students)")
                        else:
                            parts = []
                            for sec in sorted(prog_counts.keys(), key=lambda x: (x == '', x)):
                                cnt = prog_counts[sec]
                                sec_label = sec if sec != '' else 'no section'
                                parts.append(f"Section {escape_latex(sec_label)}: {cnt}")
                            sec_str = ', '.join(parts)
                            body_lines.append(f"      \\item {escape_latex(prog_clean)} ({sec_str})")
                    body_lines.append("    \\end{itemize}")

                # --- inline itemized list showing room assignments for this test (if any) ---
                key = (date_raw, slot, sNo)
                room_assignments = assignments_map.get(key, [])
                if not room_assignments:
                    body_lines.append("    Rooms: No assignment found for this test.\\\\")
                else:
                    body_lines.append("    Rooms:")
                    body_lines.append("    \\begin{itemize}[leftmargin=*,noitemsep]")
                    for rec in sorted(room_assignments, key=lambda x: (x['room'], x['block'])):
                        rname = escape_latex(rec.get('room', ''))
                        blk = escape_latex(rec.get('block', ''))
                        cnt = rec.get('count', 0)
                        # inline list still shows invigilator (if available) — unchanged
                        inv = None
                        date_candidates = set()
                        if hasattr(d, 'strftime'):
                            date_candidates.add(d.strftime('%d-%b-%y'))
                            date_candidates.add(d.strftime('%d-%b-%Y'))
                            date_candidates.add(d.strftime('%d-%B-%Y'))
                        date_candidates.add(date_str)
                        if date_raw:
                            date_candidates.add(date_raw)
                        for dc in date_candidates:
                            inv = invig_map.get((dc, slot, rec.get('room'), rec.get('block')))
                            if inv:
                                break
                        if inv:
                            body_lines.append(f"      \\item {rname} Block {blk} -- {cnt} students (Inv: {escape_latex(inv)})")
                        else:
                            body_lines.append(f"      \\item {rname} Block {blk} -- {cnt} students")
                    body_lines.append("    \\end{itemize}")
            body_lines.append('\\end{itemize}')

            # --- insert the 8x8 room allocation grid for this session (template-based) ---
            date_raw_candidates = set()
            if items:
                for c in items:
                    dr = (c.get('date_raw') or '').strip()
                    if dr:
                        date_raw_candidates.add(dr)
            if hasattr(d, 'strftime'):
                date_raw_candidates.add(d.strftime('%d-%b-%y'))
                date_raw_candidates.add(d.strftime('%d-%b-%Y'))
                date_raw_candidates.add(d.strftime('%d-%B-%Y'))
            date_raw_candidates.add(date_str)

            session_counts_map = aggregate_session_counts_from_assignments_map(assignments_map, date_raw_candidates, slot)
            body_lines.append('\\vspace{6pt}')
            # grid prints only counts/capacities; invigilator names are intentionally omitted
            body_lines.append(room_grid_for_session_template(rooms_list, session_counts_map))
            body_lines.append('\\vspace{12pt}')

        body_lines.append('\\vspace{6pt}')

    body_lines.append('\\end{document}')
    return '\n'.join(body_lines)


# ---- main -----------------------------------------------------------------

def main():
    counts_by_test, totals_per_test = compute_test_counts_by_prog_sec(STUDENTS_CSV)
    mapping = read_schedule(SCHEDULE_CSV)
    assignments_map = load_assignments_map(ASSIGNMENTS_DIR)
    invig_map = load_invig_map(ASSIGNMENTS_DIR)  # still loaded for inline lists, but NOT shown in grid
    rooms_list = load_rooms_list(ROOMS_CSV)
    latex = build_latex_sections(mapping, counts_by_test, totals_per_test, assignments_map, rooms_list, invig_map)
    with open(OUTPUT_TEX, 'w', encoding='utf-8') as f:
        f.write(latex)
    print(f"Wrote LaTeX file to '{OUTPUT_TEX}'. Compile with pdflatex or lualatex.")


if __name__ == '__main__':
    main()
