# europe_trip_2026 - Design Spec

## I. Project Information

| Item | Value |
| ---- | ----- |
| **Project Name** | 法意瑞家庭旅行 2026 |
| **Canvas Format** | PPT 16:9 (1280×720) |
| **Page Count** | 14 |
| **Design Style** | 旅行手册风 — 温馨活泼实用 |
| **Target Audience** | 家庭成员（父母+11岁女儿） |
| **Use Case** | 行前参考手册 |
| **Created Date** | 2026-06-27 |

---

## II. Canvas Specification

| Property | Value |
| -------- | ----- |
| **Format** | PPT 16:9 |
| **Dimensions** | 1280×720 |
| **viewBox** | `0 0 1280 720` |
| **Margins** | 左右60px，上下50px |
| **Content Area** | 1160×620 |

---

## III. Visual Theme

### Theme Style

- **Style**: 旅行手册风 — 温馨、活泼、实用
- **Theme**: Light theme
- **Tone**: 活力、温馨、探索感

### Color Scheme

| Role | HEX | Purpose |
| ---- | --- | ------- |
| **Background** | `#FFFFFF` | 页面白底 |
| **Secondary bg** | `#F0F4F8` | 卡片浅蓝灰底 |
| **Primary** | `#1B4965` | 深蓝（海洋/天空）— 标题、主要色块 |
| **Accent** | `#E8983F` | 橙黄（夕阳/活力）— 高亮、重点 |
| **Secondary accent** | `#5FA8D3` | 浅蓝（湖泊/冰川）— 次要强调 |
| **Body text** | `#2D3748` | 深灰主文字 |
| **Secondary text** | `#718096` | 中灰标注 |
| **Tertiary text** | `#A0AEC0` | 淡灰页脚 |
| **Border/divider** | `#CBD5E0` | 卡片边框 |
| **Success** | `#48BB78` | 绿色（自然/确认） |
| **Warning** | `#E53E3E` | 红色（提醒） |

---

## IV. Typography System

**Typography direction**: 现代CJK无衬线，清晰易读

| Role | Chinese | English | Fallback tail |
| ---- | ------- | ------- | ------------- |
| **Title** | `"Microsoft YaHei"` | `Arial` | `sans-serif` |
| **Body** | `"Microsoft YaHei"` | `Arial` | `sans-serif` |

**Per-role font stacks**:

- Title: `"Microsoft YaHei", "PingFang SC", Arial, sans-serif`
- Body: `"Microsoft YaHei", "PingFang SC", Arial, sans-serif`

### Font Size Hierarchy

**Baseline**: Body font size = 20px

| Purpose | Size | Weight |
| ------- | ---- | ------ |
| Cover title | 56px | Bold |
| Chapter opener | 44px | Bold |
| Page title | 32px | Bold |
| Subtitle | 26px | SemiBold |
| **Body** | **20px** | Regular |
| Annotation | 16px | Regular |
| Footer | 12px | Regular |

---

## V. Layout Principles

### Page Structure

- **Header**: 60-80px（页标题+日期标签）
- **Content**: 520-560px（主体内容）
- **Footer**: 30px（页码+项目名）

### Layout Patterns

| Pattern | Used for |
| ------- | -------- |
| Full-bleed + floating text | 封面、章节页 |
| Three/four column cards | 每日行程安排 |
| Symmetric split (5:5) | 酒店信息+景点 |
| Top-bottom split | 费用表格、交通汇总 |

---

## VI. Icon Usage Specification

| Purpose | Icon Path | Page |
| ------- | --------- | ---- |
| 飞机 | `chunk-filled/plane` | 交通页 |
| 火车 | `chunk-filled/train` | 交通页 |
| 酒店 | `chunk-filled/building` | 全程 |
| 餐饮 | `chunk-filled/utensils` | 行程页 |
| 景点 | `chunk-filled/map-pin` | 行程页 |
| 日历 | `chunk-filled/calendar` | 全程 |
| 费用 | `chunk-filled/coins` | 费用页 |

---

## VII. Visualization Reference List

无数据可视化图表页。

---

## VIII. Image Resource List

