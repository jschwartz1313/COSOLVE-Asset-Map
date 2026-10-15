import assert from "node:assert/strict";
import test from "node:test";

import { THEME_LABELS, THEMES, normalizeTheme } from "../../static/js/theme-switcher.js";

test("the presentation switch exposes only the two active modes", () => {
  assert.deepEqual(THEMES, ["classic", "dark"]);
  assert.deepEqual(
    THEMES.map((theme) => THEME_LABELS[theme]),
    ["Current", "Dark"],
  );
});

test("unknown or missing presentation modes return to the current view", () => {
  assert.equal(normalizeTheme("dark"), "dark");
  assert.equal(normalizeTheme("showcase"), "classic");
  assert.equal(normalizeTheme("showcase-light"), "classic");
  assert.equal(normalizeTheme("color"), "classic");
  assert.equal(normalizeTheme(""), "classic");
  assert.equal(normalizeTheme("unknown"), "classic");
  assert.equal(normalizeTheme(null), "classic");
});
