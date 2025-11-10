<?php
session_start();
require_once __DIR__ . '/includes/student_functions.php';

// Step 1: Security check — ensure this page is only accessible after first login
if (!isset($_SESSION['pending_usn'])) {
    header("Location: index.php");
    exit();
}

$usn = $_SESSION['pending_usn'];
$name = $_SESSION['pending_name'];
$error = "";
$success = "";

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $newpass = trim($_POST['newpass']);
    $confpass = trim($_POST['confpass']);

    if (strlen($newpass) < 6) {
        $error = "⚠️ Password must be at least 6 characters long.";
    } elseif ($newpass !== $confpass) {
        $error = "❌ Passwords do not match.";
    } elseif ($newpass === 'cse@ju2025') {
        $error = "⚠️ You must choose a new password (not the default one).";
    } else {
        // Step 2: Update CSV with new hashed password
        update_password($usn, $newpass);

        // Step 3: Promote to full login session
        $student = get_student_record($usn);
        $_SESSION['usn'] = $student['USN'];
        $_SESSION['name'] = $student['NAME'];
        $_SESSION['branch'] = $student['BRANCH'];
        $_SESSION['sem'] = $student['SEM'];
        $_SESSION['sec'] = $student['SEC'];

        // Step 4: Cleanup temporary session and redirect
        unset($_SESSION['pending_usn']);
        unset($_SESSION['pending_name']);

        header("Location: dashboard.php");
        exit();
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Change Password - First Login</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
</head>
<body class="bg-light">

<div class="container mt-5" style="max-width:420px;">
    <div class="card shadow-sm border-0">
        <div class="card-body">
            <h4 class="card-title text-center mb-3">🔑 First Login Password Change</h4>
            <p class="text-center text-muted">
                Welcome, <strong><?= htmlspecialchars($name) ?></strong><br>
                (USN: <?= htmlspecialchars($usn) ?>)
            </p>

            <?php if ($error): ?>
                <div class="alert alert-danger py-2"><?= htmlspecialchars($error) ?></div>
            <?php endif; ?>

            <form method="POST">
                <div class="mb-3">
                    <label class="form-label">New Password</label>
                    <input type="password" name="newpass" class="form-control" required minlength="6">
                </div>

                <div class="mb-3">
                    <label class="form-label">Confirm New Password</label>
                    <input type="password" name="confpass" class="form-control" required minlength="6">
                </div>

                <button class="btn btn-success w-100">Save and Continue</button>
            </form>

            <div class="text-muted small mt-3 text-center">
                Passwords must be at least 6 characters long.
            </div>
        </div>
    </div>
</div>

</body>
</html>
