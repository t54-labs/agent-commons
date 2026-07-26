import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";


const requireFromWeb = createRequire(new URL("../web/package.json", import.meta.url));
const { chromium } = requireFromWeb("@playwright/test");
const currentDirectory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(currentDirectory, "..");
const source = path.join(root, "docs/assets/commons-social-preview.html");
const output = path.join(root, "docs/assets/commons-social-preview.png");

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 640 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(source).href);
  await page.waitForLoadState("load");
  await page.screenshot({ path: output, type: "png" });
  process.stdout.write(`${output}\n`);
} finally {
  await browser.close();
}
