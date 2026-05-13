// Headless smoke test for the persistence layer.
// Loads event_ranker.html, simulates a saved file, reloads, confirms it's
// still in the library, opens it, then removes it.
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

  await page.goto(HTML_URL);
  await page.waitForFunction(() => !!window.__ranker);

  // Initially empty.
  let savedCount = await page.evaluate(() => window.__ranker.state.savedFiles.length);
  assert(savedCount === 0, "starts with no saved files");

  // Simulate an upload.
  const json = fs.readFileSync(JSON_PATH, "utf8");
  await page.evaluate(jsonText => {
    const data = JSON.parse(jsonText);
    window.__ranker.saveFile("NYC_Events_April.docx", data);
    window.__ranker.render();
  }, json);

  let rowCount = await page.$$eval(".saved-file-row", els => els.length);
  assert(rowCount === 1, "saved file shows up as a row");

  let storage = await page.evaluate(() => localStorage.getItem("nyc_event_ranker_v1"));
  assert(storage && storage.length > 0, "localStorage entry written");
  const parsedStorage = JSON.parse(storage);
  assert(parsedStorage.files[0].filename === "NYC_Events_April.docx", "stored filename is correct");

  // Reload and confirm persistence survived.
  await page.reload();
  await page.waitForFunction(() => !!window.__ranker);
  rowCount = await page.$$eval(".saved-file-row", els => els.length);
  assert(rowCount === 1, "saved file persists across reload");

  // Click the open button.
  await page.click(".saved-file-open");
  await page.waitForSelector(".weekend-card");
  const cards = await page.$$eval(".weekend-card", els => els.length);
  assert(cards === 4, "opening a saved file lands on weekend-select with 4 weekends");

  // Go back to file-load via the "Load different file" button.
  await page.click("text=Load different file");
  await page.waitForSelector(".saved-file-row");

  // Re-upload the same filename and confirm it dedups (still one row).
  await page.evaluate(jsonText => {
    const data = JSON.parse(jsonText);
    window.__ranker.saveFile("NYC_Events_April.docx", data);
    window.__ranker.render();
  }, json);
  rowCount = await page.$$eval(".saved-file-row", els => els.length);
  assert(rowCount === 1, "re-uploading same filename does not duplicate");

  // Add a second filename.
  await page.evaluate(jsonText => {
    const data = JSON.parse(jsonText);
    data.month = "May 2025";
    window.__ranker.saveFile("NYC_Events_May.docx", data);
    window.__ranker.render();
  }, json);
  rowCount = await page.$$eval(".saved-file-row", els => els.length);
  assert(rowCount === 2, "different filename adds a new row");

  // Remove the first entry via the API (skipping confirm dialog).
  await page.evaluate(() => {
    const firstId = window.__ranker.state.savedFiles[0].id;
    window.__ranker.removeSavedFile(firstId);
    window.__ranker.render();
  });
  rowCount = await page.$$eval(".saved-file-row", els => els.length);
  assert(rowCount === 1, "removeSavedFile drops the entry");

  // Reload again and confirm the surviving entry stuck.
  await page.reload();
  await page.waitForFunction(() => !!window.__ranker);
  rowCount = await page.$$eval(".saved-file-row", els => els.length);
  assert(rowCount === 1, "removal persists across reload");

  await browser.close();
  console.log("\nALL PERSISTENCE TESTS PASSED");
})().catch(err => { console.error(err); process.exit(1); });
