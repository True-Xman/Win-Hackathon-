import json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import atexit, hashlib, shutil
import common
import hunt
import persist
hunt.REQUIRE_WRITE_ACCESS = False  # tests never touch the network; the preflight gate is exercised below with local bare repos

# Isolation: tests must never touch the real evidence/ or out/ (the scheduled agent owns them), even when a test fails.
REAL_EVID, REAL_OUT = hunt.EVID, hunt.DATA


def _tree_hash(*roots):
    h = hashlib.sha256()
    for root in roots:
        for d, _, fs in sorted(os.walk(root)):
            if "__pycache__" in d:
                continue
            for f in sorted(fs):
                h.update(os.path.join(d, f).encode())
                h.update(open(os.path.join(d, f), "rb").read())
    return h.hexdigest()


REAL_HASH = _tree_hash(REAL_EVID, REAL_OUT) if os.path.isdir(REAL_OUT) else _tree_hash(REAL_EVID)
_SANDBOX = tempfile.mkdtemp(prefix="hunter_test_")
atexit.register(shutil.rmtree, _SANDBOX, True)
shutil.copytree(REAL_EVID, os.path.join(_SANDBOX, "evidence"), ignore=shutil.ignore_patterns("rules_cache"))  # claims/budget are read-only inputs
os.makedirs(os.path.join(_SANDBOX, "evidence", "rules_cache"), exist_ok=True)
os.makedirs(os.path.join(_SANDBOX, "out"), exist_ok=True)
hunt.EVID = os.path.join(_SANDBOX, "evidence")
hunt.DATA = common.DATA = os.path.join(_SANDBOX, "out")
hunt.GAS_BUDGET_F = os.path.join(hunt.EVID, "wallet_budget.json")
hunt.STATE_F = os.path.join(hunt.EVID, "source_state.json")
ORIG_RULES_TEXT = hunt.rules_text  # an earlier test replaces hunt.rules_text for good; keep the real one for the bot-wall test

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


def test_missing_kyc_payout_and_fee_is_promising_not_rejected():
    item = {"kind": "task", "lane": "BUILD", "title": "AI agent hackathon",
            "reward_usd": 50000, "deadline": "2999-01-01T00:00:00Z",
            "text": "Build an AI agent demo. Fully online."}
    cands, top = hunt.run(tempfile.mkdtemp(), [item])
    c = cands[0]
    assert c["gates"]["kyc"] == "UNKNOWN"
    assert c["gates"]["payout"] == "UNKNOWN"
    assert c["gates"]["paid_action"] == "UNKNOWN"
    assert c["status"] == "NEEDS_CHECK" and c["tier"] == "PROMISING"
    assert len(top) == 1 and top[0]["title"] == "AI agent hackathon"


def test_explicit_kyc_fiat_or_fee_still_rejected():
    cases = [
        ("kyc", "Winners must complete KYC. Prizes paid in USDC. Free to enter."),
        ("payout", "Prizes paid by bank transfer. Free to enter."),
        ("paid_action", "Entry fee is $10. Prizes paid in USDC.")
    ]
    for gate, txt in cases:
        c = run([{"kind": "task", "title": gate, "reward_usd": 1000, "text": txt}])[0]
        assert c["gates"][gate] == "FAIL" and c["tier"] is None


def test_verified_and_promising_get_distinct_sections():
    verified = {"kind": "task", "lane": "BUILD", "title": "Verified AI hackathon",
                "reward_usd": 10000, "deadline": "2999-01-01T00:00:00Z",
                "text": "Build an AI agent demo. No KYC required. Open to everyone, anywhere. Free to enter. Fully online. Prizes paid in USDC."}
    promising = {"kind": "task", "lane": "BUILD", "title": "Promising AI hackathon",
                 "reward_usd": 50000, "deadline": "2999-01-01T00:00:00Z",
                 "text": "Build an AI agent demo. Fully online."}
    _, top = hunt.run(tempfile.mkdtemp(), [promising, verified])
    assert {c["tier"] for c in top} == {"VERIFIED", "PROMISING"}
    assert top[0]["tier"] == "VERIFIED"
    with open(os.path.join(hunt.DATA, "shortlist.md")) as f:
        summary = f.read()
    assert "## VERIFIED" in summary and "## PROMISING" in summary


