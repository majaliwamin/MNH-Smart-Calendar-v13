import time

VISIBLE_ROLES = {"administrator": "Rep", "lecturer": "Staff", "hod": "HOD", "coordinator": "Coordinator", "executive_dean": "Executive Dean"}


def write_activity(connection, role, action, collection=None, item_id=None, summary=""):
    connection.execute(
        "INSERT INTO audit(at,role,action,collection,item_id,summary) VALUES(?,?,?,?,?,?)",
        (int(time.time() * 1000), role, action, collection, item_id, str(summary)[:240]),
    )
