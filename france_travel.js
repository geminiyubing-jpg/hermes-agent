const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9"; // 10" x 5.625"
pres.author = "Kabi";
pres.title = "探索法国";

// ── Color Palette: French Elegance ──
const NAVY    = "1B2A4E";  // deep navy
const CREAM   = "F5EFE0";  // warm cream
const GOLD    = "C9A961";  // muted gold
const ROSE    = "D4796E";  // soft rose
const WHITE   = "FFFFFF";
const DARK    = "2D2D2D";
const MUTED   = "8A8A8A";
const LIGHT   = "EDE7D9";

// ── Helper: section accent bar ──
function accentBar(slide, x, y, w, h, color) {
  slide.addShape(pres.shapes.RECTANGLE, {
    x, y, w, h,
    fill: { color: color || GOLD },
    line: { type: "none" }
  });
}

// ══════════════════════════════════════════════
// SLIDE 1: Title
// ══════════════════════════════════════════════
let s1 = pres.addSlide();
s1.background = { color: NAVY };

// Decorative top bar
s1.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 0, w: 10, h: 0.06,
  fill: { color: GOLD }, line: { type: "none" }
});

// Large title text
s1.addText("FRANCE", {
  x: 0.8, y: 1.2, w: 8.4, h: 1.5,
  fontSize: 64, fontFace: "Georgia", bold: true,
  color: WHITE, charSpacing: 20, align: "left"
});

// Subtitle
s1.addText("探索法兰西 · 浪漫与魅力之旅", {
  x: 0.85, y: 2.6, w: 7, h: 0.6,
  fontSize: 22, fontFace: "Georgia",
  color: GOLD, align: "left"
});

// Divider line
s1.addShape(pres.shapes.LINE, {
  x: 0.85, y: 3.3, w: 3, h: 0,
  line: { color: GOLD, width: 2 }
});

// Description
s1.addText("从巴黎铁塔到普罗旺斯花海，从蔚蓝海岸到卢瓦尔城堡\n一场关于艺术、美食与浪漫的旅程", {
  x: 0.85, y: 3.5, w: 7, h: 0.8,
  fontSize: 14, fontFace: "Calibri",
  color: CREAM, align: "left", lineSpacingMultiple: 1.5
});

// Bottom bar
s1.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 5.5, w: 10, h: 0.125,
  fill: { color: GOLD }, line: { type: "none" }
});

// ══════════════════════════════════════════════
// SLIDE 2: Why France / Overview
// ══════════════════════════════════════════════
let s2 = pres.addSlide();
s2.background = { color: CREAM };

accentBar(s2, 0, 0, 0.08, 5.625, NAVY);

s2.addText("为什么选择法国？", {
  x: 0.5, y: 0.4, w: 9, h: 0.7,
  fontSize: 32, fontFace: "Georgia", bold: true,
  color: NAVY, margin: 0
});

// 4 highlight cards
const highlights = [
  { title: "世界第一大旅游目的地", desc: "每年迎来超过9000万游客\n是全球最受欢迎的旅游国家", stat: "9000万+" },
  { title: "UNESCO 世界遗产", desc: "拥有45处世界文化遗产\n历史底蕴深厚", stat: "45处" },
  { title: "米其林美食天堂", desc: "世界顶级美食之都\n拥有628家米其林星级餐厅", stat: "628颗星" },
  { title: "艺术与时尚之都", desc: "卢浮宫、时装周、电影节\n全球文化与艺术的中心", stat: "∞" }
];

