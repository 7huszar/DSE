import psycopg2 as psy


conn = psy.connect(host="localhost", port="5433", database="cd_db", user="admin", password="admin")

cur = conn.cursor()

#cur.execute("CREATE TABLE test (id serial PRIMARY KEY, num integer, data varchar);")

cur.execute("INSERT INTO test (num, data) VALUES (%s, %s)",(109, "abc'defj"))
cur.execute("INSERT INTO test (num, data) VALUES (%s, %s)",(110, "abc'defg"))

cur.execute("SELECT DISTINCT * FROM test;")

print(cur.fetchall())

conn.commit()

cur.close()
conn.close()