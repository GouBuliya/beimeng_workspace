/**
 * @PURPOSE: CSV 导入导出工具
 * @OUTLINE:
 *   - parseCSV(): 解析 CSV 内容
 *   - generateCSV(): 生成 CSV 内容
 *   - downloadCSV(): 下载 CSV 文件
 *   - importCSVFile(): 导入 CSV 文件到表格
 *   - exportTableToCSV(): 导出表格数据为 CSV
 * @DEPENDENCIES:
 *   - 无外部依赖
 */

const CSVUtils = {
  /**
   * 列名映射：中文别名 -> 英文字段名
   */
  COLUMN_ALIASES: {
    // 产品名称
    '产品名称': 'product_name',
    '商品名称': 'product_name',
    '商品': 'product_name',
    'product_name': 'product_name',

    // 负责人
    '主品负责人': 'owner',
    '负责人': 'owner',
    'owner': 'owner',

    // 型号
    '型号': 'model_number',
    '货号': 'model_number',
    'model_number': 'model_number',

    // 颜色/规格
    '颜色/规格': 'color_spec',
    '颜色规格': 'color_spec',
    '颜色': 'color_spec',
    '规格': 'color_spec',
    'color_spec': 'color_spec',

    // 采集数量
    '采集数量': 'collect_count',
    '数量': 'collect_count',
    'collect_count': 'collect_count',

    // 进货价
    '进货价': 'cost_price',
    '成本价': 'cost_price',
    '价格': 'cost_price',
    'cost_price': 'cost_price',

    // 规格单位
    '规格单位': 'spec_unit',
    '单位': 'spec_unit',
    'spec_unit': 'spec_unit',

    // 规格选项
    '规格选项': 'spec_options',
    'spec_options': 'spec_options',

    // 实拍图
    '实拍图': 'image_files',
    '实拍图片': 'image_files',
    '图片': 'image_files',
    '图片链接': 'image_files',
    'image_files': 'image_files',

    // 尺码图
    '尺码图': 'size_chart_image_url',
    '尺码表': 'size_chart_image_url',
    'size_chart_image_url': 'size_chart_image_url',

    // 视频链接
    '视频链接': 'product_video_url',
    '产品视频': 'product_video_url',
    '视频': 'product_video_url',
    'product_video_url': 'product_video_url',
  },

  /**
   * 字段显示名称
   */
  COLUMN_HEADERS: {
    'product_name': '产品名称',
    'owner': '主品负责人',
    'model_number': '型号',
    'color_spec': '颜色/规格',
    'collect_count': '采集数量',
    'cost_price': '进货价',
    'spec_unit': '规格单位',
    'spec_options': '规格选项',
    'image_files': '实拍图',
    'size_chart_image_url': '尺码图',
    'product_video_url': '视频链接',
  },

  /**
   * 解析 CSV 内容
   * @param {string} content - CSV 文本内容
   * @returns {Array<Object>} 解析后的数据数组
   */
  parseCSV(content) {
    const lines = this.splitCSVLines(content);
    if (lines.length < 2) {
      return [];
    }

    // 解析表头
    const headers = this.parseCSVLine(lines[0]);
    const fieldMapping = this.mapHeaders(headers);

    // 解析数据行
    const data = [];
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;

      const values = this.parseCSVLine(line);
      const row = {};

      headers.forEach((header, index) => {
        const fieldName = fieldMapping[header];
        if (fieldName) {
          row[fieldName] = values[index] || '';
        }
      });

      // 检查是否有实际数据
      if (Object.values(row).some(v => v && v.trim())) {
        data.push(row);
      }
    }

    return data;
  },

  /**
   * 分割 CSV 行（处理多行单元格）
   */
  splitCSVLines(content) {
    const lines = [];
    let currentLine = '';
    let inQuotes = false;

    for (let i = 0; i < content.length; i++) {
      const char = content[i];
      const nextChar = content[i + 1];

      if (char === '"') {
        if (inQuotes && nextChar === '"') {
          currentLine += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
          currentLine += char;
        }
      } else if ((char === '\n' || (char === '\r' && nextChar === '\n')) && !inQuotes) {
        if (currentLine.trim()) {
          lines.push(currentLine);
        }
        currentLine = '';
        if (char === '\r') i++;
      } else if (char !== '\r') {
        currentLine += char;
      }
    }

    if (currentLine.trim()) {
      lines.push(currentLine);
    }

    return lines;
  },

  /**
   * 解析单行 CSV
   */
  parseCSVLine(line) {
    const values = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      const nextChar = line[i + 1];

      if (char === '"') {
        if (!inQuotes) {
          inQuotes = true;
        } else if (nextChar === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else if (char === ',' && !inQuotes) {
        values.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }

    values.push(current.trim());
    return values;
  },

  /**
   * 将表头映射到字段名
   */
  mapHeaders(headers) {
    const mapping = {};
    headers.forEach(header => {
      const cleaned = header.trim();
      const fieldName = this.COLUMN_ALIASES[cleaned];
      if (fieldName) {
        mapping[header] = fieldName;
      }
    });
    return mapping;
  },

  /**
   * 生成 CSV 内容
   * @param {Array<Object>} data - 数据数组
   * @param {Array<string>} fields - 字段列表
   * @returns {string} CSV 文本内容
   */
  generateCSV(data, fields) {
    if (!data || data.length === 0) {
      return '';
    }

    // 使用指定字段或从数据推断
    const columns = fields || Object.keys(this.COLUMN_HEADERS);

    // 生成表头（使用中文名称）
    const headerRow = columns.map(field => {
      const displayName = this.COLUMN_HEADERS[field] || field;
      return this.escapeCSVValue(displayName);
    });

    // 生成数据行
    const dataRows = data.map(row => {
      return columns.map(field => {
        let value = row[field];

        // 处理数组值
        if (Array.isArray(value)) {
          value = JSON.stringify(value);
        }

        return this.escapeCSVValue(value || '');
      });
    });

    // 组合为 CSV
    const allRows = [headerRow, ...dataRows];
    return allRows.map(row => row.join(',')).join('\n');
  },

  /**
   * 转义 CSV 值
   */
  escapeCSVValue(value) {
    const strValue = String(value);
    // 如果包含逗号、引号、换行，需要用引号包裹
    if (strValue.includes(',') || strValue.includes('"') || strValue.includes('\n')) {
      return '"' + strValue.replace(/"/g, '""') + '"';
    }
    return strValue;
  },

  /**
   * 下载 CSV 文件
   * @param {string} content - CSV 内容
   * @param {string} filename - 文件名
   */
  downloadCSV(content, filename = 'selection_data.csv') {
    // 添加 BOM 以支持 Excel 中文显示
    const bom = '\uFEFF';
    const blob = new Blob([bom + content], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.style.display = 'none';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  },

  /**
   * 导入 CSV 文件
   * @param {File} file - 文件对象
   * @returns {Promise<Array<Object>>} 解析后的数据
   */
  importCSVFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onload = (e) => {
        try {
          const content = e.target.result;
          const data = this.parseCSV(content);
          resolve(data);
        } catch (error) {
          reject(new Error('CSV 解析失败: ' + error.message));
        }
      };

      reader.onerror = () => {
        reject(new Error('文件读取失败'));
      };

      // 尝试多种编码
      reader.readAsText(file, 'UTF-8');
    });
  },

  /**
   * 导出表格数据为 CSV 并下载
   * @param {TableEditor} tableEditor - 表格编辑器实例
   * @param {string} filename - 文件名
   */
  exportTableToCSV(tableEditor, filename) {
    const data = tableEditor.getData();
    if (data.length === 0) {
      alert('表格中没有数据可导出');
      return;
    }

    const fields = tableEditor.columns.map(c => c.data);
    const csv = this.generateCSV(data, fields);
    this.downloadCSV(csv, filename);
  },

  /**
   * 从 CSV 文件导入到表格
   * @param {File} file - 文件对象
   * @param {TableEditor} tableEditor - 表格编辑器实例
   * @returns {Promise<number>} 导入的行数
   */
  async importCSVToTable(file, tableEditor) {
    const data = await this.importCSVFile(file);
    if (data.length === 0) {
      throw new Error('CSV 文件为空或格式不正确');
    }

    tableEditor.loadData(data);
    return data.length;
  },
};

// 导出到全局
window.CSVUtils = CSVUtils;
