# CardFlip v1.2.0 preview — Workspace and research

Install over v1.1.1 on a development branch. See [TESTING.md](TESTING.md) for the acceptance and observation-only workflow.

- Workspace: 200 recent card families, clearable history, separate paper trades and actual inventory, CSV export, dated net-value snapshots and net profit accounting. No automatic buys.
- Career context: NFL draft and rookie data, NBA bio/draft fields where available, MLB debut and optional level-specific minor league stats. Source/date retained; no automated ranking or news ingestion.
- Investment research: descriptive market and cached player evidence; chronological replay using cached title-derived sales, not a predictive model.
- Existing auction mode and clipboard workflow unchanged. No new requirements or paid API. PSA remains optional.

# CardFlip Local v0.9.1

Personal sports card recognition and resale research tool. Local Python and Chrome/Brave side panel. No paid hosting or AI API. Sold data uses your existing CompsAPI account and 100-request local monthly cap. No site monitoring, automated capture or bidding.

## Upgrade (existing installations)
Stop the backend with Ctrl+C. In Terminal:

```sh
cd ~/Downloads
unzip -o CardFlip-Local-v0.7.1.zip
cd cardflip-local
bash start.sh
```

No new Python dependencies compared with v0.4. If starting from an earlier version, run `.venv/bin/python -m pip install -r requirements.txt`. New installations run `bash setup.sh` before starting; enter the API key in `.env`. This archive excludes `.env`, `data/`, and `.venv/`; existing credentials and database persist. Reload the correct unpacked extension at brave://extensions or chrome://extensions and reopen it. Both UI and connection status should show 0.7.

## Ollama
Open the Ollama app and run `ollama list` to confirm qwen3.5:4b (fast) and optionally qwen3.5:9b (detail). Install via `ollama pull qwen3.5:4b` if needed. The backend only calls http://127.0.0.1:11434 and keeps the model warm for 15 minutes. Do not expose Ollama or the CardFlip server on the public internet. OCR only is available as a separate mode (requires Tesseract).

Copy token without printing it:

```sh
grep '^LOCAL_TOKEN=' ~/Downloads/cardflip-local/.env | cut -d= -f2- | tr -d '\n' | pbcopy
```

Paste into Connect. API key remains in .env; never paste into the sidebar.

## Workflow
1. Select Fast AI (default), Detailed AI, or OCR only. Paste a permitted card photo or choose a PNG/JPEG under 5 MB. Upload automatically scans the full image. The AI returns compact structured fields and metadata. Exact image recognition results are cached separately for 30 days; no original images stored. Model timing and cache status are visible. The detailed model is opt-in, not an automatic slow fallback.
2. If the identity has all fields and is not a detected autograph or numbered card, the checked Auto-fetch option triggers one preliminary lookup (cached when possible). Disable it to test without spending API requests. If parallel is unknown the scan stops. Verify Base manually and click the Base button or enter the actual parallel. Unknown is never silently Base. Correct wrong identity fields before lookup.
3. The decision panel appears near the top. A preliminary estimate is not a verified bid recommendation. Review actual sold listings and confirm the exact variant, grade, designation, and conditions. Confirm individual rows or bulk-confirm the newest ten only after review. All selected recent matching rows (up to 90 days) are used, not just ten. Counts are provider samples, not market totals. Break-even and 30-day-vs-prior-60-day median trend are shown when sufficient data exists.
4. Enter the next bid and edit expense settings. Max flip bid is the lower of the ROI and profit thresholds, calculated from the lower quartile of buyer-paid sales less the haircut. Default minimum profit for new users is $5 and ROI 25%; existing saved settings are retained. The bid excludes acquisition tax and shipping. No bid recommendation on stale, demo, insufficient, or unverified data. No automatic purchases.

## Current limits
- AI recognizes raw cards and other graders as suggestions; actual pricing is currently limited to supported graded cards (PSA/CGC/BGS/SGC) with exact identities. Specialized inserts, serial numbers, autographs and relics need manual validation; no automatic special-card lookup. Model output may be wrong even when complete. AI is not proof of card authenticity or exact parallel. No player outlook, hold recommendation, automated grade comparisons or portfolio yet.
- API response time plus inference may exceed 5–10 seconds. Only user's CLI benchmarks on one card are known; integrated model endpoint tests mock Ollama. No real browser, live API key or Mac inference tested in build environment. Local model output may vary with image preprocessing/schema.
- 24-hour sales cache, 100 monthly request cap, conservative request counting preserved. Existing cache rows remain usable. No paid plan upgrades. No unauthorized livestream capture or monitoring. Test with permitted images.

