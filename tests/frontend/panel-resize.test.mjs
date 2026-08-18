import assert from "node:assert/strict";
import test from "node:test";

import { constrainPanelWidths } from "../../static/js/panel-resize.js";

test("wide map layouts preserve requested side-panel widths", () => {
  assert.deepEqual(
    constrainPanelWidths({ containerWidth: 1440, leftWidth: 300, rightWidth: 400 }),
    { left: 300, right: 400, leftVisible: true, resizable: true },
  );
});

test("crowded desktop layouts preserve the minimum map and panel widths", () => {
  const layout = constrainPanelWidths({
    containerWidth: 900,
    leftWidth: 460,
    rightWidth: 520,
  });

  assert.equal(layout.leftVisible, true);
  assert.equal(layout.resizable, true);
  assert.equal(layout.left + layout.right, 564);
  assert.ok(layout.left >= 220);
  assert.ok(layout.right >= 260);
});

test("tablet layouts resize only the results panel", () => {
  assert.deepEqual(
    constrainPanelWidths({ containerWidth: 800, leftWidth: 300, rightWidth: 500 }),
    { left: 300, right: 472, leftVisible: false, resizable: true },
  );
});

test("stacked mobile layouts disable horizontal resizing", () => {
  const layout = constrainPanelWidths({
    containerWidth: 390,
    leftWidth: 300,
    rightWidth: 400,
  });

  assert.equal(layout.leftVisible, false);
  assert.equal(layout.resizable, false);
});
