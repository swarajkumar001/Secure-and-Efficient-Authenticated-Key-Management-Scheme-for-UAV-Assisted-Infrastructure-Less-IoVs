"""The six flaws of the first design (each must succeed against ours.py and fail against
hardened.py), functional regression of the hardened scheme, and C4 quorum eviction."""
import os
import pytest

from cutcord import ec, hardened as hd, ours, sym
from cutcord.ec import P, mul, enc_point

NOW = 1_000


def world(mod_ta, mod_tuav, ids=("TUAV-A", "TUAV-B")):
    ta = mod_ta()
    ts = [mod_tuav(i, ta.register_tuav(i), ta.Ppub) for i in ids]
    for i, a in enumerate(ts):
        for b in ts[i + 1:]:
            oa, ob = a.link_offer(NOW), b.link_offer(NOW)
            a.link_accept(ob, NOW); b.link_accept(oa, NOW)
    return (ta, *ts)


@pytest.fixture
def v1():
    return world(ours.TA, ours.TUAV)


@pytest.fixture
def h():
    return world(hd.HardenedTA, hd.HardenedTUAV)


def v1_member(ta, role="join"):
    return ours.Member(ta.register(os.urandom(16), 2), ta.Ppub, role=role)


def h_member(ta, role="join"):
    return hd.HardenedMember(ta.register(os.urandom(16), 2, role=role), ta.Ppub, role=role)


def join(T, ms, ep=1, now=NOW):
    b = T.beacon(now)
    acc, st = T.verify_window([m.request(b, ep, now) for m in ms], now, ep)
    acks = T.admit(acc, now)
    for m in ms:
        if m.role in ("join",) and "join" in acks:
            m.receive(acks["join"])
        if m.role == "veh" and "veh" in acks:
            m.receive(acks["veh"])
    return acc, acks, st


def junk_for(c, now=NOW):
    return ours.Request(c.ident, c.ep, c.X, c.Y, mul(P, 7), now, mul(P, 9), 12345)


def mint(A, B, ident, ep, X, Y, hk, role=b"join", now=NOW):
    """what a captured TUAV can build from K_ab alone"""
    N = os.urandom(12)
    body = (len(ident).to_bytes(2, "big") + ident + ep.to_bytes(4, "big") + enc_point(X) + enc_point(Y)
            + role + hk + N + (now + 30).to_bytes(8, "big"))
    return sym.seal(A.links[B.id], body, A.id + B.id)


# ---------------------------------------------------------------- A1 spoofed failure
def test_a1_v1_one_forged_packet_evicts_an_honest_uav(v1):
    ta, A, B = v1
    ms = [v1_member(ta) for _ in range(3)]
    c = ms[1].cred(1)
    b = A.beacon(NOW)
    A.verify_window([junk_for(c)] + [m.request(b, 1, NOW) for m in ms], NOW, 1)
    assert c.key in A.evicted
    b2 = A.beacon(NOW + 1)
    assert A.verify_window([ms[1].request(b2, 1, NOW + 1)], NOW + 1, 1)[0] == []
    B.merge_evictions(A.id, A.share_evictions(B.id))
    assert c.key in B.evicted


def test_a1_hardened_forged_packet_evicts_nobody(h):
    ta, A, B = h
    ms = [h_member(ta) for _ in range(3)]
    c = ms[1].cred(1)
    b = A.beacon(NOW)
    acc, st = A.verify_window([junk_for(c)] + [m.request(b, 1, NOW) for m in ms], NOW, 1)
    assert len(acc) == 3 and c.key not in A.evicted and st["rejected"] == 1


def test_a1_hardened_every_pid_spoofed_all_still_admitted(h):
    ta, A, _ = h
    ms = [h_member(ta) for _ in range(6)]
    b = A.beacon(NOW)
    reqs = [junk_for(m.cred(1)) for m in ms] + [m.request(b, 1, NOW) for m in ms]
    acc, st = A.verify_window(reqs, NOW, 1)
    assert len(acc) == 6 and not A.evicted and st["single_checks"] == 12


