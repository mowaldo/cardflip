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
