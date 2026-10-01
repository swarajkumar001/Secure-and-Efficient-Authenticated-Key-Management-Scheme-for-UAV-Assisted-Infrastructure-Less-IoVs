"""
TUAV-assisted infrastructure-less IoV simulator - Streamlit shell.

Run from the folder ABOVE this one:

    streamlit run uav_iov_simulator/app.py

This module does routing and rendering only. Every state change goes through
`state.act_*`, and no rendering function here mutates anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `streamlit run uav_iov_simulator/app.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from uav_iov_simulator import config, state as S
from uav_iov_simulator.crypto.backend_pairing import is_available as pairing_available
from uav_iov_simulator.paper_model import cost as paper_cost
from uav_iov_simulator.paper_model import overhead as paper_overhead
from uav_iov_simulator.protocol.entities import Status
from uav_iov_simulator.simulation import datalink, experiments
from uav_iov_simulator.visualization import (
    network_graph, performance, presentation, protocol_animation, security,
)


st.set_page_config(
    page_title="TUAV IoV Simulator",
    page_icon="::",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------- styling --
st.markdown("""
<style>
  :root {
    --ink:#131820; --ink2:#55606D; --ink3:#8A949F;
    --rule:#DCE2E8; --panel:#F4F6F9;
    --amber:#A8580A; --amber-bg:#FCF3E7; --amber-line:#E0B77E;
    --teal:#145D66;  --teal-bg:#E6F1F2;  --teal-line:#8FBFC4;
    --green:#1C6B45; --green-bg:#E7F2EC; --green-line:#8CC0A4;
    --red:#97302F;   --red-bg:#FBECEA;   --red-line:#DFA8A3;
    --blue:#2A6DB0;  --blue-bg:#E9F1F9;
  }

  .block-container { padding-top: 2.0rem; max-width: 1480px; }

  /* ---------------- masthead ---------------- */
  .mast { display:flex; align-items:flex-start; gap:14px;
          border-bottom:2px solid var(--ink); padding-bottom:12px;
          margin-bottom:6px; }
  .mast .badge { flex:none; width:46px; height:46px; border-radius:3px;
          background:var(--amber); color:#fff; display:flex;
          align-items:center; justify-content:center;
          font-size:19px; font-weight:800; letter-spacing:-.04em; }
  .mast h1 { margin:0; font-size:27px; font-weight:800; letter-spacing:-.02em;
          line-height:1.15; color:var(--ink); }
  .mast .sub { font-size:12.5px; color:var(--ink3); margin-top:3px;
          line-height:1.45; }

  /* ---------------- status cards ---------------- */
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(138px,1fr));
           gap:8px; margin:14px 0 4px; }
  .card { background:#fff; border:1px solid var(--rule); border-radius:3px;
          padding:9px 12px 10px; position:relative; overflow:hidden; }
  .card:before { content:""; position:absolute; left:0; top:0; bottom:0;
          width:3px; background:var(--ink3); }
  .card .l { font-size:9px; letter-spacing:.1em; text-transform:uppercase;
          color:var(--ink3); font-weight:700; }
  .card .v { font-size:17px; font-weight:800; color:var(--ink);
          letter-spacing:-.01em; line-height:1.25; margin-top:1px; }
  .card .n { font-size:10.5px; color:var(--ink3); margin-top:1px; }
  .card.good:before { background:var(--green); }
  .card.good  .v { color:var(--green); }
  .card.warn:before { background:var(--amber); }
  .card.warn  .v { color:var(--amber); }
  .card.bad:before  { background:var(--red); }
  .card.bad   .v { color:var(--red); }

  /* ---------------- callouts ---------------- */
  .note { border-left:3px solid var(--amber); background:var(--amber-bg);
          padding:11px 15px; font-size:13.5px; margin:9px 0;
          border-radius:0 3px 3px 0; line-height:1.55; }
  .paper-note { border-left:3px solid var(--amber); background:var(--amber-bg);
          padding:11px 15px; font-size:13.5px; margin:9px 0;
          border-radius:0 3px 3px 0; line-height:1.55; }
  .alarm-note { border-left:3px solid var(--red); background:var(--red-bg);
          padding:11px 15px; font-size:13.5px; margin:9px 0;
          border-radius:0 3px 3px 0; line-height:1.55; }
  .good-note  { border-left:3px solid var(--green); background:var(--green-bg);
          padding:11px 15px; font-size:13.5px; margin:9px 0;
          border-radius:0 3px 3px 0; line-height:1.55; }

  /* ---------------- fidelity chips ---------------- */
  .fid { display:inline-block; padding:3px 10px; font-size:10px; font-weight:800;
         letter-spacing:.08em; border-radius:2px; }
  .fid-faithful { background:var(--green-bg); color:var(--green);
                  border:1px solid var(--green-line); }
  .fid-abstract { background:var(--amber-bg); color:var(--amber);
                  border:1px solid var(--amber-line); }

  /* ---------------- section headings ---------------- */
  .sec { font-size:11px; font-weight:800; letter-spacing:.1em;
         text-transform:uppercase; color:var(--ink3);
         border-bottom:1px solid var(--rule); padding-bottom:5px;
         margin:16px 0 9px; }

  /* ---------------- tabs ---------------- */
  .stTabs [data-baseweb="tab-list"] { gap:2px; border-bottom:1px solid var(--rule); }
  .stTabs [data-baseweb="tab"] { height:38px; padding:0 13px; font-size:13.5px;
         font-weight:600; color:var(--ink2); border-radius:3px 3px 0 0; }
  .stTabs [aria-selected="true"] { color:var(--amber) !important;
         background:var(--amber-bg); }

  /* ---------------- misc ---------------- */
  div[data-testid="stMetricValue"] { font-size:24px; font-weight:800; }
  div[data-testid="stMetricLabel"] { font-size:11px; letter-spacing:.04em; }
  section[data-testid="stSidebar"] { border-right:1px solid var(--rule); }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ state --
