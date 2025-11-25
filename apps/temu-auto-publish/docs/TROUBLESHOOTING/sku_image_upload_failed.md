# SKU图片上传失败问题排查

## 问题现象

妙手ERP提示："成功上传0个，失败1个，去重0个；失败原因：请输入正确的网络图片地址"

## 常见原因

### 1. URL包含中文字符（最常见）

**问题**：URL路径中包含中文，如 `https://xxx.com/10月新品/A045.jpg`

**解决**：已自动进行URL编码，将中文转换为 `%E5%8D%81%E6%9C%88...`

**验证**：
```bash
# 在浏览器中访问原始URL和编码后的URL，确保都能正常显示图片
```

### 2. 域名白名单限制

妙手ERP可能只接受特定的图床域名：
- ✅ 阿里云OSS（`*.aliyuncs.com`）
- ✅ 七牛云（`*.qiniucdn.com`）
- ✅ 腾讯云COS（`*.myqcloud.com`）
- ❌ 其他自建图床可能被拒绝

**解决**：使用妙手支持的图床服务

### 3. 图片URL不是直链

**问题**：URL返回的是HTML页面而不是图片

**验证**：
```bash
# 使用 curl 测试
curl -I "你的图片URL"

# 响应头应该包含：
Content-Type: image/jpeg
# 或
Content-Type: image/png
```

### 4. 图片格式或大小不符合要求

妙手可能对图片有以下要求：
- **格式**：JPG、PNG、WEBP
- **大小**：通常不超过5MB
- **尺寸**：建议800x800或更大

### 5. SSL证书问题

如果是HTTPS链接，确保：
- ✅ 证书有效
- ✅ 没有自签名证书
- ✅ 证书链完整

## 解决方案

### 方案1：确保URL编码正确

已在代码中实现自动URL编码：

```python
# src/browser/first_edit_dialog_codegen.py
def _normalize_input_url(raw_text: str) -> str:
    # 自动将中文路径编码为 %E5%... 格式
    from urllib.parse import quote, urlparse, urlunparse
    # ...
```

### 方案2：使用妙手认可的图床

如果当前图床不被接受，可以：

1. **上传到阿里云OSS**（推荐）
   ```python
   # 使用阿里云OSS Python SDK
   import oss2
   
   auth = oss2.Auth('access_key', 'secret_key')
   bucket = oss2.Bucket(auth, 'endpoint', 'bucket_name')
   bucket.put_object_from_file('path/image.jpg', 'local_file.jpg')
   ```

2. **使用妙手自己的图床**
   - 通过妙手ERP界面上传
   - 获取妙手生成的CDN链接

### 方案3：图片预处理

确保图片符合要求：

```bash
# 使用 ImageMagick 调整图片
convert input.jpg -resize 800x800 -quality 85 output.jpg

# 或使用 Python PIL
from PIL import Image
img = Image.open('input.jpg')
img = img.resize((800, 800), Image.LANCZOS)
img.save('output.jpg', quality=85, optimize=True)
```

## 调试步骤

1. **验证URL可访问性**
   ```bash
   curl -I "https://your-image-url.jpg"
   ```

2. **检查URL编码**
   ```python
   from urllib.parse import quote
   encoded = quote('10月新品', safe='')
   print(encoded)  # 应输出: %E5%8D%81%E6%9C%88%E6%96%B0%E5%93%81
   ```

3. **查看完整的编码后URL**
   - 检查日志中的 "URL编码: xxx -> xxx" 信息
   - 复制编码后的URL在浏览器中验证

4. **测试不同的图床**
   - 临时上传到阿里云OSS测试
   - 使用公开的图床服务测试

## 当前实现

代码已自动处理URL编码，会在日志中显示：

```
[DEBUG] URL编码: https://xxx.com/10月新品/A045.jpg -> https://xxx.com/%E5%8D%81%E6%9C%88%E6%96%B0%E5%93%81/A045.jpg
```

如果编码后仍然失败，说明是域名白名单或其他限制。

## 建议

**短期解决**：
- 将图片上传到阿里云OSS
- 使用英文路径命名，避免中文

**长期方案**：
- 建立标准的图床服务
- 所有图片统一使用阿里云OSS
- 路径全部使用英文或数字


