"""Correctness and security behaviour of the proposed framework (C1, C2, C3, TR)."""
import os
import pytest

from cutcord import ec, ours, sym
from cutcord.ec import P, mul, enc_point

NOW = 1_000


@pytest.fixture(scope="module")
def world():
    ta = ours.TA()
    ta_creds = ta.register_tuav("TUAV-A")
    tb_creds = ta.register_tuav("TUAV-B")
    A = ours.TUAV("TUAV-A", ta_creds, ta.Ppub)
    B = ours.TUAV("TUAV-B", tb_creds, ta.Ppub)
    rids = [os.urandom(16) for _ in range(6)]
    uavs = [ours.Member(ta.register(r, 3), ta.Ppub) for r in rids[:4]]
    vehs = [ours.Member(ta.register(r, 3), ta.Ppub, role="veh") for r in rids[4:]]
    return ta, A, B, rids, uavs, vehs


def join(A, members, ep=1, now=NOW):
    b = A.beacon(now)
    reqs = [m.request(b, ep, now) for m in members]
    acc, st = A.verify_window(reqs, now, ep)
    acks = A.admit(acc, now)
    return reqs, acc, acks, st


def test_registration_keys_consistent(world):
    ta, *_ , uavs, _ = world
    c = uavs[0].cred(1)
    assert ec.eq(mul(P, c.sk), ours.public_key(ta.Ppub, c.ident, c.ep, c.X, c.Y))


def test_c1_join_and_group_key(world):
    ta, A, B, rids, uavs, vehs = world
    reqs, acc, acks, st = join(A, uavs)
    assert len(acc) == 4 and st["batch_checks"] == 1 and st["single_checks"] == 0
    assert all(u.receive(acks["join"]) for u in uavs)
    assert len({u.GK for u in uavs}) == 1 and uavs[0].GK == A.GK


def test_ta_cannot_sign_without_x(world):
    """escrow-freeness: the TA knows d but not x"""
    ta, A, B, rids, uavs, vehs = world
    c = uavs[0].cred(2)
    fake = ours.Credential(c.ident, c.ep, c.X, c.Y, c.d, x=ec.rand_scalar())   # TA guesses x
    R, v = ours.sign(fake, b"m", NOW)
    assert not ours.verify(ta.Ppub, c.ident, c.ep, c.X, c.Y, b"m", NOW, R, v)


def test_key_replacement_fails(world):
    """type-I: replacing X invalidates the TA's partial key"""
    ta, A, B, rids, uavs, vehs = world
    c = uavs[1].cred(2)
    x2 = ec.rand_scalar()
    forged = ours.Credential(c.ident, c.ep, mul(P, x2), c.Y, c.d, x2)
    R, v = ours.sign(forged, b"m", NOW)
    assert not ours.verify(ta.Ppub, forged.ident, forged.ep, forged.X, forged.Y, b"m", NOW, R, v)


def test_batch_rejects_cancelling_errors(world):
    ta, A, B, rids, uavs, vehs = world
    b = A.beacon(NOW)
    reqs = [u.request(b, 2, NOW) for u in uavs[:2]]
    delta = 12345
    reqs[0].v = (reqs[0].v + delta) % ec.q
    reqs[1].v = (reqs[1].v - delta) % ec.q
    items = [A._item(r) for r in reqs]
    assert not ours.batch_verify(ta.Ppub, items)


def test_fallback_keeps_honest_and_evicts_bad(world):
    ta, A, B, rids, uavs, vehs = world
    T = ours.TUAV("TUAV-A", A.cred, ta.Ppub)
    b = T.beacon(NOW)
    reqs = [u.request(b, 3, NOW) for u in uavs]
    reqs[2].v = (reqs[2].v + 1) % ec.q
    acc, st = T.verify_window(reqs, NOW, 3)
    assert len(acc) == 3 and reqs[2].key in T.evicted and T.mode == "individual"
    assert st["batch_checks"] == 1 and st["single_checks"] == 4


