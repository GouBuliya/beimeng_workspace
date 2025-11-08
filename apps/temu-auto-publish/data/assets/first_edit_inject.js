/**
 * @PURPOSE: 注入妙手首次编辑弹窗, 以稳定方式填写核心字段
 * @OUTLINE:
 *   - window.__FIRST_EDIT_APPLY__: 主函数, 接收 payload 并返回执行结果
 *   - fillField(): 尝试多个选择器填写文本输入框
 *   - dispatchInput(): 触发 input/change 事件确保前端识别
 * @GOTCHAS:
 *   - 选择器按优先级排列, 若页面结构调整需同步更新
 *   - 某些字段可能存在多规格, 默认取第一个输入
 */

(() => {
  const dispatchInput = (element, value) => {
    if (!element) return;
    element.focus();
    element.value = value ?? "";
    const inputEvent = new Event("input", { bubbles: true });
    const changeEvent = new Event("change", { bubbles: true });
    element.dispatchEvent(inputEvent);
    element.dispatchEvent(changeEvent);
  };

  const toStringValue = (value) => {
    if (value === undefined || value === null) {
      return "";
    }
    return String(value);
  };

  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const fillField = (selectors, value, result, label) => {
    let filled = false;
    for (const selector of selectors) {
      const elements = Array.from(document.querySelectorAll(selector));
      if (!elements.length) continue;
      for (const element of elements) {
        dispatchInput(element, value);
        filled = true;
      }
    }
    if (filled) {
      result.filled.push(label || selectors.join(","));
      return true;
    }
    result.missing.push(label || selectors.join(","));
    return false;
  };

  window.__FIRST_EDIT_APPLY__ = async (payload) => {
    const result = { success: true, filled: [], missing: [] };

    const hasVariants = Array.isArray(payload.variants) && payload.variants.length > 0;

    if (Array.isArray(payload.specs) && payload.specs.length > 0) {
      await applySpecs(payload.specs, result);
    }

    // 标题
    fillField(
      [
        ".collect-box-editor-dialog-V2 input[placeholder*='标题']",
        "input[placeholder*='标题']",
        "input[placeholder*='Title']",
      ],
      payload.title,
      result,
      "title",
    );

    // 商品编号 / 型号
    fillField(
      [
        ".collect-box-editor-dialog-V2 input[placeholder*='型号']",
        "input[placeholder*='商品编号']",
        "input[placeholder*='产品编号']",
      ],
      payload.product_number,
      result,
      "product_number",
    );

    if (!hasVariants) {
      // 价格字段
      fillField(
        [
          "input[placeholder*='建议售价']",
          "input[placeholder*='售价']",
        ],
        payload.price,
        result,
        "price",
      );
      fillField(
        [
          "input[placeholder*='供货价']",
          "input[placeholder*='供货价格']",
        ],
        payload.supply_price,
        result,
        "supply_price",
      );
      fillField(
        [
          "input[placeholder*='货源价']",
          "input[placeholder*='来源价格']",
          "input[placeholder*='采购价']",
        ],
        payload.source_price,
        result,
        "source_price",
      );

      // 库存
      fillField(
        [
          "input[placeholder*='库存']",
          "input[placeholder*='数量']",
        ],
        payload.stock,
        result,
        "stock",
      );
    }

    // 重量
    fillField(
      [
        "input[placeholder*='重量'][type='number']",
        "input[placeholder*='重量'][type='text']",
      ],
      payload.weight_g,
      result,
      "weight_g",
    );

    // 尺寸
    const dimensionSelectors = [
      { key: "length_cm", label: "length_cm", selectors: ["input[placeholder*='长']", "input[aria-label*='长']"] },
      { key: "width_cm", label: "width_cm", selectors: ["input[placeholder*='宽']", "input[aria-label*='宽']"] },
      { key: "height_cm", label: "height_cm", selectors: ["input[placeholder*='高']", "input[aria-label*='高']"] },
    ];

    for (const { key, selectors, label } of dimensionSelectors) {
      fillField(selectors, payload[key], result, label);
    }

    // 供货链接
    if (payload.supplier_link) {
      fillField(
        [
          "input[placeholder*='链接']",
          "input[placeholder*='URL']",
        ],
        payload.supplier_link,
        result,
        "supplier_link",
      );
    }

    if (hasVariants) {
      const variantRows = Array.from(
        document.querySelectorAll(".pro-virtual-table__row.pro-virtual-scroll__row")
      );
      const fallback = {
        price: payload.price,
        supply_price: payload.supply_price,
        source_price: payload.source_price,
        stock: payload.stock,
      };

      payload.variants.forEach((variant, index) => {
        const row = variantRows[index];
        if (!row) {
          result.missing.push(`variant_row_${index + 1}`);
          return;
        }

        const fieldMap = [
          ["price", ["input[placeholder*='建议售价']", "input[placeholder*='售价']"]],
          ["supply_price", ["input[placeholder*='供货价']", "input[placeholder*='供货价格']"]],
          [
            "source_price",
            ["input[placeholder*='货源价']", "input[placeholder*='来源价格']", "input[placeholder*='采购价']"],
          ],
          ["stock", ["input[placeholder*='库存']", "input[placeholder*='数量']"]],
        ];

        for (const [field, selectors] of fieldMap) {
          const value = toStringValue(variant[field] ?? fallback[field]);
          let filled = false;
          for (const selector of selectors) {
            const input = row.querySelector(selector);
            if (!input) continue;
            dispatchInput(input, value);
            result.filled.push(`${field}[row=${index + 1}]`);
            filled = true;
            break;
          }

          if (!filled) {
            result.missing.push(`${field}[row=${index + 1}]`);
          }
        }
      });
    }

    if (result.missing.length > 0) {
      result.success = false;
    }
    return result;
  };

  const applySpecs = async (specs, result) => {
    const spec = specs[0];
    if (!spec) return;

    const container = document.querySelector(".sku-setting");
    if (!container) {
      result.missing.push("spec_container");
      return;
    }

    const nameInput = container.querySelector("input[placeholder*='规格名称']");
    if (nameInput && spec.name) {
      dispatchInput(nameInput, spec.name);
      result.filled.push("spec_name");
    }

    const options = Array.isArray(spec.options) ? spec.options : [];
    if (!options.length) {
      return;
    }

    let optionInputs = Array.from(container.querySelectorAll("input[placeholder*='选项']"));
    const addButton = Array.from(container.querySelectorAll("button")).find(
      (btn) => btn.textContent && btn.textContent.includes("添加选项")
    );

    while (optionInputs.length < options.length && addButton) {
      addButton.click();
      await wait(150);
      optionInputs = Array.from(container.querySelectorAll("input[placeholder*='选项']"));
    }

    options.forEach((opt, idx) => {
      const input = optionInputs[idx];
      if (!input) {
        result.missing.push(`spec_option_${idx + 1}`);
        return;
      }
      dispatchInput(input, opt);
      result.filled.push(`spec_option_${idx + 1}`);
    });
  };
})();

