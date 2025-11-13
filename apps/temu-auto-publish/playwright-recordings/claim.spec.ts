import { test, expect } from '@playwright/test';

test.use({
  colorScheme: 'light',
  locale: 'zh-CN',
  viewport: {
    height: 720,
    width: 1280
  }
});

test('test', async ({ page }) => {
  await page.goto('https://erp.91miaoshou.com/?redirect=%2Fcommon_collect_box%2Fitems%3FtabPaneName%3Dall');
  await page.getByRole('textbox', { name: '手机号/子账号/邮箱' }).click();
  await page.getByRole('textbox', { name: '手机号/子账号/邮箱' }).fill('lyl12345678');
  await page.getByRole('textbox', { name: '密码' }).click();
  await page.getByRole('textbox', { name: '密码' }).fill('Lyl12345678.');
  await page.getByRole('button', { name: '立即登录' }).click();
  await page.goto('https://erp.91miaoshou.com/common_collect_box/items?tabPaneName=all');
  await page.getByRole('button', { name: '我知道了' }).click();
  await page.locator('.list-goods-item-side').first().click();
  await page.getByLabel('认领到').getByRole('menuitem', { name: 'Temu全托管' }).press('ControlOrMeta+ControlOrMeta+CapsLock');
  await page.getByLabel('认领到').getByRole('menuitem', { name: 'Temu全托管' }).click();
  await page.locator('#jx-id-5526-80').hover();
  await page.locator('span').filter({ hasText: 'Temu全托管' }).click();
  await page.getByRole('button', { name: '确定' }).click();
  await page.goto('https://erp.91miaoshou.com/common_collect_box/items?tabPaneName=all');
  await page.locator('#jx-id-1917-80').hover();
  await page.locator('span').filter({ hasText: 'Temu全托管' }).click();
  await page.getByRole('button', { name: '确定' }).click();
  await page.getByRole('button', { name: '确定' }).click();
  await page.getByText('认领到 平台认领配置 分组 删除 更多').click();
  await page.getByRole('button', { name: '确定' }).click();
  await page.locator('.jx-checkbox').first().click();
  await page.locator('#jx-id-1917-80').click();
  await page.getByRole('button', { name: '确定' }).click();
  await page.locator('#jx-id-1917-80').press('Escape');
  await page.getByRole('dialog', { name: '批量认领' }).click();
  await page.locator('body').press('Escape');
  await page.locator('.is-fixed-left.is-selection-column.pro-virtual-table__row-cell > .jx-checkbox > .jx-checkbox__input > .jx-checkbox__inner').first().click();
  await page.locator('.vue-recycle-scroller__item-view.hover > .pro-virtual-scroll__row > .pro-virtual-table__row-body > .is-fixed-left.is-selection-column > .jx-checkbox').click();
  await page.locator('#jx-id-4599-80').click();
  await page.locator('span').filter({ hasText: 'Temu全托管' }).click();
  await page.getByRole('button', { name: '确定' }).click();
  await page.getByRole('button', { name: '关闭', exact: true }).click();
  await page.locator('#jx-id-4599-80').click();
  await page.getByRole('button', { name: '确定' }).click();
  await page.getByRole('button', { name: '关闭', exact: true }).click();
});