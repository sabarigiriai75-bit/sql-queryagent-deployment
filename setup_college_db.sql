-- =============================================================
-- SQL Query Agent — MySQL Setup Script
-- Run this as root in MySQL Workbench or the MySQL CLI
-- =============================================================

-- Step 1: Create the database
CREATE DATABASE IF NOT EXISTS college_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE college_db;

-- Step 2: Create tables
CREATE TABLE IF NOT EXISTS students (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    name             VARCHAR(100) NOT NULL,
    department       VARCHAR(50)  NOT NULL,
    cgpa             DECIMAL(3,1) NOT NULL,
    email            VARCHAR(150),
    graduation_year  INT
);

CREATE TABLE IF NOT EXISTS courses (
    id           INT AUTO_INCREMENT PRIMARY KEY,
    course_name  VARCHAR(150) NOT NULL,
    department   VARCHAR(50)  NOT NULL,
    credits      INT          NOT NULL
);

CREATE TABLE IF NOT EXISTS enrollments (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    student_id INT NOT NULL,
    course_id  INT NOT NULL,
    grade      VARCHAR(5),
    FOREIGN KEY (student_id) REFERENCES students(id),
    FOREIGN KEY (course_id)  REFERENCES courses(id)
);

-- Step 3: Seed students
INSERT INTO students (name, department, cgpa, email, graduation_year) VALUES
    ('Aarav Sharma',  'CSE',  9.2, 'aarav@college.edu',   2025),
    ('Ananya Roy',    'CSE',  8.8, 'ananya@college.edu',  2025),
    ('Rohan Mehta',   'ECE',  7.9, 'rohan@college.edu',   2026),
    ('Priya Patel',   'EEE',  8.5, 'priya@college.edu',   2025),
    ('Vikram Singh',  'MECH', 6.9, 'vikram@college.edu',  2026),
    ('Sneha Gupta',   'CSE',  9.5, 'sneha@college.edu',   2024),
    ('Karthik Raja',  'ECE',  8.1, 'karthik@college.edu', 2025);

-- Step 4: Seed courses
INSERT INTO courses (course_name, department, credits) VALUES
    ('Database Management Systems', 'CSE',  4),
    ('Artificial Intelligence',     'CSE',  4),
    ('Digital Signal Processing',   'ECE',  3),
    ('Power Electronics',           'EEE',  4),
    ('Thermodynamics',              'MECH', 3);

-- Step 5: Seed enrollments
INSERT INTO enrollments (student_id, course_id, grade) VALUES
    (1, 1, 'A'),
    (1, 2, 'A+'),
    (2, 1, 'B+'),
    (3, 3, 'A'),
    (4, 4, 'B'),
    (5, 5, 'C+'),
    (6, 2, 'A+'),
    (7, 3, 'B+');

-- Step 6: Create read-only user for the app
CREATE USER IF NOT EXISTS 'queryagent_user'@'localhost'
    IDENTIFIED BY 'StrongPassword123!';

GRANT SELECT ON college_db.* TO 'queryagent_user'@'localhost';

FLUSH PRIVILEGES;

-- Step 7: Verify everything worked
SELECT 'college_db created successfully!' AS status;
SHOW TABLES;
SELECT COUNT(*) AS student_count FROM students;
