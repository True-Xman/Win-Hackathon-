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
    json.dump([{"kind": "task", "title": f"t{i}", "reward_usd": 5, "text": "Prizes paid in USDC. No KYC required. Free to enter."} for i in range(6)], open(d + "/s.json", "w"))
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

def test_claim_applies_but_never_overrides_fail_and_stale_ignored():
    items = [{"kind": "task", "source": "agenthansa", "title": "a", "url": "u1", "text": "Do it."},
             {"kind": "task", "source": "agenthansa", "title": "b", "url": "u2", "text": "Prize paid by bank transfer."}]
    a, b = run(items)
    assert a["gates"]["payout"] == "PASS" and "claim" in a["evidence"]["payout"][-1] and a["gates"]["kyc"] == "UNKNOWN"
    assert b["gates"]["payout"] == "FAIL"
    hunt.CLAIMS = {k: dict(v, stale=True) for k, v in hunt.load_claims().items()}
    assert hunt.verify(hunt.normalize(items[0], "x"))["gates"]["payout"] != "PASS"

def test_dedupe_by_native_id_across_urls():
    it = {"kind": "task", "source": "s", "native_id": "7", "title": "t", "url": "https://x/a", "text": "x"}
    assert len(run([it, dict(it, url="https://x/b")])) == 1

def test_build_lane_labels_and_weak_not_forced():
    good = {"kind": "task", "lane": "BUILD", "title": "AI agent hackathon", "reward_usd": 20000, "deadline": "2999-01-01T00:00:00Z",
            "text": "Build an AI agent demo. Free to enter. Prizes paid in USDC to your wallet. Fully online."}
    weak = dict(good, title="tiny", reward_usd=10, text="Build a thing. Free to enter. Prizes paid in USDC to your wallet.")

    top = hunt.run(__import__("tempfile").mkdtemp(), [good, weak])[1]
    assert [c["title"] for c in top] == ["AI agent hackathon"] and top[0]["lane"] == "BUILD" and top[0]["build"]["prize"] > 0

def test_listing_text_can_only_add_fail():
    it = {"kind": "task", "lane": "BUILD", "title": "t", "text": "", "discovery_text": "Winners must complete identity verification. Prizes paid in USDC. No KYC required."}
    c = run([it])[0]
    assert c["gates"]["kyc"] == "FAIL" and c["gates"]["payout"] != "PASS"

def test_risein_listing_parse_and_rules_url():
    import collectors
    card = '<a href="/eco/hack"><span>Online</span><span><span></span>Open</span><span>Eco</span><span>Hackathon</span></a>'
    detail = ('<h1>Hack</h1><div>Prize pool</div><div>$5,000</div>Deadline</div><div>Oct 12, 2999</div>'
              '<a href="https://sponsor.example/rules">r</a><a href="https://www.linkedin.com/x">l</a>')
    page = "<h3>Ecosystem opportunities</h3>" + card
    old = collectors.fetch
    collectors.fetch = lambda u, **k: (200, page if u.endswith("/earn") else detail)
    try:
        items, h = collectors.risein()
    finally:
        collectors.fetch = old
    assert len(items) == 1 and items[0]["rules_url"] == "https://sponsor.example/rules" and items[0]["lane"] == "BUILD" and items[0]["text"] == ""

def test_per_opportunity_claim_does_not_leak_to_other_items():
    hunt.CLAIMS = {("s:/a", "kyc"): {"verdict": "FAIL", "stale": False, "quote": "q", "url": "u", "checked_at": "2026-10-06"}}
    a = hunt.verify(hunt.normalize({"source": "s", "native_id": "/a", "title": "a", "text": "x"}, "f"))
    b = hunt.verify(hunt.normalize({"source": "s", "native_id": "/b", "title": "b", "text": "x"}, "f"))
    assert a["gates"]["kyc"] == "FAIL" and b["gates"]["kyc"] != "FAIL"

if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
