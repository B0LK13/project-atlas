import pathlib, re
FILES = ["WORKLOG.md","docs/backlog.md",
         "docs/evidence/AS-OBSIDIAN-CAPTURE-001-F6-ERROR-BOUNDARY.md",
         "docs/evidence/AS-OBSIDIAN-CAPTURE-001-F7-BOM-OWNERSHIP.md",
         "/tmp/b737_cur.md"]
# The two claims this PR retracts, matched at CONCEPT level so that wording,
# word order and line wrapping cannot hide a copy.
CLAIMS = {
 "A: all post-r1 findings were claim-record, not code":
   (re.compile(rb"claim record", re.I), re.compile(rb"(not the code|rather than the code|rather than in the code)", re.I)),
 "B: all post-r1 rounds changed only evidence prose":
   (re.compile(rb"evidence prose", re.I), re.compile(rb"(only|prose only)", re.I)),
}
RETRACT = re.compile(rb"(earlier revision|\*\*false\*\*|overstates|retract|which is \*\*false\*\*|the seals said)", re.I)
tot_live = 0
for label,(r1,r2) in CLAIMS.items():
    print(f"\n=== claim {label} ===")
    n = 0
    for f in FILES:
        flat = re.sub(rb"\s+", b" ", pathlib.Path(f).read_bytes())
        for m in re.finditer(rb"[^.!?]{0,400}[.!?]", flat):
            s = m.group(0)
            if not (r1.search(s) and r2.search(s)): continue
            n += 1
            ctx = flat[max(0,m.start()-320):m.end()+320]      # look BOTH ways
            live = not RETRACT.search(ctx)
            tot_live += live
            print(f"  [{'LIVE' if live else 'retraction'}] {f.split('/')[-1]}: {s.strip().decode('utf-8','replace')[:150]}")
    if n == 0: print("  (no occurrences)")
print(f"\n  TOTAL LIVE OCCURRENCES OF THE TWO RETRACTED CLAIMS: {tot_live}")
