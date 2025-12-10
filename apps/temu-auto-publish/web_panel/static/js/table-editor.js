/**
 * @PURPOSE: Handsontable 表格编辑器封装类 - 匹配 CSV 选品表结构
 * @OUTLINE:
 *   - class TableEditor: 表格编辑器核心类
 *   - init(): 初始化表格
 *   - openSpecGroupEditor(): 打开规格组编辑器（规格+进货价+SKU图 1:1 绑定）
 *   - getData(): 获取表格数据，输出 JSON 数组格式
 * @DEPENDENCIES:
 *   - 外部: Handsontable (CDN)
 *   - 内部: ImageCellEditor, SpecGroupEditor
 */

class TableEditor {
  constructor(containerId, options = {}) {
    this.containerId = containerId;
    this.container = document.getElementById(containerId);
    this.hot = null;
    this.draftKey = 'temu_table_draft_v2';
    this.autosaveTimeout = null;
    this.onDataChange = options.onDataChange || (() => {});

    // 列配置 - 匹配 CSV 结构
    // CSV列: 序号,产品名称,标题后缀,规格数组,规格单位,进货价,sku实拍图数组,视频链接,到货状态,尺码图
    this.columns = [
      {
        data: 'product_name',
        title: '产品名称 *',
        width: 160,
        validator: (value, callback) => callback(!!value && value.trim() !== ''),
      },
      {
        data: 'title_suffix',
        title: '标题后缀',
        width: 100,
      },
      {
        data: 'spec_unit',
        title: '规格单位',
        width: 90,
      },
      {
        // 规格组：包含 规格数组 + 进货价 + sku实拍图数组（1:1 绑定）
        data: 'spec_group',
        title: '规格详情',
        width: 180,
        renderer: this.specGroupRenderer.bind(this),
        editor: false,
      },
      {
        data: 'video_url',
        title: '视频链接',
        width: 150,
        renderer: this.videoRenderer.bind(this),
        editor: false,
      },
      {
        data: 'availability',
        title: '到货状态',
        width: 80,
        type: 'dropdown',
        source: ['1', '0'],
        allowInvalid: false,
      },
      {
        data: 'size_chart_url',
        title: '尺码图',
        width: 120,
        renderer: this.singleImageRenderer.bind(this),
        editor: false,
      },
    ];

    // 内部数据存储（用于规格组的三个数组）
    this.specGroupData = {};
  }

  /**
   * 初始化表格
   */
  init() {
    if (!this.container) {
      console.error(`Container #${this.containerId} not found`);
      return;
    }

    const initialData = this.getEmptyRows(5);

    this.hot = new Handsontable(this.container, {
      data: initialData,
      columns: this.columns,
      colHeaders: this.columns.map(c => c.title),
      rowHeaders: true,
      height: 480,
      licenseKey: 'non-commercial-and-evaluation',
      stretchH: 'none',
      autoWrapRow: true,
      autoWrapCol: true,
      contextMenu: true,
      manualColumnResize: true,
      manualRowResize: true,
      copyPaste: true,
      undo: true,
      outsideClickDeselects: false,
      afterChange: (changes, source) => {
        if (source !== 'loadData') {
          this.triggerAutosave();
          this.updateRowCount();
          this.onDataChange();
        }
      },
      afterCreateRow: () => {
        this.updateRowCount();
        this.triggerAutosave();
      },
      afterRemoveRow: (index, amount) => {
        // 清理规格组数据
        for (let i = 0; i < amount; i++) {
          delete this.specGroupData[index + i];
        }
        this.updateRowCount();
        this.triggerAutosave();
      },
      cells: (row, col) => {
        const cellProperties = {};
        const colData = this.columns[col]?.data;
        if (colData === 'spec_group' || colData === 'size_chart_url') {
          cellProperties.readOnly = true;
        }
        return cellProperties;
      },
    });

    // 绑定单元格点击事件
    this.container.addEventListener('click', (e) => {
      // 规格组点击
      const specGroupCell = e.target.closest('.spec-group-cell');
      if (specGroupCell) {
        const row = parseInt(specGroupCell.dataset.row, 10);
        this.openSpecGroupEditor(row);
        return;
      }

      // 图片单元格点击
      const imageCell = e.target.closest('.image-cell');
      if (imageCell) {
        const row = parseInt(imageCell.dataset.row, 10);
        const col = parseInt(imageCell.dataset.col, 10);
        this.openImageEditor(row, col);
        return;
      }

      // 视频单元格点击
      const videoCell = e.target.closest('.video-cell');
      if (videoCell) {
        const row = parseInt(videoCell.dataset.row, 10);
        const col = parseInt(videoCell.dataset.col, 10);
        this.openVideoEditor(row, col);
      }
    });

    this.updateRowCount();
    this.checkDraft();
  }