def test_no_entry_fee_is_pass_not_fee_fail():
    from gates import analyze
    assert analyze("No entry fee. Prizes paid in USDC.")["gates"]["paid_action"]["verdict"] == "PASS"
    assert analyze("Entry fee is $10. Prizes paid in USDC.")["gates"]["paid_action"]["verdict"] == "FAIL"


def test_negated_kyc_is_not_misread_as_mandatory():
    from gates import analyze
    assert analyze("No KYC is required.")["gates"]["kyc"]["verdict"] == "PASS"
    assert analyze("KYC is mandatory.")["gates"]["kyc"]["verdict"] == "FAIL"

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

def test_login_wall_marked_not_rejected():
    import hunt as h
    h.rules_text = lambda url: ("Continue with GitHub\nContinue with Google", "static")
    it = {"kind": "task", "lane": "BUILD", "title": "gated", "rules_url": "https://x", "reward_usd": 50000, "deadline": "2999-01-01T00:00:00Z", "text": "Build an AI app demo."}
    c = run([it])[0]
    assert c["status"] == "LOGIN-REQUIRED-FOR-VERIFY" and c["gates"]["payout"] != "PASS"

def test_cooldown_after_three_empty_runs(tmp=None):
    import tempfile, json as j
    hunt.STATE_F = tempfile.mktemp()
    st = {}
    for _ in range(3):
        hunt.update_state(st, ["devpost", "gigs"], [])
    assert "cooldown_until" in st["devpost"] and "gigs" not in st
    cands = run([{"kind": "task", "source": "x", "title": "t", "reward_usd": 5, "text": "Prizes paid in USDC. No KYC required. Free to enter."}])
    hunt.update_state(st, ["x"], cands)
    assert st["x"]["empty_runs"] == 0

def test_small_reward_ok_if_low_hassle_but_crowded_or_heavy_is_not():
    base = {"kind": "task", "reward_usd": 2, "text": "Post one link. Prizes paid in USDC to your wallet. No KYC required. Free to enter.", "competition": 1}
    easy = hunt.run(__import__("tempfile").mkdtemp(), [dict(base, title="easy")])[1]
    crowd = hunt.run(__import__("tempfile").mkdtemp(), [dict(base, title="crowd", competition=500)])[1]
    heavy = hunt.run(__import__("tempfile").mkdtemp(), [dict(base, title="heavy", text=base["text"] + " Build and code a full prototype. " * 80)])[1]
    assert [c["title"] for c in easy] == ["easy"] and crowd == [] and heavy == []

def test_gas_prefilter_never_covers_only_tx_specific_does():
    hunt.rpc_gas_price_wei = lambda n: 6_000_000
    base = "Prizes paid in USDC to your wallet. No KYC required. Participants must pay network gas for the claim transaction on Base."
    a = run([{"kind": "task", "reward_usd": 20, "competition": 1, "text": base, "title": "a"}])[0]
    assert a["gates"]["paid_action"] == "GAS-PREFILTER-OK" and "need" in a["gas"]
    assert a["tier"] == "PROMISING" and hunt.qualified(a) is True  # reviewable, NOT tx-cleared
    calls = {"eth_estimateGas": hex(60000), "eth_gasPrice": hex(6_000_000), "eth_call": hex(5_000_000_000)}
    hunt._rpc = lambda net, m, p: calls[m]
    spec = {"network": "base", "to": "0x" + "11" * 20, "data": "0xa9059cbb"}
    b = run([{"kind": "task", "reward_usd": 20, "competition": 1, "text": base, "title": "b", "gas_tx": spec}])[0]
    assert b["gates"]["paid_action"] == "GAS-COVERED" and b["gas"]["basis"] == "tx-specific" and b["gas"]["l1_fee_wei"] == 5_000_000_000
    calls["eth_estimateGas"] = hex(10**11)  # huge tx -> balance cannot cover with margin
    c = run([{"kind": "task", "reward_usd": 20, "competition": 1, "text": base, "title": "c", "gas_tx": spec}])[0]
    assert c["gates"]["paid_action"] == "FAIL"
    def boom(*a): raise RuntimeError("execution reverted")
    hunt._rpc = boom
    d = run([{"kind": "task", "reward_usd": 20, "competition": 1, "text": base, "title": "d", "gas_tx": spec}])[0]
    assert d["gates"]["paid_action"] == "UNKNOWN"
    nonet = run([{"kind": "task", "reward_usd": 20, "text": base.replace(" on Base", ""), "title": "n"}])[0]
    assert nonet["gates"]["paid_action"] == "UNKNOWN"
    fee = run([{"kind": "task", "reward_usd": 20, "text": base + " Also a submission fee of 1 USDC applies on Base.", "title": "f"}])[0]
    assert fee["gates"]["paid_action"] == "FAIL" and not fee["gas_only"]