if "sys" not in st.session_state:
    st.session_state.sys = S.SystemState()
sim: S.SystemState = st.session_state.sys


# ---------------------------------------------------------------- sidebar --
with st.sidebar:
    st.markdown("### Crypto backend")

    faithful_ok = pairing_available()
    options = ["abstract"] + (["faithful"] if faithful_ok else [])
    labels = {
        "abstract": "Abstracted  ·  instant  ·  n <= 1000",
        "faithful": "Faithful  ·  real BN128 pairings  ·  n <= 30",
    }
    backend_name = st.radio(
        "backend", options, format_func=lambda k: labels[k],
        label_visibility="collapsed",
        index=options.index(sim.backend_name) if sim.backend_name in options else 0,
    )
    if not faithful_ok:
        st.caption("`pip install py_ecc` to enable the faithful backend.")

    if backend_name == "faithful":
        st.markdown('<span class="fid fid-faithful">FAITHFUL</span>',
                    unsafe_allow_html=True)
        st.caption("Real pairings. The TA side is genuinely slow — that is the finding, "
                   "not a bug.")
    else:
        st.markdown('<span class="fid fid-abstract">ABSTRACTED</span>',
                    unsafe_allow_html=True)
        st.caption("Toy bilinear group. Genuinely bilinear, so the algebra and the "
                   "failure modes are exact. Not secure.")

    st.divider()
    st.markdown("### Network")
    n_uav = st.slider("UAVs", config.LIMITS["n_uav_min"],
                      config.LIMITS["n_uav_max"], config.DEFAULTS["n_uav"])
    n_veh = st.slider("Vehicles", config.LIMITS["n_vehicle_min"],
                      config.LIMITS["n_vehicle_max"], config.DEFAULTS["n_vehicle"])

    if backend_name == "faithful" and n_uav > config.LIMITS["faithful_interactive_max"]:
        st.warning(f"n = {n_uav} on the faithful backend means roughly "
                   f"{n_uav * 0.2:.0f} s of real pairing work on the TA side.")

    st.divider()
    st.markdown("### TA link")
    st.caption("Our addition. The paper models neither latency nor availability, "
               "yet Step GA1 crosses this link for every verification.")
    rtt = st.slider("Round-trip latency (ms)", 0, 800,
                    int(config.DEFAULTS["ta_rtt_ms"]), step=10)
    avail = st.slider("Availability", 0.0, 1.0,
                      config.DEFAULTS["ta_availability"], step=0.05)
    if avail < 1.0:
        st.markdown('<div class="alarm-note">With the link down, Step GA3 cannot be '
                    'evaluated at all. Authentication does not slow down — it stops.'
                    '</div>', unsafe_allow_html=True)

    st.divider()
    st.markdown("### Adversary")
    poison = st.slider("Forged credentials (fraction)", 0.0, 0.5, 0.0, step=0.05)
    identify = st.checkbox("Allow culprit identification", value=False,
                           help="OFF by default because the published scheme cannot do "
                                "this. Step GA4 has no else-branch. Turning it on shows "
                                "what a fix would cost.")

    st.divider()
    st.markdown("### Actions")
    c1, c2 = st.columns(2)
    do_init = c1.button("Initialize", width="stretch", type="primary")
    do_reset = c2.button("Reset", width="stretch")

    do_register = st.button("Register UAVs", width="stretch",
                            disabled=not sim.initialized)
    do_auth = st.button("Start Authentication", width="stretch",
                        disabled=not sim.uavs)
    do_key = st.button("Distribute Group Key", width="stretch",
                       disabled=not (sim.last_auth and sim.last_auth.ok))

    st.markdown("###### Dynamic membership")
    c3, c4 = st.columns(2)
    do_add = c3.button("Add UAV", width="stretch", disabled=not sim.initialized)
    remove_target = None
    keyed_now = [u for u in sim.uavs if u.status in (Status.KEYED, Status.AUTHENTICATED)]
    if keyed_now:
        remove_target = st.selectbox("Revoke", [u.name for u in keyed_now],
                                     label_visibility="collapsed")
    do_remove = c4.button("Revoke", width="stretch", disabled=not keyed_now)
    do_update = st.button("Update Group Key", width="stretch",
                          disabled=not any(u.crt_modulus for u in sim.uavs))

    st.markdown("###### Session")
    do_session = st.button("New Session (new pseudonyms)", width="stretch",
                           disabled=not sim.initialized)

    st.divider()
    present = st.toggle("Presentation Mode",
                        help="Strips the dashboard to one idea per screen.")


# ---------------------------------------------------------------- actions --
if do_reset:
    st.session_state.sys = S.act_reset(sim)
    st.rerun()

if do_init:
    sim = S.act_initialize(sim, backend_name=backend_name,
                           rtt_ms=float(rtt), availability=float(avail))
    sim = S.act_register(sim, n_uav)
    sim = S.act_attach_vehicles(sim, n_veh)
    st.session_state.sys = sim
    st.rerun()

# keep the link knobs live without needing a re-initialize
if sim.link is not None:
    sim.link.rtt_ms = float(rtt)
    sim.link.availability = float(avail)

if do_register:
    sim = S.act_register(sim, n_uav)
    sim = S.act_attach_vehicles(sim, n_veh)
