# import sqlite3

# def get_db_connection():
#     conn = sqlite3.connect("database.db")
#     conn.row_factory = sqlite3.Row
#     return conn

# def execute_db_query(conn, statement):
#     conn.execute(statement)
#     conn.close()

# def fetch_from_db_query(conn, statement):
#     rows = conn.execute(statement).fetchall()
#     conn.close()
#     return rows

# def init_db():
#     conn = sqlite3.connect("database.db")
#     with open("schema.sql") as f:
#         conn.executescript(f.read())

#     cur = conn.cursor()
#     cur.execute("INSERT INTO posts (title, content) VALUES (?, ?)",
#                 ('first post', 'content for first post')
#                 )
#     cur.execute("INSERT INTO posts (title, content) VALUES (?, ?)",
#                 ('second post', 'content for second post')
#                 )

#     conn.commit()
#     conn.close()

from datetime import datetime, UTC
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(15), unique=True, nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    inventories = db.relationship('Inventory', backref='user', lazy=True)
    cashflows = db.relationship('Cashflow', backref='user', lazy=True)

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    last_update_date = db.Column(db.DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC))

class Cashflow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_purpose = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    credit_debit = db.Column(db.String(10), nullable=False)  # 'credit' or 'debit'
    date = db.Column(db.DateTime, default=datetime.now(UTC))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