无外部图片。使用纯SVG矢量设计（图标+色块+文字）。

---

## IX. Content Outline

### Part 1: 封面与总览

#### Slide 01 - 封面
- **Layout**: 深蓝渐变全屏背景 + 居中大标题
- **Title**: 法意瑞家庭旅行
- **Subtitle**: 2026.7.25 — 8.8 · 15天欧洲三国探索之旅
- **Info**: Family Trip · Paris → Swiss → Italy

#### Slide 02 - 行程总览
- **Layout**: 横向时间线 + 三国分段
- **Content**: 巴黎(3天) → 瑞士(5天) → 意大利(8天) 路线图

#### Slide 03 - 费用汇总
- **Layout**: 表格式费用明细
- **Content**: 12家酒店费用 + 交通费用，合计约¥34,000

### Part 2: 法国巴黎

#### Slide 04 - 巴黎篇 (7/25-7/27)
- **Layout**: 三列日卡 + 酒店信息条
- **Content**: Day1凯旋门+铁塔+游船 / Day2卢浮宫+圣母院 / Day3飞苏黎世
- **Hotel**: 巴黎凯旋门万丽酒店 ¥6,233

### Part 3: 瑞士

#### Slide 05 - 苏黎世→卢塞恩 (7/27-7/29)
- **Layout**: 双列日卡 + 交通信息
- **Content**: TGV到达苏黎世 / 卢塞恩瑞吉山徒步
- **Hotels**: 苏黎世蒙塔那 ¥1,785 / 沃尔德斯塔得霍夫 ¥1,807

#### Slide 06 - 因特拉肯→格林德瓦 (7/29-7/31)
- **Layout**: 双列日卡 + 少女峰亮点
- **Content**: 因特拉肯环湖 / 少女峰经典徒步路线
- **Hotels**: 多林特 ¥3,016 / 德比品质 ¥2,187 / 比滕贝格 ¥3,210

### Part 4: 意大利

#### Slide 07 - 米兰 (8/1-8/2)
- **Layout**: 双列日卡 + 购物信息
- **Content**: EC27到达米兰 / 米兰大教堂+奥特莱斯
- **Hotels**: 美利亚怡思得 ¥1,456 / 杜拉克 ¥1,337

#### Slide 08 - 多洛米蒂 (8/3-8/4)
- **Layout**: 双列日卡 + UNESCO亮点
- **Content**: 刀峰山Seceda / 三峰Tre Cime / 布拉耶斯湖
- **Hotels**: My Daum公寓 ¥3,174 / 太阳高尔夫 ¥2,104

#### Slide 09 - 威尼斯 (8/5)
- **Layout**: 单日大卡 + 水城亮点
- **Content**: 圣马可广场 / 大运河 / 贡多拉
- **Hotel**: 基娅拉小屋 ¥1,172

#### Slide 10 - 罗马 (8/6-8/8)
- **Layout**: 双列日卡 + 经典景点
- **Content**: 斗兽场+梵蒂冈 / 特莱维喷泉+西班牙广场
- **Hotel**: 罗马宫廷大酒店 ¥3,723

### Part 5: 实用信息

#### Slide 11 - 全程交通汇总
- **Layout**: 表格式交通明细
- **Content**: 4段主要交通（北京✈️巴黎 / TGV巴黎→苏黎世 / EC苏黎世→米兰 / ✈️威尼斯→罗马）

#### Slide 12 - 行李清单与实用Tips
- **Layout**: 双列清单
- **Content**: 必带物品 + 瑞士通票/自驾注意事项/餐厅推荐

---

## X. Speaker Notes Requirements

每页一份讲解备注，包含行程重点和注意事项提示。

---

## XI. Technical Constraints Reminder

1. viewBox: `0 0 1280 720`
2. 背景使用 `<rect>` 元素
3. 文字换行使用 `<tspan>`
4. 透明度使用 `fill-opacity` / `stroke-opacity`
5. 禁用: `mask`, `<style>`, `class`, `foreignObject`, `textPath`, `animate*`, `script`
6. Unicode符号直接写原始字符，XML保留字转义
