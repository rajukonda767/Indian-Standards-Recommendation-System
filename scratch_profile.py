import time
t0 = time.time()
import sys
sys.path.insert(0, 'backend')
t1 = time.time()
print('sys.path:', t1 - t0)

from app.parsers.mention_extractor import load_db_sets
t2 = time.time()
print('import mention_extractor:', t2 - t1)

load_db_sets()
t3 = time.time()
print('load_db_sets():', t3 - t2)

from app.parsers.standard_resolver import StandardResolver
t4 = time.time()
print('import StandardResolver:', t4 - t3)

r = StandardResolver()
t5 = time.time()
print('init StandardResolver:', t5 - t4)

from app.db import get_db_cursor
t6 = time.time()
print('import db:', t6 - t5)

with get_db_cursor() as cur:
    cur.execute('SELECT 1;')
    print(cur.fetchone())
t7 = time.time()
print('first db query:', t7 - t6)
