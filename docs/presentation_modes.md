# Presentation modes

The public interface provides four browser-side presentation modes. They all use the same Django views, asset records, filters, saved views, and exports.

| Mode | Purpose |
| --- | --- |
| Current | The established light COSOLVE interface. |
| Dark | The same layout and controls with a dark palette. |
| Color | A restrained editorial atlas treatment using burgundy and green accents. |
| Showcase | A presentation-focused dark treatment with a cinematic, multi-section entrance and real Virginia photography. |

The selected mode is stored in the browser under `cosolve-display-mode`. It does not modify filter URLs, saved views, or any underlying data.

Print and PDF output suppresses the decorative presentation layers and uses a neutral light treatment for legibility.

## Showcase photography

The Showcase entrance uses downloaded, locally optimized copies of these source images:

- NASA Langley autonomous flight research, Hampton, Virginia: NASA / Bowman, [NASA source](https://www.nasa.gov/aeronautics/nasa-flies-autonomous-drones/)
- Autonomous surface vessel demonstration, Fort Monroe, Virginia: U.S. Navy public-domain image, [DVIDS source](https://www.dvidshub.net/image/144663/autonomous-unmanned-surface-vehicle-demonstration)
- UAS beach survey, Virginia Beach: U.S. Army photo by Patrick Bloodgood, public domain, [DVIDS source](https://www.dvidshub.net/image/5738169/flying-uas)
- Norfolk International Terminal: U.S. Army photo by Patrick Bloodgood, public domain, [DVIDS source](https://www.dvidshub.net/image/5052532/usace-port-virginia-ramp-up-norfolk-harbor-deepening-efforts)

The generated atlas and panorama files remain presentation artwork only and must not be treated as evidence for an asset record.