if do_session:
    sim = S.act_new_session(sim)
if do_auth:
    sim = S.act_authenticate(sim, poison_fraction=poison, identify_culprits=identify)
if do_key:
    sim = S.act_distribute_key(sim)
if do_add:
    sim = S.act_add_uav(sim, 1)
if do_remove and remove_target:
    idx = int(remove_target.replace("UAV", ""))
    sim = S.act_remove_uav(sim, [idx])
if do_update:
    sim = S.act_update_key(sim)

st.session_state.sys = sim

# The sidebar is built BEFORE these actions execute, so its `disabled` flags
# were computed from the previous state. Without this rerun, "Distribute Group
# Key" would still look disabled immediately after a successful authentication
# and the user would have to click something unrelated to wake it up.
if any([do_register, do_session, do_auth, do_key, do_add, do_remove, do_update]):
    st.rerun()


# ----------------------------------------------------------------- header --
st.markdown(f"""
<div class="mast">
  <div class="badge">TU</div>
  <div>
    <h1>Infrastructure-Less IoV &mdash; Authenticated Key Management</h1>
    <div class="sub">
      Simulating {config.PAPER['authors']},
      <i>{config.PAPER['title']}</i>,
      {config.PAPER['venue']}, {config.PAPER['year']}.<br>
      {config.DISCLAIMER_SHORT}
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

cards = "".join(
    f'<div class="card {c["tone"]}">'
    f'<div class="l">{c["label"]}</div>'
    f'<div class="v">{c["value"]}</div>'
    f'<div class="n">{c["note"]}</div></div>'
    for c in sim.status_banner()
)
st.markdown(f'<div class="cards">{cards}</div>', unsafe_allow_html=True)


# ------------------------------------------------------ presentation mode --
if present:
    if "pstep" not in st.session_state:
        st.session_state.pstep = 0

    total_steps = presentation.total()
    idx = st.session_state.pstep
    step = presentation.step(idx)

    nav = st.columns([1, 1, 6, 2])
    if nav[0].button("Back", width="stretch", disabled=idx == 0):
        st.session_state.pstep = max(0, idx - 1)
        st.rerun()
    if nav[1].button("Next", width="stretch", disabled=idx >= total_steps - 1):
        st.session_state.pstep = min(total_steps - 1, idx + 1)
        st.rerun()
    nav[3].markdown(
        f'<div style="text-align:right;color:#8A949F;font-size:13px;'
        f'padding-top:8px">step {step.n} of {total_steps}</div>',
        unsafe_allow_html=True)

    st.progress((idx + 1) / total_steps)

    ready = step.check(sim) if step.check else True
    label, value = step.metric(sim) if step.metric else ("", "")

    st.markdown(
        f"""
<div style="padding:26px 0 8px">
  <div style="font-size:12px;letter-spacing:.14em;text-transform:uppercase;
              color:#A8580A;font-weight:700">{step.eyebrow}</div>
  <div style="font-size:44px;font-weight:700;line-height:1.1;margin-top:8px;
              color:#131820">{step.headline}</div>
  <div style="font-size:19px;color:#55606D;max-width:70ch;margin-top:14px;
              line-height:1.55">{step.body}</div>
</div>
""", unsafe_allow_html=True)

    if value:
        m = st.columns([1, 2])
        if ready:
            m[0].metric(label, value)
        else:
            m[0].warning(f"Not ready — {step.requires}")

    st.markdown(
        f'<div class="paper-note"><b>Say:</b> {step.say}<br>'
        f'<span style="color:#8A949F;font-size:12px">'
        f'Switch off Presentation Mode and open the <b>{step.tab_hint}</b> tab '
        f'to show this live.</span></div>',
        unsafe_allow_html=True)

    with st.expander("Which steps are ready to demo?"):
        st.dataframe(pd.DataFrame(presentation.readiness(sim)),
                     width="stretch", hide_index=True)

    st.stop()


# ------------------------------------------------------------------- tabs --
(tab_net, tab_proto, tab_keys, tab_attack, tab_anon, tab_data, tab_sec,
 tab_perf, tab_vs, tab_results, tab_about) = st.tabs(
    ["Network", "Protocol run", "Group key", "Attacks", "Anonymity",
     "Secure exchange", "Security board", "Performance", "Paper vs us",
     "Results", "About the research"]
)

# ---------------------------------------------------------------- Network --
with tab_net:
    left, right = st.columns([3, 2], gap="large")
    with left:
        view = st.radio(
            "view", ["Live state", "Animated walkthrough"],
            horizontal=True, label_visibility="collapsed",
            help="Live state shows the system as it is right now. The "
                 "walkthrough plays one full authentication run so you can "
                 "watch the messages move.")

        if view == "Animated walkthrough":
            anim = protocol_animation.build(sim)
            if anim is None:
                st.info("Press **Initialize** in the sidebar first.")
            else:
                st.plotly_chart(anim, width="stretch",
                                config={"displayModeBar": False})
                st.caption(protocol_animation.CAPTION)
        else:
            st.plotly_chart(network_graph.render(sim), width="stretch",
                            config={"displayModeBar": False})
            st.markdown(network_graph.legend_html(), unsafe_allow_html=True)

    with right:
        st.markdown("#### Registered UAVs")
        if sim.uavs:
            st.dataframe(pd.DataFrame(sim.uav_table()), width="stretch",
                         hide_index=True, height=300)
            st.caption("Permanent identities and secrets are never rendered. "
                       "The fingerprint is a one-way label so you can follow an "
                       "entity across sessions.")
        else:
            st.info("No UAVs yet. Press **Initialize** in the sidebar.")

        st.markdown("#### Event log")
        if sim.events:
            rows = [e.row() for e in reversed(sim.events[-40:])]
            st.dataframe(pd.DataFrame(rows), width="stretch",
                         hide_index=True, height=260)
        else:
            st.caption("Nothing has happened yet.")

# ----------------------------------------------------------- Protocol run --
with tab_proto:
    if sim.last_auth is None:
        st.info("Run **Start Authentication** to see Steps US1–US3 and GA1–GA4.")
    else:
        res = sim.last_auth
        if res.ok:
            st.success(f"Group authentication succeeded — {len(res.verified)} "
                       f"UAV(s) verified by a single equation.")
        else:
            st.error(f"Group authentication failed. {res.reason}")

        c = st.columns(4)
        c[0].metric("UAV signing (all n)", f"{res.drone_ops.wall_ms:.1f} ms")
        c[1].metric("TUAV side", f"{res.tuav_ops.wall_ms:.1f} ms",
                    help="Target-group multiplications and two exponentiations. "
                         "No pairings — by construction.")
        c[2].metric("TA side", f"{res.ta_ops.wall_ms:.1f} ms",
                    help="Every pairing in the protocol happens here. The paper "
                         "does not report this number.")
        c[3].metric("TA link", f"{res.link.latency_ms:.0f} ms" if res.link else "—")

        if res.ta_ops.wall_ms > 0 and res.tuav_ops.wall_ms > 0:
            ratio = res.ta_ops.wall_ms / max(res.tuav_ops.wall_ms, 1e-9)
            st.markdown(
                f'<div class="paper-note"><b>The pairings did not disappear — they '
                f'moved.</b> On this run the TA did <b>{ratio:,.0f}×</b> the work the '
                f'TUAV did. The paper reports only the TUAV side, which is what makes '
                f'its group-authentication figure small.</div>',
                unsafe_allow_html=True)

        if not res.ok and not res.culprits_identified and res.rejected:
            st.markdown(
                f'<div class="alarm-note"><b>All {len(res.rejected)} members were '
                f'rejected and the culprit is unknown.</b> Step GA4 of the paper reads '
                f'only: “If matches, the validity of the vehicles can be proved.” '
                f'There is no else-branch anywhere in the paper.</div>',
                unsafe_allow_html=True)

        st.markdown("#### Operation counts")
        st.dataframe(pd.DataFrame([
            {"Actor": "UAVs (signing)", **res.drone_ops.as_dict()},
            {"Actor": "TUAV (GA3)", **res.tuav_ops.as_dict()},
            {"Actor": "TA (GA2)", **res.ta_ops.as_dict()},
        ]), width="stretch", hide_index=True)

        if sim.packets:
            st.markdown("#### One request packet (Step US3)")
            p = sim.packets[0]

            def _short(value: int, width: int = 26) -> str:
                """Truncate a big integer's hex form for display only."""
                h = f"{value:x}".upper()
                return h[:width] + ("..." if len(h) > width else "")

            st.code("\n".join([
                "Request   : AUTH",
                f"ts2       : {p.ts2:.3f}",
                f"ID_i      : TEMP_{_short(p.id_temp)}",
                f"xi_i      : {_short(p.xi)}",
                f"upsilon_i : {_short(p.upsilon)}",
                f"Gamma_i   : {sim.backend.g1_repr(p.gamma)}",
            ]), language="text")
            st.caption("This is everything that goes on the air in Step US3. The "
                       "permanent identity and the secret s_i appear nowhere in it.")

# --------------------------------------------------------------- Group key --
with tab_keys:
    if sim.last_key is None:
        st.info("Run **Distribute Group Key** after a successful authentication.")
    else:
        kres = sim.last_key
        if kres.ok:
            st.success(f"Epoch {kres.epoch}: {len(kres.recovered)} member(s) recovered "
                       f"the same group key from one broadcast.")
        else:
            st.warning(kres.reason)

        c = st.columns(4)
        c[0].metric("Epoch", kres.epoch)
        c[1].metric("Members", len(kres.members))
        c[2].metric("Recovered key", len(kres.recovered))
        c[3].metric("Broadcast size",
                    f"{kres.broadcast.size_bytes:,} B" if kres.broadcast else "—")

        st.markdown(
            '<div class="paper-note"><b>Declared correction.</b> The paper defines '
            'sigma_i as <code>h1(s_i · xi_i)·P</code>, a point on the curve, then uses it '
            'as a modulus in Steps GD1 and GD6 — which is undefined for a curve point. '
            'We read sigma_i as an integer there and derive a prime from the same hash, '
            'which is the only reading under which the construction typechecks. Under '
            'that reading the paper\'s construction is correct and we implement it '
            'verbatim.</div>', unsafe_allow_html=True)

        rows = []
        for u in sim.uavs:
            if u.crt_modulus is None:
                continue
            holds = (u.group_key is not None and sim.tuav
                     and u.group_key == sim.tuav.group_key)
            rows.append({
                "UAV": u.name,
                "Status": u.status,
                "Modulus bits": u.crt_modulus.bit_length(),
                "Key epoch": u.key_epoch if u.key_epoch is not None else "—",
                "Holds current key": "yes" if holds else "NO",
            })
        if rows:
            st.markdown("#### Key holders")
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
            st.caption("Revoke a UAV, then press **Update Group Key**: the revoked "
                       "member keeps its old value, which no longer opens anything — "
                       "and the survivors receive no individual message at all.")

# --------------------------------------------------------------- Attacks ---
with tab_attack:
    st.markdown(
        '<div class="paper-note">These demonstrate <b>behaviour</b>, not proof. '
        'The paper\'s Theorems 1&ndash;5 are mathematical arguments; watching an '
        'implementation resist an attack is weaker evidence, and is labelled as '
        'such throughout.</div>', unsafe_allow_html=True)

    a1, a2 = st.columns(2, gap="large")

    # ---- replay -------------------------------------------------------
    with a1:
        st.markdown("#### Replay attack")
        st.caption("Theorem 3. Two defences stand in the way, and you can switch "
                   "the first one off to see the second.")

        cap_col, _ = st.columns([1, 1])
        if cap_col.button("Capture packet", width="stretch",
                          disabled=not sim.packets):
            sim = S.act_capture_packet(sim)
            st.session_state.sys = sim

        if sim.captured_packet is not None:
            p = sim.captured_packet
            st.code(f"captured from UAV{p.uav_index}\n"
                    f"ts2 = {p.ts2:.3f}\n"
                    f"every field was transmitted in the clear", language="text")

        delay = st.slider("Replay after (seconds)", 0, 600, 120, step=10)
        bypass = st.checkbox(
            "Disable the timestamp check",
            help="Exposes the cryptographic defence underneath: R_tu and ID_tu "
                 "are regenerated each session, so an old credential cannot "
                 "balance the equation regardless of its timestamp.")

        if st.button("Replay packet", width="stretch",
                     disabled=sim.captured_packet is None):
            sim = S.act_replay(sim, delay_s=float(delay), bypass_timestamp=bypass)
            st.session_state.sys = sim

        rep = sim.evidence.get("replay")
        if rep:
            (st.success if rep.blocked else st.error)(
                f"{rep.verdict} — {rep.stage}")
            for line in rep.narrative:
                st.markdown(f"- {line}")
            if rep.detail:
                st.dataframe(pd.DataFrame(
                    [{"Field": k, "Value": str(v)}
                     for k, v in rep.detail.items()]),
                    width="stretch", hide_index=True)

    # ---- impersonation + revoked --------------------------------------
    with a2:
        st.markdown("#### Impersonation")
        st.caption("Theorem 1. A fake UAV builds a perfectly-shaped request on a "
                   "guessed secret.")
        if st.button("Attempt impersonation", width="stretch",
                     disabled=not sim.active):
            sim = S.act_impersonate(sim)
            st.session_state.sys = sim

        imp = sim.evidence.get("impersonation")
        if imp:
            (st.success if imp.blocked else st.error)(
                f"{imp.verdict} — {imp.stage}")
            for line in imp.narrative:
                st.markdown(f"- {line}")

        st.divider()
        st.markdown("#### Revoked UAV data access")
        st.caption("Steps DU1–DU2. A revoked member keeps its old key and tries "
                   "to read current traffic.")
        if st.button("Attempt access with stale key", width="stretch",
                     disabled=not sim.revoked):
            sim = S.act_revoked_access(sim)
            st.session_state.sys = sim
        if not sim.revoked:
            st.caption("Revoke a UAV and update the group key to enable this.")

        rev = sim.evidence.get("revoked_access")
        if rev:
            (st.success if rev.blocked else st.error)(
                f"{rev.verdict} — {rev.stage}")
            for line in rev.narrative:
                st.markdown(f"- {line}")

    st.divider()
    st.markdown("#### Batch poisoning — the one the paper does not defend against")
    st.caption("Set the adversary slider in the sidebar above zero, run "
               "authentication, then press this.")
    if st.button("Report on the last batch", width="stretch",
                 disabled=sim.last_auth is None):
        sim = S.act_batch_poison_report(sim)
        st.session_state.sys = sim

    bp = sim.evidence.get("batch_poison")
    if bp:
        (st.success if bp.blocked else st.error)(f"{bp.verdict} — {bp.stage}")
        for line in bp.narrative:
            st.markdown(f"- {line}")
        if bp.detail:
            st.dataframe(pd.DataFrame([bp.detail]), width="stretch",
                         hide_index=True)

# -------------------------------------------------------------- Anonymity --
with tab_anon:
    sim = S.act_anonymity_view(sim)
    st.session_state.sys = sim
    view = sim.evidence.get("anonymity")

    st.markdown("#### What a passive eavesdropper sees")
    st.caption("Every temporary identity observed on the air, in time order. "
               "Run **New Session** a few times to build up history.")

    if view and view.observed:
        public = [{k: v for k, v in r.items() if not k.startswith("_")}
                  for r in view.observed]
        st.dataframe(pd.DataFrame(public), width="stretch", hide_index=True,
                     height=260)
        if view.linkable:
            st.error(view.note)
        else:
            st.success(view.note)
    else:
        st.info("No sessions observed yet. Run authentication, then **New "
                "Session**, then authenticate again.")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("##### One UAV across sessions")
        if sim.uavs:
            pick = st.selectbox("UAV", [u.name for u in sim.uavs],
                                key="anon_pick")
            target = next(u for u in sim.uavs if u.name == pick)
            if target.history:
                rows = [{"Session": i + 1,
                         "Temporary ID": f"TEMP_{t:x}".upper()[:14]}
                        for i, (_, t) in enumerate(target.history)]
                st.dataframe(pd.DataFrame(rows), width="stretch",
                             hide_index=True)
                st.caption("Same drone, same permanent identity, different "
                           "pseudonym every session. That is unlinkability (F9).")
            else:
                st.caption("This UAV has not signed anything yet.")

    with c2:
        st.markdown("##### Conditional privacy (Theorem 4)")
        st.caption("Anonymous to everyone — except the TA, on request. That "
                   "escape hatch is what separates *anonymous* from "
                   "*untraceable*.")
        if sim.uavs:
            tgt = st.selectbox("Reveal identity of", [u.name for u in sim.uavs],
                               key="reveal_pick")
            if st.button("Reveal identity (TA only)", width="stretch"):
                sim = S.act_reveal_identity(sim, tgt)
                st.session_state.sys = sim
        if sim.revealed_identity:
            st.dataframe(pd.DataFrame(
                [{"Field": k, "Value": str(v)}
                 for k, v in sim.revealed_identity.items()]),
                width="stretch", hide_index=True)
            st.caption("Only a fingerprint is shown — the simulator never "
                       "renders the raw permanent identity, even here.")

# ---------------------------------------------------------- Secure exchange --
with tab_data:
    st.markdown("#### Secure data exchange under the group key")
    st.markdown(
        '<div class="paper-note"><b>Scope note.</b> The paper establishes '
        'kappa_tu and stops there — it specifies no bulk cipher. AES-GCM is '
        '<i>our</i> choice, so that "ACCESS DENIED" is a genuine authentication-tag '
        'failure rather than a string comparison we decided to fail.</div>',
        unsafe_allow_html=True)

    msg = st.text_input("Message to broadcast",
                        "ACCIDENT DETECTED - JUNCTION 14 - TWO VEHICLES")
    if st.button("Encrypt and broadcast", width="stretch",
                 disabled=not (sim.tuav and sim.tuav.group_key)):
        sim = S.act_exchange(sim, msg)
        st.session_state.sys = sim
    if not (sim.tuav and sim.tuav.group_key):
        st.info("Distribute the group key first.")

    ex = sim.last_exchange
    if ex:
        c = st.columns(3)
        c[0].metric("Opened", len(ex.opened_by))
        c[1].metric("Denied", len(ex.denied))
        c[2].metric("Epoch", ex.envelope.epoch)

        st.code(f"plaintext  : {ex.message}\n"
                f"ciphertext : {ex.envelope.hex_preview(48)}\n"
                f"nonce      : {ex.envelope.nonce.hex().upper()}\n"
                f"size       : {ex.envelope.size_bytes} bytes",
                language="text")

        rows = []
        for u in sim.uavs:
            ok = u.name in ex.opened_by
            rows.append({"UAV": u.name, "Status": u.status,
                         "Result": "decrypted" if ok else "ACCESS DENIED"})
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
        st.caption(datalink_note := "A wrong key fails the GCM tag, so the "
                   "ciphertext is rejected outright rather than decrypted into "
                   "garbage. That is why an AEAD is used here.")

# ---------------------------------------------------------- Security board --
with tab_sec:
    rows = security.evaluate(sim)
    counts = security.summary(rows)

    c = st.columns(3)
    c[0].metric("Demonstrated", counts.get(security.DEMONSTRATED, 0),
                help=security.LEVEL_HELP[security.DEMONSTRATED])
    c[1].metric("Structural", counts.get(security.STRUCTURAL, 0),
                help=security.LEVEL_HELP[security.STRUCTURAL])
    c[2].metric("Not shown", counts.get(security.NOT_SHOWN, 0),
                help=security.LEVEL_HELP[security.NOT_SHOWN])

    st.markdown(f'<div class="alarm-note">{security.HONESTY_NOTE}</div>',
                unsafe_allow_html=True)

    st.dataframe(pd.DataFrame([{
        "": r.tag, "Property": r.name, "Evidence level": r.level,
        "What the simulator shows": r.evidence, "Where": r.where,
    } for r in rows]), width="stretch", hide_index=True, height=440)

# ------------------------------------------------------------ Performance --
with tab_perf:
    st.markdown(
        f'<div class="alarm-note"><b>{config.DISCLAIMER_TIMING}</b></div>',
        unsafe_allow_html=True)

    st.markdown("#### Run the sweeps")

    # E1 measures cryptographic cost, so it honours the selected backend.
    # E7 and E8 measure PROTOCOL BEHAVIOUR over dozens of repeated runs. On the
    # faithful backend that is ~5.5 minutes of real pairings and the app looks
    # frozen - so they always run on the abstraction, which reproduces the
    # behaviour exactly because it is genuinely bilinear.
    max_n = 120 if sim.backend_name == "abstract" else 20
    n_list = [n for n in (5, 10, 20, 40, 60, 90, 120) if n <= max_n]

    c1, c2, c3 = st.columns(3)
    if c1.button(f"E1 · scaling with n  ({sim.backend_name})", width="stretch"):
        with st.spinner(f"sweeping n = {n_list} on the {sim.backend_name} "
                        f"backend …"):
            st.session_state["e1"] = experiments.e1_scaling(
                sim.backend_name, n_values=tuple(n_list), rtt_ms=float(rtt))
    if c2.button("E7 · availability cliff", width="stretch"):
        with st.spinner("70 authentication attempts across 7 link availabilities …"):
            st.session_state["e7"] = experiments.e7_availability(
                "abstract", n=12, trials=10, rtt_ms=float(rtt))
    if c3.button("E8 · batch poisoning", width="stretch"):
        with st.spinner("60 authentication attempts across 6 forged fractions …"):
            st.session_state["e8"] = experiments.e8_poisoning(
                "abstract", n=20, trials=5)

    st.caption(
        "**E1** uses the backend you selected, because it measures cryptographic "
        "cost. **E7 and E8** always use the abstraction: they repeat "
        "authentication dozens of times to get a statistic, and what they "
        "measure is protocol *behaviour* — which the abstraction reproduces "
        "exactly, being genuinely bilinear. On the faithful backend the same "
        "sweeps would take about five minutes of real pairings and tell you "
        "nothing new.")

    if sim.backend_name == "faithful":
        st.warning(
            f"Faithful backend selected: **E1 is capped at n = {max_n}** and will "
            f"take roughly {max_n * 0.25:.0f} seconds, because every UAV costs a "
            f"real ~190 ms pairing on the TA side. Switch to Abstracted for the "
            f"full sweep to n = 120.")

    e1 = st.session_state.get("e1")
    if e1 is not None and not e1.empty:
        st.markdown("#### Where the work actually happens")
        st.plotly_chart(performance.chart_where_the_work_happens(e1),
                        width="stretch", config={"displayModeBar": False})
        st.caption("Dashed grey = the paper's reported curve. Solid = measured "
                   "here. The red series is the TA-side cost, which the paper "
                   "does not report at all.")

        tot = e1[e1["phase"] == "GA (TUAV side)"]
        ta_tot = e1[e1["phase"] == "GA (TA side)"]
        if not tot.empty and not ta_tot.empty:
            biggest = tot["n"].max()
            t_ms = float(tot[tot["n"] == biggest]["ms"].iloc[0])
            a_ms = float(ta_tot[ta_tot["n"] == biggest]["ms"].iloc[0])
            m = st.columns(3)
            m[0].metric(f"TUAV side at n={biggest}", f"{t_ms:.1f} ms")
            m[1].metric(f"TA side at n={biggest}", f"{a_ms/1000:.1f} s")
            m[2].metric("Ratio", f"{a_ms/max(t_ms,1e-9):,.0f}x")

        with st.expander("Measured data"):
            st.dataframe(e1, width="stretch", hide_index=True)

    st.divider()
    st.markdown("#### The paper's own Table III")
    st.plotly_chart(performance.chart_paper_table_iii(),
                    width="stretch", config={"displayModeBar": False})
    st.caption(paper_cost.WHY_NOT_COMPARABLE)

    hk = paper_cost.headline_check()
    st.markdown("###### Transcription check")
    st.caption("Our Table III constants must reproduce the figures the paper "
               "states in prose. If this ever disagrees, every chart above is wrong.")
    st.dataframe(pd.DataFrame([
        {"Figure": k, "Our model": f"{got:.4f} ms",
         "Paper states": f"{want:.4f} ms",
         "": "MATCH" if ok else "MISMATCH"}
        for k, (got, want, ok) in hk.items()
    ]), width="stretch", hide_index=True)

    e7 = st.session_state.get("e7")
    e8 = st.session_state.get("e8")
    if e7 is not None or e8 is not None:
        st.divider()
        g1, g2 = st.columns(2, gap="large")
        if e7 is not None and not e7.empty:
            with g1:
                st.markdown("#### The availability cliff")
                st.plotly_chart(performance.chart_availability_cliff(e7),
                                width="stretch",
                                config={"displayModeBar": False})
        if e8 is not None and not e8.empty:
            with g2:
                st.markdown("#### Goodput under batch poisoning")
                st.plotly_chart(performance.chart_goodput(e8),
                                width="stretch",
                                config={"displayModeBar": False})

    st.divider()
    st.markdown("#### Communication overhead")
    st.plotly_chart(performance.chart_overhead(120), width="stretch",
                    config={"displayModeBar": False})
    st.markdown(f'<div class="paper-note">{paper_overhead.WHY_OURS_DIFFERS}</div>',
                unsafe_allow_html=True)

    oc1, oc2 = st.columns(2, gap="large")
    with oc1:
        b = paper_overhead.request_as_paper_counts_it()
        st.markdown(f"###### {b.label}")
        st.dataframe(pd.DataFrame(b.rows()), width="stretch", hide_index=True)
    with oc2:
        b = paper_overhead.request_as_pairing_requires()
        st.markdown(f"###### {b.label}")
        st.dataframe(pd.DataFrame(b.rows()), width="stretch", hide_index=True)

    st.markdown("###### Costs Table V does not count")
    bcast = (sim.last_key.broadcast.size_bytes
             if (sim.last_key and sim.last_key.broadcast) else 0)
    st.dataframe(pd.DataFrame(paper_overhead.uncounted_costs(
        len(sim.uavs) or 1, bcast)), width="stretch", hide_index=True)

# ------------------------------------------------------------ Paper vs us --
with tab_vs:
    st.markdown("#### What this simulator is, and what it is not")
    st.dataframe(pd.DataFrame([
        {"Aspect": "Protocol flow",
         "The paper": "Steps IS/US/GA/GD/DU",
         "This simulator": "Same steps, same labels",
         "Fidelity": "FAITHFUL"},
        {"Aspect": "Bilinear pairing",
         "The paper": "supersingular curve, 80-bit",
         "This simulator": "real BN128 via py_ecc, or a toy bilinear group",
         "Fidelity": "FAITHFUL / ABSTRACTED"},
        {"Aspect": "Credential Gamma_i",
         "The paper": "as printed in Step US2",
         "This simulator": "computed exactly as printed",
         "Fidelity": "FAITHFUL"},
        {"Aspect": "Aggregate equation",
         "The paper": "Step GA3",
         "This simulator": "same equation; correctness asserted by a unit test",
         "Fidelity": "FAITHFUL"},
        {"Aspect": "CRT group key",
         "The paper": "sigma_i used as both point and modulus",
         "This simulator": "sigma_i read as an integer; correction declared",
         "Fidelity": "INTERPRETED"},
        {"Aspect": "Security theorems",
         "The paper": "formal proofs, Theorems 1-5",
         "This simulator": "behavioural demonstrations only",
         "Fidelity": "NOT REPRODUCED"},
        {"Aspect": "Benchmark environment",
         "The paper": "MIRACL (C), 80-bit",
         "This simulator": "pure Python, BN128, this laptop",
         "Fidelity": "NOT COMPARABLE"},
        {"Aspect": "TA-side cost",
         "The paper": "not reported",
         "This simulator": "measured",
         "Fidelity": "NEW"},
        {"Aspect": "TA link latency / availability",
         "The paper": "not modelled",
         "This simulator": "modelled and swept",
         "Fidelity": "NEW"},
        {"Aspect": "Vehicle tier",
         "The paper": "explicitly out of scope",
         "This simulator": "drawn, not authenticated",
         "Fidelity": "OUT OF SCOPE"},
    ]), width="stretch", hide_index=True, height=420)

    st.markdown("#### What can honestly be compared")
    st.dataframe(pd.DataFrame([
        {"Paper reports": "GA cost linear in n with a small slope",
         "Comparable?": "YES - structural",
         "Why": "We measure the same shape and the same relative slope."},
        {"Paper reports": "Signing cheaper than pairing-based baselines",
         "Comparable?": "YES - operation counts",
         "Why": "We count the real G1 operations performed."},
        {"Paper reports": "Communication overhead is lower",
         "Comparable?": "PARTLY",
         "Why": "Element sizes are stated, but Gamma_i is counted in G (40 B) "
                "while Step GA2 needs G1 (128 B)."},
        {"Paper reports": "1.82 / 2.16 / 151 ms",
         "Comparable?": "NO",
         "Why": "Different language, curve and machine. Roughly 100x apart."},
        {"Paper reports": "Theorems 1-5",
         "Comparable?": "NO",
         "Why": "A demonstration is not a proof."},
    ]), width="stretch", hide_index=True)

# ---------------------------------------------------------------- Results --
with tab_results:
    st.markdown('<div class="sec">System status</div>', unsafe_allow_html=True)
    cols = st.columns(4)
    for i, c in enumerate(sim.status_banner()):
        cols[i % 4].metric(c["label"], c["value"], help=c["note"] or None)

    st.divider()
    r1, r2 = st.columns(2, gap="large")

    with r1:
        st.markdown("##### Membership")
        st.dataframe(pd.DataFrame([
            {"Category": "Registered", "Count": len(sim.uavs)},
            {"Category": "Authenticated", "Count": len(sim.authenticated)},
            {"Category": "Holding group key", "Count": len(sim.keyed)},
            {"Category": "Revoked", "Count": len(sim.revoked)},
        ]), width="stretch", hide_index=True)

        st.markdown("##### TA link")
        if sim.link:
            # Force strings: the stats dict mixes ints and formatted
            # percentages, and Arrow cannot serialise a mixed-type column.
            st.dataframe(pd.DataFrame(
                [{"Metric": k, "Value": str(v)}
                 for k, v in sim.link.stats().items()]),
                width="stretch", hide_index=True)

    with r2:
        st.markdown("##### Adversaries run")
        rows = []
        for key, label in (("replay", "Replay"),
                           ("impersonation", "Impersonation"),
                           ("revoked_access", "Revoked-key access"),
                           ("batch_poison", "Batch poisoning")):
            ev = sim.evidence.get(key)
            rows.append({
                "Attack": label,
                "Outcome": ev.verdict if ev else "not run",
                "Stopped at": ev.stage if ev else "-",
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        st.markdown("##### Security properties")
        counts = security.summary(security.evaluate(sim))
        st.dataframe(pd.DataFrame([
            {"Evidence level": k, "Properties": v} for k, v in counts.items()
        ]), width="stretch", hide_index=True)

    st.divider()
    st.markdown("##### Full event log")
    if sim.events:
        st.dataframe(pd.DataFrame([e.row() for e in sim.events]),
                     width="stretch", hide_index=True, height=300)

# ---------------------------------------------------------------- About ----
with tab_about:
    st.markdown(f"""
#### The problem

Conventional Internet-of-Vehicles security routes every trust decision through
roadside units — boxes on poles. A disaster destroys them first. At exactly the
moment coordinated vehicular communication matters most, the security layer has
nobody to verify anyone.

#### The paper's solution

A **tethered UAV**, powered by cable from a ground vehicle, hovers indefinitely
and takes over the roadside unit's role. Around it a swarm of ordinary drones
extends coverage. Three cryptographic choices make it cheap: certificateless
keys (no certificates, no escrow), batch verification (one equation for *n*
drones), and CRT group-key distribution (one broadcast, revocation without
disturbing survivors).

#### What this simulator does

Registration, pseudonym generation, group authentication, group-key
distribution, dynamic joining and revocation — each mapped to the paper's own
step labels so you can follow along in the PDF.

#### What it does not do

{config.DISCLAIMER_TIMING}

It does not prove the paper's security theorems. Proofs are mathematics, not
code; this demonstrates the corresponding *behaviour*, which is a different and
weaker claim.

#### Two things it measures that the paper does not

1. **The TA-side cost.** Every pairing happens on the trusted authority. The
   paper reports only the TUAV's work.
2. **The TA link.** Step GA1 crosses it for every verification. Set availability
   to zero and authentication does not degrade — it stops.

---

**Base paper:** {config.PAPER['authors']}.
*{config.PAPER['title']}.* {config.PAPER['venue']}, {config.PAPER['year']}.
DOI {config.PAPER['doi']}
""")
