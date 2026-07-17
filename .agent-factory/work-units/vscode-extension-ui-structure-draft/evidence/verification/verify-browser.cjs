"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { chromium } = require("playwright");

const root = process.cwd();
const reportPath = path.join(root, "docs/design-documents/vscode-extension-ui-structure/report/index.html");
let checks = 0;

async function check(name, assertion) {
  await assertion();
  checks += 1;
  console.log(`PASS ${String(checks).padStart(2, "0")} ${name}`);
}

async function dragWithMouse(page, source, target) {
  await source.scrollIntoViewIfNeeded();
  const sourceBox = await source.boundingBox();
  const targetBox = await target.boundingBox();
  assert.ok(sourceBox && targetBox, "drag source and target must be visible");
  const sourcePoint = {
    x: sourceBox.x + sourceBox.width / 2,
    y: sourceBox.y + sourceBox.height / 2
  };
  const targetPoint = {
    x: targetBox.x + targetBox.width / 2,
    y: targetBox.y + Math.min(targetBox.height / 2, 24)
  };
  await page.mouse.move(sourcePoint.x, sourcePoint.y);
  await page.mouse.down();
  await page.mouse.move(sourcePoint.x + 8, sourcePoint.y + 8, { steps: 4 });
  await page.mouse.move(targetPoint.x, targetPoint.y, { steps: 16 });
  await page.waitForTimeout(100);
  await page.mouse.up();
}