  /**
   * 规格组渲染器 - 显示规格数量和预览
   */
  specGroupRenderer(instance, td, row, col, prop, value, cellProperties) {
    Handsontable.renderers.TextRenderer.apply(this, arguments);
    td.innerHTML = '';
    td.className = 'htMiddle';

    const wrapper = document.createElement('div');
    wrapper.className = 'spec-group-cell';
    wrapper.dataset.row = row;

    // 获取该行的规格组数据
    const specData = this.getSpecGroupForRow(row);
    const count = specData.specs.length;

    if (count > 0) {
      // 显示规格预览
      const preview = document.createElement('div');
      preview.className = 'spec-preview';

      // 显示前3个规格
      const displaySpecs = specData.specs.slice(0, 3);
      displaySpecs.forEach((spec, i) => {
        const tag = document.createElement('span');
        tag.className = 'spec-tag';
        tag.textContent = spec;
        if (specData.prices[i]) {
          tag.title = `${spec} - ¥${specData.prices[i]}`;
        }
        preview.appendChild(tag);
      });

      if (count > 3) {
        const more = document.createElement('span');
        more.className = 'spec-more';
        more.textContent = `+${count - 3}`;
        preview.appendChild(more);
      }

      wrapper.appendChild(preview);
    }

    // 添加/编辑按钮
    const addBtn = document.createElement('span');
    addBtn.className = 'add-spec-btn';
    addBtn.textContent = count > 0 ? '✏' : '+';
    addBtn.title = count > 0 ? '编辑规格' : '添加规格';
    wrapper.appendChild(addBtn);

    td.appendChild(wrapper);
  }

  /**
   * 单图渲染器
   */
  singleImageRenderer(instance, td, row, col, prop, value, cellProperties) {
    Handsontable.renderers.TextRenderer.apply(this, arguments);
    td.innerHTML = '';
    td.className = 'htMiddle';

    const wrapper = document.createElement('div');
    wrapper.className = 'image-cell';
    wrapper.dataset.row = row;
    wrapper.dataset.col = col;

    if (value && value.trim()) {
      const img = document.createElement('img');
      img.className = 'image-thumb';
      img.src = value.trim();
      img.alt = '';
      img.onerror = () => img.classList.add('error');
      wrapper.appendChild(img);
    }

    const addBtn = document.createElement('span');
    addBtn.className = 'add-image-btn';
    addBtn.textContent = value ? '✏' : '+';
    wrapper.appendChild(addBtn);

    td.appendChild(wrapper);
  }

