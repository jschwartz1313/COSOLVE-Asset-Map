# Presentation modes

The public interface provides four browser-side presentation modes. They all use the same Django views, asset records, filters, saved views, and exports.

| Mode | Purpose |
| --- | --- |
| Current | The established light COSOLVE interface. |
| Dark | The same layout and controls with a dark palette. |
| Color | A brighter editorial atlas treatment with more color and graphic texture. |
| Showcase | A presentation-focused treatment with photography, motion, and an optional cover screen. |

The selected mode is stored in the browser under `cosolve-display-mode`. It does not modify filter URLs, saved views, or any underlying data.

The presentation artwork in `static/img/themes/` is generated visual material. It is decorative and must not be treated as evidence for an asset record. Print and PDF output suppresses the decorative presentation layers and uses a neutral light treatment for legibility.
