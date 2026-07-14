"""Generic DAG workflow experiment on the cluster -- 5 real workloads.

Workflows (workflows_real/*.json): video_analytics, video_processing
(parallel fan-out), log_processing, staircase_chain (42 steps),
random_chain (40 steps). All stages execute real work (ffmpeg, OpenCV,
log parsing, compression); durations and data sizes are measured here.

  python run_dag_workflow.py --workflow video_processing --calibrate
  python run_dag_workflow.py --workflow video_processing --policy rds_dcd
"""
import argparse
import csv
import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scheduler"))

from k8s_pool import PoolManager               # noqa: E402
from cost_model import CostModel               # noqa: E402
from dcd_policy import make_policy, POLICIES   # noqa: E402

EXT = {"analyze": ".json", "gen_log": ".log", "basic_stats": ".jsonl",
       "filter_success": ".jsonl", "success_stats": ".json",
       "transform": ".bin"}


def load_spec(name):
    return json.load(open(os.path.join(HERE, "workflows_real",
                                       name + ".json")))


def node_params(node, variant):
    p = dict(node.get("params", {}))
    p.update(variant.get("overrides", {}).get(node["id"], {}))
    return p


def out_name(i, node):
    return f"wf{i}-{node['id']}" + EXT.get(node["stage"], ".mp4")


def topo_order(nodes):
    by_id = {n["id"]: n for n in nodes}
    indeg = {n["id"]: len(n["parents"]) for n in nodes}
    order = [nid for nid, d in indeg.items() if d == 0]
    i = 0
    children = {n["id"]: [] for n in nodes}
    for n in nodes:
        for pa in n["parents"]:
            children[pa].append(n["id"])
    while i < len(order):
        for c in children[order[i]]:
            indeg[c] -= 1
            if indeg[c] == 0:
                order.append(c)
        i += 1
    return [by_id[nid] for nid in order], children


def remaining_cp(nodes, children, durs):
    """rem[n] = dur[n] + max over children (longest path to sink)."""
    rem = {}
    for n in reversed(nodes):
        nid = n["id"]
        rem[nid] = durs.get(nid, 1.0) + max(
            (rem[c] for c in children[nid]), default=0.0)
    return rem


def calib_path(wf):
    return os.path.join(HERE, "workflows_real", f"calib_{wf}.json")


