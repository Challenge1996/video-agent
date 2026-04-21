# Google Cloud 凭证配置

本项目使用 Google Cloud Text-to-Speech API 进行语音合成，需要配置凭证文件。

## 获取凭证

1. 访问 [Google Cloud Console](https://console.cloud.google.com/)
2. 创建新项目或选择现有项目
3. 搜索并启用 "Cloud Text-to-Speech API"
4. 进入 "API 和服务" > "凭据"
5. 点击 "创建凭据" > "服务账号"
6. 填写服务账号信息，点击 "创建并继续"
7. 为服务账号分配 "Editor" 或 "Text-to-Speech Admin" 角色
8. 点击 "完成"
9. 在服务账号列表中，点击刚创建的服务账号
10. 进入 "密钥" 标签页，点击 "添加密钥" > "创建新密钥"
11. 选择 JSON 格式，点击 "创建"
12. 下载的 JSON 文件就是你的凭证文件

## 配置凭证

1. 将下载的 JSON 凭证文件重命名为 `google-cloud-key.json`
2. 将文件放置到 `credentials` 目录下
3. 确保 `.env` 文件中的 `GOOGLE_APPLICATION_CREDENTIALS` 配置正确

或者，你可以设置环境变量：

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/credentials.json"
```

## 目录结构

```
credentials/
└── google-cloud-key.json  (你的凭证文件)
```

## 注意事项

- 凭证文件包含敏感信息，**不要提交到版本控制系统**
- 确保 `.gitignore` 文件中包含了 `credentials/` 目录
- 保护好你的凭证文件，防止泄露