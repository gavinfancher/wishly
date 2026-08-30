import psycopg2

conn = psycopg2.connect(
    host="database-1.cv08qo42c464.us-east-1.rds.amazonaws.com",
    port=5432,
    dbname="postgres",
    user="postgres",
    password=""
)

cur = conn.cursor()
cur.execute("select * from test")

rows = cur.fetchall()
for row in rows:
    print(row)

cur.close()
conn.close()