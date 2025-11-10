<?php
session_start();
require_once __DIR__ . '/includes/student_functions.php';

// If already logged in, go straight to dashboard
if (isset($_SESSION['usn'])) {
    header("Location: dashboard.php");
    exit();
}

$error = "";

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $usn = strtoupper(trim($_POST['usn']));
    $password = trim($_POST['password']);

    $student = get_student_record($usn);
    if (!$student) {
        $error = "❌ Invalid USN.";
    } else {
        $status = verify_login($usn, $password);

        if ($status === 'invalid') {
            $error = "❌ Incorrect password.";
        } elseif ($status === 'first_login') {
            // Temporarily store USN for password change step
            $_SESSION['pending_usn'] = $usn;
            $_SESSION['pending_name'] = $student['NAME'];
            header("Location: change_password.php");
            exit();
        } elseif ($status === 'success') {
            $_SESSION['usn'] = $student['USN'];
            $_SESSION['name'] = $student['NAME'];
            $_SESSION['branch'] = $student['BRANCH'];
            $_SESSION['sem'] = $student['SEM'];
            $_SESSION['sec'] = $student['SEC'];
            header("Location: dashboard.php");
            exit();
        }
    }
}
?>
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Student Login</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
</head>
<body class="bg-light">

<div class="container mt-5" style="max-width:420px;">
    <div class="card shadow-sm border-0">
        <div class="card-body">
            <h4 class="card-title text-center mb-3">🎓 Student Login</h4>
            <?php if ($error): ?>
                <div class="alert alert-danger py-2"><?= htmlspecialchars($error) ?></div>
            <?php endif; ?>

            <form method="POST">
                <div class="mb-3">
                    <label class="form-label">USN</label>
                    <input type="text" name="usn" class="form-control" required placeholder="e.g. 24BTRCA001">
                </div>

                <div class="mb-3">
                    <label class="form-label">Password</label>
                    <input type="password" name="password" class="form-control" required placeholder="Enter your password">
                </div>

                <button class="btn btn-primary w-100">Login</button>
            </form>

            <div class="text-muted small mt-3 text-center">
                Default password: <code>cse@ju2025</code> (change on first login)
            </div>
        </div>
    </div>
</div>

</body>
</html>
