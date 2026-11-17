from sqlalchemy import inspect

from app.db.session import engine, init_db

init_db()
print("Tables created:")
for name in inspect(engine).get_table_names():
    print(" -", name)
