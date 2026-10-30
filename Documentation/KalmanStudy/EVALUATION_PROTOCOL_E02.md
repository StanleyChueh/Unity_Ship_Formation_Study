# Held-out evaluation e02 — frozen protocol

Frozen 2026-10-29 **before any e02 run**. Spec: `eval_e02_protocol.json` (its
SHA-256 is stored in the e02 manifest; `infer_eval.py` refuses any other).

## History that this test must be read with

e01 (protocol `EVALUATION_PROTOCOL.md`) tested the pre-registered d02 KF and was
**negative** (H1 −14.1 %, p = 0.57). Its failure taxonomy was then used to design
d04 (`ROBUST_D04.md`), so e01 is development data for d04. d04 passed its
predeclared rule on development seeds 1701–1702. e02 uses 8 seeds never used
before (3911 … 4789). Both e01 and e02 are reported; e02 does not replace e01.

## Arms (same binary, plant, detector, measurements, timing)

| Arm | Estimator | Controller |
|---|---|---|
| `on_rs` (**candidate**) | Kalman range filter fusing vision range, own speed and leader-speed telemetry, 4σ innovation gating; d02 offset KF | d04 range/speed law |
| `off_rs` | matched non-Kalman EMA (vision only), same 3 s coast | d04 range/speed law |
| `raw` | **no filter**: raw YOLO box, zero rates, no coasting (hold 0 s) | d04 range/speed law |
| `off_short` | production non-Kalman behaviour (finite-difference predictor, 0.6 s hold) | original area controller |

`raw` is an ablation ("no tracking filter at all"), not production behaviour;
production "Kalman OFF" is `off_short`. The controller's use of leader-speed
telemetry is identical in `on_rs`, `off_rs` and `raw`; only `on_rs` also fuses it
into its range estimate (that fusion is part of what is being tested).

## Cases

Primary (equal weight): C8 clear variable-speed/S-turn + 2 s scheduled losses;
C10 sea 3.0 huge waves + S-turn + 2 s losses; W1 rain 0.15 + sea 1.5, natural
intermittent detection loss. 8 seeds × 3 × 4 arms = 96 runs.
Secondary (descriptive, 4 seeds, all arms): C0 calm, C1 huge waves without
scheduled loss, C4 R180 turn + 2 s losses, C7 unexpected turn inside an 8 s loss
(negative control). Heavy rain / dark storm / night are not re-run: e01b and the
condition videos show the detector is blind there (0 % correct detections).

## Hypotheses (fixed-sequence gatekeeping, α = 0.05, exact 2^8 sign-flip on seed blocks)

1. H1 `on_rs` vs `raw` — does Kalman filtering/prediction improve formation
   compared with using no tracking filter (same controller)?
2. H2 `on_rs` vs `off_short` — does the Kalman system beat production Kalman-OFF?
3. H3 `on_rs` vs `off_rs` — does the Kalman filter beat a matched non-Kalman
   filter under the same controller (estimator contribution)?

Stop at the first non-rejection; later ones are descriptive. Practical target:
≥ 20 % geometric RMSE reduction and lower formation-broken time. H2 mixes the
controller change with the estimator; its interpretation relies on H3.

## Execution

`run_d04.py --stage evaluation --tag e02 --protocol … --shard i --nshards 6`
(6 parallel simulators, separate private projects/ports; fixed-step simulation
so parallelism changes wall-clock only). Primary group first. Archiver checks
the source freeze. All runs are reported, including failures; no source, gain,
case, seed or arm changes after the first e02 run.