IMMUNEFI = ("Granite Protocol Maximum Bounty $100,000 PoC Required KYC required Submit a Bug Rewards in USDC on Ethereum. "
            "KYC required The submission of KYC information is a requirement for payout processing.")
GRANITE_HOME = "Launch App Bitcoin's Liquidity Protocol The safest way to borrow against your Bitcoin"
ADITYA = ("On-site, residential. The build runs fully on campus at Aditya University for all 48 hours. Free to enter at Level 1. "
          "Level 02 Pay \u20b9800 per member and upload the required documents. Who can participate? Any currently enrolled college or university student in India. "
          "Prize pool \u20b95,00,000")


def test_kyc_required_phrasings_fail_and_negations_do_not():
    from gates import analyze
    for t in ("KYC required", "The submission of KYC information is a requirement for payout processing.", "Winners must undergo full KYC.",
              "Payout requires identity verification."):
        assert analyze(t)["gates"]["kyc"]["verdict"] == "FAIL", t
    for t in ("No KYC required.", "KYC is not required.", "KYC not required for payout.", "Participation is possible without KYC required."):
        assert analyze(t)["gates"]["kyc"]["verdict"] != "FAIL", t
    assert analyze("We may ask for KYC in some cases.")["gates"]["kyc"]["verdict"] == "RISK"  # vague mention stays RISK, not FAIL
    assert analyze("Open worldwide.")["gates"]["kyc"]["verdict"] == "UNKNOWN"  # absence never PASS/FAIL


def test_every_sponsor_link_is_read_so_platform_kyc_clause_rejects():
    import collectors
    urls = ["https://www.granite.world/", "https://github.com/GraniteProtocol/audits", "https://immunefi.com/bug-bounty/granite-protocol/information/",
            "https://www.granite.world/", "https://static.cloudflareinsights.com/beacon.min.js/vce70"]
    ranked = collectors.rank_rules_urls([u for u in urls if "cloudflareinsights" not in u])
    assert ranked[0].startswith("https://immunefi.com") and len(set(ranked)) == len(ranked)
    pages = {"https://www.granite.world/": GRANITE_HOME, "https://immunefi.com/bug-bounty/granite-protocol/information/": IMMUNEFI}
    old = hunt.rules_text
    hunt.rules_text = lambda u: (pages.get(u, ""), "static")
    try:
        it = {"kind": "task", "lane": "BUILD", "source": "risein", "native_id": "/stacks/granite-x", "title": "Granite-like bounty", "reward_usd": 100000,
              "deadline": "2999-01-01T00:00:00Z", "rules_url": "https://www.granite.world/", "rules_urls": ranked, "discovery_text": "AI bug bounty"}
        first_only = dict(it, title="first only", native_id="/stacks/granite-y", rules_urls=[])
        c, f = run([it])[0], run([first_only])[0]
    finally:
        hunt.rules_text = old
    assert c["gates"]["kyc"] == "FAIL" and c["status"] == "REJECTED" and c["tier"] is None
    assert any("immunefi.com" in e for e in c["evidence"]["kyc"])
    assert f["gates"]["kyc"] == "UNKNOWN"  # documents the old failure mode: reading only the sponsor homepage finds nothing


def test_inr_is_never_treated_as_usd():
    from common import parse_money
    m = parse_money('\u20b9 <span data-currency-value>500,000</span>')
    assert m["currency"] == "INR" and m["amount"] == 500000 and 3000 < m["usd"] < 10000
    assert parse_money("$25,000")["usd"] == 25000 and parse_money("5 Lakhs INR")["amount"] == 500000
    assert parse_money("1,000 XYZ")["usd"] is None and parse_money("500,000")["usd"] is None  # unknown currency is never assumed USD
    import collectors
    api = {"hackathons": [{"id": 1, "title": "Rupee", "url": "https://r.devpost.com/", "displayed_location": {"location": "Online"},
                           "time_left_to_submission": "about 1 month left", "prize_amount": '\u20b9 <span data-currency-value>500,000</span>',
                           "registrations_count": 3, "themes": [], "organization_name": "Org"},
                          {"id": 2, "title": "Mystery", "url": "https://m.devpost.com/", "displayed_location": {"location": "Online"},
                           "time_left_to_submission": "about 1 month left", "prize_amount": "500,000 XYZ", "themes": []}]}
    old = collectors.fetch_json
    collectors.fetch_json = lambda u, **k: (200, api)
    try:
        items, _ = collectors.devpost(pages=1)
    finally:
        collectors.fetch_json = old
    assert [i["title"] for i in items] == ["Rupee"] and items[0]["reward_usd"] < 10000
    assert items[0]["provenance"]["prize_currency"] == "INR" and items[0]["provenance"]["prize_amount"] == 500000


