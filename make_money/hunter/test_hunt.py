import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hunt

def run(items):
    d = tempfile.mkdtemp(); json.dump(items, open(d + "/s.json", "w"))
    return hunt.run(d)[0]

def test_example_inbox():
    c = {x["title"]: x for x in hunt.run(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures"))[0]}
    assert c["EXAMPLE crypto bounty"]["status"] == "VERIFIED"
    assert c["EXAMPLE fiat bounty"]["status"] == "REJECTED"
    s = c["EXAMPLE public problem signal"]
    assert s["status"] == "NEEDS_CHECK" and s["gates"]["payout"] == "UNKNOWN"

def test_unknown_never_pass():
    c = run([{"kind": "task", "title": "t", "text": "Build a thing."}])[0]
    assert c["status"] == "NEEDS_CHECK" and "PASS" not in c["gates"].values()

def test_expired_rejected():
    c = run([{"kind": "task", "title": "t", "text": "USDC prizes, no KYC", "deadline": "2020-01-01T00:00:00Z"}])[0]
    assert c["status"] == "REJECTED"

def test_top3_cap():
    d = tempfile.mkdtemp()
    json.dump([{"kind": "task", "title": f"t{i}", "text": "Prizes paid in USDC. No KYC required."} for i in range(6)], open(d + "/s.json", "w"))
    assert len(hunt.run(d)[1]) == 3

def test_dedupe_keeps_provenance():
    it = {"kind": "task", "title": "t", "url": "https://x/1", "text": "USDC prizes. No KYC.", "provenance": {"api": "a"}}
    cs = run([it, dict(it, provenance={"api": "b"})])
    assert len(cs) == 1 and cs[0]["provenance"]["duplicates"] == [{"api": "b"}]

def test_unqualified_not_forced_into_shortlist():
    d = tempfile.mkdtemp(); json.dump([{"kind": "task", "title": "t", "text": "Build a thing."}], open(d + "/s.json", "w"))
    assert hunt.run(d)[1] == []

def test_taskmarket_normalizes_and_kyc_unknown(monkeypatch=None):
    import collectors
    task = {"id": "0x1", "referenceCode": "TSK-1", "description": "Title\nDo it", "reward": "2000000", "status": "open", "phase": "active",
            "submissionWindowOpen": True, "submissionCount": 3, "expiryTime": "2999-01-01T00:00:00Z", "mode": "bounty", "requester": "0xr", "stakeRequired": False}
    old = collectors.fetch_json
    collectors.fetch_json = lambda u, **k: (200, {"tasks": [task, dict(task, id="0x2", status="completed")], "hasMore": False})
    try:
        items, h = collectors.taskmarket()
    finally:
        collectors.fetch_json = old
    assert len(items) == 1 and items[0]["reward_usd"] == 2.0 and items[0]["provenance"]["ref"] == "TSK-1"
    c = hunt.run(__import__("tempfile").mkdtemp(), items)[0][0]
    assert c["gates"]["payout"] == "PASS" and c["gates"]["kyc"] == "UNKNOWN" and c["status"] == "NEEDS_CHECK"

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
