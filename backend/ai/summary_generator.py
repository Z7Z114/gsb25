import os
from typing import List, Dict, Optional
import logging
import json

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except Exception:  # openai 是可选依赖
    OpenAI = None
    OPENAI_AVAILABLE = False

logger = logging.getLogger(__name__)


class SummaryGenerator:
    """使用OpenAI API生成会议纪要摘要，包括扩产方案、法规挑战和营销策略"""

    def __init__(self, api_key: str = None, model: str = "gpt-4-turbo-preview"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = None
        if OPENAI_AVAILABLE and self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception:
                self.client = None

    def generate_summary(
        self,
        dialogue_text: str,
        detected_insects: List[Dict],
        meeting_context: Dict = None
    ) -> Dict:
        """
        生成完整的会议纪要摘要"""
        logger.info("开始生成会议纪要摘要...")

        if meeting_context is None:
            meeting_context = {}

        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(dialogue_text, detected_insects, meeting_context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=4000
        )

            content = response.choices[0].message.content
            summary = self._parse_response(content)

            logger.info("会议纪要摘要生成完成")
            return summary

        except Exception as e:
            logger.error(f"生成摘要时出错: {e}")
            raise

    def _build_system_prompt(self) -> str:
        return """你是一位专业的农业科技会议纪要分析师，专注于昆虫蛋白产业化领域。
你的任务是分析农业专家与企业家的对话，生成专业的会议纪要，重点关注：
1. 扩产方案：产能提升、技术优化、成本控制、供应链管理
2. 法规挑战：政策法规、审批流程、资质认证、标准制定
3. 昆虫营养分析：营养成分、营养价值、食用安全性
4. 养殖环境数据：温度、湿度、密度、周期、转化率
5. 营销策略：市场定位、目标客户、品牌建设、渠道拓展

请以JSON格式输出，结构清晰，数据准确，建议具体可行。"""

    def _build_user_prompt(
        self,
        dialogue_text: str,
        detected_insects: List[Dict],
        meeting_context: Dict
    ) -> str:
        insect_info = "\n".join([
        f"- {ins['chinese_name']} ({ins['latin_name']})"
        for ins in detected_insects
    ])

        context_info = ""
        if meeting_context:
            context_info = f"""
会议背景：
- 日期: {meeting_context.get('date', '')}
- 地点: {meeting_context.get('location', '')}
- 参会人员: {', '.join(meeting_context.get('attendees', []))}
"""

        return f"""请分析以下昆虫蛋白产业化会议对话，生成专业的会议纪要。

会议中讨论的昆虫种类：
{insect_info}

{context_info}

对话内容：
{dialogue_text}

请以严格的JSON格式输出，包含以下字段：
{{
    "meeting_basic_info": {{
        "title": "会议标题",
        "date": "会议日期",
        "duration": "会议时长",
        "attendees": ["参会人员"],
        "key_topics": ["核心议题"]
    }},
    "insect_production_analysis": {{
        "main_species": [{{
            "chinese_name": "中文名",
            "latin_name": "学名",
            "nutritional_value": {{
                "protein_content": "蛋白质含量",
                "fat_content": "脂肪含量",
                "amino_acid_profile": "氨基酸谱",
                "key_nutrients": ["关键营养成分"]
            }},
            "farming_environment": {{
                "optimal_temperature": "适宜温度",
                "optimal_humidity": "适宜湿度",
                "farming_density": "养殖密度",
                "growth_cycle": "生长周期",
                "feed_conversion_rate": "饲料转化率"
            }}
        }}],
        "environmental_data": "整体分析"
    }},
    "expansion_plan": {{
        "current_capacity": "当前产能",
        "target_capacity": "目标产能",
        "technical_optimization": ["技术优化方案"],
        "cost_analysis": {{
            "fixed_costs": "固定成本",
            "variable_costs": "可变成本",
            "cost_reduction_strategies": ["降本策略"]
        }},
        "supply_chain_management": ["供应链管理策略"],
        "implementation_timeline": "实施时间表"
    }},
    "regulatory_challenges": {{
        "current_regulations": ["现有法规"],
        "approval_process": "审批流程",
        "certification_requirements": ["资质认证要求"],
        "challenges": ["主要挑战"],
        "policy_recommendations": ["政策建议"]
    }},
    "marketing_strategy": {{
        "market_positioning": "市场定位",
        "target_customers": ["目标客户"],
        "product_portfolio": ["产品组合"],
        "pricing_strategy": "定价策略",
        "channel_strategy": ["渠道策略"],
        "brand_building": ["品牌建设"]
    }},
    "action_items": [{{
        "task": "任务",
        "responsible": "责任人",
        "deadline": "截止日期",
        "priority": "优先级"
    }}],
    "key_decisions": ["关键决策"],
    "risk_assessment": {{
        "technical_risks": ["技术风险"],
        "market_risks": ["市场风险"],
        "mitigation_strategies": ["缓解策略"]
    }}
}}"""

    def _parse_response(self, content: str) -> Dict:
        """解析OpenAI响应"""
        try:
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败，返回原始文本: {e}")
            return {"raw_content": content}

    def generate_markdown_report(self, summary: Dict) -> str:
        """将摘要转换为Markdown格式"""
        md = []

        basic = summary.get("meeting_basic_info", {})
        md.append(f"# {basic.get('title', '昆虫蛋白产业化会议纪要')}\n")
        md.append(f"**日期**: {basic.get('date', '')}  \n")
        md.append(f"**时长**: {basic.get('duration', '')}  \n")
        md.append(f"**参会人员**: {', '.join(basic.get('attendees', []))}\n")

        md.append("\n## 核心议题\n")
        for topic in basic.get("key_topics", []):
            md.append(f"- {topic}")

        md.append("\n## 昆虫蛋白分析\n")
        species = summary.get("insect_production_analysis", {})
        for sp in species.get("main_species", []):
            md.append(f"\n### {sp.get('chinese_name')} ({sp.get('latin_name')})\n")
            nutri = sp.get("nutritional_value", {})
            md.append(f"**蛋白质含量**: {nutri.get('protein_content', '')}  \n")
            md.append(f"**脂肪含量**: {nutri.get('fat_content', '')}  \n")
            md.append(f"**氨基酸谱**: {nutri.get('amino_acid_profile', '')}\n")
            md.append("**关键营养**: " + ", ".join(nutri.get('key_nutrients', [])))

            md.append("\n**养殖环境**:\n")
            env = sp.get("farming_environment", {})
            md.append(f"- 温度: {env.get('optimal_temperature', '')}")
            md.append(f"- 湿度: {env.get('optimal_humidity', '')}")
            md.append(f"- 密度: {env.get('farming_density', '')}")
            md.append(f"- 周期: {env.get('growth_cycle', '')}")
            md.append(f"- 饲料转化率: {env.get('feed_conversion_rate', '')}")

        md.append(f"\n{species.get('overall_analysis', '')}")

        md.append("\n## 扩产方案\n")
        expansion = summary.get("expansion_plan", {})
        md.append(f"**当前产能**: {expansion.get('current_capacity', '')}  \n")
        md.append(f"**目标产能**: {expansion.get('target_capacity', '')}\n")

        md.append("\n**技术优化**:\n")
        for tech in expansion.get("technical_optimization", []):
            md.append(f"- {tech}")

        cost = expansion.get("cost_analysis", {})
        md.append(f"\n**固定成本**: {cost.get('fixed_costs', '')}  \n")
        md.append(f"**可变成本**: {cost.get('variable_costs', '')}\n")

        md.append("\n**降本策略**:\n")
        for strat in cost.get("cost_reduction_strategies", []):
            md.append(f"- {strat}")

        md.append("\n**供应链管理**:\n")
        for scm in expansion.get("supply_chain_management", []):
            md.append(f"- {scm}")

        md.append(f"\n**实施时间表**: {expansion.get('implementation_timeline', '')}")

        md.append("\n## 法规挑战\n")
        reg = summary.get("regulatory_challenges", {})

        md.append("**现有法规**:\n")
        for r in reg.get("current_regulations", []):
            md.append(f"- {r}")

        md.append(f"\n**审批流程**: {reg.get('approval_process', '')}\n")

        md.append("\n**资质认证**:\n")
        for cert in reg.get("certification_requirements", []):
            md.append(f"- {cert}")

        md.append("\n**主要挑战**:\n")
        for chal in reg.get("challenges", []):
            md.append(f"- {chal}")

        md.append("\n**政策建议**:\n")
        for rec in reg.get("policy_recommendations", []):
            md.append(f"- {rec}")

        md.append("\n## 营销策略\n")
        marketing = summary.get("marketing_strategy", {})
        md.append(f"**市场定位**: {marketing.get('market_positioning', '')}\n")

        md.append("\n**目标客户**:\n")
        for cust in marketing.get("target_customers", []):
            md.append(f"- {cust}")

        md.append("\n**产品组合**:\n")
        for prod in marketing.get("product_portfolio", []):
            md.append(f"- {prod}")

        md.append(f"\n**定价策略**: {marketing.get('pricing_strategy', '')}\n")

        md.append("\n**渠道策略**:\n")
        for ch in marketing.get("channel_strategy", []):
            md.append(f"- {ch}")

        md.append("\n**品牌建设**:\n")
        for brand in marketing.get("brand_building", []):
            md.append(f"- {brand}")

        md.append("\n## 行动项\n")
        for item in summary.get("action_items", []):
            md.append(f"- [{item.get('priority', '')}] {item.get('task', '')} - {item.get('responsible', '')} (截止: {item.get('deadline', '')})")

        md.append("\n## 关键决策\n")
        for decision in summary.get("key_decisions", []):
            md.append(f"- {decision}")

        md.append("\n## 风险评估\n")
        risk = summary.get("risk_assessment", {})
        md.append("\n**技术风险**:\n")
        for tr in risk.get("technical_risks", []):
            md.append(f"- {tr}")

        md.append("\n**市场风险**:\n")
        for mr in risk.get("market_risks", []):
            md.append(f"- {mr}")

        md.append("\n**缓解策略**:\n")
        for ms in risk.get("mitigation_strategies", []):
            md.append(f"- {ms}")

        return "\n".join(md)
