# Presentation modes

## Standard light interface (October 21, 2026)

The public site now uses only the established light COSOLVE interface. The Appearance menu, alternate palettes, introduction markup, theme stylesheet, and theme-switching script have been removed. Existing browser preferences under `cosolve-display-mode` are ignored, including when the device prefers dark mode. Asset data, map basemaps, filters, saved views, and exports are unchanged.

The More menu retains its account actions, permission checks, keyboard access, and outside-click dismissal. The original presentation implementations remain recoverable from Git history.

## Retired designs (historical reference)

The earlier presentation modes all used the same Django views and underlying data:

| Mode | Purpose |
| --- | --- |
| Current | The established light COSOLVE interface. |
| Dark | The same layout and controls with a dark palette. |
| Showcase | A presentation-focused dark treatment with a cinematic, multi-section entrance and real Virginia photography. |
| Showcase Light | The full Showcase entrance, imagery, motion, and expanded layouts using the established light COSOLVE palette. |

The former selector stored its choice under `cosolve-display-mode`. The current site no longer reads or writes this preference.

Print and PDF output continues to use the light treatment.

## Compact header (September 15, 2026)

The former four-button design selector was moved into an Appearance menu. The mobile header was reduced from approximately 186px to 94px. Map, Directory, and Regions remained visible; About data, Get connected, and account actions moved under More. This navigation arrangement remains, without the Appearance menu.

## Showcase photography

The retired Showcase entrances used locally optimized copies of these source images. These files are no longer loaded by the public interface:

- NASA Langley autonomous flight research, Hampton, Virginia: NASA / Bowman, [NASA source](https://www.nasa.gov/aeronautics/nasa-flies-autonomous-drones/)
- Autonomous surface vessel demonstration, Fort Monroe, Virginia: U.S. Navy public-domain image, [DVIDS source](https://www.dvidshub.net/image/144663/autonomous-unmanned-surface-vehicle-demonstration)
- UAS beach survey, Virginia Beach: U.S. Army photo by Patrick Bloodgood, public domain, [DVIDS source](https://www.dvidshub.net/image/5738169/flying-uas)
- Norfolk International Terminal: U.S. Army photo by Patrick Bloodgood, public domain, [DVIDS source](https://www.dvidshub.net/image/5052532/usace-port-virginia-ramp-up-norfolk-harbor-deepening-efforts)

The generated atlas and panorama files remain presentation artwork only and must not be treated as evidence for an asset record.