def test_aditya_onsite_fee_student_fail_from_sponsor_text_and_claim():
    from gates import analyze
    g = analyze(ADITYA)["gates"]
    assert g["onsite"]["verdict"] == g["paid_action"]["verdict"] == g["student"]["verdict"] == "FAIL"
    assert analyze("Finals are in-person or online, your choice. Free to enter.")["gates"]["onsite"]["verdict"] != "FAIL"
    # Devpost itself is behind an anti-bot wall: the cached sponsor-site claim (evidence/claims.json) rejects it, the blocked page adds nothing
    old_evid, old_rt, old_fetch, old_render = hunt.EVID, hunt.rules_text, hunt.fetch, hunt.render_text
    hunt.EVID, hunt.rules_text = tempfile.mkdtemp(), ORIG_RULES_TEXT
    hunt.fetch, hunt.render_text = (lambda u, **k: (403, "Just a moment...")), (lambda u: "Just a moment... Enable JavaScript and cookies to continue")
    try:
        txt, how = hunt.rules_text("https://hackwithaditya.devpost.com/rules")
        it = {"kind": "task", "lane": "BUILD", "source": "devpost", "native_id": "31737", "title": "HackWithAditya", "reward_usd": 5500,
              "deadline": "2999-01-01T00:00:00Z", "rules_url": "https://hackwithaditya.devpost.com/rules"}
        other = dict(it, native_id="99999", title="Other devpost", discovery_text="Build an AI agent demo.")
        a, b = run([it])[0], run([other])[0]
    finally:
        hunt.EVID, hunt.rules_text, hunt.fetch, hunt.render_text = old_evid, old_rt, old_fetch, old_render
    assert (txt, how) == ("", "blocked")
    assert a["status"] == "REJECTED" and {a["gates"][k] for k in ("onsite", "paid_action", "student")} == {"FAIL"}
    assert b["status"] == "NEEDS_CHECK" and b["tier"] == "PROMISING" and b["rules_blocked"]  # blocked wall != FAIL, != PASS


def test_agent_visa_stays_rejected_by_its_non_cash_claim():
    # Regression: the 2026-10-06 "not a cash prize" evidence was stored as UNKNOWN, which verify() ignores, so the 10-17 tier policy re-shortlisted it.
    it = {"kind": "task", "lane": "BUILD", "source": "risein", "native_id": "/stacks/agent-visa", "title": "Agent Visa", "reward_usd": 15000,
          "deadline": "2999-01-01T00:00:00Z", "discovery_text": "The Celo Agent Visa is a tiered program for AI agents that transact on Celo. Agents qualify for the "
          "Tourist Visa with one transaction, the Work Visa with Self Agent ID, 1,000+ transactions and/or 5K+ volume."}
    c = run([it])[0]
    assert c["status"] == "REJECTED" and c["tier"] is None and c["gates"]["payout"] == "FAIL"
    # every ignored claim verdict is a latent re-shortlist: a cached rejection must be FAIL, never UNKNOWN
    for cl in json.load(open(os.path.join(hunt.EVID, "claims.json")))["claims"]:
        assert not (cl["verdict"] == "UNKNOWN" and re.search(r"not a (cash|money)|not a money opportunity", cl["quote"], re.I)), cl["source"]


