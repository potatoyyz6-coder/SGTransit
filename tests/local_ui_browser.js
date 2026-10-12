// Optional historical smoke test: needs the private Oct 8 snapshot and a live-mode
// enabled UI. All live POSTs are intercepted below. For a public no-key checkout,
// use tests/local_ui_offline.js instead.
async (page) => {
  const check = (ok, message) => { if (!ok) throw new Error(message); };
  const consoleErrors = [];
  page.on('pageerror', e => consoleErrors.push(e.message));
  let livePosts = 0;
  await page.route('**/api/plan', async route => {
    if (route.request().postDataJSON()?.mode === 'live') {
      livePosts++;
      await route.fulfill({status:503, contentType:'application/json', body:JSON.stringify({error:'测试响应：本次没有调用 LTA'})});
    } else await route.continue();
  });
  await page.route('**/api/onward', async route => {
    if (route.request().postDataJSON()?.live) {
      livePosts++;
      await route.fulfill({status:503, contentType:'application/json', body:JSON.stringify({error:'测试响应：本次没有调用 LTA'})});
    } else await route.continue();
  });
  await page.reload();
  await page.waitForFunction(() => document.querySelectorAll('.route-card').length===8 && !document.getElementById('submit').disabled);
  check(await page.locator('#mode option').count()===3,'All source modes must exist');
  check(await page.locator('.metrics > .metric').count()===4,'Four metric cells');
  check(await page.locator('.metrics > .timeline').count()===0,'Timeline must not be nested in metrics');
  await page.setViewportSize({width:1440,height:1000});
  await page.screenshot({path:'output/playwright/desktop.png'});
  await page.locator('#mode').selectOption('saved');
  await page.locator('#submit').click();
  await page.waitForFunction(() => document.getElementById('evidence').textContent.includes('2026/10/8') && !document.getElementById('submit').disabled);
  check((await page.locator('#detail h2').innerText()).includes('40.3'),'Saved result must match audited result');
  check(await page.locator('#onward-live').isDisabled(),'Historical continuation cannot refresh today');
  await page.locator('#point').selectOption('8');
  await page.locator('#onward-model').click();
  await page.waitForFunction(() => document.querySelectorAll('.onward-row').length>0 && !document.getElementById('submit').disabled);
  check((await page.locator('#onward-results').innerText()).includes('继续坐 173'),'Must offer continuing onboard');
  check((await page.locator('#onward-results').innerText()).includes('换乘 183'),'Must offer transfer alternatives');
  check(await page.locator('[data-adopt]').count()>0,'Onward routes can become the selected itinerary');
  await page.locator('input[value="no"]').check();
  await page.locator('#onward-model').click();
  await page.waitForFunction(() => !document.getElementById('submit').disabled);
  check(!(await page.locator('#onward-results').innerText()).includes('继续坐 173'),'Alighted state cannot reboard used service');
  await page.locator('[data-adopt]').first().click();
  await page.waitForFunction(() => document.getElementById('onward-status').textContent.includes('后续路线已更新') && !document.getElementById('submit').disabled);
  check((await page.locator('#point').innerText()).includes('Blk 365'),'Adopted itinerary exposes its subsequent stops');
  await page.locator('input[value="yes"]').check();
  await page.locator('#sort').selectOption('wait');
  await page.locator('.route-card').nth(1).click();
  await page.waitForFunction(() => !document.getElementById('submit').disabled);
  if(await page.locator('#variant option').count()>1) {
    const value=await page.locator('#variant option').nth(1).getAttribute('value');
    await page.locator('#variant').selectOption(value);
    await page.waitForFunction(() => !document.getElementById('submit').disabled);
    check(await page.locator('#variant').inputValue()===value,'Variant change must persist');
  }
  await page.locator('.network summary').click();
  await page.waitForFunction(() => document.querySelector('.network img').naturalWidth>0);
  await page.locator('.network summary').click();
  const download=page.waitForEvent('download');
  await page.locator('#export').click();
  check((await download).suggestedFilename().includes('reference.json'),'Export result');
  await page.locator('#case').selectOption('home');
  check(await page.locator('#mode').inputValue()==='model','Home has no private saved snapshot');
  await page.locator('#submit').click();
  await page.waitForFunction(() => document.getElementById('journey-title').textContent.includes('Signature') && !document.getElementById('submit').disabled);
  check((await page.locator('#evidence').innerText()).includes('有界搜索'),'Home bound is visible');
  await page.locator('#mode').selectOption('live');
  await page.locator('#submit').click();
  check((await page.locator('#consent-text').innerText()).includes('47'),'Consent matches case request scope');
  await page.getByRole('button',{name:'取消',exact:true}).click();
  check(livePosts===0,'Cancel must not request live collection');
  await page.locator('#submit').click();
  await page.getByRole('button',{name:'确认查询',exact:true}).click();
  await page.waitForFunction(() => !document.getElementById('error').hidden);
  check((await page.locator('#error').innerText()).includes('测试响应'),'Show API failure without destroying past reference');
  check(livePosts===1,'Exactly one intercepted request, no retries');
  await page.locator('#submit').click();
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.getElementById('consent').open);
  check(livePosts===1,'Escape after an earlier confirmation must not reuse consent');
  await page.locator('#mode').selectOption('model');
  await page.locator('#case').selectOption('school');
  await page.locator('#mode').selectOption('saved');
  await page.locator('#submit').click();
  await page.waitForFunction(() => document.getElementById('evidence').textContent.includes('2026/10/8') && !document.getElementById('submit').disabled);
  await page.locator('#sort').selectOption('time');
  for(const width of [390,320]) {
    await page.setViewportSize({width,height:844});
    await page.evaluate(() => window.scrollTo(0,0));
    const sizes=await page.evaluate(() => ({w:innerWidth,scroll:document.documentElement.scrollWidth}));
    check(sizes.scroll<=sizes.w,'No horizontal overflow at '+width);
    await page.screenshot({path:`output/playwright/mobile-${width}.png`});
    await page.locator('.route-card').first().click();
    await page.waitForFunction(() => !document.getElementById('submit').disabled);
    await page.screenshot({path:`output/playwright/mobile-detail-${width}.png`});
    await page.getByRole('button',{name:'返回候选方案',exact:true}).click();
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.evaluate(() => window.scrollTo(0,0));
  await page.screenshot({path:'output/playwright/desktop-saved.png'});
  check(consoleErrors.length===0,'No browser JS errors: '+consoleErrors.join(';'));
  return {passed:true,viewports:[1440,390,320],liveRequestsIntercepted:livePosts,realLtaCalls:0,consoleErrors};
}
