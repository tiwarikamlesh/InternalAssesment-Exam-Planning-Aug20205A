#!/usr/bin/env python3
"""
fresh_allocate_and_report_v2.py

Same as the 'fresh' allocator discussed previously, but Multi-room IC rule
applies only when a course occupies > 2 rooms in the same (date,slot).

Outputs:
 - schedule/invigilation_assignments.csv
 - faculty_duties.tex (grid uses blue!40 for duty cells; '*' for IC cells)

Usage:
    python3 fresh_allocate_and_report_v2.py
"""

import os
import glob
import csv
import re
from collections import defaultdict, Counter, OrderedDict

# ---------- Configuration ----------
ASSIGNMENTS_DIR = "schedule"
SCHEDULE_CSV = "schedule.csv"
FACULTY_CSV = "faculty.csv"
OUTPUT_INVIG_CSV = os.path.join(ASSIGNMENTS_DIR, "invigilation_assignments.csv")
OUTPUT_FACULTY_TEX = "faculty_duties.tex"

SLOT_ORDER = ["Slot-1", "Slot-2", "Slot-3", "Slot-4"]
ADJACENT = {"Slot-1": {"Slot-2"}, "Slot-2": {"Slot-1", "Slot-3"}, "Slot-3": {"Slot-2", "Slot-4"}, "Slot-4": {"Slot-3"}}
MAX_DAYS = 5

# ---------- Utilities ----------

def ensure_dir(path):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d, exist_ok=True)

def clean_spaces(s):
    if s is None:
        return ""
    return re.sub(r'[\u00A0\u2000-\u200B\u202F\u205F\u3000]', ' ', str(s))

def canonicalize_raw_name(raw):
    """Strip bracketed titles and trailing mobile numbers; trim."""
    if not raw:
        return ""
    s = clean_spaces(raw).strip()
    if '[' in s:
        s = s.split('[',1)[0].strip()
    s = re.sub(r'\s+\d{6,}$', '', s).strip()
    s = re.sub(r'\s+', ' ', s)
    return s

