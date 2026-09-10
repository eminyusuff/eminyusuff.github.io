# Academic Website Automation

This repository contains a lightweight automation layer for academic highlights.

## What is automated

- A scheduled GitHub Actions workflow runs daily.
- Approved items in `data/highlights.json` are normalized into `data/highlights.generated.json`.
- Supported item types include:
  - `conference`
  - `award`
  - `grant`
  - `travel_grant`
  - `publication`
  - `talk`
  - `news`

## Adding a conference, grant, award or travel item

Add an object to `data/highlights.json` using this schema:

```json
{
  "type": "conference",
  "date": "2026-08-28",
  "title": "IFAC World Congress 2026",
  "location": "Busan, South Korea",
  "description": "Presented our work on anomaly detection with a fuzzy adaptive Kalman filter.",
  "url": "",
  "image": "assets/events/2026-ifac-busan.jpg",
  "source": "manual",
  "status": "approved"
}
```

For a grant or award:

```json
{
  "type": "travel_grant",
  "date": "2026-08-10",
  "title": "IBRO/SfN Travel Grant",
  "location": "Chicago, USA",
  "description": "Awarded travel support to attend SfN Neuroscience 2026.",
  "url": "",
  "image": "",
  "source": "email-confirmed",
  "status": "approved"
}
```

## Photos

Event photos should be stored under:

`assets/events/`

Recommended file naming:

`YYYY-event-city-short-description.jpg`

Examples:

- `2026-ifac-busan-presentation.jpg`
- `2026-sfn-chicago-poster.jpg`
- `2025-conference-netherlands.jpg`

Then place the relative path in the item's `image` field.

## Why Gmail/Calendar items are not directly auto-published

Email and calendar records are evidence that an event may exist, but they do not always prove attendance, presentation status, award acceptance, or which photo should be public. Therefore the recommended workflow is:

1. Detect a candidate from Gmail or Calendar.
2. Create or prepare a candidate highlight.
3. Confirm the wording and photo.
4. Mark the item `approved`.
5. The site sync workflow publishes it.

This avoids false claims on a public academic website.

## Future integrations

The current schema is intentionally compatible with future ingestion from:

- ORCID
- Crossref / OpenAlex
- Gmail confirmation emails
- Google Calendar conference events
- Google Drive event-photo folders

Those integrations should create candidate items with `status: "pending"`, not public items directly.
