import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://erp.91miaoshou.com/?redirect=%2Fcommon_collect_box%2Fitems%3FtabPaneName%3Dall")
    page.get_by_role("textbox", name="手机号/子账号/邮箱").click()
    page.get_by_role("textbox", name="手机号/子账号/邮箱").click()
    page.get_by_role("textbox", name="手机号/子账号/邮箱").fill("lyl12345678")
    page.get_by_role("textbox", name="密码").click()
    page.get_by_role("textbox", name="密码").fill("Lyl12345678.")
    page.get_by_role("button", name="立即登录").click()
    page.get_by_role("dialog").filter(has_text="【线上直播】11月11日—11月13日线上直播预告2025").get_by_label("关闭此对话框").click()
    page.get_by_role("button", name="关闭此对话框").click()
    page.get_by_role("link", name="公用采集箱").click()
    page.get_by_role("button", name="我知道了").click()
    page.locator("#appScrollContainer div").filter(has_text="产品信息 任务 货源平台货源价格 库存/重量(KG） 创建者/创建时间/备注认领平台操作暂无数据 全选 反选 0条 1 前往页20条/页").locator("label span").nth(1).click()
    page.locator(".jx-checkbox").first.click()
    page.locator(".is-fixed-left.is-selection-column.pro-virtual-table__row-cell > .jx-checkbox > .jx-checkbox__input > .jx-checkbox__inner").first.click()
    page.locator(".vue-recycle-scroller__item-view.hover > .pro-virtual-scroll__row > .pro-virtual-table__row-body > .is-fixed-left.is-selection-column > .jx-checkbox > .jx-checkbox__input > .jx-checkbox__inner").click()
    page.locator(".vue-recycle-scroller__item-view.hover > .pro-virtual-scroll__row > .pro-virtual-table__row-body > .is-fixed-left.is-selection-column > .jx-checkbox").click()
    page.locator(".vue-recycle-scroller__item-view.hover > .pro-virtual-scroll__row > .pro-virtual-table__row-body > .is-fixed-left.is-selection-column > .jx-checkbox").click()
    page.locator(".vue-recycle-scroller__item-view.hover > .pro-virtual-scroll__row > .pro-virtual-table__row-body > .is-fixed-left.is-selection-column > .jx-checkbox > .jx-checkbox__input > .jx-checkbox__inner").click()
    page.locator(".jx-checkbox__input.is-focus > .jx-checkbox__inner").click()
    page.locator(".vue-recycle-scroller__item-view.hover > .pro-virtual-scroll__row > .pro-virtual-table__row-body > .is-fixed-left.is-selection-column > .jx-checkbox > .jx-checkbox__input > .jx-checkbox__inner").click()
    page.get_by_role("menu", name="认领到").locator("span").nth(1).click()
    page.get_by_role("button", name="确定").click()
    page.get_by_role("button", name="关闭", exact=True).click()
    page.get_by_role("button", name="确定").click()
    page.get_by_role("button", name="关闭", exact=True).click()
    page.locator("#jx-id-1909-139").click()
    page.get_by_role("button", name="确定").click()
    page.get_by_role("button", name="关闭", exact=True).click()
    page.get_by_role("button", name="确定").click()
    page.get_by_role("button", name="关闭", exact=True).click()
    page.get_by_role("menuitem", name="Temu全托管").click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
