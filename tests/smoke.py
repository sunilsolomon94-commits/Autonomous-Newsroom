"""Proves the editorial core works with no credentials. Run from repo root:
   PYTHONPATH=. python tests/smoke.py
"""
import os
import yaml
from pipeline.verify import Claim, evaluate_story
from pipeline import audit

rules = yaml.safe_load(open("config/editorial_rules.yaml"))

# Case 1: well sourced, one tier-1 -> publish
c1 = [Claim("Model X released today", ["s1", "s2"], [1, 2])]
# Case 2: single sourced -> hold
c2 = [Claim("Rumor of an acquisition", ["s1"], [3])]
# Case 3: negative claim about a living person, only 2 sources (needs 3) -> hold
c3 = [Claim("Executive accused of wrongdoing", ["s1", "s2"], [1, 2],
            names_living_person=True, negative_about_person=True)]
# Case 4: relaxed rule. 3 independent tier-2 sources, no tier-1 -> publish
c4 = [Claim("Three outlets report a product launch", ["s1", "s2", "s3"], [2, 2, 2])]
# Case 5: only 2 tier-2 sources, no tier-1 -> hold (needs 3 without a tier-1)
c5 = [Claim("Two outlets report a rumor", ["s1", "s2"], [2, 2])]

print("case1 (expect publish):", evaluate_story(c1, rules).decision)
print("case2 (expect hold):   ", evaluate_story(c2, rules).decision)
print("case3 (expect hold):   ", evaluate_story(c3, rules).decision)
print("case4 (expect publish):", evaluate_story(c4, rules).decision)
print("case5 (expect hold):   ", evaluate_story(c5, rules).decision)

log = "data/audit_log.jsonl"
if os.path.exists(log):
    os.remove(log)
audit.append(log, "e1", "publish", ["all claims passed"], ["s1", "s2"])
audit.append(log, "e2", "hold", ["single source"], ["s1"])
print("audit chain intact (expect True):", audit.verify_chain(log))
