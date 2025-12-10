/**
 * @PURPOSE: 图片单元格编辑器组件
 * @OUTLINE:
 *   - class ImageCellEditor: 图片编辑弹窗组件
 *   - open(): 打开编辑弹窗
 *   - close(): 关闭弹窗
 *   - addByUrl(): 通过 URL 添加图片
 *   - addByUpload(): 通过上传添加图片
 *   - removeImage(): 删除图片
 *   - initSortable(): 初始化拖拽排序
 *   - preview(): 全屏预览图片
 * @DEPENDENCIES:
 *   - 外部: SortableJS (CDN)
 */

class ImageCellEditor {
  constructor(options = {}) {
    this.multiple = options.multiple !== false;
    this.title = options.title || '编辑图片';
    this.initialUrls = options.initialUrls || [];
    this.onSave = options.onSave || (() => {});
    this.uploadEndpoint = options.uploadEndpoint || '/api/upload-image';

    this.urls = [...this.initialUrls];
    this.modal = null;
    this.sortable = null;
  }

  /**
   * 打开编辑弹窗
   */
  open() {
    this.createModal();
    document.body.appendChild(this.modal);
    this.initSortable();
    this.bindEvents();
  }

  /**
   * 关闭弹窗
   */
  close() {
    if (this.sortable) {
      this.sortable.destroy();
      this.sortable = null;
    }
    if (this.modal) {
      this.modal.remove();
      this.modal = null;
    }
  }

  /**
   * 创建弹窗 HTML
   */
  createModal() {
    this.modal = document.createElement('div');
    this.modal.className = 'image-editor-modal';
    this.modal.innerHTML = `
      <div class="image-editor-dialog">
        <div class="image-editor-header">
          <h3>${this.escapeHtml(this.title)}</h3>
          <button class="close-btn" type="button">&times;</button>
        </div>
        <div class="image-editor-body">
          <!-- 拖拽上传区域 -->
          <div class="image-drop-zone" id="image-drop-zone">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
            </svg>
            <p>拖拽图片到此处上传</p>
            <p class="hint">或点击选择文件</p>
            <input type="file" id="image-file-input" accept="image/*" ${this.multiple ? 'multiple' : ''} style="display: none;">
          </div>

          <!-- URL 输入 -->
          <div class="url-input-group">
            <input type="text" id="image-url-input" placeholder="输入图片 URL 地址">
            <button type="button" id="add-url-btn">添加</button>
          </div>

          <!-- 已添加图片列表 -->
          <p class="image-list-title">已添加图片 ${this.multiple ? '(拖拽排序)' : ''}：</p>
          <div class="image-list" id="image-list">
            ${this.renderImageList()}
          </div>
        </div>
        <div class="image-editor-footer">
          <button type="button" class="cancel-btn">取消</button>
          <button type="button" class="save-btn">确定保存</button>
        </div>
      </div>
    `;
  }

