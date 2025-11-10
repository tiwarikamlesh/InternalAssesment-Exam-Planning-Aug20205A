#!/usr/bin/env python3
"""
schedule_exams_rooms_use_both.py

Greedy scheduler that assigns students to room blocks (A/B) for each Test-Date + Test-Slot.

Behavior:
 - Deletes any existing 'schedule' directory at start, then recreates it.
 - Outputs CSVs into folder 'schedule'
 - For each course, the scheduler considers BOTH A and B blocks when placing students,
   preferring blocks with larger remaining capacity, while ensuring A and B of the same room
   host different courses.
"""

import os
import csv
import re
import shutil
from collections import defaultdict, deque
from datetime import datetime
import pandas as pd

# --- Configurable filenames ---
SCHEDULE_CSV = "schedule.csv"
STUDENTS_CSV = "students.csv"
ROOMS_CSV = "rooms.csv"
OUT_DIR = "schedule"  # folder where CSV outputs will be written

# --- Helpers -----------------------------------------------------------------


def safe_str(x):
    return "" if pd.isna(x) else str(x).strip()


def parse_tests_field(tests_field: str):
    if not tests_field:
        return []
    return [t.strip() for t in str(tests_field).split(",") if t.strip()]


def normalize_date(s: str):
    if pd.isna(s) or s is None:
        return "unknown_date"
    s0 = str(s).strip().replace("Sept", "Sep")
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s0, fmt)
            return dt.strftime("%Y%m%d")
        except Exception:
            pass
    return re.sub(r"[^0-9A-Za-z_-]", "_", s0)


# --- Read input files -------------------------------------------------------


def load_rooms(rooms_csv_path: str):
    df = pd.read_csv(rooms_csv_path, dtype=str)
    rows = []
    for _, r in df.iterrows():
        room_name = safe_str(r.get("Class room")) or safe_str(r.get("Classroom")) or safe_str(r.get("Class"))
        a_seats = int(float(safe_str(r.get("A-seats") or r.get("A_seats") or 0) or 0))
        b_seats = int(float(safe_str(r.get("B-seats") or r.get("B_seats") or 0) or 0))
        rows.append({"room": room_name, "A": a_seats, "B": b_seats})
    rows.sort(key=lambda x: (x["A"] + x["B"]), reverse=True)
    return rows


