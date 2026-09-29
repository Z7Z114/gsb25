# 昆虫蛋白产业化会议纪要系统

一个全栈应用，用于整理昆虫蛋白产业化会议的可持续食品纪要：前端展示养殖环境数据与营养分析，
后端处理农业专家与企业家双方的对话——先用 librosa 去掉会场风扇等背景噪声，再用 Whisper 识别
对话里提到的昆虫学名，用 pyannote 区分产研双方，最后由 OpenAI 生成扩产方案、法规挑战与营销
策略摘要，并把 Markdown 纪要邮件发给投资者与合作伙伴。

- 后端：FastAPI + SQLAlchemy + SQLite（`backend/`，应用入口 `backend/main.py`）
- 前端：React 18 + TypeScript + Vite + Recharts（`frontend/`，仅脚手架，不在本题范围内）
- 语音与 AI：librosa / Whisper / pyannote / OpenAI 全部是**可选**重型依赖（见 `requirements-ml.txt`）

## 功能特性

- **音频净化**：librosa 谱减法 + 维纳滤波去除风扇等低频背景噪声
- **语音转写**：Whisper 转写会议对话，并抽取对话中出现的昆虫中文名与拉丁学名
- **说话人分离**：pyannote 分离说话人，并按发言内容把说话人归为「农业专家（研发侧）」或
  「企业家（产业侧）」
- **结构化纪要**：OpenAI 生成扩产方案、法规挑战、营销策略、行动项与风险评估
- **数据沉淀**：把纪要里的昆虫营养数据与养殖环境参数写入数据库，供看板与营养页展示
- **邮件投递**：把 Markdown 纪要以 HTML + 纯文本双格式发送给投资者或合作伙伴

## 项目结构

```
.
├── requirements.txt              # 轻量依赖（可离线跑测试）
├── requirements-ml.txt           # 可选重型依赖（librosa / Whisper / pyannote / torch）
├── .env.example                  # 环境变量样例
├── backend/
│   ├── main.py                   # FastAPI 入口（uvicorn backend.main:app）
│   ├── database/models.py        # 数据库引擎、会话与 ORM 模型
│   ├── schemas/meeting.py        # Pydantic 请求 / 响应模型
│   ├── audio/processor.py        # 降噪
│   ├── audio/transcriber.py      # Whisper 转写与昆虫识别
│   ├── audio/diarizer.py         # 说话人分离与角色判定
│   ├── ai/summary_generator.py   # 会议纪要生成
│   ├── email/sender.py           # Markdown 邮件投递
│   └── tests/                    # 冒烟测试
└── frontend/                     # React 前端脚手架
```

## 快速开始

```bash
pip install -r requirements.txt                    # 轻量依赖；重型语音依赖见 requirements-ml.txt
uvicorn backend.main:app --reload --port 8000      # 后端
cd frontend && npm install && npm run dev          # 前端（http://localhost:3000）
```

配置全部来自环境变量（可配置项见 `.env.example`）：`DATABASE_URL`、`UPLOAD_DIR`、
`CLEANED_DIR`、`OPENAI_API_KEY`、`PYANNOTE_AUTH_TOKEN`、`SMTP_*`。

`OPENAI_API_KEY` / `PYANNOTE_AUTH_TOKEN` / `SMTP_*` 全部留空时，后端走离线分支：
不联网、不加载模型，也仍然能把一次会议处理成一份可读的结构化纪要。

## API 端点

- `GET /` 服务信息
- `POST /api/meetings`、`GET /api/meetings`、`GET /api/meetings/{meeting_id}`
- `POST /api/meetings/{meeting_id}/audio` 上传会议录音
- `POST /api/process-audio` 后台降噪 + 转写 + 说话人分离
- `POST /api/generate-summary` 后台生成结构化纪要
- `POST /api/send-email` 投递纪要邮件
- `GET /api/dashboard/stats` 看板统计
- `GET /api/insects/nutrition`、`GET /api/environment/data`
- `GET /api/transcripts/{transcript_id}`、`GET /api/summaries/{summary_id}`、
  `GET /api/summaries/{summary_id}/markdown`

## 行为规格（验收标准）

以下是本系统的验收标准，与实现不一致的一律视为缺陷。所有接口在资源不存在时统一返回 404，
参数或资源归属非法时返回 4xx 而不是 500。

### A. 会议与看板
- **A1** `GET /api/dashboard/stats` 必须返回 200，且响应体包含 `total_meetings`、
  `total_insect_species`、`avg_protein_content`、`total_processing_minutes`、`recent_meetings`
  五个字段；空库上也必须返回 200。
- **A2** `avg_protein_content` 是所有 `InsectData` 行 `protein_content` 的算术平均；
  没有任何有效值时为 `0`。
- **A3** `total_insect_species` 是按 `chinese_name` 去重后的物种数。
- **A4** `POST /api/meetings` 返回 200 且响应体带 `id`/`status`/`created_at`；
  `GET /api/meetings/{id}` 对不存在的 id 返回 404，存在时返回 `meeting` 以及
  `audio_files`、`transcripts`、`summaries`、`insect_data`、`environment_data` 五个列表。

