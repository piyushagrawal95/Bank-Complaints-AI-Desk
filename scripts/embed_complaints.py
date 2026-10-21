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
        print("Finding complaints with narratives that need vector indexing...")
        sql = """
            SELECT c.complaint_id, c.product, c.issue, c.narrative 
            FROM complaints c
            LEFT JOIN complaint_embeddings ce ON ce.complaint_id = c.complaint_id
            WHERE c.narrative IS NOT NULL AND TRIM(c.narrative) != '' AND ce.complaint_id IS NULL
            LIMIT 500;
        """
        rows = conn.execute(sql).fetchall()
        print(f"Found {len(rows)} complaints to embed.")

        if not rows:
            print("All eligible complaints already indexed.")
            return

        texts = [f"{r[1]} - {r[2]}: {r[3][:1000]}" for r in rows]
        print("Generating embeddings...")
        embeddings = list(embed_model.embed(texts, batch_size=BATCH_SIZE))

        print("Storing in complaint_embeddings table...")
        with conn.cursor() as cur:
            insert_sql = "INSERT INTO complaint_embeddings (complaint_id, embedding) VALUES (%s, %s)"
            cur.executemany(
                insert_sql,
                [
                    (r[0], emb.tolist() if hasattr(emb, "tolist") else list(emb))
                    for r, emb in zip(rows, embeddings)
                ],
            )
            conn.commit()

        total = conn.execute("SELECT COUNT(*) FROM complaint_embeddings").fetchone()[0]
        print(f"Done! Total indexed complaints for similarity search: {total}")


if __name__ == "__main__":
    main()
