# Real-Cluster Container Deployment for DCD Workflow Scheduling

Companion deployment for the paper *"Scientific Workflow Scheduling in
Cloud Considering Cold Start and Variable Pricing Model"*. Executes
real containerized workflows on a Kubernetes cluster under the paper's
scheduling approaches, with **measured** (not simulated) cold starts,
execution times, inter-task data transfers, and spot-style revocations.

## Concept mapping (paper -> deployment)

| Paper concept | Deployment realization |
|---|---|
| Container instance | task-runner pod on the cluster |
| Cold start | measured: pod creation -> HTTP server ready |
| Warm start | reuse of a running pod (function affinity via last stage) |
| Committed (reserved) / on-demand / spot | node pools via label `pool=` |
| Spot revocation | monitor replays historical price trace, kills spot pods when price > threshold |
| Data transfer | real files written/read through a shared volume |
| Cost | measured pod lifetimes x pricing from `../Dataset/pricing.csv` |

## Repository layout

```
deployment/
├── kind-config.yaml        # 4-node cluster: reserved/ondemand/spot pools,
│                           # shared /data volume (disk-backed)
├── task-runner/            # the container image every task runs in
│   ├── Dockerfile          # python:3.11-slim + ffmpeg + OpenCV
│   └── server.py           # 11 real workflow stages (see below)
├── scheduler/
│   ├── k8s_pool.py         # pod pool: create/reuse/revoke, cold-start timing
│   ├── cost_model.py       # pricing from Dataset CSVs, spot trace replay
│   └── dcd_policy.py       # all scheduling approaches (see below)
├── workflows_real/         # workflow DAG specs + calibration files
│   ├── video_analytics.json    (4 nodes, linear)
│   ├── video_processing.json   (4 nodes, fan-out + join)
│   ├── log_processing.json     (4 nodes, linear)
│   ├── staircase_chain.json    (42 nodes, deep chain)
│   └── random_chain.json       (40 nodes, deep chain)
├── run_dag_workflow.py     # experiment driver (calibrate + run)
├── run_reduced.ps1         # batch driver: 6 approaches x 3 workflows
└── results/                # output CSVs (per-task + per-run summaries)
```

## Workflow stages (all real computation)

`generate` (ffmpeg video synthesis), `transcode` (downscale re-encode),
`analyze` (OpenCV Canny/ORB/contours per sampled frame), `annotate`
(draw detections, re-encode), `cut_segment`/`merge` (ffmpeg segment
split/concat), `gen_log`/`basic_stats`/`filter_success`/`success_stats`
(HTTP log synthesis, regex parsing, filtering, aggregation),
`transform` (compression rounds for deep chains).

## Scheduling approaches (scheduler/dcd_policy.py)

| Key | Paper name | Pools |
|---|---|---|
| d_random      | Random baseline      | on-demand |
| d_sota        | FaasCache            | on-demand |
| d_dcd         | DCD (D)              | on-demand |
| ds_sota2      | CEWB                 | on-demand + spot |
| rd_dcd        | DCD (R+D)            | reserved + on-demand |
| rds_random    | Random               | all three |
| rds_dcd       | DCD (R+D+S)          | all three |
| rds_dcd_pred  | DCD (R+D+S w/ Pred.) | all three + pre-warming |

## Prerequisites

Docker Desktop (WSL2), `kind`, `kubectl`, Python 3.10+ with
`pip install kubernetes requests`.

## Quick start

```powershell
# 1. cluster (once)
kind create cluster --name dcd --config kind-config.yaml

# 2. task image
docker build -t dcd-task-runner:latest task-runner
kind load docker-image dcd-task-runner:latest --name dcd

# 3. proxy (separate terminal, leave running)
kubectl proxy

# 4. calibrate (measures per-stage durations, used for deadlines/slack)
.\run_reduced.ps1 -Calibrate

# 5. experiments (6 instances per run)
.\run_reduced.ps1 6
```

Single runs:
```powershell
python run_dag_workflow.py --workflow video_processing --policy rds_dcd --instances 6
```

Key knobs: `--deadline-factor` (default 1.4 x critical path),
`--spot-bid` (0.25), `--spot-slack-factor` / `--revoke-penalty`
(rigidity of the spot decision), `--reserved-capacity` (2),
`--arrival-window` (60 s), `--keep-alive` (30 s idle eviction).

## Outputs

Per run: `results/dag_<workflow>_<policy>_..._summary.csv` (costs per
pool, profit, deadline misses, cold starts, measured transfer/compute
seconds, pool mix) and `..._tasks.csv` (per-task placement, cold-start
seconds, read/compute/write timings, MB moved). The batch script also
writes a combined comparison CSV.

## Troubleshooting

- "running scripts is disabled": `Set-ExecutionPolicy -Scope Process Bypass`
- Pods 503 right after creation: spot revocation (expected) or pod not
  ready; tasks retry and escalate to on-demand automatically.
- "No space left on device": shared volume must be disk-backed
  (kind-config uses /var/lib/dcd-shared); results/data are auto-cleaned
  between runs.
- Docker engine 500 / DNS failures: restart Docker Desktop
  (`wsl --shutdown` first); recreate the cluster if the API server
  stays unreachable (`kind delete cluster --name dcd` + create).