## Tests
`python -m unittest discover -s tests -v` (use .venv/bin/python if installed in venv).

## v0.6 — Variant discovery and verified slab memory

- With automatic lookup enabled, a vision result missing only the variant (and with no detected autograph or print serial) triggers a broad search for the same player, year, set, checklist number, grader and grade designation. The request asks for up to 240 sales in the preceding 90 days; actual coverage varies. You can also press **Find possible variants** manually.
- Candidate listings are screened for the same card identity and grouped using explicit title evidence. An unspecified title is not evidence of Base. Conflicting, numbered, specialty and unrecognized parallel titles are excluded where detected. These heuristics are incomplete; inspect the listings. Conditional bids are not a safe floor, and the overall decision remains VERIFY VARIANT — PASS.
- Confirm the exact variant using the appropriate group button, the existing Base button, or manual entry. A fresh family cache can serve the subsequent exact lookup without another request. If it lacks classified matches, a targeted force refresh is available. Family cache freshness is 24 hours, and derived exact caches inherit the original fetch timestamp. Changing deal rules requires recalculating possible variants (normally via the cache).
- After reviewing the card and certificate number, press **Remember verified slab identity** to save your confirmation locally. Subsequent scans with the same grader/certificate and matching core identity can recall the variant. Conflicting fields are not overwritten automatically. This is NOT official authentication; a cloned certificate can appear on a counterfeit slab. Memory is stored in the existing SQLite cache; you may correct it by explicitly saving the corrected identity.
- PSA access is optional and is not integrated in this release. Request approval through https://www.psacard.com/support. The API may impose licensing restrictions; no unofficial scraping or credential bypass is implemented.
- All existing quota, preview and manual sold-comparison checks remain in force. No automatic purchasing or live stream capture. Raw, autograph, serial-numbered and relic pricing, player intelligence, hold estimates and inventory management remain future work.
- Upgrade from v0.5: stop server, unzip with `-o` into the parent of `cardflip-local`, run `bash start.sh`, reload unpacked extension. Existing `.env`, `.venv` and `data/` are not in the ZIP. No new dependencies.

## v0.7 — Compact auction workspace

Default Auction mode keeps image input, identity, next bid and decision close together. Research expands the drawers; individual drawers can be opened in either mode. Paste or choose an authorized image to scan automatically. New clears the current card and bid without deleting caches. Conditional estimates are visually distinct from confirmed valuations. Use Review sold comps to inspect listings and confirm exact matches before bidding. No new dependencies, API permissions or automatic capture.

## v0.7.1 — Visual polish

Modern dark auction terminal, blue controls, clear amber conditional estimates and green only for positive verified buying decisions. No changes to recognition, market matching, pricing, quota, or storage.

### v0.8 — Max-bid-first auction mode and raw cards

- Upload or paste an authorized image; the fast local model identifies the card and attempts the sales lookup automatically. Raw/ungraded is now a selectable condition, with no numeric grade required. If the model is uncertain, use the Raw / ungraded button only after checking the card.
- The price panel shows profit, ROI and total cost at the calculated maximum bid even when no bid is entered. The optional bid checker lets you compare a specific offer. A whole-dollar copy button appears only when reviewed comps support a valid bid ceiling. It never places a bid.
- Checklist card number and print run are separate. Enter `75` for a card numbered `73/75`. Raw searches use the provider's `graded=false` filter; numbered comps must match the denominator. Unknown checklist numbers with a known print run and edition can generate a **conditional** estimate, never a verified purchase signal. Generic autograph/insert titles and raw condition still need review.
- Fast vision uses a 15-second response-read timeout and the external sales lookup uses 2-second connect / 8-second read timeouts; these are not hard end-to-end deadlines. The sidebar reports total scan/lookup time. Cache hits are usually faster, but no live auction latency is guaranteed. If a card is unclear, skip it rather than rush. Capture automation is not enabled.
- Upgrade over v0.7.1 by extracting into the existing directory and restarting. The archive intentionally omits `.env`, databases and virtual environments. Recognition cache version changes to correct older raw/serial parsing; the next scan of an existing photo may run inference again.

