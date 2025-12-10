/**
 * @PURPOSE: 规格组编辑器 - 处理规格+进货价+SKU图的1:1绑定编辑
 * @OUTLINE:
 *   - class SpecGroupEditor: 规格组弹窗编辑器
 *   - open(): 打开弹窗
 *   - close(): 关闭弹窗
 *   - addVariant(): 添加规格变体
 *   - removeVariant(): 删除规格变体
 *   - save(): 保存并回调
 * @DEPENDENCIES:
 *   - 外部: SortableJS (可选，用于拖拽排序)
 */

class SpecGroupEditor {
  constructor(options = {}) {
    this.initialData = options.initialData || { specs: [], prices: [], images: [] };
    this.onSave = options.onSave || (() => {});
    this.onCancel = options.onCancel || (() => {});

    // 复制数据避免直接修改原数据
    this.data = {
      specs: [...this.initialData.specs],
      prices: [...this.initialData.prices],
      images: [...this.initialData.images],
    };

    this.modal = null;
    this.overlay = null;
  }

  /**
   * 打开编辑器弹窗
   */
  open() {
    this.createModal();
    this.renderVariants();
    document.body.appendChild(this.overlay);
    document.body.appendChild(this.modal);

    // 禁止背景滚动
    document.body.style.overflow = 'hidden';

    // 聚焦第一个输入框
    setTimeout(() => {
      const firstInput = this.modal.querySelector('.variant-spec-input');
      if (firstInput) firstInput.focus();
    }, 100);
  }

  /**
   * 关闭编辑器弹窗
   */
  close() {
    if (this.overlay) {
      this.overlay.remove();
      this.overlay = null;
    }
    if (this.modal) {
      this.modal.remove();
      this.modal = null;
    }
    document.body.style.overflow = '';
  }

  /**
   * 创建弹窗 DOM
   */
  createModal() {
    // 遮罩层
    this.overlay = document.createElement('div');
    this.overlay.className = 'spec-editor-overlay';
    this.overlay.addEventListener('click', () => this.close());

    // 弹窗容器
    this.modal = document.createElement('div');
    this.modal.className = 'spec-editor-modal';
    this.modal.innerHTML = `
      <div class="spec-editor-header">
        <h3>编辑规格详情</h3>
        <button type="button" class="spec-editor-close">&times;</button>
      </div>
      <div class="spec-editor-body">
        <div class="spec-editor-tip">
          规格、进货价、SKU图为 1:1 绑定关系，添加规格时需同时填写对应信息
        </div>
        <div class="spec-variants-header">
          <span class="header-spec">规格选项</span>
          <span class="header-price">进货价</span>
          <span class="header-image">SKU图</span>
          <span class="header-action">操作</span>
        </div>
        <div class="spec-variants-list"></div>
        <button type="button" class="spec-add-variant-btn">+ 添加规格</button>
      </div>
      <div class="spec-editor-footer">
        <button type="button" class="spec-editor-cancel">取消</button>
        <button type="button" class="spec-editor-save">确定保存</button>
      </div>
    `;

    // 绑定事件
    this.modal.querySelector('.spec-editor-close').addEventListener('click', () => this.close());
    this.modal.querySelector('.spec-editor-cancel').addEventListener('click', () => {
      this.onCancel();
      this.close();
    });
    this.modal.querySelector('.spec-editor-save').addEventListener('click', () => this.save());
    this.modal.querySelector('.spec-add-variant-btn').addEventListener('click', () => this.addVariant());

    // 阻止点击弹窗内部关闭
    this.modal.addEventListener('click', (e) => e.stopPropagation());
  }

  /**
   * 渲染规格变体列表
   */
  renderVariants() {
    const list = this.modal.querySelector('.spec-variants-list');
    list.innerHTML = '';

    // 确保三个数组长度一致
    const maxLen = Math.max(this.data.specs.length, this.data.prices.length, this.data.images.length);
    for (let i = this.data.specs.length; i < maxLen; i++) this.data.specs.push('');
    for (let i = this.data.prices.length; i < maxLen; i++) this.data.prices.push('');
    for (let i = this.data.images.length; i < maxLen; i++) this.data.images.push('');

    if (this.data.specs.length === 0) {
      // 显示空状态
      list.innerHTML = '<div class="spec-empty">暂无规格，点击下方按钮添加</div>';
      return;
    }

    this.data.specs.forEach((spec, index) => {
      const row = this.createVariantRow(index, spec, this.data.prices[index], this.data.images[index]);
      list.appendChild(row);
    });

    // 初始化拖拽排序（如果 SortableJS 可用）
    if (typeof Sortable !== 'undefined') {
      new Sortable(list, {
        handle: '.variant-drag-handle',
        animation: 150,
        onEnd: (evt) => {
          // 重新排列数据
          const oldIndex = evt.oldIndex;
          const newIndex = evt.newIndex;
          this.moveVariant(oldIndex, newIndex);
        },
      });
    }
  }