  /**
   * 视频渲染器 - 显示视频封面预览
   */
  videoRenderer(instance, td, row, col, prop, value, cellProperties) {
    Handsontable.renderers.TextRenderer.apply(this, arguments);
    td.innerHTML = '';
    td.className = 'htMiddle';

    const wrapper = document.createElement('div');
    wrapper.className = 'video-cell';
    wrapper.dataset.row = row;
    wrapper.dataset.col = col;

    if (value && value.trim()) {
      const videoUrl = value.trim();

      // 创建视频元素用于获取封面
      const video = document.createElement('video');
      video.className = 'video-thumb';
      video.src = videoUrl;
      video.muted = true;
      video.preload = 'metadata';
      video.crossOrigin = 'anonymous';

      // 视频加载后暂停在第一帧作为封面
      video.addEventListener('loadeddata', () => {
        video.currentTime = 0.1; // 跳到 0.1 秒获取第一帧
      });

      // 播放图标覆盖层
      const playIcon = document.createElement('span');
      playIcon.className = 'video-play-icon';
      playIcon.innerHTML = '▶';

      video.onerror = () => {
        video.classList.add('error');
        playIcon.style.display = 'none';
      };

      wrapper.appendChild(video);
      wrapper.appendChild(playIcon);
    }

    const addBtn = document.createElement('span');
    addBtn.className = 'add-video-btn';
    addBtn.textContent = value ? '✏' : '+';
    wrapper.appendChild(addBtn);

    td.appendChild(wrapper);
  }

  /**
   * 获取行的规格组数据
   */
  getSpecGroupForRow(row) {
    if (!this.specGroupData[row]) {
      this.specGroupData[row] = {
        specs: [],
        prices: [],
        images: [],
      };
    }
    return this.specGroupData[row];
  }

  /**
   * 设置行的规格组数据
   */
  setSpecGroupForRow(row, data) {
    this.specGroupData[row] = data;
    // 更新单元格显示
    const colIndex = this.columns.findIndex(c => c.data === 'spec_group');
    if (colIndex >= 0) {
      this.hot.setDataAtCell(row, colIndex, JSON.stringify(data), 'specGroupUpdate');
    }
    this.triggerAutosave();
  }

  /**
   * 打开规格组编辑器
   */
  openSpecGroupEditor(row) {
    const specData = this.getSpecGroupForRow(row);

    // 使用 SpecGroupEditor（如果可用）
    if (typeof SpecGroupEditor !== 'undefined') {
      const editor = new SpecGroupEditor({
        initialData: specData,
        onSave: (data) => {
          this.setSpecGroupForRow(row, data);
          this.hot.render();
        },
      });
      editor.open();
    } else {
      // 降级方案：简单的 prompt
      this.fallbackSpecEditor(row, specData);
    }
  }

  /**
   * 降级的规格编辑器
   */
  fallbackSpecEditor(row, specData) {
    const specsStr = specData.specs.join(', ');
    const pricesStr = specData.prices.join(', ');

    const newSpecs = prompt('请输入规格选项（逗号分隔）:', specsStr);
    if (newSpecs === null) return;

    const newPrices = prompt('请输入对应进货价（逗号分隔，数量需与规格相同）:', pricesStr);
    if (newPrices === null) return;

    const specsArray = newSpecs.split(',').map(s => s.trim()).filter(s => s);
    const pricesArray = newPrices.split(',').map(s => s.trim()).filter(s => s);

    if (specsArray.length !== pricesArray.length) {
      alert('规格数量与进货价数量不匹配！');
      return;
    }

    this.setSpecGroupForRow(row, {
      specs: specsArray,
      prices: pricesArray,
      images: specData.images.slice(0, specsArray.length), // 保持图片数组长度
    });
    this.hot.render();
  }

  /**
   * 打开图片编辑器（尺码图）
   */
  openImageEditor(row, col) {
    const currentValue = this.hot.getDataAtCell(row, col);

    if (typeof ImageCellEditor !== 'undefined') {
      const editor = new ImageCellEditor({
        multiple: false,
        title: '编辑尺码图',
        initialUrls: currentValue ? [currentValue] : [],
        onSave: (urls) => {
          this.hot.setDataAtCell(row, col, urls[0] || '');
        },
      });
      editor.open();
    } else {
      const newValue = prompt('请输入图片 URL:', currentValue || '');
      if (newValue !== null) {
        this.hot.setDataAtCell(row, col, newValue);
      }
    }
  }