highlights.forEach((item, i) => {
  const col = i % 2;
  const row = Math.floor(i / 2);
  const x = 0.6 + col * 4.6;
  const y = 1.4 + row * 2.0;

  // Card background
  s2.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 4.3, h: 1.7,
    fill: { color: WHITE },
    line: { type: "none" },
    shadow: { type: "outer", color: "000000", blur: 6, offset: 2, angle: 135, opacity: 0.08 }
  });

  // Left accent
  s2.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 0.08, h: 1.7,
    fill: { color: GOLD }, line: { type: "none" }
  });

  // Stat
  s2.addText(item.stat, {
    x: x + 0.25, y: y + 0.1, w: 1.3, h: 0.7,
    fontSize: 30, fontFace: "Georgia", bold: true,
    color: ROSE, align: "left", valign: "middle", margin: 0
  });

  // Title
  s2.addText(item.title, {
    x: x + 1.6, y: y + 0.1, w: 2.5, h: 0.7,
    fontSize: 12, fontFace: "Calibri", bold: true,
    color: NAVY, align: "left", valign: "middle", margin: 0
  });

  // Description
  s2.addText(item.desc, {
    x: x + 0.25, y: y + 0.85, w: 3.8, h: 0.7,
    fontSize: 11, fontFace: "Calibri",
    color: DARK, align: "left", valign: "top", margin: 0,
    lineSpacingMultiple: 1.3
  });
});

// ══════════════════════════════════════════════
// SLIDE 3: Paris
// ══════════════════════════════════════════════
let s3 = pres.addSlide();
s3.background = { color: NAVY };

// Section number
s3.addText("01", {
  x: 0.5, y: 0.3, w: 1.5, h: 0.6,
  fontSize: 40, fontFace: "Georgia", bold: true,
  color: GOLD, align: "left", margin: 0
});

s3.addText("PARIS · 巴黎", {
  x: 0.5, y: 0.9, w: 9, h: 0.6,
  fontSize: 28, fontFace: "Georgia", bold: true,
  color: WHITE, align: "left", margin: 0
});

accentBar(s3, 0.52, 1.55, 2.5, 0.04, GOLD);

s3.addText("光之城 · 全球最浪漫的城市", {
  x: 0.5, y: 1.7, w: 5, h: 0.4,
  fontSize: 14, fontFace: "Calibri", italic: true,
  color: CREAM, align: "left", margin: 0
});

// Attraction cards
const parisSpots = [
  { name: "埃菲尔铁塔", desc: "巴黎标志，登塔俯瞰全城夜景", icon: "🗼" },
  { name: "卢浮宫", desc: "世界最大博物馆，蒙娜丽莎真迹", icon: "🎨" },
  { name: "凯旋门", desc: "香榭丽舍大街起点，历史丰碑", icon: "🏛" },
  { name: "塞纳河游船", desc: "穿城而过，两岸灯火如画", icon: "🚢" },
  { name: "蒙马特高地", desc: "圣心大教堂，画家与艺术", icon: "🖌" },
  { name: "凡尔赛宫", desc: "法国皇室辉煌，镜厅震撼", icon: "👑" }
];

parisSpots.forEach((spot, i) => {
  const col = i % 3;
  const row = Math.floor(i / 3);
  const x = 0.5 + col * 3.1;
  const y = 2.3 + row * 1.6;

  s3.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 2.9, h: 1.35,
    fill: { color: "243456" },
    line: { color: GOLD, width: 0.5, dashType: "solid" }
  });

  s3.addText(spot.icon, {
    x: x + 0.15, y: y + 0.15, w: 0.6, h: 0.6,
    fontSize: 22, align: "center", valign: "middle", margin: 0
  });

  s3.addText(spot.name, {
    x: x + 0.8, y: y + 0.15, w: 2.0, h: 0.45,
    fontSize: 13, fontFace: "Calibri", bold: true,
    color: GOLD, align: "left", valign: "middle", margin: 0
  });

  s3.addText(spot.desc, {
    x: x + 0.15, y: y + 0.75, w: 2.6, h: 0.5,
    fontSize: 10, fontFace: "Calibri",
    color: CREAM, align: "left", valign: "top", margin: 0,
    lineSpacingMultiple: 1.2
  });
});

// ══════════════════════════════════════════════
// SLIDE 4: Provence
// ══════════════════════════════════════════════
let s4 = pres.addSlide();
s4.background = { color: CREAM };

accentBar(s4, 0, 0, 0.08, 5.625, ROSE);

s4.addText("02", {
  x: 0.5, y: 0.3, w: 1.5, h: 0.6,
  fontSize: 40, fontFace: "Georgia", bold: true,
  color: ROSE, align: "left", margin: 0
});

