import sqlite3

class CommandVault:
    def __init__(self, db_path="vault.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.create_table()

    def create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS commands 
            (id INTEGER PRIMARY KEY, name TEXT, cmd TEXT, category TEXT)
        """)
        self.conn.commit()

    def save_command(self, name, cmd):
        self.conn.execute("INSERT INTO commands (name, cmd) VALUES (?, ?)", (name, cmd))
        self.conn.commit()

    def get_all(self):
        return self.conn.execute("SELECT * FROM commands").fetchall()