"""
@PURPOSE: 测试商品采集功能
@OUTLINE:
  - 测试访问店铺
  - 测试搜索商品
  - 测试采集链接
"""

import asyncio
import os

from dotenv import load_dotenv
from src.browser.collection_controller import CollectionController
from src.browser.login_controller import LoginController


async def test_collection():
    """测试采集功能."""
    # 加载环境变量
    load_dotenv()
    username = os.getenv("MIAOSHOU_USERNAME") or os.getenv("TEMU_USERNAME")
    password = os.getenv("MIAOSHOU_PASSWORD") or os.getenv("TEMU_PASSWORD")

    if not username or not password:
        print("❌ 请在 .env 文件中配置登录凭证")
        return

    # 初始化控制器
    login_ctrl = LoginController()
    collection_ctrl = CollectionController()

    try:
        # 启动浏览器
        await login_ctrl.browser_manager.start()
        page = login_ctrl.browser_manager.page

        # 登录
        print("\n" + "=" * 60)
        print("1. 登录妙手ERP...")
        print("=" * 60)
        if not await login_ctrl.login(username, password):
            print("❌ 登录失败")
            return

        # 步骤1:访问店铺
        print("\n" + "=" * 60)
        print("2. 访问前端店铺...")
        print("=" * 60)
        if not await collection_ctrl.visit_store(page):
            print("❌ 访问店铺失败")
            return

        # 步骤2-3:搜索并采集
        print("\n" + "=" * 60)
        print("3. 搜索并采集商品...")
        print("=" * 60)

        test_keywords = [
            "药箱收纳盒",
            # 可以添加更多关键词测试
        ]

        for keyword in test_keywords:
            print(f"\n>>> 测试关键词: {keyword}")

            # 搜索并采集
            links = await collection_ctrl.search_and_collect(page, keyword=keyword, count=5)

            if links:
                print(f"\n✅ 成功采集 {len(links)} 个商品:")
                for i, link in enumerate(links):
                    print(f"\n  [{i + 1}] {link['title']}")
                    print(f"      价格: {link['price']}")
                    print(f"      链接: {link['url'][:50]}...")
            else:
                print(f"\n❌ 关键词 '{keyword}' 采集失败")

        # 等待查看结果
        print("\n" + "=" * 60)
        print("测试完成!浏览器将在10秒后关闭...")
        print("=" * 60)
        await page.wait_for_timeout(10000)

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # 关闭浏览器
        await login_ctrl.browser_manager.close()


if __name__ == "__main__":
    asyncio.run(test_collection())
