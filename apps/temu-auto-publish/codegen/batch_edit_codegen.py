import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://erp.91miaoshou.com/?redirect=%2Fsub_account%2Fusers")
    page.get_by_role("textbox", name="手机号/子账号/邮箱").click()
    page.get_by_role("textbox", name="手机号/子账号/邮箱").fill("lyl12345678")
    page.get_by_role("textbox", name="密码").click()
    page.get_by_role("textbox", name="密码").fill("Lyl12345678.")
    page.get_by_role("button", name="立即登录").click()
    page.get_by_role("button", name="关闭此对话框").click()
    page.get_by_role("link", name="公用采集箱").click()
    page.get_by_role("menuitem", name="Temu全托管").click()
    page.locator(".jx-checkbox").first.click()
    page.get_by_text("外包装").click()
    page.get_by_role("dialog").locator("form div").filter(has_text="外包装形状: 不规则 长方体 圆柱体").get_by_placeholder("请选择").click()
    page.get_by_text("长方体", exact=True).click()
    page.get_by_role("dialog").locator("form div").filter(has_text="外包装类型: 硬包装 软包装+硬物 软包装+软物").locator("i").click()
    page.get_by_text("硬包装", exact=True).click()
    page.get_by_role("radio").filter(has_text="addImages").click()
    page.get_by_role("dialog").locator("span").filter(has_text="本地上传 选择空间图片 使用网络图片").locator("i").click()
    page.locator("#el-popover-8787").get_by_text("本地上传").click()
    page.locator("body").set_input_files("packaging.png")
    page.get_by_text("deleteImages 删除前 张图片 删除后 张图片 saveImages 仅留第 张图片 addImages 添加图片 到 成为第 1 张图片成为第 2").click()
    page.get_by_role("button", name="预览").click()
    page.get_by_role("button", name="保存修改").click()
    page.get_by_role("button", name="关闭", exact=True).click()
    page.close()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