def test_a1_hardened_cost_is_bounded_per_pseudonym(h):
    ta, A, _ = h
    m = h_member(ta)
    b = A.beacon(NOW)
    reqs = [junk_for(m.cred(1)) for _ in range(40)] + [m.request(b, 1, NOW)]
    reqs[:40] = [ours.Request(r.ident, r.ep, r.X, r.Y, r.E, r.ts, r.R, i) for i, r in enumerate(reqs[:40])]
    _, st = A.verify_window(reqs, NOW, 1)
    assert st["single_checks"] <= hd.PER_PID


def test_a1_retransmission_is_not_a_conflict(h):
    ta, A, _ = h
    m = h_member(ta)
    b = A.beacon(NOW)
    r = m.request(b, 1, NOW)
    assert m.request(b, 1, NOW) is r
    acc, st = A.verify_window([r, r], NOW, 1)
    assert acc == [r] and not A.evicted and st["batch_checks"] == 1


def test_a1_member_never_signs_twice_under_one_beacon(h):
    """otherwise a captured TUAV re-offers its beacon after the join and frames the member"""
    ta, A, B = h
    m = h_member(ta)
    b = A.beacon(NOW)
    r1 = m.request(b, 1, NOW)
    m.receive(A.admit(A.verify_window([r1], NOW, 1)[0], NOW)["join"])
    assert m.pending is None and m.request(b, 1, NOW) is r1
    assert B.merge_evictions(A.id, [(A.id, A.E_a, r1, r1)]) == 0


def test_cloned_credential_is_evicted_on_evidence(h):
    ta, A, B = h
    m = h_member(ta)
    b = A.beacon(NOW)
    r1 = m.request(b, 1, NOW)
    clone = hd.HardenedMember(list(m.creds.values()), ta.Ppub)
    r2 = clone.request(b, 1, NOW)
    acc, _ = A.verify_window([r1, r2], NOW, 1)
    assert acc == [] and r1.key in A.evicted
    assert B.merge_evictions(A.id, A.share_evictions(B.id)) == 1 and r1.key in B.evicted


# ---------------------------------------------------------------- A2 phantom tickets
def _phantom_attack(A, B, sign_as=None):
    ident, hk, e = b"phantom" + b"U", os.urandom(16), ec.rand_scalar()
    X, Y, E = mul(P, 3), mul(P, 5), mul(P, e)
    tk = mint(A, B, ident, 1, X, Y, hk)
    msg = {"from": A.id, "ticket": tk, "E": E, "ts": NOW,
           "tau": sym.mac(hk, tk, enc_point(E), NOW.to_bytes(8, "big")), "R": mul(P, 11), "v": 77}
    return B.accept_handover(msg, NOW), hk, e, ident


def test_a2_v1_captured_tuav_gets_the_neighbours_group_key(v1):
    ta, A, B = v1
    (resp, why), hk, e, ident = _phantom_attack(A, B)
    assert why == "ok"
    K2 = sym.kdf(enc_point(mul(resp["E"], e)), hk, ident, B.id)
    assert sym.open_(K2, resp["blob"], enc_point(resp["E"]) + resp["ts"].to_bytes(8, "big"))[:16] == B.GK


def test_a2_hardened_phantom_rejected(h):
    ta, A, B = h
    (resp, why), *_ = _phantom_attack(A, B)
    assert resp is None and why == "bad member signature"


def test_a2_hardened_captured_tuav_cannot_use_its_own_credential(h):
    ta, A, B = h
    hk, E = os.urandom(16), mul(P, 13)
    tk = mint(A, B, A.id, 0, A.cred.X, A.cred.Y, hk)
    R, v = ours.sign(A.cred, hd.handover_msg(A.id, B.id, tk, E), NOW)
    msg = {"from": A.id, "ticket": tk, "E": E, "ts": NOW, "tau": sym.mac(hk, tk, enc_point(E), NOW.to_bytes(8, "big")), "R": R, "v": v}
    assert B.accept_handover(msg, NOW) == (None, "not a member credential")