  /**
   * 渲染图片列表
   */
  renderImageList() {
    if (this.urls.length === 0) {
      return '<div style="color: #9ca3af; font-size: 0.875rem; text-align: center; padding: 2rem;">暂无图片</div>';
    }

    return this.urls.map((url, index) => `
      <div class="image-list-item" data-index="${index}">
        <img src="${this.escapeHtml(url)}" alt="图片 ${index + 1}" onerror="this.style.display='none'">
        ${this.multiple ? `<span class="drag-handle">#${index + 1}</span>` : ''}
        <div class="image-actions">
          <button type="button" class="preview-btn" data-url="${this.escapeHtml(url)}" title="预览">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path>
            </svg>
          </button>
          <button type="button" class="delete-btn" data-index="${index}" title="删除">
            <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" width="16" height="16">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path>
            </svg>
          </button>
        </div>
      </div>
    `).join('');
  }

  /**
   * 刷新图片列表
   */
  refreshImageList() {
    const listEl = this.modal.querySelector('#image-list');
    if (listEl) {
      listEl.innerHTML = this.renderImageList();
      this.initSortable();
    }
  }

  /**
   * 初始化拖拽排序
   */
  initSortable() {
    if (!this.multiple) return;

    const listEl = this.modal?.querySelector('#image-list');
    if (!listEl || typeof Sortable === 'undefined') return;

    if (this.sortable) {
      this.sortable.destroy();
    }

    this.sortable = new Sortable(listEl, {
      animation: 150,
      ghostClass: 'sortable-ghost',
      dragClass: 'sortable-drag',
      handle: '.image-list-item',
      onEnd: (evt) => {
        // 更新 urls 数组顺序
        const newUrls = [];
        listEl.querySelectorAll('.image-list-item').forEach((item) => {
          const index = parseInt(item.dataset.index, 10);
          if (!isNaN(index) && this.urls[index]) {
            newUrls.push(this.urls[index]);
          }
        });
        this.urls = newUrls;
        this.refreshImageList();
      },
    });
  }

  /**
   * 绑定事件
   */
  bindEvents() {
    const modal = this.modal;

    // 关闭按钮
    modal.querySelector('.close-btn').onclick = () => this.close();

    // 取消按钮
    modal.querySelector('.cancel-btn').onclick = () => this.close();

    // 保存按钮
    modal.querySelector('.save-btn').onclick = () => {
      this.onSave(this.urls);
      this.close();
    };

    // 点击背景关闭
    modal.onclick = (e) => {
      if (e.target === modal) this.close();
    };

    // URL 输入
    const urlInput = modal.querySelector('#image-url-input');
    const addUrlBtn = modal.querySelector('#add-url-btn');

    addUrlBtn.onclick = () => {
      this.addByUrl(urlInput.value);
      urlInput.value = '';
    };

    urlInput.onkeypress = (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.addByUrl(urlInput.value);
        urlInput.value = '';
      }
    };

    // 文件上传
    const dropZone = modal.querySelector('#image-drop-zone');
    const fileInput = modal.querySelector('#image-file-input');

    dropZone.onclick = () => fileInput.click();

    fileInput.onchange = (e) => {
      const files = e.target.files;
      if (files && files.length > 0) {
        this.addByUpload(files);
      }
      fileInput.value = '';
    };

    // 拖拽上传
    dropZone.ondragover = (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    };

    dropZone.ondragleave = () => {
      dropZone.classList.remove('dragover');
    };

    dropZone.ondrop = (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      const files = e.dataTransfer.files;
      if (files && files.length > 0) {
        this.addByUpload(files);
      }
    };

    // 图片操作事件委托
    const listEl = modal.querySelector('#image-list');
    listEl.onclick = (e) => {
      const previewBtn = e.target.closest('.preview-btn');
      const deleteBtn = e.target.closest('.delete-btn');

      if (previewBtn) {
        e.stopPropagation();
        this.preview(previewBtn.dataset.url);
      } else if (deleteBtn) {
        e.stopPropagation();
        const index = parseInt(deleteBtn.dataset.index, 10);
        this.removeImage(index);
      }
    };
  }

  /**
   * 通过 URL 添加图片
   */
  addByUrl(url) {
    const trimmedUrl = url?.trim();
    if (!trimmedUrl) return;

    // 简单的 URL 验证
    if (!trimmedUrl.match(/^https?:\/\/.+/i) && !trimmedUrl.startsWith('/')) {
      alert('请输入有效的图片 URL');
      return;
    }

    if (!this.multiple) {
      this.urls = [trimmedUrl];
    } else {
      this.urls.push(trimmedUrl);
    }

    this.refreshImageList();
  }

  /**
   * 通过上传添加图片
   */
  async addByUpload(files) {
    const fileArray = Array.from(files);

    // 单图模式只取第一个
    const filesToUpload = this.multiple ? fileArray : [fileArray[0]];

    for (const file of filesToUpload) {
      if (!file.type.startsWith('image/')) {
        alert(`文件 ${file.name} 不是图片格式`);
        continue;
      }

      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(this.uploadEndpoint, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || '上传失败');
        }

        const result = await response.json();
        const uploadedUrl = result.url;

        if (!this.multiple) {
          this.urls = [uploadedUrl];
        } else {
          this.urls.push(uploadedUrl);
        }
      } catch (error) {
        console.error('Upload failed:', error);
        alert(`上传失败: ${error.message}`);
      }
    }

    this.refreshImageList();
  }

  /**
   * 删除图片
   */
  removeImage(index) {
    if (index >= 0 && index < this.urls.length) {
      this.urls.splice(index, 1);
      this.refreshImageList();
    }
  }

  /**
   * 全屏预览图片
   */
  preview(url) {
    const lightbox = document.createElement('div');
    lightbox.className = 'image-lightbox';
    lightbox.innerHTML = `
      <img src="${this.escapeHtml(url)}" alt="预览图片">
      <button class="close-lightbox">&times;</button>
    `;

    lightbox.onclick = () => lightbox.remove();

    document.body.appendChild(lightbox);
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

// 导出到全局
window.ImageCellEditor = ImageCellEditor;
