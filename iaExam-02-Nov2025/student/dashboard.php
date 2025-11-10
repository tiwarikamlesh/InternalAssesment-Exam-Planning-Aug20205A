<?php
session_start();
require_once __DIR__ . '/includes/student_functions.php';

// Redirect if not logged in
if (!isset($_SESSION['usn'])) {
    header("Location: index.php");
    exit();
}

// Get student info and schedule
$usn = $_SESSION['usn'];
$name = $_SESSION['name'];
$branch = $_SESSION['branch'];
$sem = $_SESSION['sem'];
$sec = $_SESSION['sec'];

$schedule = get_student_schedule($usn);
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>My Exam Schedule</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
</head>
<body class="bg-light">

<nav class="navbar navbar-dark bg-primary">
    <div class="container-fluid">
        <span class="navbar-brand mb-0 h5">🎓 Student Portal</span>
        <span class="text-white small">
            <?= htmlspecialchars($name) ?> (<?= htmlspecialchars($usn) ?>)
            &nbsp; | &nbsp;
            <a href="logout.php" class="text-white text-decoration-none">Logout</a>
        </span>
    </div>
</nav>

<div class="container mt-4 mb-5">
    <div class="card shadow-sm border-0">
        <div class="card-body">
            <h5 class="card-title text-primary mb-3">My Examination Schedule</h5>

            <p class="text-muted mb-3">
                <strong>Branch:</strong> <?= htmlspecialchars($branch) ?> &nbsp;
                <strong>Semester:</strong> <?= htmlspecialchars($sem) ?> &nbsp;
                <strong>Section:</strong> <?= htmlspecialchars($sec) ?>
            </p>

            <?php if (empty($schedule)): ?>
                <div class="alert alert-info">No schedule available for you.</div>
            <?php else: ?>
                <table class="table table-bordered table-striped align-middle">
                    <thead class="table-dark">
                        <tr>
                            <th scope="col">Test ID</th>
                            <th scope="col">Course Code</th>
                            <th scope="col">Course Name</th>
                            <th scope="col">Date</th>
                            <th scope="col">Slot</th>
                            <th scope="col">Room</th>
                            <th scope="col">Seat (A/B)</th>
                        </tr>
                    </thead>
                    <tbody>
                    <?php foreach ($schedule as $row): ?>
                        <tr>
                            <td><?= htmlspecialchars($row['TestID']) ?></td>
                            <td><?= htmlspecialchars($row['CourseCode']) ?></td>
                            <td><?= htmlspecialchars($row['CourseName']) ?></td>
                            <td><?= htmlspecialchars($row['Date']) ?></td>
                            <td><?= htmlspecialchars($row['Slot']) ?></td>
                            <td><?= htmlspecialchars($row['Room']) ?></td>
                            <td><?= htmlspecialchars($row['SeatAB']) ?></td>
                        </tr>
                    <?php endforeach; ?>
                    </tbody>
                </table>
            <?php endif; ?>
        </div>
    </div>
</div>

<footer class="text-center text-muted small mb-4">
    &copy; <?= date('Y') ?> Examination System | CSV-backed portal
</footer>

</body>
</html>
