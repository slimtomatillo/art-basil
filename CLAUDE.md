# Art Basil: notes for every agent and session

Read this first. It applies to anyone working in this repository. The project, its architecture and how to run things are in `README.md`, `OPERATIONS.md` and `ADDING_A_REGION.md`; the look and voice are in `BRAND.md`.

## When a story that visitors would notice is done, add a "What's new" entry

Visitors have a page, `whats-new.html`, listing what changed on the site. It is fed by `docs/data/whats_new.json` and is **kept by hand**, so it only stays accurate if every change that matters to a visitor adds a line.

- **Add an entry in the same pull request** as the change whenever a story adds or changes something a visitor would notice: a new venue or city, or a new feature or filter. Not for fixes (the page shows what is new, not what was wrong), scraper or proxy changes, tests, dependency bumps, or single-show data fixes.
- **Closing a story is three steps:** the Jira comment, the What's new entry, then close the ticket. Do not close a visitor-facing story without the entry.
- **Write it for visitors:** plain and warm, sentence case, one or two short sentences saying what it does for them. One entry per visible change, not per pull request. **No ticket or pull-request numbers** (a test fails if one is there).
- **Format and examples:** `OPERATIONS.md`, "What's new (the visitor page)". An entry is `{ "date": "YYYY-MM-DD", "title": "...", "text": "..." }`; add it near the top. A bad date, a missing title or text, or entries out of order fail `tests/whatsNew.test.js`.
- Several related pull requests in one story make one entry. If you are not sure whether a change counts, ask the person you are working with.

## Merging to `main` deploys live

The site is static on GitHub Pages and the daily scrape commits straight to `main`, so a merge is a release. Do not merge anything that looks unfinished to a visitor (an empty toggle, a half-built filter); hold it or hide it until it is whole.

## Running the tests

```
node --test tests/
~/.venvs/art-basil/bin/python -m unittest discover -s tests -p "test_*.py"
```

Run both before opening a pull request. Tests that write event data must swap the data-file paths to a temporary file, never the real ones.

## Working at the same time as other sessions

Other agents may be using the same checkout. Check `git status` and the current branch first; if another session is mid-change there, work in your own `git worktree` and do not switch its branch. Do not commit files you did not change.