s4.addText("PROVENCE · 普罗旺斯", {
  x: 0.5, y: 0.9, w: 9, h: 0.6,
  fontSize: 28, fontFace: "Georgia", bold: true,
  color: NAVY, align: "left", margin: 0
});

accentBar(s4, 0.52, 1.55, 2.5, 0.04, ROSE);

s4.addText("紫色花海 · 世界上最美的乡村", {
  x: 0.5, y: 1.7, w: 5, h: 0.4,
  fontSize: 14, fontFace: "Calibri", italic: true,
  color: MUTED, align: "left", margin: 0
});

// Three feature blocks
const provenceFeatures = [
  { title: "薰衣草田", desc: "6-8月是花期，瓦伦索勒高原一望无际的紫色花海，是普罗旺斯最经典的画面。", tip: "最佳花期：6月底 - 8月初" },
  { title: "石头小镇", desc: "戈尔德（Gordes）被评为法国最美村庄之一，石头垒成的房屋依山而建，如画般美丽。", tip: "必去：戈尔德 & 塞南克修道院" },
  { title: "向日葵花田", desc: "梵高笔下的阿尔勒，金黄色的向日葵与古老的罗马遗迹交相辉映。", tip: "推荐：阿尔勒 & 阿维尼翁" }
];

provenceFeatures.forEach((item, i) => {
  const x = 0.5 + i * 3.15;
  const y = 2.4;

  s4.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 2.9, h: 2.8,
    fill: { color: WHITE },
    line: { type: "none" },
    shadow: { type: "outer", color: "000000", blur: 8, offset: 3, angle: 135, opacity: 0.1 }
  });

  // Top accent
  s4.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 2.9, h: 0.08,
    fill: { color: ROSE }, line: { type: "none" }
  });

  s4.addText(item.title, {
    x: x + 0.25, y: y + 0.25, w: 2.4, h: 0.5,
    fontSize: 16, fontFace: "Georgia", bold: true,
    color: NAVY, align: "left", margin: 0
  });

  s4.addText(item.desc, {
    x: x + 0.25, y: y + 0.85, w: 2.4, h: 1.2,
    fontSize: 12, fontFace: "Calibri",
    color: DARK, align: "left", valign: "top", margin: 0,
    lineSpacingMultiple: 1.4
  });

  // Tip at bottom
  s4.addShape(pres.shapes.LINE, {
    x: x + 0.25, y: y + 2.1, w: 2.4, h: 0,
    line: { color: LIGHT, width: 1 }
  });

  s4.addText("💡 " + item.tip, {
    x: x + 0.25, y: y + 2.2, w: 2.4, h: 0.4,
    fontSize: 10, fontFace: "Calibri", italic: true,
    color: ROSE, align: "left", margin: 0
  });
});

// ══════════════════════════════════════════════
// SLIDE 5: Côte d'Azur
// ══════════════════════════════════════════════
let s5 = pres.addSlide();
s5.background = { color: NAVY };

s5.addText("03", {
  x: 0.5, y: 0.3, w: 1.5, h: 0.6,
  fontSize: 40, fontFace: "Georgia", bold: true,
  color: GOLD, align: "left", margin: 0
});

s5.addText("CÔTE D'AZUR · 蔚蓝海岸", {
  x: 0.5, y: 0.9, w: 9, h: 0.6,
  fontSize: 28, fontFace: "Georgia", bold: true,
  color: WHITE, align: "left", margin: 0
});

accentBar(s5, 0.52, 1.55, 2.5, 0.04, GOLD);

s5.addText("阳光 · 沙滩 · 地中海的蓝色梦境", {
  x: 0.5, y: 1.7, w: 5, h: 0.4,
  fontSize: 14, fontFace: "Calibri", italic: true,
  color: CREAM, align: "left", margin: 0
});

// Stats row
const stats = [
  { num: "300+", label: "年日照天数", unit: "天" },
  { num: "120km", label: "海岸线长度", unit: "公里" },
  { num: "25°C", label: "夏季平均水温", unit: "度" }
];

