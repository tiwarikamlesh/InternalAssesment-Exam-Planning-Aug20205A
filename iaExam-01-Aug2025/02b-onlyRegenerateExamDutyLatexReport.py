#!/usr/bin/env python3
"""
02_build_tex_from_assignments.py

Reads:
 - schedule/invigilation_assignments.csv (must already contain Assigned-Faculty)
 - schedule.csv (course metadata, ICs)
 - faculty.csv (optional) — each Name is kept in full for display; canonical form
   (the substring before '[') is used for mapping.

Produces:
 - faculty_duties.tex with:
    * per-faculty duty list (grouped by canonical name)
    * 5x4 day×slot grid where invigilation duty cells are colored blue!40
    * '*' in cell if faculty is IC for that session (exact normalized equality)
 - prints ASCII grids for quick verification
"""
import os
import csv
import re
from collections import defaultdict

ASSIGNMENTS_CSV = os.path.join('schedule', 'invigilation_assignments.csv')
SCHEDULE_CSV = 'schedule.csv'
FACULTY_CSV = 'faculty.csv'            # optional
OUTPUT_FACULTY_TEX = 'faculty_duties.tex'

SLOT_ORDER = ['Slot-1', 'Slot-2', 'Slot-3', 'Slot-4']
MAX_DAYS = 5  # rows in grid

VERBOSE = False  # set True to see mapping/debug prints


# ----------------- helpers -----------------

def ensure_dir(p):
    d = os.path.dirname(p)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)

def eprint(*args, **kwargs):
    if VERBOSE:
        print(*args, **kwargs)

def clean_unicode_spaces(s: str) -> str:
    # replace various unicode spaces with ASCII space
    return re.sub(r'[\u00A0\u2000-\u200B\u202F\u205F\u3000]', ' ', s)

LATEX_ESCAPES = {
    '&': r'\&', '%': r'\%', '$': r'\$', '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
    '~': r'\textasciitilde{}', '^': r'\textasciicircum{}', '\\': r'\textbackslash{}'
}

