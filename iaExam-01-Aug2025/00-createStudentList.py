import csv
import os
import glob

input_folder = 'data'
output_file = 'students.csv'

# Find all CSV files in the data folder
csv_files = glob.glob(os.path.join(input_folder, '*.csv'))
print(f"Found {len(csv_files)} CSV file(s): {csv_files}\n")

# Define required columns and their possible variants
required_cols = {
    'sno': ['s.no.', 'sno'],
    'usn': ['usn'],
    'name': ['name'],
    'branch': ['branch'],
    'sem': ['sem'],
    'sec': ['sec', 'section'],
    'eligible': ['eligible']
}

# --- First: Sanity Check ---
all_ok = True
file_checks = {}

for file_path in csv_files:
    file_name = os.path.basename(file_path)
    print(f"Checking {file_name}...")
    
    with open(file_path, mode='r', newline='') as infile:
        reader = csv.DictReader(infile)
        
        if reader.fieldnames is None:
            print(f"  Error: No header found in {file_name}")
            all_ok = False
            file_checks[file_name] = ["No header found"]
            continue
        
        headers = [h.strip() for h in reader.fieldnames]
        headers_lower = [h.lower() for h in headers]
        header_map = {h.lower().strip(): h for h in headers}
        
        missing_cols = []
        
        for key, variants in required_cols.items():
            found = False
            for variant in variants:
                if variant in header_map:
                    found = True
                    break
            if not found:
                missing_cols.append(key)
        
        if missing_cols:
            all_ok = False
            file_checks[file_name] = missing_cols
        
    print()  # Blank line for readability

if not all_ok:
    print("Sanity check failed! Issues found in the following files:\n")
    for file_name, issues in file_checks.items():
        print(f"{file_name}: Missing columns {issues}")
    print("\nPlease fix these issues before running the script again.")
    exit(1)

print("Sanity check passed! All files have the required columns.\nProceeding with merging...\n")

# --- Second: Processing and merging ---
if os.path.exists(output_file):
    os.remove(output_file)
    print(f"{output_file} has been deleted.\n")

header_written = False

with open(output_file, mode='w', newline='') as outfile:
    writer = None
    
    for file_path in csv_files:
        file_name = os.path.basename(file_path)
        lines_appended = 0
        print(f"Processing {file_name}...")
        
        with open(file_path, mode='r', newline='') as infile:
            reader = csv.DictReader(infile)
            
            headers = [h.strip() for h in reader.fieldnames]
            headers_lower = [h.lower() for h in headers]
            header_map = {h.lower().strip(): h for h in headers}
            
            actual_cols = {}
            for key, variants in required_cols.items():
                for variant in variants:
                    if variant in header_map:
                        actual_cols[key] = header_map[variant]
                        break
            
            exclude_cols = set(actual_cols.values())
            test_columns = [h for h in headers if h not in exclude_cols]
            
            if not header_written:
                fieldnames = ['USN', 'NAME', 'BRANCH', 'SEM', 'SEC', 'eligible', 'tests']
                writer = csv.DictWriter(outfile, fieldnames=fieldnames)
                writer.writeheader()
                header_written = True
            
            for row in reader:
                row = {k.strip(): v.strip() for k, v in row.items()}
                test_names = [test for test in test_columns if row.get(test, '0') == '1']
                
                writer.writerow({
                    'USN': row.get(actual_cols['usn'], ''),
                    'NAME': row.get(actual_cols['name'], ''),
                    'BRANCH': row.get(actual_cols['branch'], ''),
                    'SEM': row.get(actual_cols['sem'], ''),
                    'SEC': row.get(actual_cols['sec'], ''),
                    'eligible': row.get(actual_cols['eligible'], ''),
                    'tests': ",".join(test_names)
                })
                lines_appended += 1
        
        print(f"Processed {file_name}: {lines_appended} line(s) appended.\n")

print(f"All files have been processed and {output_file} has been created.")