stats.forEach((item, i) => {
  const x = 0.5 + i * 3.1;

  s5.addShape(pres.shapes.RECTANGLE, {
    x, y: 2.3, w: 2.9, h: 1.0,
    fill: { color: "243456" },
    line: { type: "none" }
  });

  s5.addText(item.num, {
    x: x + 0.2, y: 2.35, w: 1.5, h: 0.9,
    fontSize: 32, fontFace: "Georgia", bold: true,
    color: GOLD, align: "left", valign: "middle", margin: 0
  });

  s5.addText(item.label, {
    x: x + 1.5, y: 2.35, w: 1.3, h: 0.9,
    fontSize: 12, fontFace: "Calibri",
    color: CREAM, align: "left", valign: "middle", margin: 0,
    lineSpacingMultiple: 1.2
  });
});

// City highlights
s5.addText("必去城市", {
  x: 0.5, y: 3.6, w: 3, h: 0.4,
  fontSize: 16, fontFace: "Georgia", bold: true,
  color: GOLD, margin: 0
});

const cities = [
  "尼斯 Nice — 天使湾与老城区，蔚蓝海岸门户",
  "摩纳哥 Monaco — 世界第二小国，赌场与F1赛道",
  "戛纳 Cannes — 国际电影节之城，海滨大道",
  "圣保罗·德旺斯 — 中世纪悬崖小镇，艺术画廊"
];

cities.forEach((city, i) => {
  s5.addText("▸ " + city, {
    x: 0.5, y: 4.05 + i * 0.35, w: 9, h: 0.32,
    fontSize: 12, fontFace: "Calibri",
    color: CREAM, align: "left", margin: 0
  });
});

// ══════════════════════════════════════════════
// SLIDE 6: Loire Valley & Bordeaux
// ══════════════════════════════════════════════
let s6 = pres.addSlide();
s6.background = { color: CREAM };

accentBar(s6, 0, 0, 0.08, 5.625, NAVY);

// Left side: Loire Valley
s6.addText("04", {
  x: 0.5, y: 0.3, w: 1.0, h: 0.6,
  fontSize: 36, fontFace: "Georgia", bold: true,
  color: NAVY, margin: 0
});

s6.addText("卢瓦尔河谷", {
  x: 0.5, y: 0.9, w: 4.5, h: 0.6,
  fontSize: 24, fontFace: "Georgia", bold: true,
  color: NAVY, margin: 0
});

accentBar(s6, 0.52, 1.5, 1.5, 0.03, GOLD);

s6.addText("「法国的花园」· 皇家城堡群", {
  x: 0.5, y: 1.65, w: 4.5, h: 0.35,
  fontSize: 12, fontFace: "Calibri", italic: true,
  color: MUTED, margin: 0
});

const loireItems = [
  "香波堡 Chambord — 文艺复兴建筑典范",
  "舍农索堡 Chenonceau — 横跨河流的「女人堡」",
  "昂布瓦兹堡 Amboise — 达芬奇安葬之地",
  "300+ 座城堡散落在河谷之间"
];

loireItems.forEach((item, i) => {
  s6.addShape(pres.shapes.OVAL, {
    x: 0.55, y: 2.2 + i * 0.55 + 0.08, w: 0.12, h: 0.12,
    fill: { color: GOLD }, line: { type: "none" }
  });
  s6.addText(item, {
    x: 0.8, y: 2.2 + i * 0.55, w: 4.2, h: 0.5,
    fontSize: 12, fontFace: "Calibri",
    color: DARK, align: "left", valign: "middle", margin: 0
  });
});

// Divider
s6.addShape(pres.shapes.LINE, {
  x: 5.0, y: 0.5, w: 0, h: 4.6,
  line: { color: LIGHT, width: 1 }
});

// Right side: Bordeaux
s6.addText("05", {
  x: 5.3, y: 0.3, w: 1.0, h: 0.6,
  fontSize: 36, fontFace: "Georgia", bold: true,
  color: ROSE, margin: 0
});

s6.addText("波尔多", {
  x: 5.3, y: 0.9, w: 4.5, h: 0.6,
  fontSize: 24, fontFace: "Georgia", bold: true,
  color: NAVY, margin: 0
});

accentBar(s6, 5.32, 1.5, 1.5, 0.03, ROSE);

