# Occurrence Tracker

[![hacs][hacs-badge]][hacs-url]

A small Home Assistant integration for a question core can't answer: **when does
this usually happen?**

Core's `statistics` and `history_stats`, and the HACS `historical_stats`, all
aggregate over a *contiguous window* — "this week", "3 months ago", "all
history". None of them fold occurrences back onto a repeating cycle, so there is
no built-in way to ask "what hour of the day is this most likely?" or "is it
mostly a weekend thing?". Jinja templates can't help either: they have no access
to the recorder or the statistics tables.

This integration answers it by recording the events itself.

It's aimed at things that happen **occasionally** — once or twice a week — where
the recorder's ~10-day retention means raw history has nothing useful in it, and
where you want the pattern rather than the log.

## Installation

### HACS (custom repository)

1. HACS → ⋮ → **Custom repositories**
2. Add `https://github.com/pmaciocia/occurrence-tracker` with category
   **Integration**
3. Find **Occurrence Tracker** in HACS and download it
4. Restart Home Assistant

### Manual

Copy `custom_components/occurrence_tracker/` into your `config/custom_components/`
directory so you end up with
`config/custom_components/occurrence_tracker/manifest.json`, then restart.

### Set it up

**Settings → Devices & Services → Helpers → Create helper → Occurrence Tracker**,
then give it a name. Add as many as you like — each gets its own device and its
own stored history.

Deleting a config entry deletes its recorded occurrences too, so nothing is left
orphaned in `.storage`.

## What it creates

One config entry, one device, five entities. With the entry named *Last*:

| Entity | What it is |
|---|---|
| `button.last_record` | Press when the thing happens. |
| `sensor.last_total` | Running total, `state_class: total_increasing` — so it gets permanent hourly long-term statistics and works with date-based chart cards. |
| `sensor.last_last` | Timestamp of the most recent occurrence. |
| `sensor.last_by_hour` | State is the busiest hour (`"14:00"`). Attributes carry the full 24-hour profile. |
| `sensor.last_by_weekday` | State is the busiest day (`"Saturday"`). Attributes carry the full 7-day profile. |

Both profile sensors expose their distribution three ways:

```yaml
profile: [{hour: 0, count: 0}, {hour: 1, count: 2}, ...]   # for chart cards
counts:  [0, 2, 0, ...]                                     # for templates
total:   14
```

`by_weekday`'s profile entries are `{day: 1..7, name: "Monday", count: n}`,
Monday first.

## The design decision that matters

**It stores raw timestamps, not buckets.** Every occurrence is kept in
`.storage` as a UTC timestamp; the hour and weekday profiles are computed from
that list on demand.

At the volumes this is built for — a couple of events a week, so a few hundred a
year — the list is trivially small, and keeping the source data means the
bucketing is never a decision you're locked into. Two-hourly blocks,
weekday-versus-weekend, month of year: all of it can be added later and will
apply to everything already recorded. A design built on counters throws that
away at the moment of recording and can never get it back.

Bucketing happens in **local time** via `dt_util.as_local`, so an event at 23:30
UTC in July lands in the 00:00 bucket of the following day, as it should. This
is the part that makes the obvious alternative — querying the recorder database
with SQL — awkward, because MariaDB needs its timezone tables loaded to do the
same conversion and a fixed offset silently breaks across BST.

## Services

All three target the button entity.

| Service | Purpose |
|---|---|
| `occurrence_tracker.record` | Record an occurrence. The optional `timestamp` field records one in the **past** — the backfill path for events you remember but never logged. |
| `occurrence_tracker.remove_last` | Undo the most recent occurrence, for an accidental press. |
| `occurrence_tracker.clear` | Forget everything. Not undoable. |

```yaml
action: occurrence_tracker.record
target:
  entity_id: button.last_record
data:
  timestamp: "2026-09-01 14:30:00"
```

Removing occurrences makes `sensor.*_total` drop. Home Assistant reads that as a
meter reset on a `total_increasing` sensor and carries on correctly.

## Charting the profiles

The `profile` attribute is shaped for the
[Statistics Graph Chart Card](https://github.com/cataseven/Statistics-Graph-Chart-Card)'s
attribute data source:

```yaml
type: custom:statistics-graph-chart-card
card_header: By hour of day
chart_mode: timeline
group_by: hour
entities:
  - entity: sensor.last_by_hour
    data_attribute: profile
    data_time_field: hour
    data_value_field: count
    data_time_unit: hour_of_day
    graph_type: bar
    aggregate_func: max
    decimals: 0
```

That card has no `day_of_week` time unit, so the weekday profile is better drawn
from `counts` by any card that can plot a plain list, or read straight off the
sensor's state ("busiest day").

`sensor.*_total` carries long-term statistics, so it also drives ordinary
date-based charts — a day × hour heatmap, a GitHub-style year calendar, a weekly
count — with `aggregate_func: change`.

## Requirements

Home Assistant 2024.8.0 or newer.

## License

MIT

[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