def test_a2_hardened_self_made_credential_rejected(h):
    """the attacker chooses x and y itself, but h binds them to the master key it lacks"""
    ta, A, B = h
    x, y = ec.rand_scalar(), ec.rand_scalar()
    ident, X, Y = os.urandom(80) + b"U", mul(P, x), mul(P, y)
    fake = ours.Credential(ident, 1, X, Y, y, x)
    hk, E = os.urandom(16), mul(P, 13)
    tk = mint(A, B, ident, 1, X, Y, hk)
    R, v = ours.sign(fake, hd.handover_msg(A.id, B.id, tk, E), NOW)
    msg = {"from": A.id, "ticket": tk, "E": E, "ts": NOW, "tau": sym.mac(hk, tk, enc_point(E), NOW.to_bytes(8, "big")), "R": R, "v": v}
    assert B.accept_handover(msg, NOW) == (None, "bad member signature")


def test_a2_v1_mint_displaces_an_honest_member(v1):
    ta, A, B = v1
    m = v1_member(ta); join(B, [m])
    c = m.cred(1); hk, e = os.urandom(16), ec.rand_scalar(); E = mul(P, e)
    tk = mint(A, B, c.ident, 1, c.X, c.Y, hk)
    B.accept_handover({"from": A.id, "ticket": tk, "E": E, "ts": NOW,
                       "tau": sym.mac(hk, tk, enc_point(E), NOW.to_bytes(8, "big"))}, NOW)
    assert not m.receive_update(B.rekey([], NOW + 1))


def test_a2_hardened_member_cannot_be_displaced(h):
    ta, A, B = h
    m = h_member(ta); join(B, [m])
    before = B.members[m.cred(1).key][0]
    c = m.cred(1); hk, E = os.urandom(16), mul(P, 13)
    tk = mint(A, B, c.ident, 1, c.X, c.Y, hk)
    msg = {"from": A.id, "ticket": tk, "E": E, "ts": NOW, "tau": sym.mac(hk, tk, enc_point(E), NOW.to_bytes(8, "big")),
           "R": mul(P, 3), "v": 5}
    assert B.accept_handover(msg, NOW)[0] is None and B.members[c.key][0] == before
    assert m.receive_update(B.rekey([], NOW + 1))


def test_hardened_handover_works_and_is_single_use(h):
    ta, A, B = h
    m = h_member(ta); join(A, [m])
    k = m.cred(1).key
    m.take_ticket(A.issue_ticket(k, B.id, NOW), B.id)
    msg = m.handover_request(A.id, B.id, NOW + 1)
    resp, why = B.accept_handover(msg, NOW + 1)
    assert why == "ok" and m.handover_finish(resp, B.id) and m.GK == B.GK
    assert B.accept_handover(msg, NOW + 1) == (None, "ticket replayed")


def test_hardened_handover_signature_binds_the_destination(h):
    ta, A, B = h
    C = hd.HardenedTUAV("TUAV-C", ta.register_tuav("TUAV-C"), ta.Ppub)
    oa, oc = A.link_offer(NOW), C.link_offer(NOW); A.link_accept(oc, NOW); C.link_accept(oa, NOW)
    m = h_member(ta); join(A, [m])
    m.take_ticket(A.issue_ticket(m.cred(1).key, B.id, NOW), B.id)
    msg = m.handover_request(A.id, B.id, NOW + 1)
    assert C.accept_handover(msg, NOW + 1)[0] is None


