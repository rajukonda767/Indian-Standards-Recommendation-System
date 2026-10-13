"""
embed_standards.py
==================
One-time GPU embedding script for 400 BIS Standards.

Pipeline:
1. Load BAAI/bge-m3 on local NVIDIA RTX 3050 GPU (FP16 mode, 1024 dimensions).
2. Fetch 400 BIS standards with virtual_scope from Supabase PostgreSQL.
3. Compute 1024-dim normalized dense embeddings in batches.
4. Update the 'scope_embedding' vector column in Supabase using batch execute.
5. Create an HNSW index for ultra-fast cosine similarity lookups.
6. Run 2 test semantic queries (English & Hindi) to verify semantic retrieval.
"""

import os
import sys
import time
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
import torch
from sentence_transformers import SentenceTransformer

# -------------------------------------------------------------
# 1. Environment & DB Connection Setup
# -------------------------------------------------------------
# Look for .env in current directory or backend/
if os.path.exists('backend/.env'):
    load_dotenv('backend/.env')
elif os.path.exists('.env'):
    load_dotenv('.env')
else:
    load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("[ERROR] DATABASE_URL not found in environment or .env file.")
    sys.exit(1)

if "sslmode" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"

print("=" * 80)
print("SIH-26108: BIS STANDARDS GPU EMBEDDING PIPELINE (BAAI/bge-m3)")
print("=" * 80)

# -------------------------------------------------------------
# 2. Check GPU & Load BAAI/bge-m3 in FP16 Mode
# -------------------------------------------------------------
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"\n[1/5] Hardware Acceleration:")
print(f"      Device: {device.upper()}")
if device == "cuda":
    gpu_name = torch.cuda.get_device_name(0)
    vram_mb = torch.cuda.get_device_properties(0).total_memory / (1024 * 1024)
    print(f"      GPU: {gpu_name} ({vram_mb:.0f} MB VRAM)")
else:
    print("      WARNING: CUDA is not available, falling back to CPU.")

print("\n[2/5] Loading 'BAAI/bge-m3' multilingual model (1024 dimensions)...")
t0_model = time.time()
model = SentenceTransformer("BAAI/bge-m3", device=device)

if device == "cuda":
    model.half()  # Half precision (FP16) - fast inference, ~1.2 GB VRAM usage
    print(f"      Model loaded in FP16 mode on CUDA in {time.time() - t0_model:.2f}s")
else:
    print(f"      Model loaded on CPU in {time.time() - t0_model:.2f}s")

# -------------------------------------------------------------
# 3. Fetch Standards from Supabase
# -------------------------------------------------------------
print("\n[3/5] Connecting to Supabase database...")
conn = psycopg2.connect(
    DATABASE_URL,
    connect_timeout=15,
    keepalives=1,
    keepalives_idle=30,
    keepalives_interval=10,
    keepalives_count=5
)
cur = conn.cursor()

cur.execute("""
    SELECT id, standard_number, title, virtual_scope
    FROM standards
    WHERE scope_embedding IS NULL
    ORDER BY id ASC;
""")
rows = cur.fetchall()
total_to_embed = len(rows)
print(f"      Found {total_to_embed} standards needing scope embeddings.")

if total_to_embed == 0:
    print("      All standards already have embeddings. Checking count...")
    cur.execute("SELECT count(*) FROM standards WHERE scope_embedding IS NOT NULL;")
    already_done = cur.fetchone()[0]
    print(f"      Total embedded standards in DB: {already_done}")
else:
    # Prepare texts for embedding
    ids = []
    texts = []
    for r in rows:
        sn_id, sn_num, title, vscope = r
        # Use virtual_scope if available; fall back to title + standard number
        text_content = (vscope or f"{sn_num}: {title}").strip()
        ids.append(sn_id)
        texts.append(text_content)

    # -------------------------------------------------------------
    # 4. Generate 1024-dim Normalized Embeddings in Batches
    # -------------------------------------------------------------
    print(f"\n[4/5] Generating embeddings for {len(texts)} standards on RTX 3050 GPU...")
    batch_size = 32
    t0_embed = time.time()

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True  # Unit length for accurate cosine similarity
    )
    t_embed_elapsed = time.time() - t0_embed
    print(f"      Embedding complete in {t_embed_elapsed:.2f}s ({len(texts)/t_embed_elapsed:.1f} items/sec)")

    # -------------------------------------------------------------
    # 5. Batched Update to Supabase
    # -------------------------------------------------------------
    print(f"\n      Updating {len(embeddings)} records in Supabase 'standards' table...")
    update_data = [
        (rec_id, f"[{','.join(f'{x:.6f}' for x in emb)}]")
        for rec_id, emb in zip(ids, embeddings)
    ]

    update_query = """
        UPDATE standards AS s
        SET scope_embedding = v.scope_embedding::vector
        FROM (VALUES %s) AS v(id, scope_embedding)
        WHERE s.id = v.id;
    """

    execute_values(cur, update_query, update_data, page_size=100)
    conn.commit()
    print("      Successfully committed all embeddings to Supabase!")

# -------------------------------------------------------------
# 6. Create HNSW Cosine Index (If not present)
# -------------------------------------------------------------
print("\n      Checking/Creating HNSW index for ultra-fast cosine similarity lookups...")
try:
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_standards_scope_embedding
        ON standards USING hnsw (scope_embedding vector_cosine_ops);
    """)
    conn.commit()
    print("      HNSW vector index is ready.")
except Exception as e:
    print(f"      Index creation notice: {e}")
    conn.rollback()

# -------------------------------------------------------------
# 7. Semantic Accuracy Verification (English & Hindi)
# -------------------------------------------------------------
print("\n[5/5] Running Semantic Verification Queries against Supabase...")

test_queries = [
    {
        "lang": "English",
        "query": "PVC insulated copper wire",
        "description": "Electrical wire query"
    },
    {
        "lang": "Hindi",
        "query": "विद्युत तारों और केबलों के लिए मानक",
        "description": "Multilingual electrical cables query in Hindi"
    }
]

for test in test_queries:
    q_text = test["query"]
    print("\n" + "-" * 75)
    print(f"Query ({test['lang']}): \"{q_text}\"")
    print(f"Context: {test['description']}")
    print("-" * 75)

    # Encode test query with same model & normalization
    q_emb = model.encode([q_text], normalize_embeddings=True)[0]
    q_vec_str = f"[{','.join(f'{x:.6f}' for x in q_emb)}]"

    # Vector search on Supabase: 1 - cosine distance = cosine similarity
    cur.execute("""
        SELECT standard_number, title, dept,
               round((1 - (scope_embedding <=> %s::vector))::numeric, 4) AS similarity
        FROM standards
        WHERE scope_embedding IS NOT NULL
        ORDER BY scope_embedding <=> %s::vector ASC
        LIMIT 3;
    """, (q_vec_str, q_vec_str))

    results = cur.fetchall()
    for rank, (sn, title, dept, score) in enumerate(results, start=1):
        print(f"  #{rank} [Score: {score:.4f}] {sn} ({dept})")
        print(f"      Title: {title}")

# Verify final row count
cur.execute("SELECT count(*) FROM standards WHERE scope_embedding IS NOT NULL;")
total_embedded = cur.fetchone()[0]
print("\n" + "=" * 80)
print(f"VERIFICATION COMPLETE: {total_embedded}/400 standards have active 1024-dim embeddings!")
print("=" * 80)

cur.close()
conn.close()
