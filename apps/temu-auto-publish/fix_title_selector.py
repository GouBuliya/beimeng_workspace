#!/usr/bin/env python3
"""
修复first_edit_controller.py中的标题字段选择器
确保定位到"产品标题"而不是"简易描述"
"""


def fix_get_original_title(lines, start_line):
    """修复get_original_title方法中的选择器"""
    # 找到 "# 尝试多个可能的标题输入框选择器" 这一行
    for i in range(start_line, min(start_line + 50, len(lines))):
        if "# 尝试多个可能的标题输入框选择器" in lines[i]:
            # 替换选择器列表
            selector_start = i + 1
            # 找到 title_selectors = [ 这一行
            while (
                selector_start < len(lines) and "title_selectors = [" not in lines[selector_start]
            ):
                selector_start += 1

            if selector_start < len(lines):
                # 找到选择器列表的结束位置
                selector_end = selector_start + 1
                bracket_count = 1
                while selector_end < len(lines) and bracket_count > 0:
                    if "[" in lines[selector_end]:
                        bracket_count += lines[selector_end].count("[")
                    if "]" in lines[selector_end]:
                        bracket_count -= lines[selector_end].count("]")
                    selector_end += 1

                # 创建新的选择器列表(优先通过表单结构定位"产品标题")
                new_selectors = """            # 优先通过表单结构定位"产品标题"字段
            title_selectors = [
                # 方法1:通过相邻的label文本定位(最准确)
                "xpath=//label[contains(text(), '产品标题')]/following::textarea[1]",
                "xpath=//div[contains(@class, 'jx-form-item')]//label[contains(text(), '产品标题')]/..//textarea",

                # 方法2:通过placeholder定位
                "textarea[placeholder*='产品标题']",
                "textarea[placeholder*='请输入产品标题']",

                # 方法3:通过排除简易描述(降级方案)
                "textarea.jx-textarea__inner",  # 会找到第一个,可能是简易描述
            ]
"""
                # 替换选择器列表
                lines[selector_start:selector_end] = [new_selectors]
                return i
    return -1


def fix_edit_title(lines, start_line):
    """修复edit_title方法中的选择器"""
    # 与get_original_title使用相同的逻辑
    return fix_get_original_title(lines, start_line)


# 读取文件
with open("src/browser/first_edit_controller.py", encoding="utf-8") as f:
    lines = f.readlines()

# 找到get_original_title方法
get_original_title_line = -1
edit_title_line = -1

for i, line in enumerate(lines):
    if "async def get_original_title" in line:
        get_original_title_line = i
        print(f"找到 get_original_title 方法在第 {i + 1} 行")
    elif "async def edit_title" in line and edit_title_line == -1:
        edit_title_line = i
        print(f"找到 edit_title 方法在第 {i + 1} 行")

# 修复两个方法(从后往前改,避免行号变化)
if edit_title_line > 0:
    fix_edit_title(lines, edit_title_line)
    print("✓ 已修复 edit_title 方法的选择器")

if get_original_title_line > 0:
    fix_get_original_title(lines, get_original_title_line)
    print("✓ 已修复 get_original_title 方法的选择器")

# 写回文件
with open("src/browser/first_edit_controller.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("\n✅ 修复完成!")
print("\n新的选择器策略:")
print("1. 优先:通过label文本'产品标题'定位 (XPath)")
print("2. 备选:通过placeholder='产品标题'定位")
print("3. 降级:使用通用textarea(可能是简易描述)")
