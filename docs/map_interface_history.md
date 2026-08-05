# Map interface history

This note preserves the map control and filter presentation that existed before the
August 5, 2026 interface simplification. The exact prior implementation remains in
Git commit `39e8b95`.

## Previous interface

- The map toolbar exposed separate expanding controls for **Save / export**,
  **Analyze**, **Layers**, and **Legend**, alongside **Filters** and **Reset**.
- On narrower screens, those controls wrapped across multiple rows and occupied a
  larger portion of the map.
- Active filters were indicated by a number inside the **Apply filters** button in
  the filter panel. Once that panel was closed, the map did not show which filters
  were active or offer a way to remove one filter directly.

## Current interface

- **Layers**, **Analyze**, and **Save and share** are grouped under one **Map tools**
  menu. **Filters**, **Reset**, and **Legend** remain directly accessible.
- Applied filters appear in a persistent strip over the map as labeled chips.
  Each chip can remove its individual filter, and **Clear all** removes the complete
  applied filter set.
- The compact-screen **Filters** button also displays the number of applied filters.