(async () => {
  console.log("INFO launch system Chrome in headless mode");
  const browser = await chromium.launch({ channel: "chrome", headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.setDefaultTimeout(5000);
  page.setDefaultNavigationTimeout(10000);
  const runtimeErrors = [];
  page.on("pageerror", (error) => runtimeErrors.push(`pageerror: ${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error") runtimeErrors.push(`console.error: ${message.text()}`);
  });
  page.on("requestfailed", (request) => runtimeErrors.push(`requestfailed: ${request.url()}`));

  try {
    console.log(`INFO open ${pathToFileURL(reportPath).href}`);
    const reportUrl = pathToFileURL(reportPath).href;
    await page.goto(reportUrl, { waitUntil: "load" });

    await check("file URL에서 report와 local CSS/JavaScript 로드", async () => {
      await page.waitForSelector("main");
      assert.equal(page.url(), reportUrl);
      assert.equal(await page.title(), "VS Code 확장 UI 구조 · Design Report 초안");
      assert.ok((await page.locator("link[rel='stylesheet']").count()) === 1);
      assert.ok((await page.evaluate(() => document.styleSheets.length)) >= 1);
    });

    await check("manifest의 모든 source projection과 두 diagram을 DOM으로 생성", async () => {
      const projection = await page.evaluate(() => {
        const data = globalThis.__VSCODE_EXTENSION_UI_STRUCTURE_REPORT_DATA__;
        return {
          expected: Object.keys(data.projectionCoverage).sort(),
          rendered: [...new Set(
            [...document.querySelectorAll("[data-projection]")]
              .map((element) => element.dataset.projection)
              .filter(Boolean)
          )].sort(),
          sourceDiagramIds: data.diagrams.map((diagram) => diagram.id),
          renderedDiagramIds: [...document.querySelectorAll("[data-diagram-id]")]
            .map((element) => element.dataset.diagramId),
          details: [...document.querySelectorAll("details.design-detail")]
            .map((element) => element.textContent.trim().length)
        };
      });
      assert.deepEqual(projection.rendered, projection.expected);
      assert.deepEqual(projection.renderedDiagramIds, projection.sourceDiagramIds);
      assert.equal(projection.details.length, 8);
      assert.ok(projection.details.every((length) => length > 0));
    });

    await check("탭 이름이 정확한 네 개", async () => {
      assert.deepEqual(await page.locator("[role='tab']").allTextContents(), ["Dashboard", "Intake", "Design", "WorkUnit"]);
    });

    await check("각 활성 탭의 TabHeader와 Body가 한 쌍으로 함께 전환", async () => {
      for (const tabId of ["dashboard", "intake", "design", "workunit"]) {
        await page.locator(`[role='tab'][data-tab='${tabId}']`).click();
        const visible = await page.evaluate(() => ({
          headers: [...document.querySelectorAll("[data-tab-header]")].filter((element) => !element.hidden).map((element) => element.dataset.tabHeader),
          bodies: [...document.querySelectorAll("[data-tab-body]")].filter((element) => !element.hidden).map((element) => element.dataset.tabBody)
        }));
        assert.deepEqual(visible, { headers: [tabId], bodies: [tabId] });
      }
    });

    await check("검토 도구가 명시적으로 선택한 단계만 표시", async () => {
      const wanted = new Set(["ready", "working"]);
      for (const input of await page.locator("#stage-visibility-review input").all()) {
        const value = await input.getAttribute("value");
        if (wanted.has(value)) await input.check();
        else await input.uncheck();
      }
      assert.deepEqual(
        await page.locator(".kanban-stage:not([hidden])").evaluateAll((elements) => elements.map((element) => element.dataset.stage)),
        ["ready", "working"]
      );
    });

    await check("Done 미선택 시 Done 단계가 숨겨짐", async () => {
      assert.equal(await page.locator(".kanban-stage[data-stage='done']").isHidden(), true);
    });

    await check("정상 칸반은 정확한 5단계와 순서", async () => {
      for (const input of await page.locator("#stage-visibility-review input").all()) await input.check();
      assert.deepEqual(
        await page.locator(".kanban-stage").evaluateAll((elements) => elements.map((element) => element.dataset.stage)),
        ["backlog", "ready", "working", "review", "done"]
      );
    });

    await check("카드의 보이는 내용은 title뿐이고 report에서 fixed height를 계산", async () => {
      const card = page.locator(".work-unit-card");
      assert.equal((await card.innerText()).trim(), "VS Code 확장 UI 구조 초안 작성");
      const style = await card.evaluate(async (element) => {
        const clones = [element.cloneNode(true), element.cloneNode(true)];
        clones.forEach((clone) => element.parentElement.append(clone));
        window.dispatchEvent(new Event("resize"));
        await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        const cardElements = [...element.parentElement.querySelectorAll(".work-unit-card")];
        const result = {
          childElementCount: element.childElementCount,
          blockSize: getComputedStyle(element).blockSize,
          equalHeightCount: new Set(cardElements.map((item) => getComputedStyle(item).blockSize)).size,
          exactSourceValueExposed: element.hasAttribute("data-height")
        };
        clones.forEach((clone) => clone.remove());
        window.dispatchEvent(new Event("resize"));
        return result;
      });
      assert.deepEqual(style.childElementCount, 0);
      assert.ok(Number.parseFloat(style.blockSize) > 0);
      assert.equal(style.equalHeightCount, 1);
      assert.equal(style.exactSourceValueExposed, false);
    });

    const card = page.locator(".work-unit-card");

    await check("허용된 Ready→Working drop 뒤 카드 위치와 status가 함께 변경", async () => {
      await dragWithMouse(page, card, page.locator("[data-drop-stage='working']"));
      assert.equal(await card.getAttribute("data-status"), "working");
      assert.equal(await card.locator("xpath=parent::*").getAttribute("data-drop-stage"), "working");
    });

    await check("허용되지 않은 Working→Done drop은 위치와 status를 변경하지 않음", async () => {
      await dragWithMouse(page, card, page.locator("[data-drop-stage='done']"));
      assert.equal(await card.getAttribute("data-status"), "working");
      assert.equal(await card.locator("xpath=parent::*").getAttribute("data-drop-stage"), "working");
    });

    await check("허용된 Working→Review drop 뒤 카드 위치와 status가 함께 변경", async () => {
      await dragWithMouse(page, card, page.locator("[data-drop-stage='review']"));
      assert.equal(await card.getAttribute("data-status"), "review");
      assert.equal(await card.locator("xpath=parent::*").getAttribute("data-drop-stage"), "review");
    });

    await check("Review→Done drop만으로 Human 승인을 우회하지 않음", async () => {
      await dragWithMouse(page, card, page.locator("[data-drop-stage='done']"));
      assert.equal(await card.getAttribute("data-status"), "review");
      assert.equal(await card.locator("xpath=parent::*").getAttribute("data-drop-stage"), "review");
      assert.equal(await page.locator("[data-human-approval='granted']").count(), 0);
    });

    await check("단계별 세로 스크롤 동작과 숨김 스크롤바를 실제 CSSOM에서 확인", async () => {
      const scrollResult = await page.locator("[data-drop-stage='backlog']").evaluate((element) => {
        element.style.blockSize = "3rem";
        for (let index = 0; index < 20; index += 1) {
          const fixture = document.createElement("div");
          fixture.textContent = `test overflow ${index}`;
          fixture.dataset.testFixture = "scroll";
          element.append(fixture);
        }
        element.scrollTop = element.scrollHeight;
        const computed = getComputedStyle(element);
        const pseudo = getComputedStyle(element, "::-webkit-scrollbar");
        return {
          overflowY: computed.overflowY,
          scrollbarWidth: computed.scrollbarWidth,
          pseudoWidth: pseudo.width,
          scrollTop: element.scrollTop,
          canScroll: element.scrollHeight > element.clientHeight
        };
      });
      assert.equal(scrollResult.overflowY, "auto");
      assert.equal(scrollResult.scrollbarWidth, "none");
      assert.equal(scrollResult.pseudoWidth, "0px");
      assert.equal(scrollResult.canScroll, true);
      assert.ok(scrollResult.scrollTop > 0);
    });

    await check("Blocked는 정상 칸반 열이 아닌 별도 예외 설명", async () => {
      assert.equal(await page.locator(".kanban-stage[data-stage='blocked']").count(), 0);
      assert.match(await page.locator(".kanban-notes").innerText(), /Blocked.*예외 상태/s);
    });

    await check("검토용 표현과 미정 제품 결정이 명시적으로 분리", async () => {
      assert.match(await page.locator("#stage-visibility-review").innerText(), /비규범적 도구/);
      assert.match(await page.locator("section[aria-labelledby='unresolved-title']").innerText(), /카드 높이의 정확한 값/);
    });

    await check("브라우저 console과 page runtime 오류 없음", async () => {
      assert.deepEqual(runtimeErrors, []);
    });

    console.log(`RESULT PASS ${checks} browser checks`);
  } finally {
    await browser.close();
  }
})().catch((error) => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
