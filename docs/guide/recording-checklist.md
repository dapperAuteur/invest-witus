# Recording checklist

The pre-flight list before any Invest.WitUS recording session, and where each clip ends up. The scripts are in
[`recording-scripts.md`](recording-scripts.md); the house rules come from the ecosystem's tutorial plans
(witus plans 30, 31 and 33).

## Before every session

**The data on screen**

- [ ] Placeholder symbols only: `INDEX`, `OTHER`, `FUNDX`, `CASH`. Made-up shares and amounts. The account is
      `Practice` at `Example Brokerage`.
- [ ] Scripts 3 to 6 run on the laptop copy, never on production's admin, which holds real statements.
- [ ] Script 5's Vercel scene shows the **Cron Jobs** list and the run status only. The log's JSON names your
      real holdings; it stays closed.
- [ ] A throwaway waitlist entry for script 1, deleted afterwards in **Waitlist entries**.
- [ ] Your WitUS account has a display name, so the header never shows an email.

**Never on camera**

- [ ] The admin password: sign in at `/admin/` before you press record.
- [ ] `.env`, any shell variable, the Vercel **Environment Variables** page, the cron secret, the Tiingo token.
- [ ] An email inbox. Script 2 cuts between "Check your email" and the return to the app.
- [ ] Real email addresses. The one on the WitUS sign-in form is cropped or cut.
- [ ] Other Vercel projects in the dashboard sidebar, if any name is private: crop to the page body.

**The window**

- [ ] The browser window at 1280 by 720 (the tutorial frame from witus plan 30, section 8.3, and the tutorial
      recording config), the same for every clip.
- [ ] Bookmarks bar hidden; one tab; no extensions showing icons.
- [ ] A private window for scripts 1, 2 and 7, signed out of invest.witus.online and accounts.witus.online.
- [ ] Notifications off (Do Not Disturb on the Mac), the calendar and mail apps closed or on another screen.
- [ ] The terminal for script 5 cleared, at the repository root, with a plain prompt.

**Warm-up**

- [ ] Every page in the script opened once before recording, so the first load is not recorded cold (Vercel's
      function and Neon both wake up; the first request after a quiet spell is slow).
- [ ] The laptop copy's `runserver` up, `migrate` run, the superuser signed in at `/admin/`, the test data from
      the top of `recording-scripts.md` entered (except what the script enters on camera).
- [ ] `data/private/prices/INDEX.csv` copied from the sample for script 5.
- [ ] The expected values in script 5 recomputed if the test data changed.

**The take**

- [ ] Read the script's **Preconditions** once more; they differ per clip.
- [ ] One take per step where possible; a flubbed line costs one step.
- [ ] Say "information, not advice" once in every clip that shows a share count or an amount (scripts 3, 4, 5, 6).
- [ ] Pause two seconds on the first frame and after the closing line, so the edit has room.
- [ ] Scroll with the keyboard; never faster than a heading can be read.

## After the session

- [ ] Delete the throwaway waitlist entry.
- [ ] Recordings go outside git. `data/private/` is gitignored; `data/private/recordings/<slug>/` is a fine
      home. Nothing under `docs/` or `src/` ever holds a video or an audio file.
- [ ] Note in the operator task which slugs are recorded.

## What each clip is published as

Per witus plan 33 (decisions 4 and 6): BAM's voice on the lead demos, captions on quick-reference clips; clips
are published to YouTube and to each app's help page. These seven are quick-reference clips.

| Slug | Script | Published as |
|---|---|---|
| `landing-and-waitlist` | 1 | YouTube; the app's help page when it has one |
| `sign-in-and-out` | 2 | YouTube; the app's help page when it has one |
| `account-and-statement` | 3 | YouTube; the app's help page when it has one |
| `compare-statements` | 4 | YouTube; the app's help page when it has one |
| `account-values-and-pull` | 5 | YouTube; the app's help page when it has one |
| `watch-list` | 6 | After chapter 09 merges; same outlets |
| `faq-and-report` | 7 | YouTube; the app's help page when it has one |

Captions are never burned into the frame (plan 33, section 7): the mp4 stays clean, and the captions travel as
a sidecar file, `<slug>.srt` for the YouTube upload and `<slug>.vtt` for a `<track kind="captions">` on a help
page, so they stay toggleable, translatable and readable by screen readers. The VOICE lines in the scripts are
the caption text. Invest.WitUS has no help page in the roadmap yet; until it does, YouTube is the one outlet,
and the help-page embed waits for that chapter.