def test_force_checks_all_sources_but_never_touches_cooldown_state():
    import datetime as dt
    hunt.STATE_F = os.path.join(hunt.EVID, "state_force.json")
    future = (dt.date.today() + dt.timedelta(days=5)).isoformat()
    state = {"taskmarket": {"empty_runs": 2, "cooldown_until": future}, "devpost": {"empty_runs": 1}}
    json.dump(state, open(hunt.STATE_F, "w"), indent=2)
    before = open(hunt.STATE_F, "rb").read()
    seen = []
    old = hunt.collect_live
    hunt.collect_live = lambda names=None: (seen.append(list(names)) or ([], {n: {"ok": True} for n in names}))
    inbox = tempfile.mkdtemp()
    try:
        hunt.main(["--live", "--force", inbox])
        assert seen[-1] == list(hunt.COLLECTORS)  # cooled-down taskmarket is checked too
        assert open(hunt.STATE_F, "rb").read() == before  # empty_runs / cooldown_until untouched
        hunt.main(["--live", inbox])  # scheduled behaviour: cooldown respected AND state updated
        assert "taskmarket" not in seen[-1] and "devpost" in seen[-1]
        after = json.load(open(hunt.STATE_F))
        assert after["devpost"]["empty_runs"] == 2 and after["taskmarket"]["cooldown_until"] == future
    finally:
        hunt.collect_live = old


def _bi(native, title="AI agent hackathon", text="Build an AI agent demo. Fully online.", reward=50000, deadline="2999-01-01T00:00:00Z", **kw):
    return dict({"kind": "task", "lane": "BUILD", "source": "s", "native_id": native, "title": title, "reward_usd": reward, "deadline": deadline,
                 "text": text, "url": f"https://x/{native}"}, **kw)


def _notify_run(items, state):
    hunt.run(tempfile.mkdtemp(), items, None, state)
    with open(os.path.join(hunt.DATA, "shortlist.md")) as f:
        return hunt.LAST_DELTA, f.read()


def test_notify_two_identical_runs_notify_once_and_never_hide_candidates():
    state = {}
    d1, md1 = _notify_run([_bi("a"), _bi("b", "Other AI hackathon")], state)
    assert len(d1["new"]) == 2 and md1.startswith("NOTIFY: 2 new")  # ONE consolidated message for both
    assert md1.count("\nNOTIFY") == 0 and md1.count("- NEW") == 2
    d2, md2 = _notify_run([_bi("a"), _bi("b", "Other AI hackathon")], state)
    assert not any(d2.values()) and md2.startswith("NOTIFY: NONE") and "NIST" in md2
    assert "AI agent hackathon" in md2 and "Other AI hackathon" in md2  # UNKNOWN candidates stay visible, only the notification is suppressed


def test_notify_ignores_score_order_title_and_unknown_flips_but_catches_material_changes():
    state = {}
    _notify_run([_bi("a"), _bi("b", "Second", reward=20000)], state)
    # reward/score/order change, retitle, UNKNOWN -> RISK wording: no notification
    d, _ = _notify_run([_bi("b", "Second", reward=90000), _bi("a", "Renamed title", reward=40000, text="Build an AI agent demo. Fully online. Winners may need to verify country of residence.")], state)
    assert not any(d.values())
    # evidence that changes eligibility: payout -> PASS and no fee -> PASS (tier stays PROMISING)
    d, md = _notify_run([_bi("a", text="Build an AI agent demo. Fully online. Prizes paid in USDC to your wallet. Free to enter.")], state)
    assert [c["title"] for c in d["changed"]] == ["AI agent hackathon"] and "payout ?->P" in "; ".join(d["changed"][0]["why"]) and not d["new"]
    # PROMISING -> VERIFIED
    full = "Build an AI agent demo. No KYC required. Open to everyone, anywhere. Free to enter. Fully online. Prizes paid in USDC."
    d, md = _notify_run([_bi("a", text=full)], state)
    assert d["changed"] and "PROMISING->VERIFIED" in d["changed"][0]["why"] and "CHANGED" in md
    d, _ = _notify_run([_bi("a", text=full)], state)
    assert not any(d.values())  # and then quiet again


def test_notify_identity_is_stable_id_not_title_and_returning_candidate_is_not_renotified():
    state = {}
    _notify_run([_bi("a", "Same Title")], state)
    d, _ = _notify_run([_bi("zzz", "Same Title", url="https://x/zzz")], state)
    assert len(d["new"]) == 1  # same title, different id -> a different candidate
    d, _ = _notify_run([_bi("a", "Totally different title")], state)
    assert not d["new"]  # same id, new title -> same candidate (it dropped out of the top and came back: no repeat)
    no_id = dict(_bi("q"), native_id=None, url="https://x/page?utm=1#frag")
    _notify_run([no_id], state)
    d, _ = _notify_run([dict(no_id, url="https://X/page/", title="retitled")], state)
    assert not d["new"]  # URL fallback is normalized (query/fragment/slash/case)