def calibrate(args, spec):
    pm = PoolManager()
    pm.clean_shared_data()
    pod = pm.create_pod("ondemand")
    print(f"calibration pod ready (cold start {pod.cold_start_s:.2f}s)")
    order, _ = topo_order(spec["nodes"])
    calib = {}
    for var in spec["variants"]:
        durs = {}
        for node in order:
            payload = {"task_id": f"cal-{node['id']}",
                       "stage": node["stage"],
                       "params": node_params(node, var),
                       "inputs": [out_name(9999, {"id": p, "stage":
                                  next(n["stage"] for n in spec["nodes"]
                                       if n["id"] == p)})
                                  for p in node["parents"]],
                       "output": out_name(9999, node)}
            r = pm.run_task(pod, payload, timeout=1800)
            if "error" in r:
                raise RuntimeError(f"{node['id']}: {r['error']}")
            durs[node["id"]] = round(r["compute_s"], 3)
        calib[var["name"]] = durs
        print(f"  {var['name']:26s} crit-path parts: "
              f"{sum(durs.values()):.1f}s total")
    pm.cleanup()
    json.dump(calib, open(calib_path(spec['name'].replace('-', '_')), "w"),
              indent=1)
    print("Saved:", calib_path(spec['name'].replace('-', '_')))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", default="video_processing",
                    choices=["video_analytics", "video_processing",
                             "log_processing", "staircase_chain",
                             "random_chain"])
    ap.add_argument("--calibrate", action="store_true")
    ap.add_argument("--policy", choices=sorted(POLICIES), default="rds_dcd")
    ap.add_argument("--instances", type=int, default=8)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--arrival-window", type=float, default=60.0)
    ap.add_argument("--deadline-factor", type=float, default=1.4)
    ap.add_argument("--spot-slack-factor", type=float, default=1.2)
    ap.add_argument("--revoke-penalty", type=float, default=8.0)
    ap.add_argument("--spot-bid", type=float, default=0.25)
    ap.add_argument("--keep-alive", type=float, default=30.0)
    ap.add_argument("--time-scale", type=float, default=60.0)
    ap.add_argument("--reserved-capacity", type=int, default=2)
    ap.add_argument("--prewarm-lead", type=float, default=5.0)
    args = ap.parse_args()

    spec = load_spec(args.workflow)
    if args.calibrate:
        calibrate(args, spec)
        return
    cpath = calib_path(args.workflow)
    if not os.path.exists(cpath):
        sys.exit(f"Run --workflow {args.workflow} --calibrate first.")
    calib = json.load(open(cpath))
    nodes, children = topo_order(spec["nodes"])
    by_id = {n["id"]: n for n in spec["nodes"]}

    random.seed(args.seed)
    pm = PoolManager()
    pm.clean_shared_data()
    cm = CostModel(os.path.join(HERE, "..", "Dataset"),
                   instance_type="c3.2xlarge", time_scale=args.time_scale)
    policy = make_policy(args.policy, pm,
                         reserved_capacity=args.reserved_capacity,
                         spot_slack_factor=args.spot_slack_factor,
                         revoke_penalty_s=args.revoke_penalty)

    t0 = time.time()
    sim_now = lambda: (time.time() - t0) * args.time_scale
    stats = {"cold": 0, "warm": 0, "reuse": 0, "cold_s": 0.0,
             "revocations": 0}
    agg = {"met": 0, "missed": 0, "reward": 0.0}
    task_rows = []
    lock = threading.Lock()
    stop = threading.Event()

    def spot_market():
        while not stop.is_set():
            if cm.spot_price(sim_now()) > args.spot_bid:
                nrev = pm.revoke_spot()
                with lock:
                    stats["revocations"] += nrev
            stop.wait(2.0)
    threading.Thread(target=spot_market, daemon=True).start()

    def reaper():
        while not stop.is_set():
            now = time.time()
            for pod in list(pm.pods):
                if pod.is_free() and now - pod.busy_until > args.keep_alive:
                    cm.charge(pod.pool, now - pod.created_at, sim_now())
                    pm.delete_pod(pod)
            stop.wait(2.0)
    threading.Thread(target=reaper, daemon=True).start()

    arrivals = sorted(random.uniform(0, args.arrival_window)
                      for _ in range(args.instances))
    variants = [random.choice(spec["variants"])
                for _ in range(args.instances)]
    od_rate = cm.rates["ondemand"]

    if args.policy == "rds_dcd_pred":
        def prewarmer():
            for arr in arrivals:
                delay = arr - args.prewarm_lead - (time.time() - t0)
                if delay > 0 and stop.wait(delay):
                    return
                try:
                    if not pm.free_pods():
                        pm.create_pod("reserved")
                except Exception:
                    pass
        threading.Thread(target=prewarmer, daemon=True).start()

    def run_instance(i, var):
        durs = calib[var["name"]]
        rem = remaining_cp(nodes, children, durs)
        crit = max(rem[n["id"]] for n in nodes if not n["parents"])
        deadline_s = args.deadline_factor * (crit + 10)
        wf_start = time.time()
        indeg = {n["id"]: len(n["parents"]) for n in nodes}
        ready = [n["id"] for n in nodes if indeg[n["id"]] == 0]
        failed = threading.Event()
        pool = ThreadPoolExecutor(max_workers=6)
        done_lock = threading.Lock()

        def exec_node(nid):
            node = by_id[nid]
            est = durs.get(nid, 1.0)
            payload = {"task_id": f"wf{i}-{nid}", "stage": node["stage"],
                       "params": node_params(node, var),
                       "inputs": [out_name(i, by_id[p])
                                  for p in node["parents"]],
                       "output": out_name(i, node)}
            slack = deadline_s - (time.time() - wf_start)
            for attempt in range(3):
                try:
                    with lock:
                        pod, kind = policy.choose(
                            {"fn_hash": node["stage"]}, slack, rem[nid],
                            force_pool="ondemand" if attempt else None)
                        pod.busy_until = time.time() + est * 2 + 20
                    r = pm.run_task(pod, payload, timeout=900)
                    if "error" in r:
                        raise RuntimeError(r["error"])
                    pod.last_fn_hash = node["stage"]
                    pod.busy_until = time.time()
                    with lock:
                        stats[kind if kind in stats else "reuse"] += 1
                        if kind == "cold":
                            stats["cold_s"] += pod.cold_start_s
                        task_rows.append([
                            i, var["name"], nid, kind, pod.pool,
                            f"{(pod.cold_start_s if kind=='cold' else 0):.3f}",
                            f"{r['read_s']:.4f}", f"{r['compute_s']:.4f}",
                            f"{r['write_s']:.4f}", f"{r['read_mb']:.2f}",
                            f"{r['wrote_mb']:.2f}"])
                    return
                except Exception as e:
                    print(f"  [wf{i} {nid} attempt {attempt+1}] "
                          f"{type(e).__name__}: {e}", flush=True)
                    time.sleep(1.0)
            failed.set()

        pending = {n["id"] for n in nodes}
        while pending and not failed.is_set():
            batch, ready[:] = list(ready), []
            if not batch:
                time.sleep(0.1)
                continue
            futs = {pool.submit(exec_node, nid): nid for nid in batch}
            for f, nid in futs.items():
                f.result()
                pending.discard(nid)
                with done_lock:
                    for c in children[nid]:
                        indeg[c] -= 1
                        if indeg[c] == 0:
                            ready.append(c)
        pool.shutdown(wait=True)

        elapsed = time.time() - wf_start
        wf_reward = 3.0 * od_rate * (crit * args.time_scale) / 3600.0
        with lock:
            if not failed.is_set() and elapsed <= deadline_s:
                agg["met"] += 1
                agg["reward"] += wf_reward
                verdict = "MET"
            else:
                agg["missed"] += 1
                verdict = "MISSED"
        print(f"wf{i} ({var['name']}): {elapsed:.1f}s vs "
              f"{deadline_s:.1f}s -> {verdict}", flush=True)

    threads = []
    for i, (arr, var) in enumerate(zip(arrivals, variants)):
        wait = arr - (time.time() - t0)
        if wait > 0:
            time.sleep(wait)
        th = threading.Thread(target=run_instance, args=(i, var))
        th.start()
        threads.append(th)
    for th in threads:
        th.join()

    for pod in list(pm.pods):
        cm.charge(pod.pool, time.time() - pod.created_at, sim_now())
    stop.set()
    pm.cleanup()
    pm.clean_shared_data()

    tot = cm.totals()
    pool_mix = {"reserved": 0, "ondemand": 0, "spot": 0}
    for r in task_rows:
        pool_mix[r[4]] += 1
    transfer_s = sum(float(r[6]) + float(r[8]) for r in task_rows)
    compute_s = sum(float(r[7]) for r in task_rows)
    share = 100 * transfer_s / max(transfer_s + compute_s, 1e-9)

    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    base = os.path.join(HERE, "results",
                        f"dag_{args.workflow}_{args.policy}"
                        f"_{args.instances}inst_seed{args.seed}")
    with open(base + "_tasks.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["instance", "variant", "node", "start_kind", "pool",
                    "cold_start_s", "data_read_s", "compute_s",
                    "data_write_s", "read_mb", "wrote_mb"])
        w.writerows(task_rows)
    with open(base + "_summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["workflow", "policy", "instances", "reserved_cost",
                    "ondemand_cost", "spot_cost", "total_cost", "reward",
                    "profit", "deadlines_missed", "cold_starts",
                    "warm_or_reuse", "total_cold_start_s",
                    "measured_transfer_s", "measured_compute_s",
                    "transfer_share_pct", "spot_revocations",
                    "tasks_on_reserved", "tasks_on_ondemand",
                    "tasks_on_spot"])
        w.writerow([args.workflow, args.policy, args.instances,
                    f"{tot['reserved']:.4f}", f"{tot['ondemand']:.4f}",
                    f"{tot['spot']:.4f}", f"{tot['total']:.4f}",
                    f"{agg['reward']:.4f}",
                    f"{agg['reward'] - tot['total']:.4f}",
                    agg["missed"], stats["cold"],
                    stats["warm"] + stats["reuse"],
                    f"{stats['cold_s']:.2f}", f"{transfer_s:.2f}",
                    f"{compute_s:.2f}", f"{share:.2f}",
                    stats["revocations"], pool_mix["reserved"],
                    pool_mix["ondemand"], pool_mix["spot"]])
    print(f"\n{args.workflow} policy={args.policy} "
          f"cost=${tot['total']:.4f} reward={agg['reward']:.4f} "
          f"profit={agg['reward']-tot['total']:.4f} "
          f"missed={agg['missed']}/{args.instances}")
    print(f"pool mix: R={pool_mix['reserved']} O={pool_mix['ondemand']} "
          f"S={pool_mix['spot']} | cold={stats['cold']} "
          f"({stats['cold_s']:.1f}s) transfer={transfer_s:.2f}s "
          f"({share:.1f}%)")
    print(f"Saved: {base}_summary.csv and _tasks.csv")


if __name__ == "__main__":
    main()
