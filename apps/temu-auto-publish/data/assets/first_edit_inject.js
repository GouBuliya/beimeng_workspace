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
    const result = { success: true, filled: [], missing: [], debug: {} };
    
    // === 1. 验证当前打开的是否为产品编辑弹窗 ===
    // 由于页面可能有多个对话框叠加，改用更宽松的文本检测
    const bodyText = document.body.textContent || '';
    
    // 必须同时包含至少2个产品编辑特征关键词
    const markers = [
      bodyText.includes('产品标题') || bodyText.includes('标题'),
      bodyText.includes('商品编号') || bodyText.includes('型号'),
      bodyText.includes('SKU') || bodyText.includes('规格'),
      bodyText.includes('重量') || bodyText.includes('包裹重量'),
      bodyText.includes('尺寸') || bodyText.includes('长宽高'),
    ];
    
    const matchCount = markers.filter(Boolean).length;
    const isProductDialog = matchCount >= 3; // 至少匹配3个特征
    
    result.debug.isProductDialog = isProductDialog;
    result.debug.markerMatchCount = matchCount;
    
    // 收集对话框信息帮助调试
    const dialogs = Array.from(document.querySelectorAll('[role="dialog"], .jx-dialog, .jx-overlay-dialog'));
    result.debug.dialogCount = dialogs.length;
    
    // 尝试找到包含"产品标题"的对话框
    const productDialog = dialogs.find(d => d.textContent && (
      d.textContent.includes('产品标题') || 
      d.textContent.includes('商品编号') ||
      d.textContent.includes('SKU设置')
    ));
    
    if (!isProductDialog || !productDialog) {
      result.success = false;
      result.debug.error = '未检测到产品编辑弹窗或弹窗未完全加载';
      result.debug.hasProductDialog = !!productDialog;
      return result;
    }
    
    result.debug.productDialogFound = true;
    
    // 调试：记录当前页面状态
    result.debug.dialogFound = !!document.querySelector('[role="dialog"], .jx-dialog, .jx-overlay-dialog');
    result.debug.totalInputs = document.querySelectorAll('input').length;
    result.debug.hasVariants = Array.isArray(payload.variants) && payload.variants.length > 0;
    result.debug.hasSpecs = Array.isArray(payload.specs) && payload.specs.length > 0;

    const hasVariants = Array.isArray(payload.variants) && payload.variants.length > 0;

    // 如果有 specs，尝试填写（但不强制要求成功）
    if (Array.isArray(payload.specs) && payload.specs.length > 0) {
      try {
      await applySpecs(payload.specs, result);
      } catch (err) {
        console.warn('Specs填写失败:', err);
        result.debug.specsError = String(err);
      }
    }

    // === 调试：收集所有输入框信息 ===
    const allInputs = Array.from(document.querySelectorAll('input'));
    result.debug.totalInputsFound = allInputs.length;
    result.debug.inputDetails = allInputs.slice(0, 20).map((inp, idx) => ({
      index: idx,
      placeholder: inp.placeholder || '',
      ariaLabel: inp.getAttribute('aria-label') || '',
      type: inp.type,
      name: inp.name || '',
      className: inp.className.slice(0, 50), // 限制长度
      inTable: !!(inp.closest('.pro-virtual-table__row') || inp.closest('.vue-recycle-scroller__item-view')),
      visible: inp.offsetParent !== null,
      disabled: inp.disabled,
    }));

    // 标题 - 使用纯JavaScript查找，排除表格内的输入框
    const titleSelectors = [
      "input[aria-label*='标题']",
      "input[aria-label*='产品标题']",
      "input[placeholder*='产品标题']",
        "input[placeholder*='标题']",
        "input[placeholder*='Title']",
    ];
    
    let titleFilled = false;
    for (const selector of titleSelectors) {
      try {
        const elements = Array.from(document.querySelectorAll(selector));
        // 过滤掉在规格表格内的输入框
        const validElements = elements.filter(el => {
          return !el.closest('.pro-virtual-table__row') && 
                 !el.closest('.pro-virtual-scroll__row') &&
                 !el.closest('.vue-recycle-scroller__item-view');
        });
        
        if (validElements.length > 0) {
          result.debug.titleCandidates = validElements.length;
          for (const element of validElements) {
            // 优先选择可见且不是disabled的
            if (element.offsetParent !== null && !element.disabled) {
              dispatchInput(element, payload.title);
              titleFilled = true;
              result.debug.titleSelector = selector;
              break;
            }
          }
          if (titleFilled) {
            result.filled.push("title");
            break;
          }
        }
      } catch (e) {
        result.debug.titleError = String(e);
        continue;
      }
    }
    if (!titleFilled) {
      result.missing.push("title");
      result.debug.titleNotFound = true;
    }

    // 商品编号 / 型号 - 使用纯JavaScript
    const productNumberSelectors = [
      "input[aria-label*='型号']",
      "input[aria-label*='商品编号']",
      "input[aria-label*='产品编号']",
      "input[placeholder*='型号']",
        "input[placeholder*='商品编号']",
        "input[placeholder*='产品编号']",
      "input[name*='productNumber']",
      "input[name*='modelNumber']",
    ];
    
    let productNumberFilled = false;
    for (const selector of productNumberSelectors) {
      try {
        const elements = Array.from(document.querySelectorAll(selector));
        const validElements = elements.filter(el => {
          return !el.closest('.pro-virtual-table__row') && 
                 !el.closest('.pro-virtual-scroll__row') &&
                 !el.closest('.vue-recycle-scroller__item-view');
        });
        
        if (validElements.length > 0) {
          for (const element of validElements) {
            if (element.offsetParent !== null && !element.disabled) {
              dispatchInput(element, payload.product_number);
              productNumberFilled = true;
              result.debug.productNumberSelector = selector;
              break;
            }
          }
          if (productNumberFilled) {
            result.filled.push("product_number");
            break;
          }
        }
      } catch (e) {
        continue;
      }
    }
    if (!productNumberFilled) {
      result.missing.push("product_number");
      result.debug.productNumberNotFound = true;
    }

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

    // 重量 - 使用纯JavaScript，排除表格内的输入框
    const weightSelectors = [
      "input[aria-label*='重量'][type='number']",
      "input[aria-label*='包裹重量']",
        "input[placeholder*='重量'][type='number']",
      "input[placeholder*='包裹重量']",
        "input[placeholder*='重量'][type='text']",
      "input[name*='weight']",
    ];
    
    let weightFilled = false;
    for (const selector of weightSelectors) {
      try {
        const elements = Array.from(document.querySelectorAll(selector));
        const validElements = elements.filter(el => {
          return !el.closest('.pro-virtual-table__row') && 
                 !el.closest('.pro-virtual-scroll__row') &&
                 !el.closest('.vue-recycle-scroller__item-view');
        });
        
        if (validElements.length > 0) {
          for (const element of validElements) {
            if (element.offsetParent !== null && !element.disabled) {
              dispatchInput(element, payload.weight_g);
              weightFilled = true;
              result.debug.weightSelector = selector;
              break;
            }
          }
          if (weightFilled) {
            result.filled.push("weight_g");
            break;
          }
        }
      } catch (e) {
        continue;
      }
    }
    if (!weightFilled) {
      result.missing.push("weight_g");
      result.debug.weightNotFound = true;
    }

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

    // 尝试多个容器选择器
    const containerSelectors = [
      ".sku-setting",
      ".pro-sku-setting", 
      "[class*='sku']",
      ".jx-form-item:has(input[placeholder*='规格'])",
    ];
    
    let container = null;
    for (const selector of containerSelectors) {
      container = document.querySelector(selector);
      if (container) {
        result.debug.specContainerSelector = selector;
        break;
      }
    }
    
    if (!container) {
      // 不再标记为 missing，只记录调试信息
      result.debug.specContainerNotFound = true;
      console.warn('未找到规格容器，跳过规格填写');
      return;
    }

    const nameInput = container.querySelector("input[placeholder*='规格名称'], input[placeholder*='规格名']");
    if (nameInput && spec.name) {
      dispatchInput(nameInput, spec.name);
      result.filled.push("spec_name");
    }

    const options = Array.isArray(spec.options) ? spec.options : [];
    if (!options.length) {
      return;
    }

    let optionInputs = Array.from(container.querySelectorAll("input[placeholder*='选项'], input[placeholder*='规格值']"));
    const addButton = Array.from(container.querySelectorAll("button")).find(
      (btn) => btn.textContent && (btn.textContent.includes("添加选项") || btn.textContent.includes("添加"))
    );

    while (optionInputs.length < options.length && addButton) {
      addButton.click();
      await wait(150);
      optionInputs = Array.from(container.querySelectorAll("input[placeholder*='选项'], input[placeholder*='规格值']"));
    }

    options.forEach((opt, idx) => {
      const input = optionInputs[idx];
      if (!input) {
        // 不再标记为 missing，只记录调试信息
        result.debug[`spec_option_${idx + 1}_missing`] = true;
        return;
      }
      dispatchInput(input, opt);
      result.filled.push(`spec_option_${idx + 1}`);
    });
  };
})();