# ---------------------------------------------------------------- A7 captured old TUAV poses as the new one
def _fake_reply(A, B, m, msg, sign_with=None):
    """the captured old TUAV knows K_M, hence hk, and answers the member in B's name"""
    hk = sym.kdf(A.members[m.cred(1).key][0], b"HO", B.id, NOW.to_bytes(8, "big"))
    e_x = ec.rand_scalar(); E_x = mul(P, e_x)
    K2 = sym.kdf(enc_point(mul(msg["E"], e_x)), hk, m.cred(1).ident, B.id)
    fake_gk = os.urandom(16)
    resp = {"E": E_x, "ts": msg["ts"], "blob": sym.seal(K2, fake_gk + (99).to_bytes(4, "big"), enc_point(E_x) + msg["ts"].to_bytes(8, "big"))}
    if sign_with is not None:
        R, v = ours.sign(sign_with, hd.handover_reply_msg(A.id, B.id, msg["ticket"], msg["E"], E_x), msg["ts"])
        resp.update(X=sign_with.X, Y=sign_with.Y, R=R, v=v)
    return resp, fake_gk, K2


def test_a7_v1_captured_old_tuav_poses_as_the_new_one(v1):
    ta, A, B = v1
    m = v1_member(ta); join(A, [m])
    m.take_ticket(A.issue_ticket(m.cred(1).key, B.id, NOW), B.id)
    msg = m.handover_request(A.id, NOW + 1)
    resp, fake_gk, K2 = _fake_reply(A, B, m, msg)
    assert m.handover_finish(resp, B.id) and m.GK == fake_gk and m.K == K2   # A now holds the member's new key


def test_a7_hardened_forged_reply_rejected_genuine_still_accepted(h):
    ta, A, B = h
    m = h_member(ta); join(A, [m])
    m.take_ticket(A.issue_ticket(m.cred(1).key, B.id, NOW), B.id)
    msg = m.handover_request(A.id, B.id, NOW + 1)
    for signer in (None, A.cred):                       # unsigned, or signed with A's own credential
        resp, fake_gk, _ = _fake_reply(A, B, m, msg, sign_with=signer)
        assert not m.handover_finish(resp, B.id) and m.GK != fake_gk
    resp, why = B.accept_handover(msg, NOW + 1)
    assert why == "ok" and m.handover_finish(resp, B.id) and m.GK == B.GK


def test_a7_hardened_reply_bound_to_this_handover(h):
    """a genuine reply from B to another member cannot be replayed to this one"""
    ta, A, B = h
    m1, m2 = h_member(ta), h_member(ta); join(A, [m1, m2])
    for m in (m1, m2):
        m.take_ticket(A.issue_ticket(m.cred(1).key, B.id, NOW), B.id)
    msg1, msg2 = m1.handover_request(A.id, B.id, NOW + 1), m2.handover_request(A.id, B.id, NOW + 1)
    resp1, _ = B.accept_handover(msg1, NOW + 1)
    assert not m2.handover_finish(resp1, B.id)
    assert m1.handover_finish(resp1, B.id)


# ---------------------------------------------------------------- A3 false lists
def test_a3_v1_captured_tuav_frames_a_member(v1):
    ta, A, B = v1
    m = v1_member(ta)
    B.merge_evictions(A.id, sym.seal(A.links[B.id], m.cred(1).key, A.id))
    assert m.cred(1).key in B.evicted


def test_a3_hardened_list_without_evidence_is_ignored(h):
    ta, A, B = h
    m = h_member(ta)
    b = A.beacon(NOW)
    r = m.request(b, 1, NOW)
    bogus = (A.id, A.E_a, r, junk_for(m.cred(1)))
    assert B.merge_evictions(A.id, [bogus]) == 0 and m.cred(1).key not in B.evicted


def test_a3_hardened_revocation_needs_the_ta(h):
    ta, A, B = h
    rid = os.urandom(16)
    creds = ta.register(rid, 2)
    rl = ta.revoke_signed(rid, 1, NOW)
    assert A.apply_revocation(rl) and creds[0].key in A.evicted
    forged = dict(rl, hashes=[os.urandom(32)])
    assert not B.apply_revocation(forged)


