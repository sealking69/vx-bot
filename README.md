# 微信 AI 机器人 —— "小v"

把你的 AI 助手接入微信公众号，关机后也能随时聊天！

## 工作原理

```
你(微信)  ->  微信服务器  ->  你的云服务器(FastAPI)  ->  OpenAI API
                                                     |
你(微信)  <-  微信服务器  <-  客服消息API   <-      AI回复
```

服务器部署在云端，24小时运行，你的电脑关机也不影响。

## 快速开始（三步走）

### 第一步：注册微信公众号

1. 打开 https://mp.weixin.qq.com
2. 点击"立即注册"，选择「订阅号」
3. 用你的微信扫码，按提示填写信息
4. 注册完成后进入后台

> **注意**：个人只能注册订阅号。订阅号有每日群发限制，但**被动回复和客服消息没有限制**，机器人聊天完全够用。

### 第二步：获取公众号配置

在公众号后台：

1. **设置与开发** -> **基本配置**
   - 记录「开发者ID(AppID)」
   - 点击「开发者密码(AppSecret)」-> 生成并记录
   - 「IP白名单」-> 填入你的服务器IP

2. **设置与开发** -> **基本配置** -> **服务器配置**
   - URL: `https://你的域名/wechat`
   - Token: 自己设定一个字符串（比如 `mytoken123`）
   - EncodingAESKey: 随机生成
   - 消息加解密方式：先选「明文模式」（测试通过后再改安全模式）

### 第三步：部署服务器

#### 方式 A：Railway（最简单，免费额度够用）

1. 把本项目上传到 GitHub
2. 打开 https://railway.app ，用 GitHub 登录
3. New Project -> Deploy from GitHub repo
4. 在 Variables 中填入环境变量（参考 `.env.example`）
5. 自动部署，得到一个 `xxx.railway.app` 域名

#### 方式 B：阿里云 / 腾讯云 轻量服务器

```bash
# SSH 连上服务器后：
git clone <你的仓库>
cd vx

pip install -r requirements.txt

cp .env.example .env
nano .env  # 填入你的配置

# 使用 systemd 保持运行
sudo tee /etc/systemd/system/vx-bot.service << EOF
[Unit]
Description=WeChat AI Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/vx
EnvironmentFile=/root/vx/.env
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable vx-bot
sudo systemctl start vx-bot
```

## 测试

部署成功后，在公众号后台「服务器配置」点击「提交」。
微信会发送 GET 请求验证，通过后就接通了。

然后用你的微信关注这个公众号，发送任意消息，机器人就会回复！

## 自定义机器人身份

编辑 `ai.py` 中的 `SYSTEM_PROMPT`，改成你想要的任何身份：

```python
SYSTEM_PROMPT = """你是小明，一个每天催我早睡的损友..."""
```

改完重新部署即可。

## 项目结构

```
vx/
├── main.py          # FastAPI 服务器（入口）
├── wechat.py        # 微信消息处理（签名、解密、客服消息）
├── ai.py            # OpenAI 对话（可自定义身份）
├── requirements.txt # Python 依赖
├── .env.example     # 环境变量模板
└── README.md        # 本文件
```

## 常见问题

**Q: 个人订阅号能用客服消息吗？**
A: 可以。认证过的订阅号才能用客服消息，但个人号虽然无法认证，在微信后台的「开发」->「接口权限」中，客服消息接口对未认证订阅号通常也是开放的（需要实际测试）。如果实在不行，可以用被动回复模式（5秒内直接返回AI回复）。

**Q: OpenAI API 太慢了，5秒内回不来怎么办？**
A: 代码已经用异步处理了：收到消息后立即返回空响应，AI 生成好后再通过客服消息接口发回去。

**Q: 国内服务器连不上 OpenAI API 怎么办？**
A: 在 `.env` 中设置 `OPENAI_BASE_URL` 指向一个代理地址或国内中转服务。