### v0.8.1 — partial raw-card discovery
- Reject standalone RC/rookie markers as checklist numbers. Flag trailing Refractor/Base conflicts and refresh old vision-cache entries using a new prompt version.
- A confirmed raw card with player, year and product may discover title-derived possible sales even without a checklist number. Groups may contain different cards, so no median or bid limit is shown until the number is known. Grade remains optional for raw cards.
- For an unrecognized or incorrect product/year, correct the fields before retrying. Discovery is not exact visual matching. No additional dependency or paid service.

## v0.9 — Card family price board

- Paste/upload an image and the default AI auto-fetch workflow now opens a mixed-grade price board, not an exact grade/variant lookup. A manual Price board button is also available. Only the player is required; include year and product whenever known. The card number is optional. Correct misread identity fields before relying on the board.
- One CompsAPI sold page (up to 240 rows, 90 days) omits grader/grade/graded restrictions. Results are cached separately for 24 hours and share the existing quota cap. No automatic retries or per-grade calls. Search without card # / Search player only are optional broader queries, each potentially using one request if not cached. Refresh uses one request. Exact lookup can reuse a matching mixed-grade cache.
- Compact matrix: variant, raw, PSA 8/9/10; market median, conditional maximum bid, and sample count. Show PSA 1–10 expands the full grade rows, including observed other graders and distinct non-PSA 10 designations. Click a grade for title evidence and sold links. Unspecified is not Base. Missing values are never extrapolated. Individual unresolved sales (including specialty cards with ambiguous editions and listings lacking a reliable checklist number) are shown separately without pooled pricing. Player-only search provides individual listing references, not grouped prices.
- Median uses buyer-paid prices before tax when shipping is known; item-only median or partial shipping-known samples are explicitly marked. Sparse groups display observed sales but no maximum bid. Conditional maximum bids require five or more recent title-derived matches, three in the last 30 days, fresh cache, known shipping and an acceptable spread, and use the existing conservative profit/ROI calculator. These are NOT confirmed buy signals. Use the exact lookup workflow and inspect condition, edition and comps before bidding. No automatic bids or live capture.
- Install over v0.8 or v0.8.1 by stopping the backend, extracting with `unzip -o CardFlip-Local-v0.9.zip`, starting it again, and reloading the unpacked extension. No new dependencies; `.env`, `.venv` and data remain untouched.

## v0.9.1 — drag-and-drop, visual comparison, local capture demo

Upgrade with `unzip -o CardFlip-Local-v0.9.1.zip` from ~/Downloads, restart the backend, reload the Brave extension. No new dependencies. The archive excludes your `.env`, `.venv` and database.

Drop one PNG/JPEG (under 5 MB) onto the scanner, paste, or click the drop zone to choose a file. All three trigger the existing automatic scan and price-board workflow. Drop again after the current scan finishes. Images are processed locally; no changes to quota or pricing logic.

**Visual reference (optional):** after scanning, open Compare a visual reference and choose a known, permitted card photo. Enter its variant if known. The local Qwen 9B model compares the two photos and returns a suggestion (similar/different/uncertain) and evidence. It does not change identity or prices. Foil and color can look different at different angles; this is not authentication. No online reference-image collection is included.

**Capture demo:** open `http://127.0.0.1:8765/capture-demo.html`, choose a card photo you own, open the CardFlip side panel, focus the demo tab and press Command+Shift+K. Check `brave://extensions/shortcuts` if the shortcut conflicts. The extension captures a single visible frame on this exact local page only. No live marketplace capture, monitoring or bidding is enabled. This lets you test the capture mechanism before seeking platform permission.

**PSA:** after recognizing a PSA certificate, a link to the official certificate page appears in Connection & API settings. The optional CLI check `.venv/bin/python psa_check.py 53353413` sends your `PSA_API_TOKEN` from `.env` in an HTTPS Bearer header. Only run it if checking access or after approval; no automatic retries or integration into price calculations. PSA may reject accounts without approval even with a generated token. The public cert endpoint is not a historical sales feed. CompsAPI remains the price source. The board now canonicalizes explicit word-order aliases (e.g. Prizm Silver / Silver Prizm) without merging Silver Mosaic with Silver Prizm or Unspecified with Base.