# ---------------------------------------------------------------- A4 role
def test_a4_v1_vehicle_credential_obtains_the_uav_key(v1):
    ta, A, _ = v1
    impostor = ours.Member(ta.register(os.urandom(16), 1), ta.Ppub, role="join")
    join(A, [impostor])
    assert impostor.GK == A.GK


def test_a4_hardened_vehicle_cannot_claim_the_uav_role(h):
    ta, A, _ = h
    impostor = hd.HardenedMember(ta.register(os.urandom(16), 1, role="veh"), ta.Ppub, role="join")
    acc, _, st = join(A, [impostor])
    assert acc == [] and st["filtered"] == 1


def test_a4_hardened_rewriting_the_role_tag_breaks_the_signature(h):
    ta, A, _ = h
    v = hd.HardenedMember(ta.register(os.urandom(16), 1, role="veh"), ta.Ppub, role="veh")
    b = A.beacon(NOW)
    r = v.request(b, 1, NOW)
    r2 = ours.Request(r.ident[:-1] + b"U", r.ep, r.X, r.Y, r.E, r.ts, r.R, r.v, "join")
    assert A.verify_window([r2], NOW, 1)[0] == []


def test_a4_hardened_vehicle_tier_still_works(h):
    ta, A, _ = h
    relay = h_member(ta); join(A, [relay])
    vs = [h_member(ta, "veh") for _ in range(2)]
    b = A.beacon(NOW + 1)
    ack, _ = A.process_bundle(relay.relay([v.request(b, 1, NOW + 1) for v in vs], NOW + 1), NOW + 1, 1)
    assert all(v.receive(ack) for v in vs) and vs[0].GK == A.VK != A.GK


# ---------------------------------------------------------------- A5 rollback
def test_a5_v1_old_update_rolls_a_member_back(v1):
    ta, A, _ = v1
    us = [v1_member(ta) for _ in range(3)]; join(A, us)
    rk1 = A.rekey([], NOW + 1)
    for u in us:
        u.receive_update(rk1)
    old = us[0].GK
    us[0].receive_update(A.rekey([us[2].cred(1).key], NOW + 2))
    assert us[0].receive_update(rk1) and us[0].GK == old == us[2].GK


def test_a5_hardened_old_update_refused(h):
    ta, A, _ = h
    us = [h_member(ta) for _ in range(3)]; join(A, us)
    rk1 = A.rekey([], NOW + 1)
    for u in us:
        assert u.receive_update(rk1)
    rk2 = A.rekey([us[2].cred(1).key], NOW + 2)
    assert us[0].receive_update(rk2) and not us[2].receive_update(rk2)
    assert not us[0].receive_update(rk1) and us[0].GK == A.GK


# ---------------------------------------------------------------- A6 key in use
def test_a6_v1_joiner_gets_the_key_already_in_use(v1):
    ta, A, _ = v1
    u = v1_member(ta); join(A, [u])
    in_use = A.GK
    later = v1_member(ta); join(A, [later])
    assert later.GK == in_use


def test_a6_hardened_joiner_gets_a_fresh_key_and_members_follow(h):
    ta, A, _ = h
    u = h_member(ta); join(A, [u])
    in_use = A.GK
    later = h_member(ta); join(A, [later], now=NOW + 1)
    assert later.GK == A.GK != in_use
    role, update = A.outbox.pop()
    assert role == "join" and u.receive_update(update) and u.GK == A.GK


def test_a6_hardened_arrival_by_handover_rekeys_and_departure_locks_out(h):
    ta, A, B = h
    stay_a, stay_b, m = h_member(ta), h_member(ta), h_member(ta)
    join(A, [stay_a, m]); join(B, [stay_b])
    k = m.cred(1).key
    gk_a, gk_b = A.GK, B.GK
    m.take_ticket(A.issue_ticket(k, B.id, NOW + 1), B.id)
    resp, _ = B.accept_handover(m.handover_request(A.id, B.id, NOW + 2), NOW + 2)
    assert m.handover_finish(resp, B.id) and m.GK == B.GK != gk_b
    assert stay_b.receive_update(B.outbox.pop()[1]) and stay_b.GK == B.GK
    update = A.depart(k, NOW + 2)
    assert stay_a.receive_update(update) and A.GK != gk_a and m.GK != A.GK


