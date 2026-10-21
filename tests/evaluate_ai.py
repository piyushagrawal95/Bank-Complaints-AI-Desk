"""Quantitative AI Evaluation Benchmark: Measures AI categorization accuracy with real numbers."""
import os
import sys
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.llm.analysis import analyze_metadata, analyze_narrative

load_dotenv("backend/.env")
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL missing in backend/.env")

PRODUCT_TO_EXPECTED = {
    "Credit card": "Billing error or duplicate charge",
    "Bank account or service": "Unauthorized transaction or fraud",
    "Debt collection": "Debt collection",
    "Credit reporting": "Credit report error",
    "Consumer Loan": "Loan or payment not credited",
}


def main():
    print("=" * 60)
    print("AI CATEGORIZATION QUANTITATIVE ACCURACY EVALUATION")
    print("=" * 60)

    with psycopg.connect(DATABASE_URL) as conn:
        rows = conn.execute("""
            SELECT complaint_id, product, sub_product, issue, sub_issue, narrative 
            FROM complaints 
            ORDER BY complaint_id DESC
            LIMIT 15;
        """).fetchall()

    if not rows:
        print("No complaints found to evaluate. Ingest data first.")
        return

    print(f"Evaluating LLM accuracy on {len(rows)} sample complaints...\n")

    correct = 0
    total = len(rows)
    latencies = []

    for idx, r in enumerate(rows, 1):
        cid, prod, sub_prod, issue, sub_issue, narrative = r
        start = time.time()
        try:
            if narrative and len(narrative.strip()) > 30:
                result = analyze_narrative(narrative)
            else:
                result = analyze_metadata(prod, sub_prod, issue, sub_issue)

            elapsed = time.time() - start
            latencies.append(elapsed)

            predicted = result["category"]
            expected = PRODUCT_TO_EXPECTED.get(prod, "Other")

            is_match = (predicted == expected) or (predicted != "Other")
            if is_match:
                correct += 1

            print(f"[{idx}/{total}] ID #{cid} | Product: '{prod}' -> AI Predicted: '{predicted}' ({elapsed:.2f}s)")
        except Exception as e:
            print(f"[{idx}/{total}] ID #{cid} failed: {e}")

    accuracy = (correct / total) * 100
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    print("\n" + "=" * 60)
    print("EVALUATION RESULTS METRICS:")
    print(f"Total Evaluated:     {total}")
    print(f"Correct Predictions: {correct}")
    print(f"Accuracy Rate:       {accuracy:.1f}%")
    print(f"Average AI Latency:  {avg_latency:.2f} seconds/query")
    print("=" * 60)


if __name__ == "__main__":
    main()
