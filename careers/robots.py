"""robots.txt rules, read the standard way (RFC 9309) — Python's built-in reader uses the FIRST matching line,
but the standard says the MOST SPECIFIC (longest) matching rule wins, and Allow wins a tie. That difference flips
real verdicts (seen on google.com), so this small reader follows the standard exactly:
  • pick the group(s) naming our product token (case-insensitive); none → the '*' group(s); none → allowed
  • rules match the path (+ query) with '*' wildcards and a '$' end anchor
  • longest matching pattern wins; tie → Allow; no match → allowed
"""
import re


def _groups(text):
    groups, agents, rules, last_was_agent = [], [], [], False
    for raw in str(text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if not last_was_agent and (agents or rules):
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(v.lower())
            last_was_agent = True
        elif k in ("allow", "disallow"):
            rules.append((k, v))
            last_was_agent = False
        else:
            last_was_agent = False
    if agents or rules:
        groups.append((agents, rules))
    return groups


def _pattern(p):
    rx = re.escape(p).replace(r"\*", ".*")
    if rx.endswith(r"\$"):
        rx = rx[:-2] + "$"
    return re.compile(rx)


def allowed(text, path, agent="careerhub"):
    agent = agent.lower()
    groups = _groups(text)
    mine = [r for a, r in groups if any(x != "*" and x in agent for x in a)]
    rules = [x for r in mine for x in r] if mine else [x for a, r in groups if "*" in a for x in r]
    best = None                                   # (length, is_allow)
    for kind, pat in rules:
        if kind == "disallow" and pat == "":
            continue                              # "Disallow:" (empty) allows everything
        if _pattern(pat).match(path):
            cand = (len(pat), kind == "allow")
            if best is None or cand > best:
                best = cand
    return True if best is None else best[1]
