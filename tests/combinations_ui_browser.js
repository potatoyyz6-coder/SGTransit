// Run through playwright-cli against the key-free daytime fixture server.
async (page) => {
  const check=(ok,message)=>{if(!ok)throw new Error(message);};
  const errors=[], requests=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.url().includes('/api/'))requests.push(r.postDataJSON());});
  const ready=()=>page.waitForFunction(()=>!document.getElementById('submit').disabled);
  await page.reload(); await ready();
  await page.setViewportSize({width:1440,height:1000});
  check(await page.locator('#tab-combinations').getAttribute('aria-selected')==='true','Default combination view');
  check(await page.locator('#individual-panel').isHidden(),'Original list retained behind tab');
  await page.locator('#case').selectOption('home');
  await page.locator('#submit').click(); await ready();
  for(let i=0;i<10;i++) {
    if((await page.locator('.graph-section').allTextContents()).some(t=>t.startsWith('Blk 109')))break;
    await page.getByRole('button',{name:'选择 151-D2 分支',exact:true}).click(); await ready();
  }
  check((await page.locator('#combination-panel').innerText()).includes('Blk 109 · 可选公交'),'Automatically found Blk 109');
  check(await page.getByRole('button',{name:'选择 61-D2 分支',exact:true}).count()===1,'61 available from original candidates');
  check(await page.locator('.rejoin').count()>0,'Common physical suffix shown');
  await page.locator('[data-inspect-service]').first().click(); await ready();
  check(await page.locator('#clear-inspection').isVisible(),'Shared service links to original routes');
  await page.locator('#clear-inspection').click(); await ready();
  await page.locator('#combination-originals summary').click();
  await page.locator('[data-expand]').first().click(); await ready();
  check((await page.locator('.expanded-stops').innerText()).includes('12061'),'Original intermediate stops accessible');
  await page.locator('[data-expand]').first().click(); await ready();
  await page.locator('#combination-originals summary').click();
  const firstId=await page.locator('[data-combination-route]').first().getAttribute('data-combination-route');
  check(Boolean(firstId),'Original ID available');
  await page.locator('[data-page-kind="route_page"][data-page="1"]').click(); await ready();
  check(await page.locator('[data-combination-route]').first().getAttribute('data-combination-route')!==firstId,'Original route paging advances');
  await page.locator('[data-page-kind="route_page"][data-page="0"]').click(); await ready();
  check(await page.locator('[data-combination-route]').first().getAttribute('data-combination-route')===firstId,'Original route paging returns without loss');
  await page.locator('[data-combination-route]').first().click(); await ready();
  check((await page.locator('#detail').innerText()).includes('所选方案'),'Original detail opened');
  await page.locator('#combination-originals summary').click();
  await page.locator('#workspace').screenshot({path:'docs/images/route-combinations.png'});
  for(const width of [390,320]) {
    await page.setViewportSize({width,height:844});
    check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Overflow '+width);
    await page.locator('#workspace').scrollIntoViewIfNeeded();
    await page.screenshot({path:`output/playwright/combinations-${width}.png`,fullPage:true});
    await page.locator('#tab-routes').click();
    await page.locator('.route-card').first().click(); await ready();
    await page.locator('#tab-combinations').click();
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.getByRole('button',{name:'选择 61-D2 分支',exact:true}).click(); await ready();
  check((await page.getByRole('button',{name:'选择 61-D2 分支',exact:true}).innerText()).includes('继续坐'),'61 arrival retains onboard state');
  await page.getByRole('button',{name:'选择 61-D2 分支',exact:true}).click(); await ready();
  check(await page.locator('[data-combination-route]').count()===1,'Selected exact original route');
  await page.locator('[data-combination-route]').click(); await ready();
  const point=await page.locator('#point option').evaluateAll(options=>options.find(o=>o.textContent.trim().endsWith('· 61'))?.value);
  await page.locator('#point').selectOption(point);
  await page.locator('#onward-model').click(); await ready();
  check((await page.locator('#onward-results').innerText()).includes('继续坐 61'),'Original onward continuation works');
  await page.locator('#combination-back').click(); await ready();
  check(await page.locator('[data-branch]').count()>1,'Undo restores compatible alternatives');
  await page.locator('#custom').check(); await ready();
  await page.locator('#departure').fill('2026-10-23T10:00');
  await page.locator('#submit').click(); await ready();
  const groups=await page.locator('#combination-endpoints option').count();
  check(groups>1,'Custom endpoint groups preserved');
  await page.locator('#combination-endpoints').selectOption('1'); await ready();
  await page.locator('#combination-originals summary').click();
  check((await page.locator('#combination-originals').innerText()).includes('接驳 未知'),'Unknown access stays unknown');
  check(errors.length===0,'JS errors '+errors.join(';'));
  check(requests.filter(Boolean).every(r=>r.mode!=='live'&&!r.live),'No live API calls');
  return {passed:true,viewports:[1440,390,320],errors,customGroups:groups};
}
