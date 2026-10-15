import ingest
import db_2 as db

with db.connection(ingest.DB_CONFIG) as conn:
    with conn.cursor() as cursor:
        cursor.execute(
            f"SELECT source, COUNT(*) AS chunks FROM {ingest.TABLE} "
            f"GROUP BY source ORDER BY source"
        )
        rows = cursor.fetchall()
        
print(f"Database: {ingest.DB_CONFIG['database']} Table: {ingest.TABLE}")
print(f"{len(rows)} documents\n")
for r in rows:
    print(f"{r['chunks']:5} {r['source']}")