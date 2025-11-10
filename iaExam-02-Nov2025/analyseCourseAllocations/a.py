import csv
from collections import defaultdict

allocation_file = "allocation.csv"
subjects_file = "subjects.csv"
output_file = "allocation_display_full.tex"

# Step 1: Load subjects.csv
subjects = {}
with open(subjects_file, newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        if len(row) < 6:
            continue
        code = row[1].strip()      # subject code
        full_name = row[3].strip() # subject full name
        semester = row[4].strip()  # semester
        lpte = row[5].strip()      # LTPE
        subjects[code] = {"name": full_name, "semester": semester, "lpte": lpte}

# Step 2: Read allocation.csv
allocations = []
course_faculty_map = defaultdict(set)  # map full course name -> set of faculty info
with open(allocation_file, newline='', encoding='utf-8') as csvfile:
    reader = csv.reader(csvfile)
    for row in reader:
        if len(row) < 5:
            continue
        program = row[2].strip()
        section = row[1].strip()
        faculty_name = row[4].strip()
        courses = [c.strip() for c in row[5:] if c.strip()]
        allocations.append({"faculty": faculty_name, "courses": courses, "program": program, "section": section})

        # Build mapping for courses to faculties
        for course in courses:
            subj_code = course[:-1] if course[-1].isalpha() else course
            if subj_code in subjects:
                course_name = subjects[subj_code]["name"]
            else:
                course_name = f"{course} - details not found"
            faculty_info = f"{faculty_name} ({program}-{section})"
            course_faculty_map[course_name].add(faculty_info)

# Step 3: Write LaTeX
with open(output_file, "w", encoding="utf-8") as f:
    f.write("\\documentclass{article}\n")
    f.write("\\usepackage[utf8]{inputenc}\n")
    f.write("\\begin{document}\n\n")
    
    # Main enumeration of faculties
    f.write("\\begin{enumerate}\n")
    for entry in allocations:
        f.write(f"\\item {entry['faculty']}\n")
        f.write("  \\begin{itemize}\n")
        for course in entry['courses']:
            subj_code = course[:-1] if course[-1].isalpha() else course
            if subj_code in subjects:
                info = subjects[subj_code]
                f.write(f"    \\item {course} - {info['name']}, Sem {info['semester']}, LTPE {info['lpte']}\n")
            else:
                f.write(f"    \\item {course} - details not found\n")
        f.write("  \\end{itemize}\n")
    f.write("\\end{enumerate}\n\n")

    # Course to faculty mapping
    f.write("\\section*{Course-wise Faculty List}\n")
    f.write("\\begin{enumerate}\n")
    for course_name, faculties in course_faculty_map.items():
        f.write(f"  \\item {course_name}\n")
        f.write("    \\begin{itemize}\n")
        for fac in sorted(faculties):
            f.write(f"      \\item {fac}\n")
        f.write("    \\end{itemize}\n")
    f.write("\\end{enumerate}\n")

    f.write("\\end{document}\n")

print(f"LaTeX file created with full course info and course-faculty mapping: {output_file}")