s6.addText("「世界红酒之都」· 葡萄酒的圣地", {
  x: 5.3, y: 1.65, w: 4.5, h: 0.35,
  fontSize: 12, fontFace: "Calibri", italic: true,
  color: MUTED, margin: 0
});

const bordeauxItems = [
  "梅多克 Médoc — 拉菲、拉图等顶级酒庄",
  "圣埃美隆 Saint-Émilion — 世界遗产小镇",
  "葡萄酒博物馆 La Cité du Vin — 沉浸式体验",
  "18世纪古典建筑群，整座城市为世界遗产"
];

bordeauxItems.forEach((item, i) => {
  s6.addShape(pres.shapes.OVAL, {
    x: 5.35, y: 2.2 + i * 0.55 + 0.08, w: 0.12, h: 0.12,
    fill: { color: ROSE }, line: { type: "none" }
  });
  s6.addText(item, {
    x: 5.6, y: 2.2 + i * 0.55, w: 4.0, h: 0.5,
    fontSize: 12, fontFace: "Calibri",
    color: DARK, align: "left", valign: "middle", margin: 0
  });
});

// Bottom tip
s6.addText("🍷 贴士：参加酒庄品鉴游（Dégustation），提前在官网预约", {
  x: 0.5, y: 4.8, w: 9, h: 0.5,
  fontSize: 11, fontFace: "Calibri", italic: true,
  color: MUTED, align: "center", margin: 0
});

// ══════════════════════════════════════════════
// SLIDE 7: French Cuisine
// ══════════════════════════════════════════════
let s7 = pres.addSlide();
s7.background = { color: NAVY };

s7.addText("FRENCH CUISINE", {
  x: 0.5, y: 0.3, w: 9, h: 0.6,
  fontSize: 28, fontFace: "Georgia", bold: true,
  color: WHITE, align: "left", margin: 0
});

accentBar(s7, 0.52, 0.95, 2.5, 0.04, GOLD);

s7.addText("法国美食 · 值得专程飞一趟的味道", {
  x: 0.5, y: 1.1, w: 6, h: 0.4,
  fontSize: 14, fontFace: "Calibri", italic: true,
  color: CREAM, align: "left", margin: 0
});

// Food grid
const foods = [
  { name: "🥐 可颂", desc: "酥脆黄油味的经典早餐" },
  { name: "🐌 法式蜗牛", desc: "蒜香黄油烤制，巴黎必尝" },
  { name: "🧀 法式奶酪", desc: "超过400种，搭配红酒绝配" },
  { name: "🥩 红酒炖牛肉", desc: "勃艮第经典，浓郁醇香" },
  { name: "🫕 法式洋葱汤", desc: "焦香奶酪覆盖，温暖治愈" },
  { name: "🍰 马卡龙", desc: "色彩缤纷，甜而不腻" },
  { name: "🍷 波尔多红酒", desc: "世界顶级葡萄酒产区" },
  { name: "🍮 焦糖布丁", desc: "脆焦糖壳下的丝滑布丁" }
];

foods.forEach((food, i) => {
  const col = i % 4;
  const row = Math.floor(i / 4);
  const x = 0.5 + col * 2.35;
  const y = 1.8 + row * 1.8;

  s7.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 2.1, h: 1.5,
    fill: { color: "243456" },
    line: { type: "none" },
    shadow: { type: "outer", color: "000000", blur: 4, offset: 2, angle: 135, opacity: 0.1 }
  });

  s7.addText(food.name, {
    x, y: y + 0.15, w: 2.1, h: 0.5,
    fontSize: 13, fontFace: "Calibri", bold: true,
    color: GOLD, align: "center", valign: "middle", margin: 0
  });

  s7.addText(food.desc, {
    x: x + 0.15, y: y + 0.7, w: 1.8, h: 0.7,
    fontSize: 10, fontFace: "Calibri",
    color: CREAM, align: "center", valign: "top", margin: 0,
    lineSpacingMultiple: 1.2
  });
});

// ══════════════════════════════════════════════
// SLIDE 8: Travel Tips
// ══════════════════════════════════════════════
let s8 = pres.addSlide();
s8.background = { color: CREAM };