def test_a6_hardened_vehicle_key_rotates_too(h):
    ta, A, _ = h
    relay = h_member(ta); join(A, [relay])
    vs = [h_member(ta, "veh") for _ in range(2)]
    b = A.beacon(NOW + 1)
    ack, _ = A.process_bundle(relay.relay([v.request(b, 1, NOW + 1) for v in vs], NOW + 1), NOW + 1, 1)
    for v in vs:
        v.receive(ack)
    old = A.VK
    update = A.rekey([vs[1].cred(1).key], NOW + 2, role="veh")
    assert vs[0].receive_update(update) and vs[0].GK == A.VK != old and not vs[1].receive_update(update)


# ---------------------------------------------------------------- C4 quorum eviction
@pytest.fixture
def cell_ring():
    return world(hd.HardenedTA, hd.HardenedTUAV, ids=("T0", "T1", "T2", "T3", "T4"))


def test_c4_t_votes_evict_and_neighbours_cut_the_link(cell_ring):
    ta, x, a, b, c, d = cell_ring
    assert b.receive_vote(a.vote(x.id, NOW)) is None
    cert = b.receive_vote(c.vote(x.id, NOW))
    assert cert and x.id in b.blocked and x.id not in b.links
    assert d.apply_cert(x.id, cert) and x.id not in d.links


def test_c4_member_refuses_beacons_after_the_certificate(cell_ring):
    ta, x, a, b, c, d = cell_ring
    m = h_member(ta)
    b1 = x.beacon(NOW)
    m.request(b1, 1, NOW)
    cert = [a.vote(x.id, NOW), b.vote(x.id, NOW)]
    assert m.apply_cert(x.id, cert)
    with pytest.raises(AssertionError):
        m.request(x.beacon(NOW + 1), 2, NOW + 1)


def test_c4_too_few_or_duplicate_votes_fail(cell_ring):
    ta, x, a, b, c, d = cell_ring
    assert not hd.cert_ok(ta.Ppub, x.id, [a.vote(x.id, NOW)], 2)
    assert not hd.cert_ok(ta.Ppub, x.id, [a.vote(x.id, NOW), a.vote(x.id, NOW + 1)], 2)


def test_c4_target_cannot_vote_and_votes_do_not_transfer(cell_ring):
    ta, x, a, b, c, d = cell_ring
    assert not hd.cert_ok(ta.Ppub, x.id, [x.vote(x.id, NOW), a.vote(x.id, NOW)], 2)
    assert not hd.cert_ok(ta.Ppub, b.id, [a.vote(x.id, NOW), c.vote(x.id, NOW)], 2)


def test_c4_member_credential_cannot_vote(cell_ring):
    ta, x, a, b, c, d = cell_ring
    cr = ta.register(os.urandom(16), 1)[0]
    R, v = ours.sign(cr, hd.vote_msg(x.id), NOW)
    vote = hd.Vote(cr.ident, cr.X, cr.Y, x.id, NOW, R, v)
    assert not hd.vote_ok(ta.Ppub, vote) and b.receive_vote(vote) is None
    assert not hd.cert_ok(ta.Ppub, x.id, [vote, a.vote(x.id, NOW)], 2)


def test_c4_handover_stops_after_eviction(cell_ring):
    ta, x, a, b, c, d = cell_ring
    m = h_member(ta); join(x, [m])
    m.take_ticket(x.issue_ticket(m.cred(1).key, b.id, NOW), b.id)
    assert b.apply_cert(x.id, [a.vote(x.id, NOW), c.vote(x.id, NOW)])
    assert b.accept_handover(m.handover_request(x.id, b.id, NOW + 1), NOW + 1)[0] is None
