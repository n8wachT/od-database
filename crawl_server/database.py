import os
import json
import sqlite3


class Task:

    def __init__(self, url: str, priority: int = 1, callback_type: str = None, callback_args: str = None):
        self.url = url
        self.priority = priority
        self.callback_type = callback_type
        self.callback_args = json.loads(callback_args) if callback_args else {}

    def to_json(self):
        return ({
            "url": self.url,
            "priority": self.priority,
            "callback_type": self.callback_type,
            "callback_args": json.dumps(self.callback_args)
        })


class TaskManagerDatabase:

    def __init__(self, db_path):
        self.db_path = db_path

        if not os.path.exists(db_path):
            self.init_database()

    def init_database(self):

        with open("task_db_init.sql", "r") as f:
            init_script = f.read()

        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(init_script)
            conn.commit()

    def pop_task(self):

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT id, url, priority, callback_type, callback_args"
                           " FROM Queue ORDER BY priority DESC, Queue.id ASC LIMIT 1")
            task = cursor.fetchone()

            if task:
                cursor.execute("DELETE FROM Queue WHERE id=?", (task[0],))
                conn.commit()
                return Task(task[1], task[2], task[3], task[4])
            else:
                return None

    def put_task(self, task: Task):

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("INSERT INTO Queue (url, priority, callback_type, callback_args) VALUES (?,?,?,?)",
                           (task.url, task.priority, task.callback_type, json.dumps(task.callback_args)))
            conn.commit()

    def get_tasks(self):

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM Queue")
            tasks = cursor.fetchall()

            return [Task(t[1], t[2], t[3], t[4]) for t in tasks]