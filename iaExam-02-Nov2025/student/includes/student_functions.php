<?php
/**
 * student_functions.php
 * ---------------------
 * High-level helper functions for authentication, password management,
 * and schedule retrieval using CSV-based data.
 */

require_once __DIR__ . '/csv_utils.php';

/**
 * Get a student's complete record from students.csv
 * Returns associative array or null if not found.
 */
function get_student_record($usn) {
    $path = __DIR__ . '/../data/students.csv';
    $rows = safe_csv_read($path);

    // Skip header if present
    if (count($rows) > 0 && strtoupper(trim($rows[0][0])) == 'USN') {
        array_shift($rows);
    }

    foreach ($rows as $row) {
        if (trim($row[0]) == $usn) {

            // Parse quoted comma-separated tests safely
            $testField = isset($row[6]) ? trim($row[6]) : '';
            $testField = trim($testField, "\"'"); // remove surrounding quotes
            $tests = array_filter(array_map('trim', explode(',', $testField)));

            return [
                'USN'      => trim($row[0]),
                'NAME'     => trim($row[1]),
                'BRANCH'   => trim($row[2]),
                'SEM'      => trim($row[3]),
                'SEC'      => trim($row[4]),
                'ELIGIBLE' => trim($row[5]),
                'TESTS'    => $tests
            ];
        }
    }
    return null;
}

/**
 * Verify student login.
 * Returns: 'invalid' | 'first_login' | 'success'
 */
function verify_login($usn, $password) {
    $path = __DIR__ . '/../data/passwords.csv';
    $rows = safe_csv_read($path);

    foreach ($rows as $row) {
        if ($row[0] == $usn) {
            $hash = $row[1] ?? '';
            if ($hash !== '' && password_verify($password, $hash)) {
                return 'success';
            }
            return 'invalid';
        }
    }

    // First login case (no entry in passwords.csv)
    if ($password === 'cse@ju2025') {
        return 'first_login';
    }
    return 'invalid';
}

/**
 * Update or insert a student's password (hashed).
 */
function update_password($usn, $new_password) {
    $path = __DIR__ . '/../data/passwords.csv';
    $rows = safe_csv_read($path);
    $hash = password_hash($new_password, PASSWORD_DEFAULT);
    $updated = false;

    foreach ($rows as &$row) {
        if ($row[0] == $usn) {
            $row[1] = $hash;
            $updated = true;
            break;
        }
    }

    if (!$updated) {
        $rows[] = [$usn, $hash];
    }

    safe_csv_write($path, $rows);
}

/**
 * Read schedule.csv into a mapping of test ID → details.
 * Uses your 13-column structure.
 */
function get_schedule_map() {
    $path = __DIR__ . '/../data/schedule.csv';
    $rows = safe_csv_read($path);
    $map = [];

    // Remove header if present
    if (count($rows) > 0 && strtolower(trim($rows[0][0])) == 'sno') {
        array_shift($rows);
    }

    foreach ($rows as $row) {
        // Expect at least 13 columns: sNo through Test-Slot
        if (count($row) < 13) continue;

        $map[trim($row[0])] = [
            'CourseCode' => trim($row[1]),
            'CourseName' => trim($row[2]),
            'Date'       => trim($row[11]),
            'Slot'       => trim($row[12])
        ];
    }

    return $map;
}

/**
 * Get student's ROOM and BLOCK (A/B) for each test from assignments CSVs.
 * Returns: [ testId => ['Room' => 'Room-101', 'Block' => 'A'] , ... ]
 */
function get_student_roomblock($usn) {
    $dir = __DIR__ . '/../data/schedule/';
    $files = glob($dir . 'assignments_*.csv');
    $rbMap = [];

    foreach ($files as $file) {
        $rows = safe_csv_read($file);
        if (count($rows) == 0) continue;

        // Detect header row automatically
        $header = array_map('trim', $rows[0]);
        $startIndex = (isset($header[0]) && strtolower($header[0]) == 'date') ? 1 : 0;

        for ($i = $startIndex; $i < count($rows); $i++) {
            $r = $rows[$i];

            // Expected columns:
            // 0:Date, 1:Slot, 2:Room, 3:Block, 4:SeatNo, 5:USN, 6:Course-sNo, 7:Course-Code
            if (!isset($r[5]) || !isset($r[6]) || !isset($r[2]) || !isset($r[3])) continue;

            if (trim($r[5]) == $usn) {
                $testId = trim($r[6]);      // Course-sNo (Test ID)
                $room   = trim($r[2]);      // Room
                $block  = strtoupper(trim($r[3])); // Block A/B
                // Save only the first found mapping per testId
                if (!isset($rbMap[$testId])) {
                    $rbMap[$testId] = ['Room' => $room, 'Block' => $block];
                }
            }
        }
    }
    return $rbMap;
}

/**
 * Combine student's tests, schedule info, and ROOM/BLOCK (A/B).
 */
function get_student_schedule($usn) {
    $student = get_student_record($usn);
    if (!$student) return [];

    $tests = $student['TESTS'];
    $scheduleMap = get_schedule_map();
    $roomBlockMap = get_student_roomblock($usn);

    $final = [];
    foreach ($tests as $testId) {
        if (isset($scheduleMap[$testId])) {
            $info = $scheduleMap[$testId];
            $room = $roomBlockMap[$testId]['Room']  ?? '-';
            $seat = $roomBlockMap[$testId]['Block'] ?? '-'; // Seat shown as A/B only

            $final[] = [
                'TestID'     => $testId,
                'CourseCode' => $info['CourseCode'],
                'CourseName' => $info['CourseName'],
                'Date'       => $info['Date'],
                'Slot'       => $info['Slot'],
                'Room'       => $room,
                'SeatAB'     => $seat, // A or B only
            ];
        }
    }

    // Sort by Date and Slot
    usort($final, function($a, $b) {
        return strcmp($a['Date'] . $a['Slot'], $b['Date'] . $b['Slot']);
    });

    return $final;
}
?>
