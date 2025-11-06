#!/usr/bin/env python3
"""
sessions_and_attendance_outputs.py

- Prints detailed session blocks (Date/Slot/Room with Seat A/B courses and IC/Invigilator info).
- Writes the printed blocks (plain text) to invigilatorSign.txt.
- Generates LaTeX attendance pages (one page per course-block) and writes them to attendance_sheets.tex.

Files used:
 - schedule/assignments_*.csv
 - rooms.csv
 - schedule.csv
 - schedule/invigilation_assignments.csv
 - students.csv

Behavior:
 - Only sessions with at least one non-empty Course-sNo are printed / produce pages.
 - Robust to header variants, missing fields.
"""

import os
import glob
import csv
import re
from collections import defaultdict

ASSIGNMENTS_DIR = "schedule"
ASSIGNMENT_PATTERN = os.path.join(ASSIGNMENTS_DIR, "assignments_*.csv")
ROOMS_CSV = "rooms.csv"
SCHEDULE_CSV = "schedule.csv"
INVIG_CSV = os.path.join(ASSIGNMENTS_DIR, "invigilation_assignments.csv")
STUDENTS_CSV = "students.csv"

OUTPUT_ATTENDANCE_TEX = "attendance_sheets.tex"
OUTPUT_CONSOLE_TEXT = "invigilatorSign.txt"

# ---------------- helpers ----------------

def safe_str(v):
    if v is None:
        return ""
    return str(v).strip()

def normalize_block(b):
    if not b:
        return ""
    b = safe_str(b).strip().upper()
    if not b:
        return ""
    if b[0] in ("A","B"):
        return b[0]
    return b

def normalize_sno(x):
    s = safe_str(x)
    if not s:
        return ""
    s = s.strip()
    if re.fullmatch(r"\d+\.\d+", s):
        try:
            s = str(int(float(s)))
        except Exception:
            pass
    return s

# ---------------- read rooms ----------------

def read_rooms(path):
    rooms = {}
    if not os.path.exists(path):
        return rooms
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                reader.fieldnames = [fn.strip() for fn in reader.fieldnames]
            for row in reader:
                room_name = (row.get("Class room") or row.get("Classroom") or row.get("Class") or
                             row.get("Room") or row.get("Room Name") or "").strip()
                if not room_name:
                    for v in row.values():
                        if safe_str(v):
                            room_name = safe_str(v)
                            break
                if not room_name:
                    continue
                def parse_seat(cands):
                    for c in cands:
                        if c in row and safe_str(row.get(c)):
                            try:
                                return int(float(safe_str(row.get(c))))
                            except Exception:
                                return None
                    return None
                a = parse_seat(['A-seats','A_seats','A Seats','A','A_Seats'])
                b = parse_seat(['B-seats','B_seats','B Seats','B','B_Seats'])
                rooms[room_name] = {'A': a, 'B': b}
    except Exception as e:
        print(f"Warning: failed to read rooms.csv: {e}")
    return rooms

def find_room_seats(room_name, rooms_map):
    if not room_name:
        return None, None
    if room_name in rooms_map:
        r = rooms_map[room_name]; return r.get('A'), r.get('B')
    for k,v in rooms_map.items():
        if k.lower() == room_name.lower():
            return v.get('A'), v.get('B')
    for k,v in rooms_map.items():
        if room_name.lower() in k.lower() or k.lower() in room_name.lower():
            return v.get('A'), v.get('B')
    return None, None

# ---------------- load schedule (course metadata) ----------------

def load_schedule_map(path):
    cmap = {}
    if not os.path.exists(path):
        print(f"Warning: {path} not found. Course info will be empty.")
        return cmap
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                reader.fieldnames = [h.strip() for h in reader.fieldnames]
            for r in reader:
                sNo = normalize_sno(r.get('sNo') or r.get('SNo') or r.get('sno') or r.get('S.No') or r.get('S.No.') or '')
                if not sNo:
                    continue
                cmap[sNo] = {
                    'course_code': safe_str(r.get('Course-Code') or r.get('Course Code') or r.get('CourseCode') or ''),
                    'course_name': safe_str(r.get('Course-Name') or r.get('Course Name') or r.get('CourseName') or ''),
                    'ic': safe_str(r.get('Course-Coordinator-Name') or r.get('Course Coordinator Name') or r.get('Course-Coordinator') or r.get('Coordinator') or ''),
                    'ic_mobile': safe_str(r.get('Contact-No') or r.get('Contact No') or r.get('Contact') or '')
                }
    except Exception as e:
        print(f"Warning: failed to read {path}: {e}")
    return cmap