def test_notify_deadline_critical_once_and_state_survives_new_sessions():
    import datetime as dt
    soon = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=2)).isoformat()
    state = {}
    _notify_run([_bi("a")], state)
    hunt.save_notify_state(state)
    state2 = hunt.load_notify_state()  # fresh session: only the file survives
    assert state2["candidates"] == state["candidates"] and state2["candidates"]["s#a"]["told"]["tier"] == "PROMISING"
    d, md = _notify_run([_bi("a", deadline=soon)], state2)
    assert len(d["deadline"]) == 1 and not d["new"] and "DEADLINE" in md
    d, _ = _notify_run([_bi("a", deadline=soon)], state2)
    assert d["deadline"] == []  # alerted once only
    d, _ = _notify_run([_bi("n", deadline=soon)], state2)
    assert len(d["new"]) == 1 and d["deadline"] == []  # brand-new near-deadline candidate = single "new" line


def test_force_run_does_not_consume_notifications():
    hunt.STATE_F = os.path.join(hunt.EVID, "state_notify.json")
    if os.path.exists(hunt.notify_path()):
        os.remove(hunt.notify_path())
    old = hunt.collect_live
    hunt.collect_live = lambda names=None: ([_bi("f")], {n: {"ok": True} for n in names})
    inbox = tempfile.mkdtemp()
    try:
        hunt.main(["--live", "--force", inbox])
        assert not os.path.exists(hunt.notify_path())  # probe: nothing consumed
        hunt.main(["--live", inbox])
        assert hunt.LAST_DELTA["new"] and os.path.exists(hunt.notify_path())
        hunt.main(["--live", inbox])
        assert not any(hunt.LAST_DELTA.values())  # 2nd scheduled run: nothing repeated
    finally:
        hunt.collect_live = old


def test_unacknowledged_notification_is_repeated_once_and_ack_settles_it():
    # legacy (no ack protocol yet): told immediately, never repeated
    legacy = {}
    _notify_run([_bi("a")], legacy)
    assert not any(_notify_run([_bi("a")], legacy)[0].values())
    # ack protocol: notification failed (no ack) -> repeated as REMINDER, then settled after MAX attempts (bounded, no infinite spam)
    ns = {"ack_enabled": True}
    d1, _ = _notify_run([_bi("a")], ns)
    assert len(d1["new"]) == 1 and not d1["new"][0]["reminder"] and ns["candidates"]["s#a"]["told"] is None
    d2, md2 = _notify_run([_bi("a")], ns)
    assert len(d2["new"]) == 1 and d2["new"][0]["reminder"] and "REMINDER" in md2
    d3, _ = _notify_run([_bi("a")], ns)
    assert not any(d3.values())  # best-effort cap reached
    # ack protocol: delivered (agent called --ack-notify before sending) -> never repeated
    ns = {"ack_enabled": True}
    _notify_run([_bi("a")], ns)
    assert hunt.ack_notify(ns) == 1 and ns["candidates"]["s#a"]["pending"] is None and ns["candidates"]["s#a"]["told"]["tier"] == "PROMISING"
    assert not any(_notify_run([_bi("a")], ns)[0].values())
    # a material change while a notification is unconfirmed is announced relative to what the user was actually told
    ns = {"ack_enabled": True}
    _notify_run([_bi("a")], ns)
    d, _ = _notify_run([_bi("a", text="Build an AI agent demo. Fully online. Prizes paid in USDC to your wallet.")], ns)
    assert len(d["new"]) == 1 and not d["changed"]


def test_ack_command_enables_protocol_and_persists_acknowledgement():
    if os.path.exists(hunt.notify_path()):
        os.remove(hunt.notify_path())
    ns = hunt.load_notify_state()
    ns["ack_enabled"] = True
    _notify_run([_bi("a")], ns)
    hunt.save_notify_state(ns)
    hunt.main(["--ack-notify"])
    after = hunt.load_notify_state()
    assert after["ack_enabled"] is True and after["candidates"]["s#a"]["pending"] is None and after["candidates"]["s#a"]["told"]["tier"] == "PROMISING"
    hunt.main(["--ack-notify"])  # idempotent
    os.remove(hunt.notify_path())


