"""Example: inspect a project and apply an already-approved keep-block plan."""

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from jianying_project import JianyingProject


def main(draft_path: str, timeline: str, plan_path: str, apply: bool = False) -> None:
    project = JianyingProject(draft_path)
    print(json.dumps(project.probe(), ensure_ascii=False, indent=2))
    before = project.validate(timeline)
    if not before["ok"]:
        raise RuntimeError(before)
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8-sig"))
    dry_run = project.apply_plan(timeline, plan, dry_run=True)
    print(json.dumps(dry_run, ensure_ascii=False, indent=2))
    if apply and dry_run.get("would_change"):
        print(json.dumps(project.apply_plan(timeline, plan, dry_run=False), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) not in {4, 5} or (len(sys.argv) == 5 and sys.argv[4] != "--apply"):
        raise SystemExit("usage: inspect_and_apply_plan.py DRAFT TIMELINE PLAN.json [--apply]")
    main(*sys.argv[1:4], apply=len(sys.argv) == 5)
