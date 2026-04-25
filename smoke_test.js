// Headless smoke test for event_ranker.html
const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const HTML_URL = "file://" + path.resolve(__dirname, "event_ranker.html");
const JSON_PATH = path.resolve(__dirname, "events_april.json");

function assert(cond, msg) {
  if (!cond) { console.error("FAIL:", msg); process.exit(1); }
  console.log("ok:", msg);
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  page.on("pageerror", err => { console.error("pageerror:", err); process.exit(1); });
  page.on("console", msg => {
    if (msg.type() === "error") console.error("console.error:", msg.text());
  });

  await page.goto(HTML_URL);
  await page.waitForFunction(() => !!window.__ranker);

  // Inject JSON without an actual file dialog.
  const json = fs.readFileSync(JSON_PATH, "utf8");
  await page.evaluate(jsonText => {
    const r = window.__ranker;
    const fakeFile = { /* unused */ };
    // Bypass FileReader by directly running the parse path:
    const data = JSON.parse(jsonText);
    r.state.data = data;
    r.state.fileError = "";
    r.state.allResults = [];
    r.state.rankedWeekendIndices = new Set();
    r.goto("weekendSelect");
  }, json);

  // Confirm weekendSelect rendered the right month + cards.
  const monthTitle = await page.textContent("h1");
  assert(/April/i.test(monthTitle), "month title contains 'April'");
  const cardCount = await page.$$eval(".weekend-card", els => els.length);
  assert(cardCount === 4, "renders 4 weekend cards");

  // Click first weekend.
  await page.click(".weekend-card");
  await page.waitForSelector(".ranking-list .event-card");
  const initialOrder = await page.$$eval(".ranking-list .event-card", cards =>
    cards.map(c => c.querySelector(".event-title").textContent)
  );
  assert(initialOrder.length > 0, "ranking list has events");

  // Confirm initial order is chronological (Friday before Sunday).
  const days = await page.$$eval(".ranking-list .day-pill", pills => pills.map(p => p.textContent));
  let lastIdx = -1;
  let chronologicalOk = true;
  const order = { Friday: 0, Saturday: 1, Sunday: 2 };
  for (const d of days) {
    const idx = order[d];
    if (idx == null) continue;
    if (idx < lastIdx) { chronologicalOk = false; break; }
    lastIdx = idx;
  }
  assert(chronologicalOk, "initial order is Fri → Sat → Sun");

  // Programmatically reorder via state, re-render, confirm rank labels updated.
  await page.evaluate(() => {
    const r = window.__ranker;
    // Move last to first.
    const arr = r.state.rankedEvents;
    const moved = arr.splice(arr.length - 1, 1)[0];
    arr.unshift(moved);
    r.render();
  });
  const firstTitleAfter = await page.textContent(".ranking-list .event-card:first-child .event-title");
  const lastInOriginal = initialOrder[initialOrder.length - 1];
  assert(firstTitleAfter === lastInOriginal, "reorder moved last event to first");

  // Click 'Done ranking' → tiering.
  await page.click(".sticky-actions .btn.primary");
  await page.waitForSelector(".dropdowns");

  // Set Must=3, Want=6, Can=10.
  await page.selectOption(".dropdown-cell.must-go select", "3");
  await page.selectOption(".dropdown-cell.want-to-go select", "6");
  await page.selectOption(".dropdown-cell.can-go select", "10");

  const tierBadges = await page.$$eval(".event-card .tier-badge", els => els.map(e => e.textContent));
  assert(tierBadges.slice(0, 3).every(t => t === "Must Go"), "ranks 1-3 are Must Go");
  assert(tierBadges.slice(3, 6).every(t => t === "Want to Go"), "ranks 4-6 are Want to Go");
  assert(tierBadges.slice(6, 10).every(t => t === "Can Go"), "ranks 7-10 are Can Go");
  assert(tierBadges.slice(10).every(t => t === "Cut"), "ranks 11+ are Cut");

  // Cascading reset: change Must to 8, Want should clear because 6 < 8.
  await page.selectOption(".dropdown-cell.must-go select", "8");
  const wantValue = await page.$eval(".dropdown-cell.want-to-go select", el => el.value);
  assert(wantValue === "", "lower cutoff resets when upper cutoff swallows it");

  // Reset and finalize for CSV.
  await page.selectOption(".dropdown-cell.must-go select", "3");
  await page.selectOption(".dropdown-cell.want-to-go select", "6");
  await page.selectOption(".dropdown-cell.can-go select", "10");

  await page.click(".sticky-actions .btn.primary");
  await page.waitForSelector(".tier-section.must-go");

  // CSV content via buildCsvRows hook.
  const csvText = await page.evaluate(() => window.__ranker.buildCsvRows(window.__ranker.state.allResults));
  const lines = csvText.split("\r\n");
  assert(lines[0] === "month,weekend_dates,rank,event_name,day,venue,tier,date_ranked", "csv header matches spec");
  assert(lines.length > 1, "csv has data rows");
  const cols = lines[1].split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/);
  assert(cols.length === 8, "csv row has 8 columns");

  // Multi-weekend accumulation: rank weekend 2 too.
  await page.click("text=Rank another weekend");
  await page.click(".weekend-grid .weekend-card:nth-child(2)");
  await page.waitForSelector(".ranking-list .event-card");
  await page.click(".sticky-actions .btn.primary");
  await page.selectOption(".dropdown-cell.must-go select", "2");
  await page.click(".sticky-actions .btn.primary");
  await page.waitForSelector(".tier-section.must-go");

  const resultsCount = await page.evaluate(() => window.__ranker.state.allResults.length);
  assert(resultsCount === 2, "session accumulates results across weekends");

  const csv2 = await page.evaluate(() => window.__ranker.buildCsvRows(window.__ranker.state.allResults));
  assert(csv2.split("\r\n").length > lines.length, "csv grew when second weekend was added");

  await browser.close();
  console.log("\nALL SMOKE TESTS PASSED");
})().catch(err => { console.error(err); process.exit(1); });
