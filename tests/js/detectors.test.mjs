// Parity tests: the browser port (LandingPage/detectors.js) must match the Python detectors.
// Run with:  node --test tests/js/
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { DETECTOR_CLASSES } = require("../../LandingPage/detectors.js");
const fixtures = JSON.parse(readFileSync(new URL("../fixtures/pose_sequences.json", import.meta.url), "utf8"));

function expand(frame) {
  const [x, y, visibility] = fixtures.default_landmark;
  const points = Array.from({ length: 33 }, () => ({ x, y, visibility }));
  for (const [i, px, py, pv] of frame) points[i] = { x: px, y: py, visibility: pv };
  return points;
}

function run(sequence) {
  const detector = new DETECTOR_CLASSES[sequence.exercise]();
  return sequence.frames.map((frame) => detector.process(expand(frame)));
}

for (const sequence of fixtures.sequences) {
  test(`${sequence.name}: rep count`, () => {
    assert.equal(run(sequence).at(-1).reps, sequence.expected_reps);
  });

  test(`${sequence.name}: matches Python frame by frame`, () => {
    const js = run(sequence);
    assert.equal(js.length, sequence.python_outputs.length);

    js.forEach((out, i) => {
      const py = sequence.python_outputs[i];
      assert.deepEqual(Object.keys(out).sort(), Object.keys(py).sort(), `frame ${i} keys`);

      for (const [key, expected] of Object.entries(py)) {
        if (typeof expected === "number" && key !== "reps") {
          // Angles are truncated to whole degrees; allow 1° for floating-point edge cases.
          assert.ok(Math.abs(out[key] - expected) <= 1, `frame ${i} ${key}: js ${out[key]} vs py ${expected}`);
        } else {
          assert.equal(out[key], expected, `frame ${i} ${key}`);
        }
      }
    });
  });
}
