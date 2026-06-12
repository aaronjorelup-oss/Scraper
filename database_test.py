import pyodbc
conn = pyodbc.connect(
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=aeri-sql-2019;"
    "DATABASE=CCCRM;"
    "Trusted_Connection=yes;"
)
cursor = conn.cursor()
cursor.execute("SELECT TOP 5 LTRIM(RTRIM(FULLPART)) FROM REQ WHERE AUTO_MATCH = 1")
for row in cursor.fetchall():
    print(row[0])
conn.close()