# Presentation modes

The public interface provides four browser-side presentation modes under **Appearance** in the header. They all use the same Django views, asset records, filters, saved views, and exports.

| Mode | Purpose |
| --- | --- |
| Current | The established light COSOLVE interface. |
| Dark | The same layout and controls with a dark palette. |
| Showcase | A presentation-focused dark treatment with a cinematic, multi-section entrance and real Virginia photography. |
| Showcase Light | The full Showcase entrance, imagery, motion, and expanded layouts using the established light COSOLVE palette. |

The selected mode is stored in the browser under `cosolve-display-mode`. It does not modify filter URLs, saved views, or any underlying data.

Print and PDF output suppresses the decorative presentation layers and uses a neutral light treatment for legibility.

## Compact header (September 15, 2026)

The previous always-visible four-button design selector is now an Appearance menu. All four designs remain available; no stakeholder preference has been chosen as a permanent replacement. The mobile header is reduced from approximately 186px to 94px. Map, Directory, and Regions stay visible; About data, Get connected, and account actions are under More, with the same permission checks as before. Menus close with Escape, an outside click, or a selection.

## Showcase photography

Both Showcase entrances use downloaded, locally optimized copies of these source images:

- NASA Langley autonomous flight research, Hampton, Virginia: NASA / Bowman, [NASA source](https://www.nasa.gov/aeronautics/nasa-flies-autonomous-drones/)
- Autonomous surface vessel demonstration, Fort Monroe, Virginia: U.S. Navy public-domain image, [DVIDS source](https://www.dvidshub.net/image/144663/autonomous-unmanned-surface-vehicle-demonstration)
- UAS beach survey, Virginia Beach: U.S. Army photo by Patrick Bloodgood, public domain, [DVIDS source](https://www.dvidshub.net/image/5738169/flying-uas)
- Norfolk International Terminal: U.S. Army photo by Patrick Bloodgood, public domain, [DVIDS source](https://www.dvidshub.net/image/5052532/usace-port-virginia-ramp-up-norfolk-harbor-deepening-efforts)

The generated atlas and panorama files remain presentation artwork only and must not be treated as evidence for an asset record.