accentBar(s8, 0, 0, 0.08, 5.625, GOLD);

s8.addText("实用旅行贴士", {
  x: 0.5, y: 0.3, w: 9, h: 0.7,
  fontSize: 30, fontFace: "Georgia", bold: true,
  color: NAVY, margin: 0
});

const tips = [
  { icon: "🗓", title: "最佳旅行时间", desc: "4-6月 & 9-10月，气候宜人，游客较少。\n7-8月薰衣草花期人多但最热闹。" },
  { icon: "✈️", title: "签证与交通", desc: "申根签证。TGV高铁连通各大城市，\n建议购买France Rail Pass。巴黎地铁覆盖全城。" },
  { icon: "💰", title: "预算参考", desc: "每日预算约€100-200（住宿+餐饮+门票）。\n米其林餐厅人均€80-300。" },
  { icon: "🗣", title: "语言与礼仪", desc: "法语为主，旅游区可用英语。\n记得说Bonjour问好，法国人很看重礼貌。" },
  { icon: "🏨", title: "住宿建议", desc: "巴黎住1-7区安全便捷；普罗旺斯住城堡酒店；\n蔚蓝海岸住尼斯作为大本营。" },
  { icon: "📱", title: "实用APP", desc: "Google Maps、Citymapper（交通）、\nTheFork（餐厅预订）、SNCF（火车票）。" }
];

tips.forEach((tip, i) => {
  const col = i % 2;
  const row = Math.floor(i / 2);
  const x = 0.5 + col * 4.7;
  const y = 1.15 + row * 1.45;

  s8.addShape(pres.shapes.RECTANGLE, {
    x, y, w: 4.4, h: 1.25,
    fill: { color: WHITE },
    line: { type: "none" },
    shadow: { type: "outer", color: "000000", blur: 4, offset: 2, angle: 135, opacity: 0.08 }
  });

  s8.addText(tip.icon, {
    x: x + 0.15, y: y + 0.2, w: 0.7, h: 0.7,
    fontSize: 22, align: "center", valign: "middle", margin: 0
  });

  s8.addText([
    { text: tip.title, options: { bold: true, color: NAVY, breakLine: true } },
    { text: tip.desc, options: { color: DARK } }
  ], {
    x: x + 0.95, y: y + 0.15, w: 3.3, h: 1.0,
    fontSize: 11, fontFace: "Calibri",
    align: "left", valign: "top", margin: 0,
    lineSpacingMultiple: 1.25
  });
});

// ══════════════════════════════════════════════
// SLIDE 9: Closing
// ══════════════════════════════════════════════
let s9 = pres.addSlide();
s9.background = { color: NAVY };

// Top bar
s9.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 0, w: 10, h: 0.06,
  fill: { color: GOLD }, line: { type: "none" }
});

s9.addText("MERCI!", {
  x: 0.5, y: 1.2, w: 9, h: 1.2,
  fontSize: 60, fontFace: "Georgia", bold: true,
  color: GOLD, align: "center", charSpacing: 15
});

s9.addText("谢谢观看", {
  x: 0.5, y: 2.5, w: 9, h: 0.6,
  fontSize: 22, fontFace: "Georgia",
  color: WHITE, align: "center"
});

s9.addShape(pres.shapes.LINE, {
  x: 3.5, y: 3.2, w: 3, h: 0,
  line: { color: GOLD, width: 2 }
});

s9.addText("愿你的法国之旅如诗如画 🇫🇷\n\nÀ bientôt en France!", {
  x: 1, y: 3.4, w: 8, h: 1.2,
  fontSize: 14, fontFace: "Calibri",
  color: CREAM, align: "center",
  lineSpacingMultiple: 1.5
});

// Bottom bar
s9.addShape(pres.shapes.RECTANGLE, {
  x: 0, y: 5.5, w: 10, h: 0.125,
  fill: { color: GOLD }, line: { type: "none" }
});

// ── Save ──
pres.writeFile({ fileName: "/Volumes/DATA/hermes-agent-main/探索法国.pptx" })
  .then(() => console.log("✅ PPT created successfully!"))
  .catch(err => console.error("❌ Error:", err));
