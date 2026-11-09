# Benchmarks

Real accuracy numbers for VisionFit's rep counter, measured on hand-labelled clips.

## Recording clips

Aim for about 4 clips per exercise (20 total), 15–40 seconds each:

- Film side-on with the whole body in frame (the same setup the app recommends).
- Mix it up: different people, clothes, lighting and distances.
- Include a few honest mistakes: shallow squats, sagging push-ups, swinging curls.
- Count the reps yourself while watching the clip back. For squats and lunges, only count
  reps that actually reach depth, because that is the rule being measured.

## Running

1. Put the clips in `benchmarks/clips/` (this folder is git-ignored, so videos stay private).
2. Add one line per clip to `labels.csv`, for example `squat_01.mp4,Squats,12`.
   Exercise names must match exactly: `Squats`, `Push-ups`, `Biceps Curls (Dumbbell)`,
   `Shoulder Press`, `Lunges`.
3. From the repo root, run `python scripts/benchmark.py`.

The script writes `RESULTS.md` with exact-match rate, rep-level accuracy, mean absolute error,
and pose-model latency. Commit `RESULTS.md` and link it from the main README.
