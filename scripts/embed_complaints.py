"""Generate vector embeddings for complaints with narratives for similarity search."""
import os
import psycopg
from dotenv import load_dotenv
from fastembed import TextEmbedding

load_dotenv("backend/.env")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL is missing in backend/.env")

BATCH_SIZE = 128


def main():
    embed_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")

    with psycopg.connect(DATABASE_URL) as conn:
        print("Starting resume-safe batch vector indexing for complaints with narratives...")
        batch_num = 1
        total_session = 0
        fetch_limit = 500

        while True:
            sql = """
                SELECT c.complaint_id, c.product, c.issue, c.narrative 
                FROM complaints c
                LEFT JOIN complaint_embeddings ce ON ce.complaint_id = c.complaint_id
                WHERE c.narrative IS NOT NULL AND TRIM(c.narrative) != '' AND ce.complaint_id IS NULL
                LIMIT %s;
            """
            rows = conn.execute(sql, [fetch_limit]).fetchall()
            if not rows:
                if batch_num == 1:
                    print("All eligible complaints already indexed.")
                else:
                    print(f"Completed! Fully indexed all eligible complaints.")
                break

            print(f"[Batch {batch_num}] Embedding {len(rows)} complaints...")
            texts = [f"{r[1]} - {r[2]}: {r[3][:1000]}" for r in rows]
            embeddings = list(embed_model.embed(texts, batch_size=BATCH_SIZE))

            with conn.cursor() as cur:
                insert_sql = """
                    INSERT INTO complaint_embeddings (complaint_id, embedding) 
                    VALUES (%s, %s)
                    ON CONFLICT (complaint_id) DO NOTHING
                """
                cur.executemany(
                    insert_sql,
                    [
                        (r[0], emb.tolist() if hasattr(emb, "tolist") else list(emb))
                        for r, emb in zip(rows, embeddings)
                    ],
                )
                conn.commit()

            total_session += len(rows)
            batch_num += 1

        total = conn.execute("SELECT COUNT(*) FROM complaint_embeddings").fetchone()[0]
        print(f"Done! Session indexed: {total_session}. Total indexed in database: {total}")


if __name__ == "__main__":
    main()
