import sqlite3


class DBManager:
    def __init__(self, db_name):
        self.db = db_name
        self.conn = sqlite3.connect(self.db, check_same_thread=False)
        self.cur = self.conn.cursor()
        print(f"Connected to database: {db_name}")

    def change_db(self, db_name):
        self.close()
        self.db = db_name
        self.conn = sqlite3.connect(self.db, check_same_thread=False)
        self.cur = self.conn.cursor()
        print(f"Switched to database: {db_name}")

    def close(self):
        self.conn.close()

    def commit_changes(self):
        self.conn.commit()

    def execute_sql(self, sql_code):
        try:
            print(f"Executing SQL:\n{sql_code}")
            self.cur.executescript(sql_code)
            self.commit_changes()
            print("SQL executed successfully")
            return self.cur  # Return the cursor for fetching results if needed
        except sqlite3.Error as e:
            print(f"SQL execution error: {e}")
            raise

