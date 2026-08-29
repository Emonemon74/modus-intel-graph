"""Quick manual check of the cascade reasoner.

    uv run python scripts/demo_cascade.py "Model execution" "AI fully automates this activity"
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db import session_scope
from app.models import Activity
from app.pipeline.cascade import get_cascade, run_cascade

activity_name = sys.argv[1] if len(sys.argv) > 1 else "Model execution"
hypothesis = sys.argv[2] if len(sys.argv) > 2 else "AI fully automates this activity"

with session_scope() as s:
    aid = s.scalars(select(Activity.id).filter(Activity.name == activity_name)).first()
if aid is None:
    sys.exit(f"no activity named {activity_name!r}")

t0 = time.time()
run_id = run_cascade("activity", aid, hypothesis)
res = get_cascade(run_id)

print(f"\nCASCADE_DONE  {time.time() - t0:.0f}s  run={run_id}  {len(res['results'])} material impacts\n")
for r in res["results"]:
    print(f"  d{r['depth']}  {r['affected_type']:8}  {r['label']}")
    print(f"       effect: {r['effect']}")
    print(f"       path:   {'  ->  '.join(r['path'])}\n")