def load_students(students_csv_path: str):
    df = pd.read_csv(students_csv_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    students = []
    for _, row in df.iterrows():
        eligible = safe_str(row.get("eligible")) or "1"
        if eligible not in ("1", "True", "TRUE", "true"):
            continue
        usn = safe_str(row.get("USN"))
        branch = safe_str(row.get("BRANCH"))
        sem = safe_str(row.get("SEM"))
        sec = safe_str(row.get("SEC"))
        tests = parse_tests_field(safe_str(row.get("tests")))
        students.append(
            {"USN": usn, "BRANCH": branch, "SEM": sem, "SEC": sec, "tests": tests}
        )
    return students


def load_schedule(schedule_csv_path: str):
    df = pd.read_csv(schedule_csv_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    mapping = defaultdict(list)
    for _, row in df.iterrows():
        date = safe_str(row.get("Test-Date"))
        slot = safe_str(row.get("Test-Slot"))
        sNo = safe_str(row.get("sNo"))
        code = safe_str(row.get("Course-Code"))
        name = safe_str(row.get("Course-Name"))
        programs = safe_str(row.get("Common for Programs"))
        faculty = safe_str(row.get("Course-Coordinator-Name"))
        roomnum = safe_str(row.get("RoomNumber"))
        cabin = safe_str(row.get("CabinNumber"))
        mapping[(date, slot)].append(
            {
                "sNo": sNo,
                "code": code,
                "name": name,
                "programs": programs,
                "faculty": faculty,
                "roomnum": roomnum,
                "cabin": cabin,
            }
        )
    return mapping


# --- Scheduler --------------------------------------------------------------


def schedule_for_slot_use_both(date, slot, courses, students, rooms):
    """Consider both A and B blocks when assigning students; prefer blocks with largest remaining capacity."""
    course_students = {}
    for c in courses:
        sno = c["sNo"]
        usns = [s["USN"] for s in students if sno in s["tests"]]
        course_students[sno] = deque(usns)

    total_seats = sum(r["A"] + r["B"] for r in rooms)
    total_students_needed = sum(len(course_students[s]) for s in course_students)
    if total_students_needed > total_seats:
        raise RuntimeError(
            f"Insufficient seats for {date} {slot}: need {total_students_needed}, have {total_seats}"
        )

    room_blocks = []
    for r in rooms:
        room_blocks.append(
            {
                "room": r["room"],
                "A": {"sNo": None, "capacity": r["A"], "assigned": []},
                "B": {"sNo": None, "capacity": r["B"], "assigned": []},
            }
        )

    course_order = sorted(list(course_students.keys()), key=lambda s: len(course_students[s]), reverse=True)

    for sno in course_order:
        while course_students[sno]:
            candidates = []
            for ri, rb in enumerate(room_blocks):
                for bk in ("A", "B"):
                    block = rb[bk]
                    other_block = rb["B" if bk == "A" else "A"]
                    if other_block["sNo"] is not None and other_block["sNo"] == sno:
                        continue
                    cap_left = block["capacity"] - len(block["assigned"])
                    if cap_left <= 0:
                        continue
                    candidates.append((ri, bk, cap_left))
            if not candidates:
                raise RuntimeError(
                    f"Unable to place all students for course {sno} on {date} {slot}: remaining {len(course_students[sno])}"
                )
            candidates.sort(key=lambda x: x[2], reverse=True)
            ri, bk, cap_left = candidates[0]
            block = room_blocks[ri][bk]
            take = min(cap_left, len(course_students[sno]))
            for _ in range(take):
                usn = course_students[sno].popleft()
                block["assigned"].append({"USN": usn, "sNo": sno})
            if block["sNo"] is None and block["assigned"]:
                block["sNo"] = sno

    assignments = []
    for rb in room_blocks:
        for bk in ("A", "B"):
            block = rb[bk]
            cap = block["capacity"]
            assigned_list = block["assigned"]
            for i in range(cap):
                seat_no = i + 1
                if i < len(assigned_list):
                    rec = assigned_list[i]
                    course_entry = next((c for c in courses if c["sNo"] == rec["sNo"]), None)
                    course_code = course_entry["code"] if course_entry else ""
                    assignments.append(
                        {
                            "Date": date,
                            "Slot": slot,
                            "Room": rb["room"],
                            "Block": bk,
                            "SeatNo": seat_no,
                            "USN": rec["USN"],
                            "Course-sNo": rec["sNo"],
                            "Course-Code": course_code,
                        }
                    )
                else:
                    assignments.append(
                        {
                            "Date": date,
                            "Slot": slot,
                            "Room": rb["room"],
                            "Block": bk,
                            "SeatNo": seat_no,
                            "USN": "",
                            "Course-sNo": "",
                            "Course-Code": "",
                        }
                    )
    return assignments


# --- Main -------------------------------------------------------------------


def main():
    # Start fresh: delete and recreate output dir
    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    rooms = load_rooms(ROOMS_CSV)
    students = load_students(STUDENTS_CSV)
    schedule_map = load_schedule(SCHEDULE_CSV)

    for (date, slot), courses in schedule_map.items():
        print(f"\nScheduling for Date='{date}' Slot='{slot}' ...")
        sNo_set = {c["sNo"] for c in courses}
        students_in_slot = [s for s in students if any(t in sNo_set for t in s["tests"])]
        print(f"  Number of students to schedule in this slot: {len(students_in_slot)}")
        total_capacity = sum(r["A"] + r["B"] for r in rooms)
        print(f"  Total available seats: {total_capacity}")
        if len(students_in_slot) > total_capacity:
            print(f"  ERROR: Need {len(students_in_slot)} seats but only {total_capacity} are available. Skipping this slot.")
            continue
        try:
            assignments = schedule_for_slot_use_both(date, slot, courses, students_in_slot, rooms)
        except RuntimeError as e:
            print(f"  ERROR while scheduling: {e}")
            continue

        date_slug = normalize_date(date)
        slot_slug = slot.replace(" ", "_")
        out_file = os.path.join(OUT_DIR, f"assignments_{date_slug}_{slot_slug}.csv")
        fieldnames = ["Date", "Slot", "Room", "Block", "SeatNo", "USN", "Course-sNo", "Course-Code"]
        with open(out_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for rec in assignments:
                w.writerow(rec)
        print(f"  Wrote assignment CSV: {out_file}")
        summary = defaultdict(int)
        for rec in assignments:
            if rec["USN"]:
                summary[rec["Course-sNo"]] += 1
        print("  Assigned students per test:")
        for c in courses:
            sno = c["sNo"]
            print(f"    {sno} ({c['code']}): {summary.get(sno,0)}")

    print("\nScheduling finished. All outputs are in the folder:", OUT_DIR)


if __name__ == "__main__":
    main()