## v0.9.2 — quick quote, fewer controls, local demo shortcut

Install over v0.9.1 by stopping the backend, extracting this archive in the parent folder, restarting and reloading the extension. Your credentials, database and cache are not included or overwritten. No new dependencies.

- The maximum flip bid panel above the price board uses the same deal rules. When a recognized variant and grade have one matching row, it selects that row; otherwise select the variant/grade or click a matrix price. All board numbers remain conditional references, never verified buying signals. The exact lookup and reviewed comps workflow remains under More scan tools. Recognition diagnostics, visual comparison and search controls are collapsed by default.
- Sparse or otherwise weak named-variant cells now have a separate low-confidence reference limit (`~Max`). With fewer than five sales, use the lowest observed buyer-paid sale and an additional 20% reduction; otherwise use the lower quartile and an additional 15% reduction. Unknown shipping contributes zero revenue; the usual haircut, shipping, tax, profit and ROI settings also apply. No positive margin displays Pass. Unspecified variants and stale caches do not receive these limits. These estimates are not validated probability forecasts. Review card/grade/condition and sales before bidding.
- Local demo: reload extension, then refresh `http://127.0.0.1:8765/capture-demo.html`, choose a photo and click **Scan demo** in the open sidebar. It reads the selected local file directly (not the whole browser window). Default Mac shortcut is Control+Shift+Y; existing installations may retain the old shortcut, so set it at `brave://extensions/shortcuts` and focus the demo tab before pressing. No live-site capture or monitoring. If Notion intercepts a shortcut, change it or use the button.
- PSA diagnostic distinguishes timeout, TLS, connectivity, non-JSON HTTP response, authorization and successful structured response. A generic request failure never establishes approval. No token or raw exception is printed. No automatic retries. No PSA pricing integration.

## v0.9.3 — local demo capture repair

The Scan demo button now reads the chosen photo using an on-demand script in the exact local demo tab, with explicit progress and errors. It requires the scripting permission, limited to the existing loopback host permission. Reload the extension and confirm site access for 127.0.0.1 if requested. The shortcut remains Control+Shift+Y; try the button first. No external site capture is enabled.

## v0.9.4 — Brave tab selection fix
The shortcut uses its actual tab ID. The button uses the active tab in its window, falling back to the focused window only if no active tab is reported. Missing tab URL metadata no longer causes premature failure; the injected reader checks the exact loopback origin and demo path before reading the selected file. Query strings and hashes are accepted on that demo path. Known non-demo URLs are rejected before injection. No new browser permissions or live-site capture. If disconnected, the received image is retained and the UI prompts for the local token before scanning.

## 1.0.0 — Visual intelligence preview (local reference library)

This is an incremental upgrade of v0.9.4, not a replacement of the pricing engine. The stable main branch/tag should remain unchanged until tested. The existing `.env`, `.gitignore`, `data/`, `.venv/` and Git history are not included in the upgrade archive.

1. Scan a card normally; correct the player, year, product and checklist number if necessary.
2. Under **More scan tools → Compare a visual reference**, choose an authorized photo of a known card from the same family and enter its exact variant (e.g. Base or Silver Prizm).
3. Select **Save photo as verified local reference**, and confirm the family and variant. This stores a resized JPEG locally in the existing SQLite database. Only manually saved reference photos persist; ordinary query images are not stored by this library. The library is limited to 250 photos total and 24 per family. Delete a reference in the same drawer when no longer needed.
4. On later scans the price board loads as before. Local visual matching follows asynchronously; the top three distinct known references appear as visual suggestions. Click **View price** to select the corresponding board row if present. This does not select a bid or mark the variant verified. You can also trigger **Find matches in my library** manually.

The matching module attempts to isolate a portrait quadrilateral and straighten perspective when reasonably unambiguous, then compares ORB local features and spatial color histograms. This is an experimental heuristic, not a calibrated probability. It may crop a slab rather than its card, confuse nearly identical foils, or miss tilted or obscured cards. The original recognition input is unchanged; cropping is currently only used for reference comparison. No DINO model or PSA integration is included in this preview. No extra CompsAPI requests are used by reference matching. The user must verify the exact variant and grade before relying on a price.