  /**
   * 创建单个变体行
   */
  createVariantRow(index, spec, price, imageUrl) {
    const row = document.createElement('div');
    row.className = 'spec-variant-row';
    row.dataset.index = index;

    row.innerHTML = `
      <span class="variant-drag-handle" title="拖拽排序">⋮⋮</span>
      <input type="text" class="variant-spec-input" placeholder="规格名称" value="${this.escapeHtml(spec || '')}">
      <input type="text" class="variant-price-input" placeholder="进货价" value="${this.escapeHtml(price || '')}">
      <div class="variant-image-cell">
        ${imageUrl ? `<img src="${this.escapeHtml(imageUrl)}" class="variant-image-thumb" alt="">` : ''}
        <input type="text" class="variant-image-input" placeholder="图片URL" value="${this.escapeHtml(imageUrl || '')}">
        <button type="button" class="variant-upload-btn" title="上传图片">📤</button>
      </div>
      <button type="button" class="variant-remove-btn" title="删除此规格">&times;</button>
    `;

    // 规格输入
    const specInput = row.querySelector('.variant-spec-input');
    specInput.addEventListener('input', (e) => {
      this.data.specs[index] = e.target.value;
    });

    // 价格输入
    const priceInput = row.querySelector('.variant-price-input');
    priceInput.addEventListener('input', (e) => {
      this.data.prices[index] = e.target.value;
    });

    // 图片URL输入
    const imageInput = row.querySelector('.variant-image-input');
    imageInput.addEventListener('input', (e) => {
      this.data.images[index] = e.target.value;
      this.updateImagePreview(row, e.target.value);
    });

    // 上传按钮
    const uploadBtn = row.querySelector('.variant-upload-btn');
    uploadBtn.addEventListener('click', () => this.uploadImage(index, row));

    // 删除按钮
    const removeBtn = row.querySelector('.variant-remove-btn');
    removeBtn.addEventListener('click', () => this.removeVariant(index));

    return row;
  }

  /**
   * 更新图片预览
   */
  updateImagePreview(row, url) {
    const cell = row.querySelector('.variant-image-cell');
    let thumb = cell.querySelector('.variant-image-thumb');

    if (url && url.trim()) {
      if (!thumb) {
        thumb = document.createElement('img');
        thumb.className = 'variant-image-thumb';
        thumb.alt = '';
        cell.insertBefore(thumb, cell.firstChild);
      }
      thumb.src = url.trim();
      thumb.onerror = () => thumb.classList.add('error');
      thumb.onload = () => thumb.classList.remove('error');
    } else if (thumb) {
      thumb.remove();
    }
  }

  /**
   * 上传图片
   */
  uploadImage(index, row) {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';

    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);

      try {
        const uploadBtn = row.querySelector('.variant-upload-btn');
        uploadBtn.textContent = '⏳';
        uploadBtn.disabled = true;

        const response = await fetch('/api/upload-image', {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error('上传失败');
        }

        const result = await response.json();
        const url = result.url;

        this.data.images[index] = url;
        const imageInput = row.querySelector('.variant-image-input');
        imageInput.value = url;
        this.updateImagePreview(row, url);

        uploadBtn.textContent = '📤';
        uploadBtn.disabled = false;
      } catch (err) {
        alert('图片上传失败: ' + err.message);
        const uploadBtn = row.querySelector('.variant-upload-btn');
        uploadBtn.textContent = '📤';
        uploadBtn.disabled = false;
      }
    };

    input.click();
  }

  /**
   * 添加规格变体
   */
  addVariant() {
    this.data.specs.push('');
    this.data.prices.push('');
    this.data.images.push('');
    this.renderVariants();

    // 滚动到底部并聚焦
    const list = this.modal.querySelector('.spec-variants-list');
    list.scrollTop = list.scrollHeight;

    const lastRow = list.lastElementChild;
    if (lastRow) {
      const specInput = lastRow.querySelector('.variant-spec-input');
      if (specInput) specInput.focus();
    }
  }

  /**
   * 删除规格变体
   */
  removeVariant(index) {
    this.data.specs.splice(index, 1);
    this.data.prices.splice(index, 1);
    this.data.images.splice(index, 1);
    this.renderVariants();
  }

  /**
   * 移动规格变体（拖拽排序）
   */
  moveVariant(oldIndex, newIndex) {
    const moveItem = (arr, from, to) => {
      const item = arr.splice(from, 1)[0];
      arr.splice(to, 0, item);
    };

    moveItem(this.data.specs, oldIndex, newIndex);
    moveItem(this.data.prices, oldIndex, newIndex);
    moveItem(this.data.images, oldIndex, newIndex);
  }

  /**
   * 保存数据
   */
  save() {
    // 过滤掉空的规格
    const validIndices = [];
    this.data.specs.forEach((spec, i) => {
      if (spec && spec.trim()) {
        validIndices.push(i);
      }
    });

    const cleanData = {
      specs: validIndices.map(i => this.data.specs[i].trim()),
      prices: validIndices.map(i => (this.data.prices[i] || '').trim()),
      images: validIndices.map(i => (this.data.images[i] || '').trim()),
    };

    this.onSave(cleanData);
    this.close();
  }

  /**
   * HTML 转义
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
}

// 导出供全局使用
window.SpecGroupEditor = SpecGroupEditor;
