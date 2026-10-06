import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hunt

def run(items):
    d = tempfile.mkdtemp(); json.dump(items, open(d + "/s.json", "w"))
    return hunt.run(d)[0]

def test_example_inbox():
    c = {x["title"]: x for x in hunt.run(os.path.join(os.path.dirname(hunt.DATA), "inbox"))[0]}
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

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
