# utils/tools.py
# 合并自 scenario_tool.py, objection_tool.py, eval_tool.py

from typing import Any, Literal # Literal 用于 enum 类型提示
from strands import tool # 导入 @tool 装饰器

# --- scenario_tool ---
@tool
def scenario_tool(
    drug: str, 
    specialty: str, 
    level: Literal["basic", "intermediate", "advanced"] = "basic", 
    lang: Literal["zh", "en"] = "zh"
) -> dict:
    """
    生成医生人设 + 场景开场白

    Args:
        drug (str): 药品名称
        specialty (str): 医生专科
        level (Literal["basic", "intermediate", "advanced"]): 医生级别, 默认为 "basic".
        lang (Literal["zh", "en"]): 语言, 默认为 "zh".
    """
    # Tool implementation - 生成医生人设和开场白
    if lang == "zh":
        doctor_persona = f"您是一位{specialty}科的{level}级医生，对{drug}有深入了解，善于与患者沟通，专业且耐心。"
        opening_line = f"您好，我是{specialty}科医生。今天想和您聊聊关于{drug}的一些情况，您有什么想了解的吗？"
    else:
        doctor_persona = f"You are a {level}-level doctor in {specialty}, with deep knowledge of {drug}, good at communicating with patients, professional and patient."
        opening_line = f"Hello, I\'m a doctor in {specialty}. Today I\'d like to talk with you about {drug}. What would you like to know?"

    # 格式化结果为文本
    result_text = f"医生人设：{doctor_persona}\n\n开场白：{opening_line}"

    # Return structured response (toolUseId is handled by the agent)
    return {
        "status": "success",
        "content": [{"text": result_text}]
    }

# --- objection_tool ---
@tool
def objection_tool(
    drug: str, 
    topic: Literal["efficacy", "safety", "cost", "convenience"]
) -> dict:
    """
    给定药品，列出常见异议与要点提示

    Args:
        drug (str): 药品名称
        topic (Literal["efficacy", "safety", "cost", "convenience"]): 关注话题
    """
    # Tool implementation - 生成常见异议和应对要点
    objections_db = {
        "efficacy": [
            {
                "objection": "这个药真的有效吗？",
                "hint": "引用临床试验数据，说明药物的有效率和起效时间"
            },
            {
                "objection": "和其他药物相比效果如何？",
                "hint": "对比研究结果，突出药物的独特优势"
            }
        ],
        "safety": [
            {
                "objection": "这个药有什么副作用？",
                "hint": "诚实告知常见副作用，强调安全监测和管理措施"
            },
            {
                "objection": "长期使用安全吗？",
                "hint": "提供长期安全性数据，说明监测方案"
            }
        ],
        "cost": [
            {
                "objection": "这个药太贵了",
                "hint": "从性价比角度分析，提及可能的医保政策或患者援助项目"
            }
        ],
        "convenience": [
            {
                "objection": "用药方式太复杂",
                "hint": "详细说明用药方法，提供简化的用药指导"
            }
        ]
    }

    # Get objections for the specified topic
    result = objections_db.get(topic, [
        {
            "objection": f"关于{drug}的{topic}方面的疑虑",
            "hint": "提供专业、准确的信息回应"
        }
    ])

    # 格式化结果为文本
    result_lines = [f"药品：{drug} | 话题：{topic}\n"]
    for i, item in enumerate(result, 1):
        result_lines.append(f"{i}. 异议：{item['objection']}")
        result_lines.append(f"   应对要点：{item['hint']}\n")
    
    result_text = "\n".join(result_lines)

    # Return structured response
    return {
        "status": "success",
        "content": [{"text": result_text}]
    }

# --- eval_tool ---
@tool
def eval_tool(
    repUtterance: str, 
    context: str
) -> dict:
    """
    打分药代回答的准确性 + 合规性，并给简短改进建议

    Args:
        repUtterance (str): 药代的回答内容
        context (str): 对话上下文
    """
    # Tool implementation - 评估回答质量
    # 简化的评分逻辑（实际应用中可能需要更复杂的NLP分析）
    
    # 基础评分因素
    score = 70  # 基础分
    
    # 准确性评估
    if len(repUtterance) > 50:  # 回答有一定长度
        score += 10
    if "临床试验" in repUtterance or "研究" in repUtterance:  # 引用证据
        score += 10
    if "副作用" in repUtterance or "安全" in repUtterance:  # 提及安全性
        score += 5
    
    # 合规性评估
    forbidden_words = ["一定", "绝对", "包治", "神药"]
    if any(word in repUtterance for word in forbidden_words):
        score -= 20
    
    # 专业性评估
    professional_terms = ["适应症", "禁忌症", "药物相互作用", "不良反应"]
    if any(term in repUtterance for term in professional_terms):
        score += 5
    
    # 确保分数在合理范围内
    score = max(0, min(100, score))
    
    # 生成改进建议
    comments = []
    
    if score < 60:
        comments.append("回答需要更加专业和准确")
    elif score < 80:
        comments.append("可以增加更多循证医学证据")
    else:
        comments.append("回答质量良好")
    
    if len(repUtterance) < 30:
        comments.append("建议提供更详细的信息")
    
    if not any(word in repUtterance for word in ["临床", "研究", "试验"]):
        comments.append("建议引用相关临床研究数据")
    
    comment = "；".join(comments[:2])  # 最多取前两个建议

    # 格式化结果为文本
    result_text = f"评估结果：\n分数：{score}/100\n改进建议：{comment}"

    # Return structured response
    return {
        "status": "success",
        "content": [{"text": result_text}]
    } 