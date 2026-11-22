# Apple Calendar + Reminders website sync

This integration is designed for the owner's Mac and intentionally reads only two dedicated Apple containers:

- Calendar: `Academic Website`
- Reminders list: `Academic Website`

## One-time setup

On the Mac, clone or update the website repository, then run:

```bash
cd ~/path/to/eminyusuff.github.io
git pull
zsh macos/install.sh
```

The installer creates the dedicated Calendar and Reminders list if needed, creates `~/Pictures/AcademicSiteInbox`, and installs a macOS `launchd` job that runs at login and every 6 hours while the Mac is available.

macOS may request permission for Terminal/Python to automate Calendar and Reminders. Allow those permissions for the sync to work.

Git push authentication must already work on this Mac.

## How to use Calendar

Create academic events inside the `Academic Website` calendar just as normal Calendar events:

- Title: `IFAC World Congress 2026`
- Location: `BEXCO, Busan, South Korea`
- Start/end dates: conference dates
- Notes: optional description, presentation title, URL, grant information, etc.

Future events are exported as `upcoming`; past events as `attended`.

## How to use Reminders

Create quick academic records in the `Academic Website` Reminders list. Prefixes determine the type:

- `Grant: IBRO/SfN Travel Grant`
- `Fellowship: TÜBİTAK 2219`
- `Award: Best Poster Award`
- `Conference: SfN Neuroscience 2026`
- `Workshop: NeuroLeman`

The reminder Notes field becomes the website description. A reminder is only eligible for publication after it is marked completed.

## Photos

Put a curated event photo in:

`~/Pictures/AcademicSiteInbox`

Start the filename with the event start date in ISO format:

`2026-06-15-wageningen.jpg`

The sync copies the first matching image into `assets/events/` and links it to the corresponding academic record. This explicit photo inbox prevents unrelated personal photos from being uploaded automatically.

## Manual test

```bash
python3 macos/sync_apple_academic.py
cat data/apple_inbox.json
```

To test the full pull/sync/commit/push path:

```bash
zsh macos/run_and_push.sh
```

## Logs

- `~/Library/Logs/academic-site-sync.log`
- `~/Library/Logs/academic-site-sync-error.log`
