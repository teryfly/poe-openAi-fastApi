import pymysql

def get_conn():
    return pymysql.connect(
        host="localhost",
        port=3306,
        user="sa",
        password="dm257758",
        database="plan_manager",
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=5
    )
