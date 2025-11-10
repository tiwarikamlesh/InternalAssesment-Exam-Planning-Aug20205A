<?php
/**
 * csv_utils.php
 * --------------
 * Utility functions for safe reading and writing of CSV files
 * using file-level locks to prevent simultaneous write conflicts.
 */

/**
 * Safely read a CSV file and return an array of rows.
 * Each row is an array of values.
 */
function safe_csv_read($path) {
    $rows = [];
    if (!file_exists($path)) {
        return $rows;  // return empty if file doesn't exist
    }

    $handle = fopen($path, 'r');
    if ($handle === false) {
        return $rows;
    }

    if (flock($handle, LOCK_SH)) { // shared lock for reading
        while (($row = fgetcsv($handle, 0, ',', '"', "\\")) !== false) {
            $rows[] = $row;
        }
        flock($handle, LOCK_UN);
    }
    fclose($handle);
    return $rows;
}

/**
 * Safely write all rows to a CSV file atomically.
 * Overwrites the file content.
 */
function safe_csv_write($path, $rows) {
    $temp = $path . '.tmp';
    $handle = fopen($temp, 'w');
    if ($handle === false) return false;

    if (flock($handle, LOCK_EX)) { // exclusive lock for writing
        foreach ($rows as $row) {
            fputcsv($handle, $row);
        }
        fflush($handle);
        flock($handle, LOCK_UN);
    }
    fclose($handle);

    // Atomic rename to avoid partial writes
    rename($temp, $path);
    return true;
}

/**
 * Safely append a single row to a CSV file.
 */
function safe_csv_append($path, $row) {
    $handle = fopen($path, 'a');
    if ($handle === false) return false;

    if (flock($handle, LOCK_EX)) {
        fputcsv($handle, $row);
        fflush($handle);
        flock($handle, LOCK_UN);
    }
    fclose($handle);
    return true;
}
?>
