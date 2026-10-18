import os
import unittest
from sqlalchemy import create_engine, text
from database import get_db
from db_manager import DatabaseManager
from sql_agent import (
    query_database,
    is_destructive,
    validate_sql,
    discover_schema,
    generate_schema_aware_sql,
    verify_active_database
)

class TestSQLAIAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = next(get_db())
        cls.manager = DatabaseManager(cls.db)
        
        # Discover connections in db
        all_dbs = cls.manager.get_user_databases("user1")
        cls.college_db = next((d for d in all_dbs if d["database"] == "college_database" and d["type"] == "mysql"), None)
        cls.sample_db = next((d for d in all_dbs if d["database"] == "sample_college.db" and d["type"] == "sqlite"), None)
        cls.office_db = next((d for d in all_dbs if d["database"] == "office_management_db" and d["type"] == "mysql"), None)
        
        assert cls.college_db is not None, "MySQL college_database connection must be registered in database_connections"

    # Test 1: Selecting MySQL college_database uses the correct connection and identifies active database
    def test_01_college_database_connection(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        eng = create_engine(cs)
        with eng.connect() as conn:
            active_db = verify_active_database(conn, "mysql", self.college_db["database"])
            self.assertEqual(active_db.lower(), "college_database")

    # Test 2: A count query against college_database.students returns 100
    def test_02_student_count_returns_100(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        res = query_database(
            connection_string=cs,
            question="How many students are in the database?",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"], f"Query failed: {res.get('result')}")
        self.assertIn("college_database", res.get("database_name", "").lower())
        self.assertEqual(res["row_count"], 1)
        count_val = list(res["rows"][0].values())[0]
        self.assertEqual(int(count_val), 100)

    # Test 3: A department grouping query returns department counts that sum to 100
    def test_03_department_grouping_sums_to_100(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        question = "Show the total number of students in each department, sorted from highest to lowest."
        res = query_database(
            connection_string=cs,
            question=question,
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"], f"Query failed: {res.get('result')}")
        self.assertIn("GROUP BY", res["executed_sql"].upper())
        self.assertIn("ORDER BY", res["executed_sql"].upper())
        self.assertIn("DESC", res["executed_sql"].upper())
        
        total_sum = 0
        for row in res["rows"]:
            for k, v in row.items():
                if k != "department":
                    total_sum += int(v)
        self.assertEqual(total_sum, 100)

    # Test 4: A CGPA filter generates a query with the correct department and CGPA conditions
    def test_04_cgpa_filter_conditions(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        question = "List CSE students with CGPA above 8.5"
        res = query_database(
            connection_string=cs,
            question=question,
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"], f"Query failed: {res.get('result')}")
        sql_upper = res["executed_sql"].upper()
        self.assertIn("CGPA", sql_upper)
        self.assertIn(">", sql_upper)
        self.assertIn("8.5", sql_upper)
        self.assertTrue("COMPUTER SCIENCE" in sql_upper or "CSE" in sql_upper)

    # Test 5: Selecting Sample College DB executes against SQLite, not MySQL
    def test_05_sample_college_db_executes_on_sqlite(self):
        if self.sample_db:
            cs = self.manager.get_connection_string(self.sample_db["id"])
            res = query_database(
                connection_string=cs,
                question="How many students are in the database?",
                expected_db_name=self.sample_db["database"],
                db_type=self.sample_db["type"],
                connection_id=self.sample_db["id"]
            )
            self.assertTrue(res["success"])
            count_val = list(res["rows"][0].values())[0]
            # Sample SQLite DB has 7 students, while MySQL has 100
            self.assertEqual(int(count_val), 7)
            self.assertNotEqual(int(count_val), 100)

    # Test 6: Selecting Office Management Database executes against its own configured connection
    def test_06_office_management_db_executes_on_its_own(self):
        if self.office_db:
            cs = self.manager.get_connection_string(self.office_db["id"])
            res = query_database(
                connection_string=cs,
                question="How many employees are in each department?",
                expected_db_name=self.office_db["database"],
                db_type=self.office_db["type"],
                connection_id=self.office_db["id"]
            )
            self.assertTrue(res["success"])
            self.assertEqual(res["database_name"].lower(), "office_management_db")
            self.assertIn("departments", res["executed_sql"].lower())
            self.assertIn("employees", res["executed_sql"].lower())

    # Test 7: Adding a connection does not duplicate existing connections
    def test_07_adding_connection_deduplicates(self):
        initial_count = len(self.manager.get_user_databases("user1"))
        # Add an identical connection to college_database
        res = self.manager.add_database(
            user_id="user1",
            db_name="College Database Reconnected",
            db_type=self.college_db["type"],
            host=self.college_db["host"],
            port=self.college_db["port"],
            username=self.college_db["username"],
            password=self.manager.get_connection(self.college_db["id"]).password,
            database=self.college_db["database"]
        )
        self.assertTrue(res["success"])
        after_count = len(self.manager.get_user_databases("user1"))
        self.assertEqual(initial_count, after_count, "Connection count should remain same due to deduplication")

    # Test 8: An invalid database password produces a clear, safe error
    def test_08_invalid_password_safe_error(self):
        res = self.manager.add_database(
            user_id="user1",
            db_name="Bad Password Test",
            db_type="mysql",
            host="localhost",
            port=3306,
            username="root",
            password="DefinitelyWrongPassword123!@#",
            database="college_database"
        )
        self.assertFalse(res["success"])
        self.assertIn("Connection failed", res["message"])
        self.assertNotIn("DefinitelyWrongPassword123!@#", res["message"])

    # Test 9: A missing table or column does not trigger a silent fallback to another database
    def test_09_missing_table_returns_clear_error(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        # college_database has no employees or salary table
        res = query_database(
            connection_string=cs,
            question="Show employees earning more than 70000",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertFalse(res["success"])
        self.assertIn("does not contain an 'employees' table", res["result"])
        # Must not fabricate a SELECT * FROM students query
        self.assertNotIn("SELECT * FROM students LIMIT 50", res.get("executed_sql") or "")

    # Test 10: The SQL displayed on dashboard matches the SQL actually executed
    def test_10_sql_matches_executed(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        res = query_database(
            connection_string=cs,
            question="Show the total number of students in each department, sorted from highest to lowest.",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"])
        self.assertIsNotNone(res.get("executed_sql"))
        self.assertIn(res["executed_sql"], res["result"])

    # Test 11: Query results correspond to the selected database and executed SQL
    def test_11_results_correspond_to_selected_database(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        res = query_database(
            connection_string=cs,
            question="Show all students limit 5",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"])
        self.assertEqual(res["database_name"].lower(), "college_database")
        self.assertEqual(len(res["rows"]), 5)
        # Verify first row has roll_number starting with COLL2026 (from college_database)
        self.assertTrue(any("COLL2026" in str(v) for v in res["rows"][0].values()))

    # Test 12: Destructive SQL is rejected by the read-only natural-language query workflow
    def test_12_destructive_sql_rejected(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        destructive_prompts = [
            "DROP TABLE students;",
            "DELETE FROM students WHERE id = 1;",
            "TRUNCATE TABLE students;",
            "ALTER TABLE students ADD COLUMN test INT;"
        ]
        for p in destructive_prompts:
            res = query_database(
                connection_string=cs,
                question=p,
                expected_db_name=self.college_db["database"],
                db_type=self.college_db["type"],
                connection_id=self.college_db["id"]
            )
            self.assertFalse(res["success"], f"Expected destructive prompt '{p}' to be rejected")
            self.assertIn("rejected", res["result"].lower())

    # Test 13: Numeric decimal parsing with trailing sentence punctuation preserves decimal exactly
    def test_13_decimal_filter_with_trailing_punctuation(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        # Query ends with a period, which previously resulted in malformed SQL "WHERE cgpa > 8.5.;"
        res = query_database(
            connection_string=cs,
            question="List all students with CGPA above 8.5.",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"], f"Query failed with: {res.get('result')}")
        self.assertIsNotNone(res.get("executed_sql"))
        sql_clean = res["executed_sql"].strip()
        # Must preserve 8.5 without dangling or double period
        self.assertIn("cgpa > 8.5", sql_clean.lower())
        self.assertNotIn("8.5.", sql_clean)
        self.assertNotIn("8.;", sql_clean)
        # All returned rows must have cgpa > 8.5
        for row in res["rows"]:
            self.assertGreater(float(row["cgpa"]), 8.5)

    # Test 14: Multiple numeric conditions (CGPA and attendance) without demanding an employees table
    def test_14_multiple_conditions_cgpa_and_attendance(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        res = query_database(
            connection_string=cs,
            question="List all students with CGPA above 8.0 and attendance above 75",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"], f"Query failed with: {res.get('result')}")
        sql_clean = res["executed_sql"].lower()
        self.assertIn("students", sql_clean)
        self.assertIn("cgpa > 8.0", sql_clean)
        self.assertIn("attendance_percentage > 75", sql_clean)
        for row in res["rows"]:
            self.assertGreater(float(row["cgpa"]), 8.0)
            self.assertGreater(float(row["attendance_percentage"]), 75.0)

    # Test 15: Department grouping and average CGPA queries
    def test_15_department_grouping_average_cgpa(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        res = query_database(
            connection_string=cs,
            question="Show average CGPA in each department",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"], f"Query failed with: {res.get('result')}")
        sql_clean = res["executed_sql"].lower()
        self.assertIn("avg(cgpa)", sql_clean)
        self.assertIn("group by department", sql_clean)
        self.assertEqual(len(res["rows"]), 5)

        # Test simple overall average
        res_overall = query_database(
            connection_string=cs,
            question="What is the average CGPA of students?",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res_overall["success"])
        self.assertIn("avg(cgpa)", res_overall["executed_sql"].lower())

    # Test 16: Incomplete SQL validation cleanly halts execution before running
    def test_16_incomplete_sql_validation_rejection(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        # Query with dangling decimal point
        res1 = query_database(
            connection_string=cs,
            question="SELECT * FROM students WHERE cgpa > 8.",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertFalse(res1["success"])
        self.assertIn("Execution halted", res1["result"])
        self.assertIn("Incomplete numeric literal", res1["result"])

        # Query with dangling operator
        res2 = query_database(
            connection_string=cs,
            question="SELECT * FROM students WHERE cgpa >",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertFalse(res2["success"])
        self.assertIn("Execution halted", res2["result"])

    # Test 17: Missing table or invalid column returns clear error
    def test_17_missing_columns_or_invalid_sql(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        # college_database has no professors table
        res = query_database(
            connection_string=cs,
            question="SELECT non_existent_column FROM students;",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertFalse(res["success"])
        self.assertIn("non_existent_column", res["result"])

    # Test 18: Exact three-condition student query (CGPA > 8.0, attendance > 75%, zero backlogs)
    def test_18_three_condition_student_query(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        res = query_database(
            connection_string=cs,
            question="Find students with CGPA above 8.0, attendance above 75%, and zero backlogs.",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"], f"Query failed with: {res.get('result')}")
        self.assertIsNotNone(res.get("executed_sql"))
        sql_clean = res["executed_sql"].lower()
        self.assertIn("students", sql_clean)
        self.assertIn("cgpa > 8.0", sql_clean)
        self.assertIn("attendance_percentage > 75", sql_clean)
        self.assertTrue("backlogs = 0" in sql_clean or "backlogs <= 0" in sql_clean)
        self.assertGreater(len(res["rows"]), 0)
        for row in res["rows"]:
            self.assertGreater(float(row["cgpa"]), 8.0)
            self.assertGreater(float(row["attendance_percentage"]), 75.0)
            self.assertEqual(int(row["backlogs"]), 0)

    # Test 19: Student lookup by register number selects only requested name column(s)
    def test_19_student_lookup_by_register_number_name_only(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        res = query_database(
            connection_string=cs,
            question="What is the name of the student with register number COLL2026001?",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"], f"Query failed with: {res.get('result')}")
        self.assertIsNotNone(res.get("executed_sql"))
        sql_clean = res["executed_sql"].lower()
        # Should filter by register number column (roll_number)
        self.assertIn("roll_number = 'coll2026001'", sql_clean)
        # Should select name columns (first_name, last_name) and not SELECT *
        self.assertIn("first_name", sql_clean)
        self.assertIn("last_name", sql_clean)
        self.assertNotIn("select *", sql_clean)
        self.assertEqual(res["row_count"], 1)
        self.assertEqual(set(res["columns"]), {"first_name", "last_name"})

    # Test 20: Student lookup by roll number without asking for name returns all details
    def test_20_student_lookup_by_roll_number_all_details(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        res = query_database(
            connection_string=cs,
            question="Find student with roll number COLL2026002",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertTrue(res["success"], f"Query failed with: {res.get('result')}")
        sql_clean = res["executed_sql"].lower()
        self.assertIn("roll_number = 'coll2026002'", sql_clean)
        self.assertEqual(res["row_count"], 1)
        self.assertIn("first_name", res["rows"][0])

    # Test 21: Unresolvable specific question returns a clear error instead of generic fallback
    def test_21_unresolvable_specific_query_returns_error_no_silent_fallback(self):
        cs = self.manager.get_connection_string(self.college_db["id"])
        res = query_database(
            connection_string=cs,
            question="Find students whose favorite hobby is chess",
            expected_db_name=self.college_db["database"],
            db_type=self.college_db["type"],
            connection_id=self.college_db["id"]
        )
        self.assertFalse(res["success"])
        self.assertIsNone(res.get("executed_sql"))
        self.assertIn("Could not generate SQL query", res.get("result", ""))
        self.assertNotIn("SELECT * FROM students LIMIT 100", res.get("result", ""))

    # Test 22: Student lookup on SQLite database selects single name column
    def test_22_sqlite_student_lookup_name_column(self):
        if self.sample_db:
            cs = self.manager.get_connection_string(self.sample_db["id"])
            res = query_database(
                connection_string=cs,
                question="What is the name of student with id 1?",
                expected_db_name=self.sample_db["database"],
                db_type=self.sample_db["type"],
                connection_id=self.sample_db["id"]
            )
            self.assertTrue(res["success"], f"Query failed with: {res.get('result')}")
            sql_clean = res["executed_sql"].lower()
            self.assertIn("select name from students", sql_clean)
            self.assertIn("id = '1'", sql_clean)
            self.assertEqual(res["row_count"], 1)
            self.assertEqual(res["columns"], ["name"])

if __name__ == "__main__":
    unittest.main()


