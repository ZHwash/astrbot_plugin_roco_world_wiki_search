import { makeHeaders } from "../config";
import type { SkillDetail } from "./skill-detail";

// 兼容Node.js和Bun的sleep函数
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export interface PetDetail {
  id: number;
  name: string;
  form: string;
  regionalFormName: string;
  initialStageName: string;
  hasAltColor: string;
  stage: string;
  type: string;
  description: string;
  element: string;
  element2: string;
  ability: string;
  abilityDesc: string;
  hp: number;
  physicalAttack: number;
  magicAttack: number;
  physicalDefense: number;
  magicDefense: number;
  speed: number;
  size: string;
  weight: string;
  distribution: string;
  questTasks: string[];
  questSkillStones: string[];
  skills: string[];
  skillUnlockLevels: number[];
  bloodlineSkills: string[];
  learnableSkillStones: string[];
  evolutionCondition: string;
  updateVersion: string;
  spriteImage?: string;
  skillDetails: SkillDetail[];
  bloodlineSkillDetails: SkillDetail[];
  learnableSkillStoneDetails: SkillDetail[];
}

async function fetchWikitext(name: string, retries = 3): Promise<string> {
  const url = `https://wiki.biligame.com/rocom/index.php?title=${encodeURIComponent(name)}&action=raw`;

  for (let i = 0; i < retries; i++) {
    const res = await fetch(url, { headers: makeHeaders() });
    if (res.status === 567) {
      await sleep(3000 * (i + 1));
      continue;
    }
    return res.text();
  }
  return "";
}

async function fetchHtmlPage(name: string, retries = 3): Promise<string> {
  const url = `https://wiki.biligame.com/rocom/${encodeURIComponent(name)}`;

  for (let i = 0; i < retries; i++) {
    const res = await fetch(url, { headers: makeHeaders() });
    if (res.status === 567) {
      await sleep(3000 * (i + 1));
      continue;
    }
    return res.text();
  }
  return "";
}

function extractPetId(html: string): number | null {
  // 匹配 NOxxx.精灵名 或 NO.xxx 等格式
  const match = html.match(/NO\.?(\d+)[\.．]/);
  if (match && match[1]) {
    return parseInt(match[1]);
  }
  return null;
}

function parseWikitext(wikitext: string): PetDetail | null {
  // 匹配 {{精灵信息|...}}
  const match = wikitext.match(/\{\{精灵信息\s*\|([\s\S]*?)\}\}/);
  if (!match) return null;

  const raw = match[1]!;

  // 解析 key=value 对，按 \n| 分割保留多行值
  const data = new Map<string, string>();
  const pairs = raw.split(/\n\|/);
  for (const pair of pairs) {
    const eqIndex = pair.indexOf("=");
    if (eqIndex === -1) continue;
    const key = pair.slice(0, eqIndex).trim();
    const value = pair.slice(eqIndex + 1).trim();
    data.set(key, value);
  }

  const splitComma = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);
  // 课题用换行或逗号分隔
  const splitTasks = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);

  return {
    id: 0, // 默认值，稍后从HTML中提取
    name: "",
    form: data.get("精灵形态") ?? "",
    regionalFormName: data.get("地区形态名称") ?? "",
    initialStageName: data.get("精灵初阶名称") ?? "",
    hasAltColor: data.get("是否有异色") ?? "",
    stage: data.get("精灵阶段") ?? "",
    type: data.get("精灵类型") ?? "",
    description: data.get("精灵描述") ?? "",
    element: data.get("主属性") ?? "",
    element2: data.get("2属性") ?? "",
    ability: data.get("特性") ?? "",
    abilityDesc: data.get("特性描述") ?? "",
    hp: parseInt(data.get("生命") ?? "0"),
    physicalAttack: parseInt(data.get("物攻") ?? "0"),
    magicAttack: parseInt(data.get("魔攻") ?? "0"),
    physicalDefense: parseInt(data.get("物防") ?? "0"),
    magicDefense: parseInt(data.get("魔防") ?? "0"),
    speed: parseInt(data.get("速度") ?? "0"),
    size: data.get("体型") ?? "",
    weight: data.get("重量") ?? "",
    distribution: data.get("分布地区") ?? "",
    questTasks: splitTasks(data.get("图鉴课题") ?? ""),
    questSkillStones: splitComma(data.get("课题技能石") ?? ""),
    skills: splitComma(data.get("技能") ?? ""),
    skillUnlockLevels: splitComma(data.get("技能解锁等级") ?? "").map(Number).filter((n) => !isNaN(n)),
    bloodlineSkills: splitComma(data.get("血脉技能") ?? ""),
    learnableSkillStones: splitComma(data.get("可学技能石") ?? ""),
    evolutionCondition: data.get("进化条件") ?? "",
    updateVersion: data.get("更新版本") ?? "",
    spriteImage: data.get("宠物立绘形态") ?? undefined,
    skillDetails: [],
    bloodlineSkillDetails: [],
    learnableSkillStoneDetails: [],
  };
}

export async function crawlPet(name: string): Promise<PetDetail | null> {
  const wikitext = await fetchWikitext(name);
  const detail = parseWikitext(wikitext);
  if (!detail) return null;
  
  detail.name = name;
  
  // 从HTML页面中提取精灵编号
  const html = await fetchHtmlPage(name);
  if (html) {
    const petId = extractPetId(html);
    if (petId !== null) {
      detail.id = petId;
    }
  }
  
  return detail;
}

// 入口
if (import.meta.main) {
  const pet = await crawlPet("炽心勇狮");
  console.log(JSON.stringify(pet, null, 2));
}