  /**
   * 打开视频编辑器
   */
  openVideoEditor(row, col) {
    const currentValue = this.hot.getDataAtCell(row, col);

    // 创建视频编辑弹窗
    const modal = document.createElement('div');
    modal.className = 'video-editor-modal';
    modal.innerHTML = `
      <div class="video-editor-content">
        <div class="video-editor-header">
          <h3>编辑视频链接</h3>
          <button class="video-editor-close">&times;</button>
        </div>
        <div class="video-editor-body">
          <div class="video-upload-zone">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M15 10l-4 4l6 6l4-16l-18 7l6 2l2 6l2-4"></path>
            </svg>
            <p>拖拽视频到此处上传，或点击选择文件</p>
            <span class="hint">支持 MP4、WebM 格式，最大 100MB</span>
            <input type="file" class="video-file-input" accept="video/mp4,video/webm" style="display:none">
          </div>
          <div class="video-upload-progress" style="display:none">
            <div class="progress-bar"><div class="progress-fill"></div></div>
            <span class="progress-text">上传中...</span>
          </div>
          <div class="video-url-input">
            <label>或输入视频 URL</label>
            <input type="text" class="video-url-field" placeholder="请输入视频链接 (MP4/WebM)" value="${currentValue || ''}">
          </div>
          <div class="video-preview-container">
            <label>视频预览</label>
            <div class="video-preview-wrapper">
              ${currentValue ? `
                <video class="video-preview" controls preload="metadata">
                  <source src="${currentValue}" type="video/mp4">
                  您的浏览器不支持视频播放
                </video>
              ` : '<div class="video-preview-placeholder">上传或输入 URL 后预览视频</div>'}
            </div>
          </div>
        </div>
        <div class="video-editor-footer">
          <button class="btn-cancel">取消</button>
          <button class="btn-save">保存</button>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    const urlInput = modal.querySelector('.video-url-field');
    const previewWrapper = modal.querySelector('.video-preview-wrapper');
    const closeBtn = modal.querySelector('.video-editor-close');
    const cancelBtn = modal.querySelector('.btn-cancel');
    const saveBtn = modal.querySelector('.btn-save');
    const uploadZone = modal.querySelector('.video-upload-zone');
    const fileInput = modal.querySelector('.video-file-input');
    const progressContainer = modal.querySelector('.video-upload-progress');
    const progressFill = modal.querySelector('.progress-fill');
    const progressText = modal.querySelector('.progress-text');

    // 更新预览函数
    const updatePreview = (url) => {
      if (url) {
        previewWrapper.innerHTML = `
          <video class="video-preview" controls preload="metadata">
            <source src="${url}" type="video/mp4">
            您的浏览器不支持视频播放
          </video>
        `;
      } else {
        previewWrapper.innerHTML = '<div class="video-preview-placeholder">上传或输入 URL 后预览视频</div>';
      }
    };

    // URL 输入时更新预览
    let debounceTimer;
    urlInput.addEventListener('input', () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        updatePreview(urlInput.value.trim());
      }, 500);
    });

    // 点击上传区域触发文件选择
    uploadZone.addEventListener('click', () => {
      fileInput.click();
    });

    // 拖拽上传
    uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
      uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      const files = e.dataTransfer.files;
      if (files.length > 0) {
        handleVideoUpload(files[0]);
      }
    });

    // 文件选择上传
    fileInput.addEventListener('change', () => {
      if (fileInput.files.length > 0) {
        handleVideoUpload(fileInput.files[0]);
      }
    });

    // 视频上传处理
    const handleVideoUpload = async (file) => {
      // 验证文件类型
      if (!file.type.startsWith('video/')) {
        alert('请选择视频文件');
        return;
      }

      // 验证文件大小 (100MB)
      if (file.size > 100 * 1024 * 1024) {
        alert('视频文件不能超过 100MB');
        return;
      }

      // 显示进度条
      uploadZone.style.display = 'none';
      progressContainer.style.display = 'block';
      progressFill.style.width = '0%';
      progressText.textContent = '上传中... 0%';

      try {
        const formData = new FormData();
        formData.append('file', file);

        const xhr = new XMLHttpRequest();

        // 上传进度
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) {
            const percent = Math.round((e.loaded / e.total) * 100);
            progressFill.style.width = percent + '%';
            progressText.textContent = `上传中... ${percent}%`;
          }
        });

        // 上传完成
        xhr.addEventListener('load', () => {
          if (xhr.status === 200) {
            const response = JSON.parse(xhr.responseText);
            if (response.url) {
              urlInput.value = response.url;
              updatePreview(response.url);
              progressText.textContent = '上传成功!';
              setTimeout(() => {
                progressContainer.style.display = 'none';
                uploadZone.style.display = 'block';
              }, 1000);
            } else {
              throw new Error(response.detail || '上传失败');
            }
          } else {
            throw new Error('上传失败: ' + xhr.statusText);
          }
        });

        // 上传错误
        xhr.addEventListener('error', () => {
          progressContainer.style.display = 'none';
          uploadZone.style.display = 'block';
          alert('上传失败，请检查网络连接');
        });

        xhr.open('POST', '/api/upload-video');
        xhr.send(formData);

      } catch (error) {
        progressContainer.style.display = 'none';
        uploadZone.style.display = 'block';
        alert('上传失败: ' + error.message);
      }
    };

    // 关闭弹窗
    const closeModal = () => {
      modal.remove();
    };

    closeBtn.addEventListener('click', closeModal);
    cancelBtn.addEventListener('click', closeModal);
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    // 保存
    saveBtn.addEventListener('click', () => {
      const newValue = urlInput.value.trim();
      this.hot.setDataAtCell(row, col, newValue);
      closeModal();
    });

    // 自动聚焦输入框
    urlInput.focus();
    urlInput.select();
  }

  /**
   * 获取空行数据
   */
  getEmptyRows(count) {
    const rows = [];
    for (let i = 0; i < count; i++) {
      rows.push(this.getEmptyRow());
    }
    return rows;
  }

  getEmptyRow() {
    const row = {};
    this.columns.forEach(col => {
      if (col.data === 'availability') {
        row[col.data] = '1';
      } else {
        row[col.data] = '';
      }
    });
    return row;
  }

  /**
   * 添加行
   */
  addRow(count = 1) {
    const rowCount = this.hot.countRows();
    this.hot.alter('insert_row_below', rowCount - 1, count);
  }

  /**
   * 删除选中行
   */
  deleteRows() {
    const selected = this.hot.getSelected();
    if (!selected || selected.length === 0) {
      alert('请先选择要删除的行');
      return;
    }

    const rowsToDelete = new Set();
    selected.forEach(([startRow, , endRow]) => {
      for (let i = Math.min(startRow, endRow); i <= Math.max(startRow, endRow); i++) {
        rowsToDelete.add(i);
      }
    });

    const sortedRows = Array.from(rowsToDelete).sort((a, b) => b - a);
    sortedRows.forEach(row => {
      delete this.specGroupData[row];
      this.hot.alter('remove_row', row);
    });
  }

  /**
   * 复制选中行
   */
  duplicateRows() {
    const selected = this.hot.getSelected();
    if (!selected || selected.length === 0) {
      alert('请先选择要复制的行');
      return;
    }

    const [startRow, , endRow] = selected[0];
    const minRow = Math.min(startRow, endRow);
    const maxRow = Math.max(startRow, endRow);

    const dataToCopy = [];
    const specDataToCopy = [];

    for (let i = minRow; i <= maxRow; i++) {
      const rowData = this.hot.getDataAtRow(i);
      const newRow = {};
      this.columns.forEach((col, index) => {
        newRow[col.data] = rowData[index];
      });
      dataToCopy.push(newRow);

      // 复制规格组数据
      const specData = this.getSpecGroupForRow(i);
      specDataToCopy.push(JSON.parse(JSON.stringify(specData)));
    }

    this.hot.alter('insert_row_below', maxRow, dataToCopy.length);

    dataToCopy.forEach((row, index) => {
      const newRowIndex = maxRow + 1 + index;
      this.columns.forEach((col, colIndex) => {
        this.hot.setDataAtCell(newRowIndex, colIndex, row[col.data], 'duplicateRow');
      });
      // 复制规格组数据
      this.specGroupData[newRowIndex] = specDataToCopy[index];
    });
  }

  /**
   * 清空表格
   */
  clearAll() {
    if (!confirm('确定要清空所有数据吗？此操作不可撤销。')) {
      return;
    }

    this.specGroupData = {};
    const initialData = this.getEmptyRows(5);
    this.hot.loadData(initialData);
    this.clearDraft();
  }

  /**
   * 获取表格数据 - 输出 CSV 兼容格式
   */
  getData() {
    const allData = this.hot.getData();
    const result = [];

    allData.forEach((row, rowIndex) => {
      const rowData = {};
      let hasRealData = false;

      this.columns.forEach((col, colIndex) => {
        const value = row[colIndex];

        if (col.data === 'spec_group') {
          // 规格组特殊处理 - 输出为三个独立数组
          const specData = this.getSpecGroupForRow(rowIndex);
          rowData['spec_array'] = specData.specs;
          rowData['price_array'] = specData.prices;
          rowData['sku_images'] = specData.images;
          if (specData.specs.length > 0) hasRealData = true;
        } else if (col.data === 'availability') {
          // 默认值字段，保存但不算作有效数据
          rowData[col.data] = value;
        } else {
          rowData[col.data] = value;
          if (value !== null && value !== undefined && String(value).trim() !== '') {
            hasRealData = true;
          }
        }
      });

      if (hasRealData) {
        result.push(rowData);
      }
    });

    return result;
  }

  /**
   * 验证数据
   */
  validate() {
    const data = this.getData();
    const errors = [];

    data.forEach((row, index) => {
      if (!row.product_name || row.product_name.trim() === '') {
        errors.push({
          row: index + 1,
          column: 'product_name',
          message: '产品名称不能为空',
        });
      }

      // 验证规格组数据一致性
      const specCount = row.spec_array?.length || 0;
      const priceCount = row.price_array?.length || 0;

      if (specCount > 0 && specCount !== priceCount) {
        errors.push({
          row: index + 1,
          column: 'spec_group',
          message: `规格数量(${specCount})与进货价数量(${priceCount})不匹配`,
        });
      }
    });

    return {
      valid: errors.length === 0,
      errors,
    };
  }

  /**
   * 加载数据
   */
  loadData(data) {
    if (!Array.isArray(data) || data.length === 0) {
      this.hot.loadData(this.getEmptyRows(5));
      return;
    }

    this.specGroupData = {};

    const tableData = data.map((row, rowIndex) => {
      const newRow = {};

      this.columns.forEach(col => {
        if (col.data === 'spec_group') {
          // 从三个数组字段构建规格组
          this.specGroupData[rowIndex] = {
            specs: this.parseArray(row.spec_array || row['规格数组']),
            prices: this.parseArray(row.price_array || row['进货价']),
            images: this.parseArray(row.sku_images || row['sku实拍图数组']),
          };
          newRow[col.data] = '';
        } else {
          // 映射字段名
          const csvFieldMap = {
            'product_name': '产品名称',
            'title_suffix': '标题后缀',
            'spec_unit': '规格单位',
            'video_url': '视频链接',
            'availability': '到货状态(能上或者不能上)',
            'size_chart_url': '尺码图',
          };
          newRow[col.data] = row[col.data] || row[csvFieldMap[col.data]] || '';
        }
      });

      return newRow;
    });

    this.hot.loadData(tableData);
    this.updateRowCount();
  }

  /**
   * 解析数组（支持 JSON 字符串或已解析数组）
   */
  parseArray(value) {
    if (!value) return [];
    if (Array.isArray(value)) return value;

    const strValue = String(value).trim();
    if (!strValue) return [];

    if (strValue.startsWith('[')) {
      try {
        const parsed = JSON.parse(strValue);
        if (Array.isArray(parsed)) return parsed;
      } catch (e) {
        // 继续
      }
    }

    // 逗号分隔
    return strValue.split(',').map(s => s.trim()).filter(s => s);
  }

  /**
   * 更新行数显示
   */
  updateRowCount() {
    const count = this.getValidRowCount();
    const countEl = document.getElementById('table-row-count');
    if (countEl) {
      countEl.textContent = `已输入 ${count} 行`;
    }
  }

  /**
   * 获取有效行数（排除仅有默认值的空行）
   */
  getValidRowCount() {
    const allData = this.hot.getData();
    let count = 0;

    allData.forEach((row, rowIndex) => {
      let hasRealData = false;

      this.columns.forEach((col, colIndex) => {
        const value = row[colIndex];

        if (col.data === 'spec_group') {
          // 规格组：检查是否有规格数据
          const specData = this.getSpecGroupForRow(rowIndex);
          if (specData.specs.length > 0) hasRealData = true;
        } else if (col.data === 'availability') {
          // 跳过默认值字段，不算作有效数据
        } else {
          // 其他字段：非空即有效
          if (value !== null && value !== undefined && String(value).trim() !== '') {
            hasRealData = true;
          }
        }
      });

      if (hasRealData) count++;
    });

    return count;
  }

  /**
   * 触发自动保存
   */
  triggerAutosave() {
    if (this.autosaveTimeout) {
      clearTimeout(this.autosaveTimeout);
    }
    this.autosaveTimeout = setTimeout(() => {
      this.saveDraft();
    }, 2000);
  }

  /**
   * 保存草稿
   */
  saveDraft() {
    try {
      const data = {
        tableData: this.hot.getData(),
        specGroupData: this.specGroupData,
        savedAt: new Date().toISOString(),
      };
      localStorage.setItem(this.draftKey, JSON.stringify(data));
    } catch (e) {
      console.warn('保存草稿失败:', e);
    }
  }

  /**
   * 检查草稿
   */
  checkDraft() {
    try {
      const saved = localStorage.getItem(this.draftKey);
      if (saved) {
        const data = JSON.parse(saved);
        const savedAt = new Date(data.savedAt);
        const now = new Date();
        const hoursDiff = (now - savedAt) / (1000 * 60 * 60);

        if (hoursDiff < 24) {
          if (confirm(`发现 ${savedAt.toLocaleString()} 的草稿，是否恢复？`)) {
            // 将二维数组转换为对象数组（Handsontable 在配置 columns.data 时需要对象格式）
            const tableData = this.convertArrayToObjects(data.tableData);
            this.hot.loadData(tableData);
            this.specGroupData = data.specGroupData || {};
            this.updateRowCount();
            this.hot.render();
          }
        }
      }
    } catch (e) {
      console.warn('加载草稿失败:', e);
    }
  }

  /**
   * 将二维数组转换为对象数组
   */
  convertArrayToObjects(arrayData) {
    if (!Array.isArray(arrayData) || arrayData.length === 0) {
      return this.getEmptyRows(5);
    }

    // 检查第一行是否已经是对象
    if (typeof arrayData[0] === 'object' && !Array.isArray(arrayData[0])) {
      return arrayData;
    }

    // 二维数组转对象数组
    return arrayData.map(row => {
      const obj = {};
      this.columns.forEach((col, index) => {
        obj[col.data] = row[index] !== undefined ? row[index] : '';
      });
      return obj;
    });
  }

  /**
   * 清除草稿
   */
  clearDraft() {
    localStorage.removeItem(this.draftKey);
  }

  /**
   * 销毁表格
   */
  destroy() {
    if (this.hot) {
      this.hot.destroy();
      this.hot = null;
    }
  }
}

// 导出供全局使用
window.TableEditor = TableEditor;