def test_replayed_request_rejected_in_new_beacon(world):
    ta, A, B, rids, uavs, vehs = world
    T = ours.TUAV("TUAV-A", A.cred, ta.Ppub)
    b1 = T.beacon(NOW)
    old = uavs[0].request(b1, 2, NOW)
    T.beacon(NOW + 1)                                   # new E_a
    acc, _ = T.verify_window([old], NOW + 1, 2)
    assert acc == []


def test_rekey_locks_out_removed(world):
    ta, A, B, rids, uavs, vehs = world
    removed = uavs[3]
    old_K = removed.K
    rk = A.rekey([removed.cred(1).key], NOW + 2)
    assert all(u.receive_update(rk) for u in uavs[:3])
    assert not removed.receive_update(rk)
    # the removed member cannot open anyone else's entry with its own key
    for key, blob in rk["entries"]:
        assert sym.open_(old_K, blob, key + rk["nu"].to_bytes(4, "big") + rk["ts"].to_bytes(8, "big")) is None
    assert uavs[0].GK == A.GK != removed.GK


def test_c2_vehicle_admission_via_relay(world):
    ta, A, B, rids, uavs, vehs = world
    b = A.beacon(NOW + 3)
    vreqs = [v.request(b, 1, NOW + 3) for v in vehs]
    bundle = uavs[0].relay(vreqs, NOW + 3)
    ack, st = A.process_bundle(bundle, NOW + 3, 1)
    assert ack is not None and all(v.receive(ack) for v in vehs)
    assert vehs[0].GK == A.VK != A.GK                       # privilege separation


def test_c2_outsider_bundle_dropped(world):
    ta, A, B, rids, uavs, vehs = world
    b = A.beacon(NOW + 4)
    vreqs = [vehs[0].request(b, 2, NOW + 4)]
    bundle = {"relay": os.urandom(32), "ts": NOW + 4, "reqs": vreqs, "tag": os.urandom(32)}
    ack, st = A.process_bundle(bundle, NOW + 4, 2)
    assert ack is None and "dropped" in st


def test_c3_handover(world):
    ta, A, B, rids, uavs, vehs = world
    oa, ob = A.link_offer(NOW), B.link_offer(NOW)
    A.link_accept(ob, NOW); B.link_accept(oa, NOW)
    assert A.links[B.id] == B.links[A.id]
    m = uavs[0]
    m.take_ticket(A.issue_ticket(m.cred(1).key, B.id, NOW + 5), B.id)
    msg = m.handover_request(A.id, NOW + 6)
    resp, why = B.accept_handover(msg, NOW + 6)
    assert why == "ok" and m.handover_finish(resp, B.id) and m.GK == B.GK
    again, why2 = B.accept_handover(msg, NOW + 6)          # replayed ticket
    assert again is None and why2 == "ticket replayed"


def test_c3_evicted_member_cannot_hand_over(world):
    ta, A, B, rids, uavs, vehs = world
    m = uavs[1]
    m.take_ticket(A.issue_ticket(m.cred(1).key, B.id, NOW + 7), B.id)
    A.evicted.add(m.cred(1).key)
    B.merge_evictions(A.id, A.share_evictions(B.id))
    resp, why = B.accept_handover(m.handover_request(A.id, NOW + 8), NOW + 8)
    assert resp is None and why == "evicted"


def test_tracing_and_global_revocation(world):
    ta, A, B, rids, uavs, vehs = world
    c = uavs[2].cred(2)
    assert ta.trace(c.PID1, c.PID2, 2) == rids[2]
    banned = ta.revoke(rids[2], from_epoch=2)
    assert c.key in banned and uavs[2].cred(1).key not in banned    # past stays unlinkable
    A.apply_revocation(banned)
    b = A.beacon(NOW + 9)
    acc, _ = A.verify_window([uavs[2].request(b, 2, NOW + 9)], NOW + 9, 2)
    assert acc == []


def test_pseudonyms_unlinkable_across_epochs(world):
    ta, A, B, rids, uavs, vehs = world
    c1, c2 = uavs[0].cred(1), uavs[0].cred(2)
    assert c1.ident != c2.ident and not ec.eq(c1.X, c2.X) and not ec.eq(c1.Y, c2.Y)
