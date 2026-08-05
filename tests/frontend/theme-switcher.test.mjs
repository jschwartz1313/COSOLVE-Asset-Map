import assert from "node:assert/strict";
import test from "node:test";

import { THEME_LABELS, THEMES, normalizeTheme } from "../../static/js/theme-switcher.js";

test("the presentation switch exposes four stable modes", () => {
  assert.deepEqual(THEMES, ["classic", "dark", "color", "showcase"]);
  assert.deepEqual(
    THEMES.map((theme) => THEME_LABELS[theme]),
    ["Current", "Dark", "Color", "Showcase"],
  );
});

test("unknown or missing presentation modes return to the current view", () => {
  assert.equal(normalizeTheme("dark"), "dark");
  assert.equal(normalizeTheme("showcase"), "showcase");
  assert.equal(normalizeTheme(""), "classic");
  assert.equal(normalizeTheme("unknown"), "classic");
  assert.equal(normalizeTheme(null), "classic");
});