### B. 音频上传与处理
- **B1** 上传落盘后的文件必须真实存在，且 `POST /api/process-audio` 只受理**属于该会议**的
  录音：`meeting_id` 不存在返回 404，`audio_file_id` 不存在返回 404，录音不属于该会议返回 400。
  任何被受理的请求都不得把转录记录写到别的会议名下。
- **B2** `POST /api/process-audio` 受理成功后返回 200 且 `status` 为 `processing`。
- **B3** 后台处理成功时，会议下必须出现一条 `completed` 的转录，会议状态变为 `transcribed`；
  后台处理失败时必须把会议状态置为 `failed`，且不得留下半截转录或空摘要。

### C. 说话人角色与对话格式
- **C1** `SpeakerDiarizer.identify_roles` 的关键词打分必须计入**出现次数**：同一个关键词出现
  n 次计 n 分，而不是只计「出现过没有」。否则明显偏产业侧或偏研发侧的发言会被判成同一角色。
- **C2** 角色判定必须与片段先后顺序无关：把 `merged_segments` 反序后调用，得到的
  `speaker -> role` 映射必须与正序一致。平票（研发侧与产业侧得分相同）时按说话人标签
  `SPEAKER_xx` 的字典序裁决：标签最小的平票者判为 `expert`，其余平票者判为 `entrepreneur`。
- **C3** `SpeakerDiarizer.format_dialogue` 的时间戳：不足 1 小时用 `MM:SS`，
  达到或超过 1 小时用 `HH:MM:SS`（例如 `3661.0` → `01:01:01`）。

### D. 昆虫识别
- **D1** 转写结果里的 `detected_insects` 必须按昆虫在文本中**首次出现的先后顺序**返回
  （同名去重），不得按内置词表的声明顺序重排。

### E. 纪要生成与入库
- **E1** 未配置 `OPENAI_API_KEY`（或 OpenAI 客户端不可用）时，纪要生成必须走**确定性离线
  分支**：不联网、不抛异常，返回结构化字典，且同一份输入重复调用得到完全相同的结果。
- **E2** 离线摘要必须包含 `meeting_basic_info`、`insect_production_analysis.main_species`、
  `expansion_plan`、`regulatory_challenges`、`marketing_strategy`、`action_items`、
  `key_decisions`、`risk_assessment` 这些键（离线分支没有外部模型，各章节允许为空数组或空
  字符串，但键必须存在且内容可复现）；`main_species` 与转写得到的 `detected_insects`
  去重保序后一一对应，并带 `chinese_name` / `latin_name` 与 `nutritional_value` /
  `farming_environment` 两个子对象。
- **E3** 摘要 JSON 的 `farming_environment` 使用系统提示词里的字段名：`optimal_temperature`、
  `optimal_humidity`、`farming_density`、`growth_cycle`、`feed_conversion_rate`；
  `nutritional_value` 使用 `protein_content`、`fat_content`、`amino_acid_profile`、
  `key_nutrients`。这些字段的值可能是数字，也可能是 `"28-32℃"`、`"约 42%"`、`"60"`、
  `"14 天"` 这类字符串。
- **E4** 入库时 `optimal_temperature` 的区间解析为 `optimal_temperature_min` /
  `optimal_temperature_max`（单值时 min 与 max 相同），`optimal_humidity` 同理；
  `growth_cycle` 解析为 `growth_cycle_days`（取其中第一个整数）；
  `protein_content`、`fat_content`、`feed_conversion_rate` 取其中第一个数值；解析不出记 `0`。
  某一个物种解析失败不得影响其它物种入库。
- **E5** 同一会议重复生成纪要必须幂等：`InsectData` / `EnvironmentData` 中该会议的行数不得
  翻倍，重算结果覆盖旧值。
- **E6** 纪要生成失败（生成器抛异常，或返回的不是合法结构化摘要）时必须把会议状态置为
  `failed`，且不得写入空摘要或半截摘要；只有真正拿到结构化摘要时才允许置为 `summarized`。
- **E7** `POST /api/generate-summary` 在 `transcript_id` 不存在时返回 404。

### F. 邮件投递
- **F1** `POST /api/send-email` 在该会议没有任何摘要时返回 404。
- **F2** `recipient_type` 为 `investors` / `partners` 时使用各自的固定主题，邮件正文包含该会议
  的 Markdown 纪要。
- **F3** SMTP 抛异常时返回 `success=false`，`EmailLog.status` 为 `failed` 且 `error_message`
  非空。
- **F4** 投递成功时 `EmailLog.status` 为 `sent`，且 `EmailLog.recipients` 与请求一致。

## 已知问题

以下是真实使用中暴露出来的一部分现象（**不是全部**，验收以「行为规格」为准）：

1. 打开看板接口直接 500，一个数都看不到。
2. 录音处理完之后，会议状态一直停在原样，纪要页是空的；没有配置 `OPENAI_API_KEY` 时尤其明显。
3. 「昆虫营养」和「养殖环境」两处数据全是 0，明明会议里报了蛋白质含量和适宜温度。
4. 同一个会议反复点「生成纪要」，物种列表里会出现重复行。

## 注意事项

- Whisper / pyannote / librosa 为可选重型依赖（见 `requirements-ml.txt`），未安装时对应的
  处理环节必须优雅失败并给出确定性错误，不得在导入期崩溃。
- 前端仅为脚手架，题目范围内不需要改动前端。