def test_told_candidate_that_becomes_rejected_gets_one_correction_but_expiry_is_silent():
    state = {}
    _notify_run([_bi("k"), _bi("e", "Will expire")], state)
    d, md = _notify_run([_bi("k", text="Build an AI agent demo. Winners must complete KYC. Prizes paid in USDC."),
                         _bi("e", "Will expire", deadline="2020-01-01T00:00:00Z")], state)
    assert [i["title"] for i in d["rejected"]] == ["AI agent hackathon"] and d["rejected"][0]["why"] == ["kyc"]
    assert "CORRECTION" in md and "FAIL on kyc" in md and "Will expire" not in md.split("# Shortlist")[0]
    assert state["candidates"]["s#e"]["told"]["tier"] == "REJECTED"
    d, md = _notify_run([_bi("k", text="Build an AI agent demo. Winners must complete KYC. Prizes paid in USDC.")], state)
    assert not any(d.values()) and md.startswith("NOTIFY: NONE")  # correction is sent once
    # never-told rejected candidates stay silent
    d, _ = _notify_run([_bi("never", text="Winners must complete KYC. Prizes paid in USDC.")], {})
    assert not any(d.values())


def test_login_queue_lead_notifies_once():
    old = hunt.rules_text
    hunt.rules_text = lambda url: ("Continue with GitHub\nContinue with Google", "static")
    try:
        it = _bi("gated", "Gated hackathon", rules_url="https://gated.example/rules")
        state = {}
        d1, md1 = _notify_run([it], state)
        assert len(d1["login"]) == 1 and "LOGIN-QUEUE" in md1 and md1.count("NOTIFY:") == 1
        d2, md2 = _notify_run([it], state)
        assert not any(d2.values()) and md2.startswith("NOTIFY: NONE")
        ns = {"ack_enabled": True}
        _notify_run([it], ns)
        d, _ = _notify_run([it], ns)
        assert d["login"][0]["reminder"]  # unconfirmed login lead repeated once, same rule as candidates
    finally:
        hunt.rules_text = old


def _repo(reject_push=False):
    """A work clone + a local bare 'origin'; reject_push installs a pre-receive hook that fails like a 403 on a repo without push access."""
    base = tempfile.mkdtemp(dir=_SANDBOX)
    bare, work = os.path.join(base, "o.git"), os.path.join(base, "w")
    g = lambda *a, cwd=work: subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True)
    g("init", "-q", "--bare", "-b", "main", bare, cwd=base); g("clone", "-q", bare, work, cwd=base)
    g("config", "user.email", "t@t"); g("config", "user.name", "t")
    os.makedirs(os.path.join(work, "make_money", "evidence"))
    open(os.path.join(work, "make_money", "evidence", "notify_state.json"), "w").write("{}")
    g("add", "."); g("commit", "-qm", "base"); g("push", "-q", "origin", "HEAD:main")
    if reject_push:
        hook = os.path.join(bare, "hooks", "pre-receive")
        open(hook, "w").write("#!/bin/sh\necho 'remote: Permission denied: HTTP 403' >&2\nexit 1\n"); os.chmod(hook, 0o755)
    return work, bare, g


def _forbidden(work):
    """Point origin at a local HTTP server that answers 403 like the cloud git proxy does for a repo without push scope."""
    import http.server, threading
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self): self.send_response(403); self.end_headers(); self.wfile.write(b"access denied")
        do_POST = do_GET
        def log_message(self, *a): pass
    srv = http.server.HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    atexit.register(srv.shutdown)
    subprocess.run(["git", "remote", "set-url", "origin", f"http://127.0.0.1:{srv.server_port}/x.git"], cwd=work, check=True)
    return work


def test_preflight_ok_with_write_access_and_fails_without():
    work, _, _ = _repo()
    ok, why = persist.preflight("main", work)
    assert ok, why
    assert not persist.preflight("other-branch", work)[0]
    bad = _forbidden(_repo()[0])
    ok, why = persist.preflight("main", bad)
    assert not ok and "403" in why and "add_repo" in why
    notgit = tempfile.mkdtemp(dir=_SANDBOX)
    ok, why = persist.preflight(None, notgit)
    assert not ok and "not a git checkout" in why


