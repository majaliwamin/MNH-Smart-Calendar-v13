from app.database.postgres import adapt_sql


def test_sqlite_placeholders_are_adapted():
    assert adapt_sql("SELECT * FROM docs WHERE col=? AND id=?") == "SELECT * FROM docs WHERE col=%s AND id=%s"


def test_insert_or_replace_becomes_postgres_upsert():
    sql = adapt_sql("INSERT OR REPLACE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)")
    assert "ON CONFLICT (col, id) DO UPDATE SET" in sql
    assert "data=EXCLUDED.data" in sql
    assert "updated_at=EXCLUDED.updated_at" in sql


def test_insert_or_ignore_becomes_postgres_ignore():
    sql = adapt_sql("INSERT OR IGNORE INTO docs(col,id,data,updated_at) VALUES(?,?,?,?)")
    assert sql.endswith("ON CONFLICT DO NOTHING")


def test_sqlite_autoincrement_ddl_is_adapted():
    sql = adapt_sql("CREATE TABLE IF NOT EXISTS comm_audit(id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT)")
    assert "id BIGSERIAL PRIMARY KEY" in sql