def normalize_for_match(n):
    """Lowercase, remove honorifics and punctuation for robust matching."""
    if not n:
        return ""
    s = clean_spaces(n)
    s = re.sub(r'\[.*?\]', '', s)
    s = re.sub(r'\b(dr|mr|ms|mrs|prof|professor)\b', '', s, flags=re.I)
    s = re.sub(r'[^A-Za-z0-9\s]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip().lower()
    return s

# ---------- Loaders ----------

def load_faculty_csv(path):
    """Return list of full display strings (order preserved) and mappings."""
    display_list = []
    norm_to_display = {}
    display_to_norm = {}
    if not os.path.exists(path):
        return display_list, norm_to_display, display_to_norm
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = (row.get('Name') or row.get('NAME') or row.get('name') or '').strip()
            if not raw:
                for v in row.values():
                    if v and v.strip():
                        raw = v.strip()
                        break
            if not raw:
                continue
            display = raw
            canon = canonicalize_raw_name(display)
            norm = normalize_for_match(canon or display)
            if not norm:
                continue
            if norm not in norm_to_display:
                display_list.append(display)
                norm_to_display[norm] = display
                display_to_norm[display] = norm
    return display_list, norm_to_display, display_to_norm

def load_course_info(path):
    course_info = {}
    if not os.path.exists(path):
        print("Warning: schedule.csv not found.")
        return course_info
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            sNo = (r.get('sNo') or r.get('SNo') or r.get('sno') or '').strip()
            if not sNo:
                continue
            course_info[sNo] = {
                'course_code': (r.get('Course-Code') or r.get('Course Code') or '').strip(),
                'course_name': (r.get('Course-Name') or r.get('Course Name') or '').strip(),
                'ic_raw': (r.get('Course-Coordinator-Name') or r.get('Course Coordinator Name') or r.get('Course-Coordinator') or r.get('Coordinator') or '').strip(),
                'ic_mobile': (r.get('Contact-No') or r.get('Contact No') or r.get('Contact') or '').strip(),
                'ic_room': (r.get('RoomNumber') or r.get('Room Number') or r.get('Room') or '').strip(),
                'ic_cabin': (r.get('CabinNumber') or r.get('Cabin Number') or r.get('Cabin') or '').strip(),
                'date_raw': (r.get('Test-Date') or r.get('Test Date') or r.get('Date') or '').strip(),
                'slot': (r.get('Test-Slot') or r.get('Test Slot') or r.get('Slot') or '').strip(),
            }
    return course_info

def read_assignments_dir(assignments_dir):
    """Read schedule/assignments_*.csv and count student-present blocks"""
    pattern = os.path.join(assignments_dir, "assignments_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        print("No assignment CSVs found in", assignments_dir)
        return {}, [], files
    block_counts = defaultdict(int)
    for fn in files:
        with open(fn, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for r in reader:
                date = (r.get('Date') or '').strip()
                slot = (r.get('Slot') or '').strip()
                sNo = (r.get('Course-sNo') or r.get('sNo') or r.get('Course') or '').strip()
                room = (r.get('Room') or '').strip()
                block = (r.get('Block') or '').strip()
                usn = (r.get('USN') or '').strip()
                if not date or not slot or not sNo or not room or not block:
                    continue
                if usn:
                    key = (date, slot, sNo, room, block)
                    block_counts[key] += 1
    session_blocks = defaultdict(list)
    for (date, slot, sNo, room, block), cnt in block_counts.items():
        session_blocks[(date, slot)].append({'sNo': sNo, 'room': room, 'block': block, 'count': cnt})
    return block_counts, session_blocks, files

# ---------- Allocation algorithm ----------

def build_ic_block_map(course_info):
    """
    Returns:
      sNo_ic_norm: mapping sNo -> ic_norm
      session_ic_raw: mapping (date,slot) -> set(raw ic names)
      ic_blocked_slots: mapping ic_norm -> set((date,slot)) which includes adjacent slots
    """
    sNo_ic_norm = {}
    session_ic_raw = defaultdict(set)
    ic_blocked_slots = defaultdict(set)

    for sNo, info in course_info.items():
        ic_raw = info.get('ic_raw','').strip()
        if not ic_raw:
            sNo_ic_norm[sNo] = ""
            continue
        ic_canon = canonicalize_raw_name(ic_raw)
        ic_norm = normalize_for_match(ic_canon)
        sNo_ic_norm[sNo] = ic_norm
        date = info.get('date_raw','').strip()
        slot = info.get('slot','').strip()
        if date and slot:
            session_ic_raw[(date, slot)].add(ic_raw)
            ic_blocked_slots[ic_norm].add((date, slot))
            for adj in ADJACENT.get(slot, set()):
                ic_blocked_slots[ic_norm].add((date, adj))

    return sNo_ic_norm, session_ic_raw, ic_blocked_slots

def allocate_strict(block_counts, session_blocks, course_info, norm_order, norm_to_display):
    """Greedy strict allocation. Multi-room IC rule applied only when course occupies > 2 rooms."""
    invig = []
    faculty_load = Counter()
    assigned_slots = defaultdict(set)

    sNo_ic_norm, session_ic_raw, ic_blocked_slots = build_ic_block_map(course_info)

    sessions = sorted(session_blocks.keys(), key=lambda x: (x[0], SLOT_ORDER.index(x[1]) if x[1] in SLOT_ORDER else 999))
    for (date,slot) in sessions:
        blocks = sorted(session_blocks[(date,slot)], key=lambda b: (b['room'], b['block'], b['sNo']))
        for b in blocks:
            sNo = b['sNo']; room = b['room']; block = b['block']; cnt = int(b.get('count',0) or 0)
            if cnt <= 0:
                invig.append({'Date': date, 'Slot': slot, 'Course-sNo': sNo, 'Room': room, 'Block': block, 'Assigned-Faculty': '', 'Note': 'no-students'})
                continue

            eligible = []
            for norm in norm_order:
                if (date,slot) in assigned_slots[norm]:
                    continue
                if (date,slot) in ic_blocked_slots.get(norm, set()):
                    continue
                conflict = False
                for adj in ADJACENT.get(slot, set()):
                    if (date, adj) in assigned_slots[norm]:
                        conflict = True; break
                if conflict:
                    continue

                ic_norm_course = sNo_ic_norm.get(sNo,'')
                if ic_norm_course and norm and (ic_norm_course == norm or ic_norm_course in norm or norm in ic_norm_course):
                    # NEW: multi-room rule triggers only when course uses > 2 rooms
                    room_count = len({rb['room'] for rb in session_blocks.get((date,slot),[]) if rb['sNo']==sNo})
                    if room_count > 2:
                        continue
                eligible.append(norm)

            non_ic = []
            ic_cands = []
            ic_norm_course = sNo_ic_norm.get(sNo,'')
            for norm in eligible:
                if ic_norm_course and norm and (ic_norm_course == norm or ic_norm_course in norm or norm in ic_norm_course):
                    ic_cands.append(norm)
                else:
                    non_ic.append(norm)
            candidates = non_ic if non_ic else ic_cands

            chosen = None
            if candidates:
                chosen = sorted(candidates, key=lambda n: (faculty_load.get(n,0), n))[0]

            if chosen:
                assigned_slots[chosen].add((date,slot))
                faculty_load[chosen] += 1
                invig.append({'Date': date, 'Slot': slot, 'Course-sNo': sNo, 'Room': room, 'Block': block, 'Assigned-Faculty': norm_to_display.get(chosen, chosen), 'Note': ''})
            else:
                invig.append({'Date': date, 'Slot': slot, 'Course-sNo': sNo, 'Room': room, 'Block': block, 'Assigned-Faculty': '', 'Note': 'unassigned-strict'})

    return invig, assigned_slots, faculty_load, sNo_ic_norm, session_ic_raw, ic_blocked_slots

# ---------- One-hop shift ----------

def attempt_one_hop_shifts(invig_assignments, assigned_slots, faculty_load, norm_order, norm_to_display, sNo_ic_norm, ic_blocked_slots, session_blocks):
    session_map = defaultdict(list)
    for a in invig_assignments:
        session_map[(a['Date'], a['Slot'])].append(a)

    def has_adj_conflict(assigned_set):
        by_date = defaultdict(set)
        for d,s in assigned_set:
            by_date[d].add(s)
        for d, slots in by_date.items():
            for s in slots:
                for a in ADJACENT.get(s, set()):
                    if a in slots:
                        return True
        return False

    resolved = []
    for idx, a in enumerate(invig_assignments):
        if a.get('Assigned-Faculty'):
            continue
        date = a['Date']; slot = a['Slot']; sNo = a['Course-sNo']
        possible_candidates = []
        for norm in norm_order:
            if (date,slot) in assigned_slots.get(norm,set()):
                continue
            if (date,slot) in ic_blocked_slots.get(norm,set()):
                continue
            ic_norm_course = sNo_ic_norm.get(sNo,'')
            if ic_norm_course and norm and (ic_norm_course==norm or ic_norm_course in norm or norm in ic_norm_course):
                room_count = len({rb['room'] for rb in session_blocks.get((date,slot),[]) if rb['sNo']==sNo})
                if room_count > 2:
                    continue
            has_neighbor = False
            for adj in ADJACENT.get(slot, set()):
                if (date,adj) in assigned_slots.get(norm,set()):
                    has_neighbor = True
            if has_neighbor:
                possible_candidates.append(norm)

        for cand in possible_candidates:
            blocking_adjs = [adj for adj in ADJACENT.get(slot, set()) if (date,adj) in assigned_slots.get(cand,set())]
            for adj_slot in blocking_adjs:
                target_obj = None
                for obj in session_map.get((date,adj_slot),[]):
                    fac_display = obj.get('Assigned-Faculty','').strip()
                    if not fac_display:
                        continue
                    tnorm = None
                    for n,dsp in norm_to_display.items():
                        if dsp==fac_display:
                            tnorm = n; break
                    if tnorm is None:
                        tnorm = normalize_for_match(canonicalize_raw_name(fac_display))
                    if tnorm == cand:
                        target_obj = obj
                        break
                if not target_obj:
                    continue

                target_sNo = target_obj.get('Course-sNo','')
                alt_found = None
                for alt in norm_order:
                    if alt == cand:
                        continue
                    if (date,adj_slot) in ic_blocked_slots.get(alt,set()):
                        continue
                    ic_norm_target = sNo_ic_norm.get(target_sNo,'')
                    if ic_norm_target and alt and (ic_norm_target==alt or ic_norm_target in alt or alt in ic_norm_target):
                        room_count_t = len({rb['room'] for rb in session_blocks.get((date,adj_slot),[]) if rb['sNo']==target_sNo})
                        if room_count_t > 2:
                            continue
                    if (date,adj_slot) in assigned_slots.get(alt,set()):
                        continue
                    tmp_alt_set = set(assigned_slots.get(alt,set()))
                    tmp_alt_set.add((date,adj_slot))
                    if has_adj_conflict(tmp_alt_set):
                        continue
                    tmp_cand_set = set(assigned_slots.get(cand,set()))
                    if (date,adj_slot) in tmp_cand_set:
                        tmp_cand_set.remove((date,adj_slot))
                    tmp_cand_set.add((date,slot))
                    if has_adj_conflict(tmp_cand_set):
                        continue
                    alt_found = alt
                    break
                if not alt_found:
                    continue

                # commit shift
                if (date,adj_slot) in assigned_slots.get(cand,set()):
                    assigned_slots[cand].remove((date,adj_slot))
                assigned_slots[alt_found].add((date,adj_slot))
                target_obj['Assigned-Faculty'] = norm_to_display.get(alt_found, alt_found)
                target_obj['Note'] = 'shifted-by-algo'

                assigned_slots[cand].add((date,slot))
                invig_assignments[idx]['Assigned-Faculty'] = norm_to_display.get(cand, cand)
                invig_assignments[idx]['Note'] = f'assigned-by-shift-from-{alt_found}'
                resolved.append((date,slot,cand,adj_slot,alt_found))
                break
            if invig_assignments[idx].get('Assigned-Faculty'):
                break
    return resolved

# ---------- Writers ----------

LATEX_ESC = {'&': r'\&','%': r'\%','$': r'\$','#': r'\#','_': r'\_','{': r'\{','}': r'\}','~': r'\textasciitilde{}','^': r'\textasciicircum{}','\\': r'\textbackslash{}'}
def escape_latex(s):
    if s is None:
        return ''
    s = str(s)
    s = s.replace('\\', LATEX_ESC['\\'])
    for ch, rep in LATEX_ESC.items():
        if ch == '\\': continue
        s = s.replace(ch, rep)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def write_invig_csv(invig, out_path):
    ensure_dir(out_path)
    fieldnames = ['Date','Slot','Course-sNo','Room','Block','Assigned-Faculty','Note']
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in invig:
            w.writerow(r)
    print("Wrote", out_path)

def latex_grid_for_fac(duties, dates_ordered, slot_order, session_ic_raw, faculty_display, norm_to_display):
    rows = min(MAX_DAYS, len(dates_ordered))
    cols = len(slot_order)
    date_to_row = {d:i for i,d in enumerate(dates_ordered[:MAX_DAYS])}
    slot_to_col = {s:i for i,s in enumerate(slot_order)}
    duty_grid = [[False]*cols for _ in range(rows)]
    ic_grid = [[False]*cols for _ in range(rows)]
    for d in duties:
        r = date_to_row.get(d.get('Date',''), None)
        c = slot_to_col.get(d.get('Slot',''), None)
        if r is not None and c is not None:
            duty_grid[r][c] = True
    fac_norm = normalize_for_match(canonicalize_raw_name(faculty_display))
    for (date,slot), rawset in session_ic_raw.items():
        r = date_to_row.get(date, None)
        c = slot_to_col.get(slot, None)
        if r is None or c is None: continue
        for ic_raw in rawset:
            ic_norm = normalize_for_match(canonicalize_raw_name(ic_raw))
            if not ic_norm or not fac_norm: continue
            if ic_norm == fac_norm or ic_norm in fac_norm or fac_norm in ic_norm:
                ic_grid[r][c] = True
                break
    lines = []
    lines.append(r'\begin{flushleft}')
    lines.append(r'\textbf{Duty grid (rows = exam days, top = first date):}')
    lines.append(r'\end{flushleft}')
    col_spec = "|l|" + "c|"*cols
    lines.append(r'\begin{tabular}{' + col_spec + '}')
    lines.append(r'\hline')
    header_cells = ["Date \\ Slot"] + [escape_latex(s) for s in slot_order]
    lines.append(" & ".join(header_cells) + r" \\ \hline")
    for ri in range(rows):
        date_label = escape_latex(dates_ordered[ri])
        cells = [date_label]
        for ci in range(cols):
            duty = duty_grid[ri][ci]
            ic = ic_grid[ri][ci]
            if duty and ic:
                cells.append(r'\cellcolor{blue!40}{\textbf{*}}')
            elif duty:
                cells.append(r'\cellcolor{blue!40}~')
            elif ic:
                cells.append(r'$\ast$')
            else:
                cells.append('')
        lines.append(" & ".join(cells) + r' \\ \hline')
    lines.append(r'\end{tabular}')
    return lines

def build_faculty_tex(invig, course_info, norm_order, norm_to_display, dates_ordered, slot_order):
    session_ic_raw = defaultdict(set)
    for sNo, info in course_info.items():
        d = info.get('date_raw','').strip()
        s = info.get('slot','').strip()
        ic_raw = info.get('ic_raw','').strip()
        if d and s and ic_raw:
            session_ic_raw[(d,s)].add(ic_raw)
    by_display = defaultdict(list)
    unassigned = []
    for r in invig:
        fac = r.get('Assigned-Faculty','').strip()
        if fac:
            by_display[fac].append(r)
        else:
            unassigned.append(r)
    ordered = [norm_to_display[n] for n in norm_order]
    seen = set(ordered)
    for disp in sorted(by_display.keys()):
        if disp not in seen:
            ordered.append(disp); seen.add(disp)
    parts = []
    parts.append(r'\documentclass[a4paper,11pt]{article}')
    parts.append(r'\usepackage[margin=0.7in]{geometry}')
    parts.append(r'\usepackage{enumitem}')
    parts.append(r'\usepackage{parskip}')
    parts.append(r'\usepackage[table]{xcolor}')
    parts.append(r'\usepackage{hyperref}')
    parts.append(r'\begin{document}')
    parts.append(r'\begin{center}')
    parts.append(r'\LARGE{Invigilation Duties — Faculty Roster}\\')
    parts.append(r'\vspace{6pt}')
    parts.append(r'\end{center}')
    parts.append(r'\tableofcontents')
    parts.append(r'\newpage')
    if unassigned:
        parts.append(r'\section*{Unassigned duties}')
        parts.append(r'\addcontentsline{toc}{section}{Unassigned duties}')
        parts.append(r'\begin{itemize}[leftmargin=*]')
        for r in unassigned:
            s = f"{escape_latex(r.get('Date',''))}, {escape_latex(r.get('Slot',''))} -- Room {escape_latex(r.get('Room',''))} (Block {escape_latex(r.get('Block',''))}) -- Course {escape_latex(r.get('Course-sNo',''))}"
            if r.get('Note'):
                s += f" — {escape_latex(r.get('Note'))}"
            parts.append(f'  \\item {s}')
        parts.append(r'\end{itemize}')
        parts.append(r'\vspace{6pt}')
    for disp in ordered:
        parts.append(r'\section*{' + escape_latex(disp) + '}')
        parts.append(r'\addcontentsline{toc}{section}{' + escape_latex(disp) + '}')
        duties = by_display.get(disp, [])
        if not duties:
            parts.append(r'\begin{itemize}[leftmargin=*]')
            parts.append(r'  \item No duties assigned.')
            parts.append(r'\end{itemize}')
            parts.append(r'\vspace{6pt}')
            parts.extend(latex_grid_for_fac([], dates_ordered, slot_order, session_ic_raw, disp, norm_to_display))
            continue
        duties_sorted = sorted(duties, key=lambda d: (d.get('Date',''), d.get('Slot',''), d.get('Room',''), d.get('Block','')))
        parts.append(r'\begin{itemize}[leftmargin=*]')
        for d in duties_sorted:
            date = escape_latex(d.get('Date','')); slot = escape_latex(d.get('Slot',''))
            room = escape_latex(d.get('Room','')); block = escape_latex(d.get('Block',''))
            sNo = d.get('Course-sNo',''); note = d.get('Note','')
            info = course_info.get(sNo, {})
            cname = escape_latex(info.get('course_name','') or '')
            ic = escape_latex(info.get('ic_raw','') or '')
            ic_room = escape_latex(info.get('ic_room','') or '')
            ic_cabin = escape_latex(info.get('ic_cabin','') or '')
            ic_mobile = escape_latex(info.get('ic_mobile','') or '')
            subj = f" -- {cname}" if cname else ""
            parts.append(f'  \\item {date}, {slot} --- Room {room} (Block {block}){subj}')
            ic_parts = []
            if ic: ic_parts.append(f'IC: {ic}')
            if ic_room: ic_parts.append(f'IC Room: {ic_room}')
            if ic_cabin: ic_parts.append(f'IC Cabin: {ic_cabin}')
            if ic_mobile: ic_parts.append(f'IC Mobile: {ic_mobile}')
            if note: ic_parts.append(f'Note: {note}')
            if ic_parts:
                parts.append('    \\\\' + ', '.join(ic_parts))
        parts.append(r'\end{itemize}')
        parts.extend(latex_grid_for_fac(duties, dates_ordered, slot_order, session_ic_raw, disp, norm_to_display))
        parts.append(r'\vspace{6pt}')
    parts.append(r'\end{document}')
    return '\n'.join(parts)

# ---------- Main flow ----------

def main():
    display_list, norm_to_display, display_to_norm = load_faculty_csv(FACULTY_CSV)
    course_info = load_course_info(SCHEDULE_CSV)
    block_counts, session_blocks, files = read_assignments_dir(ASSIGNMENTS_DIR)
    print("Processed files:", files)
    print("Blocks with students found:", sum(1 for k in block_counts))

    norm_order = list(norm_to_display.keys())
    if not norm_order:
        seen = set()
        for sNo, info in course_info.items():
            ic_raw = info.get('ic_raw','').strip()
            if not ic_raw: continue
            canon = canonicalize_raw_name(ic_raw)
            norm = normalize_for_match(canon)
            if norm and norm not in seen:
                seen.add(norm); norm_order.append(norm); norm_to_display[norm] = ic_raw

    invig, assigned_slots, faculty_load, sNo_ic_norm, session_ic_raw, ic_blocked_slots = allocate_strict(block_counts, session_blocks, course_info, norm_order, norm_to_display)
    initially_unassigned = [a for a in invig if not a.get('Assigned-Faculty')]
    print("Initially unassigned:", len(initially_unassigned))

    resolved = attempt_one_hop_shifts(invig, assigned_slots, faculty_load, norm_order, norm_to_display, sNo_ic_norm, ic_blocked_slots, session_blocks)
    print("Resolved by single-hop shifts:", len(resolved))

    remaining_unassigned = [a for a in invig if not a.get('Assigned-Faculty')]
    print("Remaining unassigned after shifts:", len(remaining_unassigned))

    write_invig_csv(invig, OUTPUT_INVIG_CSV)

    dates = []
    for sNo, info in course_info.items():
        d = info.get('date_raw','').strip()
        if d: dates.append(d)
    if not dates:
        dates = sorted({r.get('Date','') for r in invig if r.get('Date')})
    dates_ordered = list(OrderedDict.fromkeys(dates))[:MAX_DAYS]

    tex = build_faculty_tex(invig, course_info, norm_order, norm_to_display, dates_ordered, SLOT_ORDER)
    ensure_dir(OUTPUT_FACULTY_TEX)
    with open(OUTPUT_FACULTY_TEX, 'w', encoding='utf-8') as f:
        f.write(tex)
    print("Wrote", OUTPUT_FACULTY_TEX)

    total = len(invig)
    assigned = sum(1 for r in invig if r.get('Assigned-Faculty'))
    print(f"Summary: total blocks {total}, assigned {assigned}, unassigned {total-assigned}")
    if remaining_unassigned:
        print("Unassigned blocks (sample):")
        for r in remaining_unassigned[:20]:
            print(" ", r['Date'], r['Slot'], r['Course-sNo'], r['Room'], r['Block'])

if __name__ == '__main__':
    main()