def test_live_and_ack_refuse_to_run_without_write_access_and_leave_state_untouched():
    real, hunt.REQUIRE_WRITE_ACCESS, called = persist.ROOT, True, []
    bad = _forbidden(_repo()[0])
    persist.ROOT, hunt.collect_live = bad, (lambda names=None: called.append(1) or ([], {}))
    persist.preflight.__defaults__ = (None, bad, "origin")
    ns = hunt.load_notify_state(); ns["candidates"]["x#1"] = {"first_seen": "2026-01-01", "told": None, "pending": {"attempts": 1, "tier": "PROMISING", "sig": "?????", "deadline_alerted": False}}
    hunt.save_notify_state(ns); before = open(hunt.notify_path(), "rb").read()
    try:
        for argv in (["--live", tempfile.mkdtemp()], ["--ack-notify"]):
            try:
                hunt.main(argv); raise AssertionError("must refuse")
            except SystemExit as e:
                assert e.code == 1
        assert not called  # expensive hunt never started
        assert open(hunt.notify_path(), "rb").read() == before  # pending announcement NOT consumed
    finally:
        persist.ROOT, hunt.REQUIRE_WRITE_ACCESS = real, False
        persist.preflight.__defaults__ = (None, real, "origin")
        os.remove(hunt.notify_path())


def test_persist_pushes_and_verifies_remote_head():
    work, bare, g = _repo()
    open(os.path.join(work, "make_money", "evidence", "notify_state.json"), "w").write('{"a": 1}')
    ok, why = persist.persist("hunter run test", "main", work, backoff=())
    assert ok, why
    assert g("rev-parse", "main", cwd=bare).stdout == g("rev-parse", "HEAD").stdout
    assert g("show", "main:make_money/evidence/notify_state.json", cwd=bare).stdout == '{"a": 1}'
    ok, why = persist.persist("again", "main", work, backoff=())  # nothing new: still verified OK
    assert ok, why


def test_failed_push_is_loud_and_remote_state_stays_pending():
    work, bare, g = _repo(reject_push=True)
    before = g("rev-parse", "main", cwd=bare).stdout
    open(os.path.join(work, "make_money", "evidence", "notify_state.json"), "w").write('{"acked": true}')
    slept = []
    old = persist.time.sleep; persist.time.sleep = slept.append
    try:
        ok, why = persist.persist("hunter run test", "main", work)
    finally:
        persist.time.sleep = old
    assert not ok and "auth" in why and "add_repo" in why and not slept  # auth failure: no pointless backoff
    assert g("rev-parse", "main", cwd=bare).stdout == before  # remote notify_state.json unchanged -> announcements stay pending
    # CLI contract: exit code 2 + BLOCKER text
    real, persist.ROOT = persist.ROOT, work
    import io, contextlib
    persist.persist.__defaults__ = (None, work, "origin", persist.PERSIST_PATHS, ())
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            try:
                hunt.main(["--persist", "x", "--branch", "main"]); raise AssertionError("must exit 2")
            except SystemExit as e:
                assert e.code == 2
    finally:
        persist.ROOT = real; persist.persist.__defaults__ = (None, real, "origin", persist.PERSIST_PATHS, persist.BACKOFF)
    assert "PERSIST: FAILED" in buf.getvalue() and "BLOCKER" in buf.getvalue()


def test_persist_retries_network_errors_then_gives_up():
    work, _, _ = _repo()
    g = lambda *a: subprocess.run(["git", *a], cwd=work, check=True, capture_output=True)
    g("remote", "set-url", "origin", "/nonexistent/path.git")
    slept = []
    old = persist.time.sleep; persist.time.sleep = slept.append
    try:
        ok, why = persist.persist("x", "main", work, backoff=(2, 4, 8, 16))
    finally:
        persist.time.sleep = old
    assert not ok and "after 5 attempts" in why and slept == [2, 4, 8, 16]


def test_tests_ran_in_sandbox_and_real_evidence_is_untouched():
    assert hunt.EVID.startswith(_SANDBOX) and hunt.DATA.startswith(_SANDBOX) and common.DATA.startswith(_SANDBOX)
    assert hunt.EVID != REAL_EVID and hunt.DATA != REAL_OUT
    now = _tree_hash(REAL_EVID, REAL_OUT) if os.path.isdir(REAL_OUT) else _tree_hash(REAL_EVID)
    assert now == REAL_HASH


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
