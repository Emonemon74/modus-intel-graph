"""The cascade reasoner -- the demo centrepiece.

Question: "If AI automates activity X, show the cascading impact."

Bounded breadth-first walk from the trigger node. At each hop the LLM judges
whether the neighbour is *materially* affected, given the hypothesis + retrieved
evidence. Material nodes are recorded and expanded further, up to
`cascade_max_depth`, at most `cascade_max_branch` neighbours per node.

Each result is committed in its own transaction, so a slow run that the client
gives up on still leaves everything it found in `cascade_runs` / `cascade_results`.

Typical path for "automate an activity":
   activity -> roles that perform it
            -> other activities those roles do
            -> skills of the affected activities
"""

import json

from app.ai import analysts
from app.ai.embeddings import EvidenceIndex
from app.config import settings
from app.db import session_scope
from app.graph.traverse import get_node, neighbours, node_label
from app.models import CascadeResult, CascadeRun
from app.pipeline.evidence import attach_evidence

_EXPAND = {
    "activity": ["ROLE_PERFORMS_ACTIVITY", "ACTIVITY_REQUIRES_SKILL", "PROCESS_HAS_ACTIVITY"],
    "role": ["ROLE_PERFORMS_ACTIVITY", "ROLE_HAS_SKILL"],
    "skill": ["ACTIVITY_REQUIRES_SKILL"],
    "process": ["PROCESS_HAS_ACTIVITY", "STAGE_HAS_PROCESS"],
    "stage": ["STAGE_HAS_PROCESS"],
}


def run_cascade(trigger_type: str, trigger_id: int, hypothesis: str) -> int:
    index = EvidenceIndex()

    with session_scope() as s:
        trigger = get_node(s, trigger_type, trigger_id)
        if trigger is None:
            raise ValueError(f"no such node {trigger_type}:{trigger_id}")
        trigger_label = node_label(trigger)
        run = CascadeRun(trigger_type=trigger_type, trigger_id=trigger_id, hypothesis=hypothesis)
        s.add(run)
        s.flush()
        run_id = run.id

    visited: set[tuple[str, int]] = {(trigger_type, trigger_id)}
    frontier = [(trigger_type, trigger_id, 0, [f"{trigger_type}:{trigger_label}"])]

    while frontier:
        ntype, nid, depth, path = frontier.pop(0)
        if depth >= settings.cascade_max_depth:
            continue

        # short read: this node's candidate neighbours
        with session_scope() as s:
            cands = []
            for rel, direction, nb_type, nb_id, _e in neighbours(s, ntype, nid, _EXPAND.get(ntype)):
                if (nb_type, nb_id) in visited:
                    continue
                nb = get_node(s, nb_type, nb_id)
                if nb is not None:
                    cands.append((nb_type, nb_id, node_label(nb)))
                if len(cands) >= settings.cascade_max_branch:
                    break

        for nb_type, nb_id, nb_label in cands:
            visited.add((nb_type, nb_id))
            with session_scope() as s:
                ev = attach_evidence(s, index, "cascade_probe", run_id,
                                     f"{hypothesis} impact on {nb_label}", k=2)
                verdict = analysts.cascade_effect(
                    hypothesis, " -> ".join(path), nb_type, nb_label, ev)
                if not verdict.material:
                    continue
                new_path = path + [f"{nb_type}:{nb_label}"]
                res = CascadeResult(
                    run_id=run_id, affected_type=nb_type, affected_id=nb_id,
                    depth=depth + 1, effect=verdict.effect, reasoning=verdict.reasoning,
                    path_json=json.dumps(new_path),
                )
                s.add(res)
                s.flush()
                attach_evidence(s, index, "cascade_result", res.id,
                                f"{nb_label} {verdict.effect}", k=2)
            frontier.append((nb_type, nb_id, depth + 1, new_path))

    index.save()
    return run_id


def get_cascade(run_id: int) -> dict:
    with session_scope() as s:
        run = s.get(CascadeRun, run_id)
        if not run:
            raise ValueError("no such cascade run")
        results = sorted(run.results, key=lambda r: r.depth)
        return {
            "id": run.id,
            "hypothesis": run.hypothesis,
            "trigger": {"type": run.trigger_type, "id": run.trigger_id},
            "results": [
                {
                    "affected_type": r.affected_type,
                    "affected_id": r.affected_id,
                    "label": node_label(get_node(s, r.affected_type, r.affected_id)),
                    "depth": r.depth,
                    "effect": r.effect,
                    "reasoning": r.reasoning,
                    "path": json.loads(r.path_json),
                }
                for r in results
            ],
        }