The library starts empty; there is no automatic source of reference photographs. Only use photos you have permission to store. PSA's approval remains separate, as do live marketplace capture permissions. The existing keyboard capture remains limited to the local demo.

Testing: `python -m unittest discover -s tests -q` (64 tests), `node tests/test_capture_worker.cjs`, and `node --check extension/app.js`. Full browser testing on Brave and real-world accuracy benchmarks remain outstanding.

## v1.0.1 preview — optional marketplace reference photos

The price board is unchanged. After scanning a card and checking its player, year, product and checklist number, expand **Find visual matches online (optional)** in the price board and click **Find reference photos**. This is opt-in and asks you to confirm that you have permission to process the images. The backend calls the documented CompsAPI `/v1/active` endpoint once if the family metadata cache is older than 24 hours. The same 100-request monthly and 10-request/minute local caps apply. No automatic polling, no paid upgrade, and no additional API key are needed.

The service filters the returned listings by exact family and checklist number, skips unsupported specialty variants and junk titles, and compares up to ten candidate images (at most two per title-derived variant) locally using the existing OpenCV feature matcher. Only HTTPS images on the specific `i.ebayimg.com/images/` host/path are accepted; redirects are rejected, downloads are bounded, and the CompsAPI key is not sent to the image host. Only API listing metadata is cached in SQLite; external photo bytes are not persisted by this feature. The user remains responsible for third-party image rights. See https://compsapi.com/docs and https://compsapi.com/terms.

These are unverified seller-labeled reference suggestions, not authentication, exact variant probabilities or sold comps. The matching score is a heuristic and may be affected by glare, artwork shared by parallels, slabs and crop errors. **View price** selects an existing sold-price board variant; it never imports asking prices, confirms identity, changes profit rules or automatically bids. Unspecified variants cannot select a bid from this panel. If no suitable images are returned, use your own authorized reference library or manual comparison. PSA is optional and still requires approval.

Live marketplace capture remains disabled; the local demo shortcut and drag/drop are unchanged. The external photo lookup is optional and intended for research or resolving uncertainty, not a guaranteed sub-10-second auction operation.

Tests: `python -m unittest discover -s tests -q`, `node tests/test_capture_worker.cjs`, `node --check extension/app.js`. Provider and image download tests use mocks; real API and Brave behavior must be verified on your machine.

## v1.0.2 preview — optional DINOv2 and timed practice

Unzip over the existing project on `feature/visual-intelligence`. This update retains the pricing board, capture shortcut, cache, credentials and local references. No required dependencies change.

### Optional local visual embeddings

```sh
.venv/bin/python -m pip install -r requirements-visual.txt
.venv/bin/python setup_visual.py
```

The explicit setup downloads `facebook/dinov2-small` to `data/models/dinov2-small` (keep `data/` ignored by Git). Restart the server. The status shows **DINO installed** if model files are present. Local or online visual matching reports the actual engine used: **OpenCV + DINOv2** or **OpenCV** if unavailable. The optional engine uses Apple MPS when supported and otherwise CPU. It never downloads weights during a scan or sends card images to a model service. External listing photos remain opt-in and ephemeral. Hybrid ranking uses 75% existing OpenCV geometry/color and 25% nonnegative DINO cosine similarity, an experimental heuristic, not a probability or variant verification. DINO may favor identical artwork across different finishes. Prices and bid limits are unchanged and never automatically selected based on similarity.

### Timed practice

Open `http://127.0.0.1:8765/capture-demo.html` and choose several authorized card photos. Open the sidebar. Choose a 10, 15 or 20 second round; click Start practice. Press Control+Shift+Y (or your assigned shortcut) to scan the currently displayed image. The page advances automatically; scanning stays manual. Verify that the result corresponds to the displayed card, especially if a scan finishes after the round changes. Previous/Next work outside a timed session. Cached images are fast; use new images to measure actual recognition. Fresh sold searches use the normal API quota. No simulated or actual bids are placed.

Before practice, optionally preload the fast model with:

```sh
curl -sS http://127.0.0.1:11434/api/generate -H 'Content-Type: application/json' -d '{"model":"qwen3.5:4b","keep_alive":"15m"}'
ollama ps
```

