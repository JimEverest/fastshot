# 代理环境下的SSL证书验证问题解决指南

## 问题描述

在使用代理服务器连接AWS S3时，可能会遇到SSL证书验证失败的错误：

```
SSL validation failed for https://xxx.s3.us-east-2.amazonaws.com/
[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
```

## 解决方案

### 方法一：在Session Manager中禁用SSL验证（推荐）

1. 打开FastShot应用
2. 按下 `Shift+F6` 打开Session Manager
3. 切换到 "Cloud Settings" 标签页
4. 在 "SSL Configuration" 部分，取消选中 "Enable SSL Certificate Verification"
5. 点击 "Save Settings" 保存配置
6. 点击 "Test Connection" 测试连接

### 方法二：手动修改配置文件

编辑 `fastshot/config.ini` 文件，在 `[CloudSync]` 部分添加或修改：

```ini
[CloudSync]
ssl_verify = False
```

### 方法三：设置环境变量（临时解决）

在运行FastShot之前设置环境变量：

```bash
# Windows
set CURL_CA_BUNDLE=
set REQUESTS_CA_BUNDLE=

# Linux/Mac
export CURL_CA_BUNDLE=""
export REQUESTS_CA_BUNDLE=""
```

## 安全注意事项

⚠️ **重要警告**：禁用SSL验证会降低连接的安全性，因为：

1. 无法验证服务器身份，可能连接到恶意服务器
2. 数据传输可能被中间人攻击
3. 不建议在生产环境中使用

## 推荐的安全做法

1. **仅在代理环境中禁用SSL验证**：只有在确认是由于代理服务器导致的证书验证问题时才禁用
2. **使用加密密钥**：确保在 "Encryption Configuration" 中设置强加密密钥
3. **限制网络访问**：确保代理服务器和网络环境的安全性
4. **定期检查**：定期检查是否可以重新启用SSL验证

## 代理配置示例

在Session Manager的代理设置中，支持以下格式：

```
# 基本代理
http://proxy.company.com:8080

# 带认证的代理
http://username:password@proxy.company.com:8080

# HTTPS代理
https://username:password@proxy.company.com:8080
```

## 测试连接

配置完成后，使用Session Manager中的 "Test Connection" 按钮验证：

1. 成功：显示 "Connection successful"
2. 失败：显示具体错误信息，根据错误信息调整配置

## 常见错误和解决方案

### 1. 代理认证失败
```
407 Proxy Authentication Required
```
**解决方案**：检查代理URL中的用户名和密码是否正确

### 2. 代理服务器无法访问
```
Connection timeout
```
**解决方案**：检查代理服务器地址和端口是否正确

### 3. AWS凭证错误
```
AWS credentials invalid
```
**解决方案**：检查AWS Access Key和Secret Key是否正确

### 4. 存储桶权限问题
```
Bucket access denied
```
**解决方案**：检查AWS凭证是否有访问指定S3存储桶的权限

## 技术实现细节

FastShot使用以下方式处理SSL验证：

1. **boto3配置**：通过 `Config(verify=False)` 禁用SSL验证
2. **urllib3警告抑制**：自动抑制SSL警告信息
3. **环境变量设置**：清空CA证书路径环境变量
4. **代理支持**：通过boto3的代理配置传递代理设置

这种实现确保了在代理环境中的兼容性，同时保持了配置的灵活性。 