# ---------------- load invigilation assignments ----------------

def load_invig_map(invig_csv_path):
    inv_map_full = defaultdict(list)   # (date,slot,room,block,sNo) -> [invigilators]
    inv_map_block = defaultdict(list)  # (date,slot,room,block) -> [invigilators]
    if not os.path.exists(invig_csv_path):
        return inv_map_full, inv_map_block
    try:
        with open(invig_csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                reader.fieldnames = [h.strip().replace('\u00A0',' ') for h in reader.fieldnames]
            for r in reader:
                date = safe_str(r.get('Date') or '')
                slot = safe_str(r.get('Slot') or '')
                room = safe_str(r.get('Room') or '')
                block = normalize_block(r.get('Block') or '')
                sNo = normalize_sno(r.get('Course-sNo') or r.get('sNo') or '')
                fac = safe_str(r.get('Assigned-Faculty') or r.get('Invigilator') or '')
                if fac:
                    if sNo:
                        inv_map_full[(date, slot, room, block, sNo)].append(fac)
                    inv_map_block[(date, slot, room, block)].append(fac)
    except Exception as e:
        print(f"Warning: failed to read invig file {invig_csv_path}: {e}")
    return inv_map_full, inv_map_block

# ---------------- load students map and assignments ----------------

def load_students_map(path):
    smap = {}
    if not os.path.exists(path):
        return smap
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if reader.fieldnames:
                reader.fieldnames = [h.strip() for h in reader.fieldnames]
            for r in reader:
                usn = safe_str(r.get('USN') or r.get('Usn') or r.get('usn') or '')
                name = safe_str(r.get('NAME') or r.get('Name') or r.get('name') or '')
                if usn:
                    smap[usn] = name
    except Exception as e:
        print(f"Warning: failed to read {path}: {e}")
    return smap

def collect_groups_with_usn(pattern):
    groups = defaultdict(list)
    files = sorted(glob.glob(pattern))
    for fn in files:
        try:
            with open(fn, newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if reader.fieldnames:
                    reader.fieldnames = [h.strip().replace('\u00A0',' ') for h in reader.fieldnames]
                for row in reader:
                    date = safe_str(row.get('Date') or row.get('date') or '')
                    slot = safe_str(row.get('Slot') or row.get('slot') or '')
                    room = safe_str(row.get('Room') or row.get('room') or '')
                    block = normalize_block(row.get('Block') or row.get('block') or '')
                    sNo = normalize_sno(row.get('Course-sNo') or row.get('sNo') or row.get('Course-sno') or '')
                    usn = safe_str(row.get('USN') or row.get('Usn') or row.get('usn') or '')
                    key = (date, slot, room)
                    groups[key].append({'sNo': sNo, 'block': block, 'USN': usn})
        except Exception as e:
            print(f"Warning: failed to read {fn}: {e}")
    return groups

# ---------------- utility formatting ----------------

def format_course_counts(counts_dict):
    if not counts_dict:
        return ""
    items = sorted(counts_dict.items(), key=lambda kv: (-kv[1], kv[0]))
    parts = [f"{s}:{cnt:02d}" for s,cnt in items]
    return ", ".join(parts)

# ---------------- LaTeX attendance page builder ----------------

def latex_escape(s):
    if s is None:
        return ''
    s = str(s)
    replace_map = {
        '\\': r'\textbackslash{}',
        '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#',
        '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'
    }
    for k,v in replace_map.items():
        s = s.replace(k, v)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def build_attendance_page_latex(date_str, slot, slot_time, room, block, sNo, course_code, course_name, usn_list, students_map, invigilator_names, ic_name, ic_mobile):
    top_info = f"Date: {latex_escape(date_str)}, {latex_escape(slot_time)}, Room: {latex_escape(room)}, Seating: {latex_escape(block)}"
    course_info = f"{latex_escape(course_code)} -- {latex_escape(course_name)}" if course_code or course_name else latex_escape(sNo)

    header = []
    header.append(r"\begin{center}")
    header.append(r"{\LARGE\textbf{FET Jain University} \\")
    header.append(r"\large\textbf{Department of CSE}} \\[4pt]")
    header.append(r"\end{center}")
    header.append(r"\textbf{Course:} " + course_info + r"\\")
    header.append(r"\noindent\textbf{Attendance Sheet} " + top_info + r" \\")
    if ic_name or ic_mobile:
        ic_parts = []
        if ic_name:
            ic_parts.append(f"IC: {latex_escape(ic_name)}")
        if ic_mobile:
            ic_parts.append(f"IC Mobile: {latex_escape(ic_mobile)}")
        header.append(r"\noindent " + ", ".join(ic_parts))
    invs = ", ".join(invigilator_names) if invigilator_names else "UNKNOWN INVIGILATOR"
    header.append(" Invigilator: " + latex_escape(invs) + r"\\[5pt]")

    rows = []
    rows.append(r"\scriptsize")
    rows.append(r"\begin{tabular}{|p{0.6cm}|p{3.0cm}|p{7.0cm}|p{4.0cm}|}")
    rows.append(r"\hline")
    rows.append(r"\textbf{S.No} & \textbf{USN} & \textbf{Name} & \textbf{Signature} \\\hline\hline")

    if not usn_list:
        rows.append(r"\multicolumn{4}{|l|}{\emph{No students assigned to this room/block for this session.}} \\")
        rows.append(r"\hline")
    else:
        usns_sorted = sorted(usn_list)
        for idx, usn in enumerate(usns_sorted, start=1):
            name = students_map.get(usn, '')
            rows.append(f"      {idx} & {latex_escape(usn)} & {latex_escape(name)} & \\\\[7pt]\\hline")
    rows.append(r"\end{tabular}")
    rows.append("\n\\newpage\n")
    return "\n".join(header + rows)

# ---------------- main flow ----------------

def main():
    rooms_map = read_rooms(ROOMS_CSV)
    schedule_map = load_schedule_map(SCHEDULE_CSV)
    inv_map_full, inv_map_block = load_invig_map(INVIG_CSV)
    students_map = load_students_map(STUDENTS_CSV)
    groups = collect_groups_with_usn(ASSIGNMENT_PATTERN)

    if not groups:
        print("No sessions found.")
        return

    # prepare LaTeX doc parts for attendance_sheets.tex
    latex_parts = []
    latex_parts.append(r"\documentclass[a4paper,11pt]{article}")
    latex_parts.append(r"\usepackage[margin=0.6in]{geometry}")
    latex_parts.append(r"\usepackage{longtable}")
    latex_parts.append(r"\usepackage{array}")
    latex_parts.append(r"\usepackage{hyperref}")
    latex_parts.append(r"\begin{document}")
    latex_parts.append(r"\pagestyle{empty}")
    latex_count = 0

    # collect console print lines to write to invigilatorSign.txt
    console_lines = []

    keys_sorted = sorted(groups.keys(), key=lambda k: (k[0], k[1], k[2]))

    SLOT_HEADINGS = {
        'Slot-1': '8:50AM - 10:20AM',
        'Slot-2': '10:40AM - 12:10PM',
        'Slot-3': '12:30PM - 2:00PM',
        'Slot-4': '2:15PM - 3:45PM',
    }

    for date, slot, room in keys_sorted:
        entries = groups[(date, slot, room)]

        a_seats, b_seats = find_room_seats(room, rooms_map)
        a_str = str(a_seats) if a_seats is not None else "UNKNOWN"
        b_str = str(b_seats) if b_seats is not None else "UNKNOWN"

        countsA = defaultdict(int); countsB = defaultdict(int)
        students_for = defaultdict(list)  # (block,sNo) -> [usn]

        for e in entries:
            sNo = e.get('sNo') or ""
            blk = e.get('block') or ""
            usn = e.get('USN') or ""
            if not sNo:
                continue
            if blk == 'A':
                countsA[sNo] += 1
                if usn:
                    students_for[('A', sNo)].append(usn)
            elif blk == 'B':
                countsB[sNo] += 1
                if usn:
                    students_for[('B', sNo)].append(usn)

        coursesA_count = len(countsA); coursesB_count = len(countsB)
        total_courses = len(set(list(countsA.keys()) + list(countsB.keys())))
        if total_courses == 0:
            # skip sessions with no courses
            continue

        # Build the console block lines (and collect them)
        sep = "-" * 43
        console_block = []
        console_block.append(sep)
        console_block.append(f"Date: {date}, {slot}")
        console_block.append(f"Room Number: {room} (A: {a_str}, B: {b_str}), Planned Courses A: {coursesA_count}, B: {coursesB_count} #Total: {total_courses}")
        console_block.append("")  # blank line
        console_block.append("[Seat A]")
        # seat A
        for sNo, cnt in sorted(countsA.items(), key=lambda kv: (-kv[1], kv[0])):
            info = schedule_map.get(sNo, {})
            course_name = info.get('course_name', 'UNKNOWN COURSE NAME')
            ic_name = info.get('ic', 'UNKNOWN IC')
            ic_mobile = info.get('ic_mobile', '')
            invs = inv_map_full.get((date, slot, room, 'A', sNo)) or inv_map_block.get((date, slot, room, 'A')) or []
            inv_str = ", ".join(invs) if invs else "UNKNOWN INVIGILATOR"
            line = f"{sNo}: {course_name}, IC Name: {ic_name}, Invigilator Name: {inv_str} ({cnt:02d} Students)"
            console_block.append(line)

            # Create LaTeX page for attendance_sheets.tex
            usns = students_for.get(('A', sNo), [])
            slot_time = SLOT_HEADINGS.get(slot, '')
            course_code = info.get('course_code','')
            page = build_attendance_page_latex(date, slot, slot_time, room, 'A', sNo, course_code, course_name, usns, students_map, invs, ic_name, ic_mobile)
            latex_parts.append(page)
            latex_count += 1

        console_block.append("")
        console_block.append("[Seat B]")
        # seat B
        for sNo, cnt in sorted(countsB.items(), key=lambda kv: (-kv[1], kv[0])):
            info = schedule_map.get(sNo, {})
            course_name = info.get('course_name', 'UNKNOWN COURSE NAME')
            ic_name = info.get('ic', 'UNKNOWN IC')
            ic_mobile = info.get('ic_mobile', '')
            invs = inv_map_full.get((date, slot, room, 'B', sNo)) or inv_map_block.get((date, slot, room, 'B')) or []
            inv_str = ", ".join(invs) if invs else "UNKNOWN INVIGILATOR"
            line = f"{sNo}: {course_name}, IC Name: {ic_name}, Invigilator Name: {inv_str} ({cnt:02d} Students)"
            console_block.append(line)

            # Create LaTeX page for attendance_sheets.tex
            usns = students_for.get(('B', sNo), [])
            slot_time = SLOT_HEADINGS.get(slot, '')
            course_code = info.get('course_code','')
            page = build_attendance_page_latex(date, slot, slot_time, room, 'B', sNo, course_code, course_name, usns, students_map, invs, ic_name, ic_mobile)
            latex_parts.append(page)
            latex_count += 1

        console_block.append(sep)
        # print block to console and append to console_lines
        for ln in console_block:
            print(ln)
            console_lines.append(ln)
        # add blank line after block
        print()
        console_lines.append("")

    latex_parts.append(r"\end{document}")

    # write attendance_sheets.tex
    try:
        with open(OUTPUT_ATTENDANCE_TEX, 'w', encoding='utf-8') as f:
            f.write("\n".join(latex_parts))
        print(f"Wrote {OUTPUT_ATTENDANCE_TEX} with {latex_count} pages.")
    except Exception as e:
        print(f"ERROR: could not write {OUTPUT_ATTENDANCE_TEX}: {e}")

    # write invigilatorSign.txt (console content)
    try:
        with open(OUTPUT_CONSOLE_TEXT, 'w', encoding='utf-8') as f:
            f.write("\n".join(console_lines))
        print(f"Wrote console output to {OUTPUT_CONSOLE_TEXT}")
    except Exception as e:
        print(f"ERROR: could not write {OUTPUT_CONSOLE_TEXT}: {e}")

if __name__ == "__main__":
    main()