No live marketplace capture is enabled. The local demo URL guard remains in place. The official Whatnot Seller API concerns seller-owned stores; obtain written permission before implementing buyer-side stream capture. PSA access is optional and still pending.

Tests: `python -m pytest -q tests`, `node tests/test_capture_worker.cjs`, `node tests/test_practice.cjs`. DINO integration tests use mocked vectors; model download, actual inference on Apple MPS, and Brave extension end-to-end practice require local testing.

## v1.1.0 preview — Player intelligence and hold research

The auction scan, visual matching, price board and manual capture workflow are unchanged. Open **Player intelligence & hold research** after scanning (or manually entering a player); confirm NBA, NFL or MLB and press **Load player stats**. This is an opt-in research action, not an automatic auction step. No additional CompsAPI requests are made.

- NBA: SportsDataverse/hoopR regular-season ESPN box score CSVs (season END year, e.g. 2027 for 2026–27). https://hoopr.sportsdataverse.org/reference/load_nba_player_box.html and https://github.com/sportsdataverse/hoopR-nba-data
- NFL: nflverse `stats_player` weekly regular-season CSVs (season START year). https://github.com/nflverse/nflverse-data/releases/tag/stats_player ; attribution to nflverse and upstream sources.
- MLB: MLB Stats API major-league season roster and regular-season hitting/pitching game logs. https://statsapi.mlb.com/api/v1 ; community documentation https://github.com/toddrob99/MLB-StatsAPI/wiki ; MLB data usage notice http://gdx.mlb.com/components/copyright.txt

No keys or additional packages required. First NBA/NFL lookup downloads a season CSV (bounded to 35 MB, timeout); files are kept beside the local database in `data/player_data/` by default and reused for 24 hours. Player summaries are cached in the existing SQLite cache for 24 hours; old cached data is explicitly flagged if a refresh fails. Only exact normalized names are matched; no fuzzy matching. Data may be delayed, current season files may be unavailable, and prospects, retired players and name collisions may need a different season or manual research. Check the displayed **Through** game date/week, not just the download time. Provider availability, terms and redistribution rights are not guaranteed; review them before commercial use.

Metrics compare recorded appearances: season average, newest five, and preceding five (minimum three). NFL rows are recorded player-weeks, not necessarily all games played. No injury, news, age, prospect ranking, or population feed is implemented yet. No missing stats are invented and no performance-to-price probability is inferred.

The optional hold calculator uses the chosen price board cell, requires a fresh non-unspecified cell with known shipping, and calculates maximum hypothetical entry bids under user-editable bear/flat/bull exit price changes and an annualized ROI target. Defaults are illustrative (-50%, 0%, +50% total price change over three years, 15% annual target), not forecasts. It includes existing selling fee, buyer tax estimate, outbound costs, purchase tax, inbound costs and minimum dollar profit. It does not include future inflation, taxes on earnings, storage or changing fees; it does not alter the flip bid or provide a hold recommendation. The board adds a recent vs older 90-day sample median trend only where sufficient shipping-known sales exist.

Tests: `python -m unittest discover -s tests` and `node tests/test_capture_worker.cjs && node tests/test_practice.cjs`. Live provider response schemas and the new Brave panel must be verified on the target Mac; the development sandbox has no network access to these providers. The existing local-only capture guard remains unchanged.

## v1.1.1 preview — Compact outlook and injury research

- The player drawer shows a compact recent-production summary and selected-card market trend. Expand Game statistics & sources for the original table and definitions.
- Production labels are descriptive heuristics using two non-overlapping five-appearance windows. They are not rankings, price predictions or probabilities. MLB game-log changes are shown without an overall direction because role and innings matter.
- Optional NFL injury research reads the nflverse season CSV (https://nflreadr.nflverse.com/reference/load_injuries.html). Shared season cache lasts six hours. Report week and dataset date are displayed; no matching report is not proof of health. No NBA/MLB automated injury inference; official report and prospect links open manually.
- Player news opens a manual news search, not a news scraping or sentiment system. No CompsAPI requests are consumed by player or injury research.
- PSA has discontinued its free API, per correspondence received by the project owner. No paid PSA integration is required or enabled.
- Hold scenarios remain hypothetical. Pricing and capture behavior remain unchanged.
