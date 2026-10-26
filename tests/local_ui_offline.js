// Run with playwright-cli run-code --filename tests/local_ui_offline.js after
// opening the UI from a clean checkout with no LTA key and no private captures.
async (page) => {
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  const errors = [];
  const liveRequests = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.route('**/api/plan', async route => {
    if (route.request().postDataJSON()?.mode === 'live') {
      liveRequests.push('plan');
      await route.abort();
    } else await route.continue();
  });
  await page.route('**/api/onward', async route => {
    if (route.request().postDataJSON()?.live) {
      liveRequests.push('onward');
      await route.abort();
    } else await route.continue();
  });
  await page.reload();
  const ready = () => page.waitForFunction(() => !document.getElementById('submit').disabled
    && document.querySelectorAll('.route-card').length > 0);
  await ready();
  check(await page.locator('#mode option[value="saved"]').evaluate(o => o.disabled), 'Private snapshot absent');
  check(await page.locator('#mode option[value="live"]').evaluate(o => o.disabled), 'No key in release smoke');
  check(await page.locator('.route-card').count() === 8, 'School families available');
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:'output/playwright/release-offline.png'});
  await page.locator('.network summary').click();
  await page.waitForFunction(() => document.querySelector('.network img').naturalWidth > 0);
  await page.locator('.network summary').click();
  await page.locator('#point').selectOption('8');
  await page.locator('#onward-model').click();
  await page.waitForFunction(() => document.querySelectorAll('.onward-row').length > 0
    && !document.getElementById('submit').disabled);
  check((await page.locator('#onward-results').innerText()).includes('继续坐 173'), 'Stay onboard available');
  await page.locator('input[value="no"]').check();
  await page.locator('#onward-model').click();
  await ready();
  check(!(await page.locator('#onward-results').innerText()).includes('继续坐 173'), 'No reboarding used service');
  await page.locator('#case').selectOption('home');
  await page.locator('#submit').click();
  await ready();
  check((await page.locator('#journey-title').innerText()).includes('Signature'), 'Home case works');
  check((await page.locator('#evidence').innerText()).includes('有界搜索'), 'Search limits visible');
  for (const width of [390,320]) {
    await page.locator('#tab-routes').click();
    await page.setViewportSize({width,height:844});
    check(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Overflow at '+width);
    await page.screenshot({path:`output/playwright/release-${width}.png`});
    await page.locator('.route-card').first().click();
    await ready();
    await page.screenshot({path:`output/playwright/release-detail-${width}.png`});
  }
  check(errors.length === 0, 'JS errors: '+errors.join(';'));
  check(liveRequests.length === 0, 'No live collection attempted');
  return {passed:true, viewports:[1440,390,320], errors, liveRequests};
}