def escape_latex(s):
    if s is None:
        return ''
    s = str(s)
    s = s.replace('\\', LATEX_ESCAPES['\\'])
    for ch, rep in LATEX_ESCAPES.items():
        if ch == '\\':
            continue
        s = s.replace(ch, rep)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def normalize_name_for_match(name: str) -> str:
    """
    Normalize a name for equality matching:
     - remove bracketed parts
     - remove honorific tokens
     - remove punctuation, collapse spaces, lowercase
    """
    if not name:
        return ''
    s = clean_unicode_spaces(name)
    s = re.sub(r'\[.*?\]', '', s)  # remove any bracketed content (extra safety)
    s = re.sub(r'\b(dr|mr|ms|mrs|prof|professor)\b', '', s, flags=re.I)
    s = re.sub(r'[^A-Za-z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s

def canonicalize_raw_name(raw: str) -> str:
    """
    Turn raw name (possibly including bracketed job and phone) into canonical display name:
     - If '[' present: take substring before first '['
     - Else: strip trailing phone-like digits and punctuation
     - Collapse whitespace and trim.
    This canonical string is used for mapping/grouping.
    """
    if not raw:
        return ''
    s = clean_unicode_spaces(raw).strip()
    if '[' in s:
        s = s.split('[', 1)[0].strip()
    else:
        s = re.sub(r'[\-\s]*\d{4,}[\d\s\-\)]*$', '', s).strip()
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# ----------------- loaders -----------------

def load_faculty_canonical(faculty_csv_path):
    """
    Load faculty.csv and return:
      - faculty_list: list of canonical display names (stripped before '[')
      - faculty_norm_map: canonical -> normalized
      - norm_to_canonical: normalized -> canonical (for mapping)
      - canonical_to_raw_full: canonical -> raw full Name from CSV (for display in section header)
    """
    facs = []
    faculty_norm_map = {}
    norm_to_canonical = {}
    canonical_to_raw_full = {}
    if not os.path.exists(faculty_csv_path):
        return facs, faculty_norm_map, norm_to_canonical, canonical_to_raw_full
    with open(faculty_csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return facs, faculty_norm_map, norm_to_canonical, canonical_to_raw_full
        for r in reader:
            raw = (r.get('Name') or r.get('NAME') or r.get('name') or '').strip()
            if not raw:
                for v in r.values():
                    if v and v.strip():
                        raw = v.strip()
                        break
            if not raw:
                continue
            canonical = canonicalize_raw_name(raw)
            if not canonical:
                continue
            # preserve order
            facs.append(canonical)
            n = normalize_name_for_match(canonical)
            faculty_norm_map[canonical] = n
            # record the raw full original name for display (if duplicate canonical appears later, keep first raw)
            if canonical not in canonical_to_raw_full:
                canonical_to_raw_full[canonical] = raw
            if n:
                if n not in norm_to_canonical:
                    norm_to_canonical[n] = canonical
    return facs, faculty_norm_map, norm_to_canonical, canonical_to_raw_full

def load_assignments(path, norm_to_canonical):
    """
    Load invigilation assignments CSV into list of dicts (strip values).
    Map Assigned-Faculty -> canonical name if normalized match found.
    Returns list of rows (with possibly remapped 'Assigned-Faculty').
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found. Run allocation first or place the file there.")
    rows = []
    unmapped_names = set()
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"No header found in {path}")
        for r in reader:
            row = {k.strip(): (v or '').strip() for k, v in r.items()}
            assigned = row.get('Assigned-Faculty', '').strip()
            if assigned:
                # canonicalize assigned raw first (so it matches faculty canonicalization)
                assigned_can = canonicalize_raw_name(assigned)
                assigned_norm = normalize_name_for_match(assigned_can)
                if assigned_norm and assigned_norm in norm_to_canonical:
                    canonical = norm_to_canonical[assigned_norm]
                    if canonical != assigned:
                        eprint(f"[MAP] Assigned-Faculty raw='{assigned}' -> canonical='{canonical}' (via '{assigned_can}')")
                    row['Assigned-Faculty'] = canonical
                else:
                    # fallback: try normalizing original assigned string directly
                    assigned_norm2 = normalize_name_for_match(assigned)
                    if assigned_norm2 and assigned_norm2 in norm_to_canonical:
                        canonical = norm_to_canonical[assigned_norm2]
                        eprint(f"[MAP-fallback] Assigned-Faculty raw='{assigned}' -> canonical='{canonical}' (via fallback norm)")
                        row['Assigned-Faculty'] = canonical
                    else:
                        unmapped_names.add(assigned)
            rows.append(row)

    if unmapped_names:
        eprint("\n[WARN] Assigned-Faculty names not matched to faculty.csv canonical names (these remain as-is):")
        for n in sorted(unmapped_names):
            eprint("   ", n)
    return rows

def load_course_info(schedule_csv_path):
    """Load schedule.csv keyed by sNo. Includes Test-Date and Test-Slot fields as 'date' and 'slot'."""
    course_info = {}
    if not os.path.exists(schedule_csv_path):
        eprint(f"Warning: {schedule_csv_path} not found. Course metadata will be empty.")
        return course_info
    with open(schedule_csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            eprint(f"Warning: schedule.csv has no header.")
            return course_info
        for r in reader:
            sNo = (r.get('sNo') or r.get('SNo') or r.get('sno') or '').strip()
            if not sNo:
                continue
            course_info[sNo] = {
                'course_code': (r.get('Course-Code') or r.get('Course Code') or r.get('CourseCode') or '').strip(),
                'course_name': (r.get('Course-Name') or r.get('Course Name') or r.get('CourseName') or '').strip(),
                'ic': (r.get('Course-Coordinator-Name') or r.get('Course Coordinator Name') or r.get('Course-Coordinator') or r.get('Coordinator') or '').strip(),
                'ic_mobile': (r.get('Contact-No') or r.get('Contact No') or r.get('Contact') or '').strip(),
                'ic_room': (r.get('RoomNumber') or r.get('Room Number') or r.get('Room') or '').strip(),
                'ic_cabin': (r.get('CabinNumber') or r.get('Cabin Number') or r.get('Cabin') or '').strip(),
                'date': (r.get('Test-Date') or r.get('Test Date') or r.get('Date') or '').strip(),
                'slot': (r.get('Test-Slot') or r.get('Test Slot') or r.get('Slot') or '').strip(),
            }
    return course_info


# ----------------- LaTeX + grid builder -----------------

def build_faculty_tex(invig_assignments, course_info, faculty_list, faculty_norm_map, canonical_to_raw_full, dates_ordered, slot_order):
    """
    Build LaTeX. Match IC cells by exact normalized equality between
    normalized(schedule IC) and faculty_norm_map[canonical_faculty_name].
    Section headers display raw_full if present (from faculty.csv).
    """
    # Build mapping (date,slot) -> set of IC raw strings (from schedule.csv)
    session_ic_raw = defaultdict(set)
    for sNo, info in course_info.items():
        d = info.get('date','').strip()
        s = info.get('slot','').strip()
        ic_raw = info.get('ic','').strip()
        if d and s and ic_raw:
            session_ic_raw[(d, s)].add(ic_raw)

    # Group assignments by faculty name (Assigned-Faculty values have been mapped to canonical where possible)
    assignments_by_fac = defaultdict(list)
    unassigned = []
    for r in invig_assignments:
        fac = r.get('Assigned-Faculty','').strip()
        if fac:
            assignments_by_fac[fac].append(r)
        else:
            unassigned.append(r)

    # Build ordered faculty list: canonical faculty from faculty_list first, then any assigned-only names appended
    ordered = list(faculty_list)
    seen = set(ordered)
    for fac in sorted(assignments_by_fac.keys()):
        if fac not in seen:
            ordered.append(fac)
            seen.add(fac)

    parts = []
    header = r"""\documentclass[a4paper,11pt]{article}
\usepackage[margin=0.7in]{geometry}
\usepackage{enumitem}
\usepackage{parskip}
\usepackage[table]{xcolor}
\usepackage{hyperref}
\begin{document}
\begin{center}
\LARGE{Invigilation Duties — Faculty Roster}\\
\vspace{6pt}
\end{center}
\tableofcontents
\newpage
"""
    parts.append(header)

    if unassigned:
        parts.append(r"\section*{Unassigned duties}")
        parts.append(r"\addcontentsline{toc}{section}{Unassigned duties}")
        parts.append(r"\begin{itemize}[leftmargin=*]")
        for r in unassigned:
            s = f"{escape_latex(r.get('Date',''))}, {escape_latex(r.get('Slot',''))} -- Room {escape_latex(r.get('Room',''))} (Block {escape_latex(r.get('Block',''))}) -- Course {escape_latex(r.get('Course-sNo',''))}"
            if r.get('Note'):
                s += f" — {escape_latex(r.get('Note'))}"
            parts.append(f"  \\item {s}")
        parts.append(r"\end{itemize}")
        parts.append(r"\vspace{6pt}")

    date_to_row = {d: idx for idx, d in enumerate(dates_ordered[:MAX_DAYS])}
    slot_to_col = {s: idx for idx, s in enumerate(slot_order)}

    eprint("\nCanonical faculty names (canonical -> normalized):")
    for can, n in faculty_norm_map.items():
        eprint(f"  '{can}' -> '{n}' (display='{canonical_to_raw_full.get(can, can)}')")

    for fac in ordered:
        # choose display name for section:
        section_display = canonical_to_raw_full.get(fac, fac)
        parts.append(f"\\section*{{{escape_latex(section_display)}}}")
        parts.append(f"\\addcontentsline{{toc}}{{section}}{{{escape_latex(section_display)}}}")
        duties = assignments_by_fac.get(fac, [])
        if not duties:
            parts.append(r"\begin{itemize}[leftmargin=*]")
            parts.append(r"  \item No duties assigned.")
            parts.append(r"\end{itemize}")
            parts.append(r"\vspace{6pt}")
            parts.extend(_latex_grid_for_faculty([], dates_ordered, slot_order, session_ic_raw, fac, faculty_norm_map))
            continue

        duties_sorted = sorted(duties, key=lambda d: (d.get('Date',''), d.get('Slot',''), d.get('Room',''), d.get('Block','')))
        parts.append(r"\begin{itemize}[leftmargin=*]")
        for d in duties_sorted:
            date = escape_latex(d.get('Date',''))
            slot = escape_latex(d.get('Slot',''))
            room = escape_latex(d.get('Room',''))
            block = escape_latex(d.get('Block',''))
            sNo = (d.get('Course-sNo') or '').strip()
            note = d.get('Note','')
            info = course_info.get(sNo, {})
            code = escape_latex(info.get('course_code','') or '')
            cname = escape_latex(info.get('course_name','') or '')
            ic = escape_latex(info.get('ic','') or '')
            ic_mobile = escape_latex(info.get('ic_mobile','') or '')
            ic_room = escape_latex(info.get('ic_room','') or '')
            ic_cabin = escape_latex(info.get('ic_cabin','') or '')

            subj = f" -- {cname}" if cname else ""
            parts.append(f"  \\item {date}, {slot} --- Room {room} (Block {block}){subj}")
            ic_parts = []
            if ic:
                ic_parts.append(f"IC: {ic}")
            if ic_room:
                ic_parts.append(f"IC Room: {ic_room}")
            if ic_cabin:
                ic_parts.append(f"IC Cabin: {ic_cabin}")
            if ic_mobile:
                ic_parts.append(f"IC Mobile: {ic_mobile}")
            if note:
                ic_parts.append(f"Note: {note}")
            if ic_parts:
                parts.append("    \\\\" + ", ".join(ic_parts))
        parts.append(r"\end{itemize}")

        parts.extend(_latex_grid_for_faculty(duties, dates_ordered, slot_order, session_ic_raw, fac, faculty_norm_map))
        parts.append(r"\vspace{6pt}")

    parts.append(r"\end{document}")
    return "\n".join(parts)


def _latex_grid_for_faculty(duties, dates_ordered, slot_order, session_ic_raw, faculty_canonical_name, faculty_norm_map):
    rows = min(len(dates_ordered), MAX_DAYS)
    cols = len(slot_order)
    duty_grid = [[False]*cols for _ in range(rows)]
    ic_grid = [[False]*cols for _ in range(rows)]
    date_to_row = {d: idx for idx, d in enumerate(dates_ordered[:MAX_DAYS])}
    slot_to_col = {s: idx for idx, s in enumerate(slot_order)}

    # mark duties
    for d in duties:
        date = d.get('Date','').strip()
        slot = d.get('Slot','').strip()
        r_idx = date_to_row.get(date, None)
        c_idx = slot_to_col.get(slot, None)
        if r_idx is not None and c_idx is not None:
            duty_grid[r_idx][c_idx] = True

    # normalized canonical for this faculty_display_name
    fac_norm = faculty_norm_map.get(faculty_canonical_name, normalize_name_for_match(faculty_canonical_name))

    # mark ICs: only when normalized(schedule_ic) == fac_norm
    for (date, slot), ic_set in session_ic_raw.items():
        r_idx = date_to_row.get(date, None)
        c_idx = slot_to_col.get(slot, None)
        if r_idx is None or c_idx is None:
            continue
        for ic_raw in ic_set:
            ic_norm = normalize_name_for_match(ic_raw)
            matched = bool(ic_norm and fac_norm and ic_norm == fac_norm)
            if matched:
                ic_grid[r_idx][c_idx] = True
                eprint(f"[GRID-MATCH-exact] canonical='{faculty_canonical_name}' date={date} slot={slot} ic_raw='{ic_raw}' ic_norm='{ic_norm}' fac_norm='{fac_norm}'")
                break
            else:
                eprint(f"[GRID-NOMATCH-exact] canonical='{faculty_canonical_name}' date={date} slot={slot} ic_raw='{ic_raw}' ic_norm='{ic_norm}' fac_norm='{fac_norm}' -> no match")

    lines = []
    lines.append(r"\begin{flushleft}")
    lines.append(r"\textbf{Duty grid (rows = exam days, top = first date):}")
    lines.append(r"\end{flushleft}")
    col_spec = "|l|" + "c|" * cols
    lines.append(r"\begin{tabular}{" + col_spec + "}")
    lines.append(r"\hline")
    header_cells = ["Date \\ Slot"] + [escape_latex(s) for s in slot_order]
    lines.append(" & ".join(header_cells) + r" \\ \hline")
    for r_i in range(rows):
        date_label = escape_latex(dates_ordered[r_i])
        cells = [date_label]
        for c_i in range(cols):
            duty = duty_grid[r_i][c_i]
            ic = ic_grid[r_i][c_i]
            if duty and ic:
                # duty background (blue!40) with bold star
                cells.append(r"\cellcolor{blue!40}{\textbf{*}}")
            elif duty:
                # duty-only cell with blue background
                cells.append(r"\cellcolor{blue!40}~")
            elif ic:
                # IC-only cell: star on plain background
                cells.append(r"$\ast$")
            else:
                cells.append(r"")
        lines.append(" & ".join(cells) + r" \\ \hline")
    lines.append(r"\end{tabular}")
    return lines


def write_faculty_tex(tex_str, out_path):
    ensure_dir(out_path)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(tex_str)
    print(f"Wrote faculty duties LaTeX to: {out_path}")


# ----------------- main -----------------

def main():
    # load canonical faculty names and raw-full mapping
    faculty_list, faculty_norm_map, norm_to_canonical, canonical_to_raw_full = load_faculty_canonical(FACULTY_CSV)

    # load assignments and map Assigned-Faculty -> canonical where possible
    try:
        invig_assignments = load_assignments(ASSIGNMENTS_CSV, norm_to_canonical)
    except Exception as e:
        print(f"ERROR loading assignments: {e}")
        return

    # load schedule.csv
    course_info = load_course_info(SCHEDULE_CSV)

    # if faculty.csv absent, fall back to unique assigned names (these are used as both canonical and raw)
    if not faculty_list:
        s = set()
        for r in invig_assignments:
            if r.get('Assigned-Faculty'):
                s.add(r['Assigned-Faculty'])
        faculty_list = sorted(s)
        faculty_norm_map = {f: normalize_name_for_match(f) for f in faculty_list}
        # for display map, canonical==raw
        canonical_to_raw_full = {f: f for f in faculty_list}

    # determine dates: prefer schedule.csv dates if available else derive from assignments
    dates_from_schedule = sorted({info.get('date','') for info in course_info.values() if info.get('date')})
    if dates_from_schedule:
        dates_ordered = dates_from_schedule[:MAX_DAYS]
    else:
        dates = sorted({r.get('Date','').strip() for r in invig_assignments if r.get('Date','').strip()})
        dates_ordered = dates[:MAX_DAYS]

    # build LaTeX
    tex = build_faculty_tex(invig_assignments, course_info, faculty_list, faculty_norm_map, canonical_to_raw_full, dates_ordered, SLOT_ORDER)
    write_faculty_tex(tex, OUTPUT_FACULTY_TEX)

    # ASCII verification (concise)
    print("\n=== Day×Slot grids (rows = exam days) ===")
    print(f"Using dates (rows): {dates_ordered}")
    print(f"Using slots (columns): {SLOT_ORDER}")
    date_to_row = {d: idx for idx, d in enumerate(dates_ordered)}
    slot_to_col = {s: idx for idx, s in enumerate(SLOT_ORDER)}
    rows = max(1, len(dates_ordered))
    cols = len(SLOT_ORDER)

    # rebuild session ic raw
    session_ic_raw = defaultdict(set)
    for sNo, info in course_info.items():
        d = info.get('date','').strip(); s = info.get('slot','').strip(); ic = info.get('ic','').strip()
        if d and s and ic:
            session_ic_raw[(d,s)].add(ic)

    # print ASCII grids for canonical faculty_list (display canonical name)
    for fac in faculty_list:
        display_full = canonical_to_raw_full.get(fac, fac)
        duty_grid = [[False]*cols for _ in range(rows)]
        ic_grid = [[False]*cols for _ in range(rows)]
        for r in invig_assignments:
            if r.get('Assigned-Faculty','').strip() != fac:
                continue
            d = r.get('Date','').strip(); s = r.get('Slot','').strip()
            ri = date_to_row.get(d, None); ci = slot_to_col.get(s, None)
            if ri is not None and ci is not None:
                duty_grid[ri][ci] = True
        fac_norm = faculty_norm_map.get(fac, normalize_name_for_match(fac))
        for (d,s), ics in session_ic_raw.items():
            ri = date_to_row.get(d, None); ci = slot_to_col.get(s, None)
            if ri is None or ci is None:
                continue
            for ic_raw in ics:
                ic_norm = normalize_name_for_match(ic_raw)
                if ic_norm and fac_norm and ic_norm == fac_norm:
                    ic_grid[ri][ci] = True
                    break

        print(f"\nFaculty: {display_full}")
        print("    " + " ".join([f"{i+1}:{c}" for i,c in enumerate(SLOT_ORDER)]))
        for r_i in range(rows):
            row_label = f"{r_i+1}:{dates_ordered[r_i] if r_i < len(dates_ordered) else ''}"
            cells = []
            for c_i in range(cols):
                duty = duty_grid[r_i][c_i]; ic = ic_grid[r_i][c_i]
                if duty and ic:
                    cells.append("*█")
                elif duty:
                    cells.append("█")
                elif ic:
                    cells.append("*")
                else:
                    cells.append(".")
            print(f"{row_label:24} {' '.join(cells)}")

    total = len(invig_assignments)
    assigned = sum(1 for r in invig_assignments if r.get('Assigned-Faculty'))
    unassigned = total - assigned
    print(f"\nSummary: total blocks {total}, assigned {assigned}, unassigned {unassigned}")


if __name__ == '__main__':
    main()
