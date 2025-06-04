import os # Import os to access environment variables
from dotenv import load_dotenv # 新增: 导入 load_dotenv
from strands import Agent
from strands.models.openai import OpenAIModel # 新增: 导入 OpenAIModel
from .tools import scenario_tool, objection_tool, eval_tool
from strands_tools import use_llm

load_dotenv() # 新增: 在脚本早期加载 .env 文件

class PharmaRepCoachAgent:
    def __init__(self):
        bedrock_model_id = os.getenv("BEDROCK_MODEL_ID")
        openai_api_key = os.getenv("OPENAI_API_KEY") # 新增: 获取 OpenAI API Key
        openai_base_url = os.getenv("OPENAI_BASE_URL") # 新增: 获取 OpenAI Base URL
        
        agent_kwargs = {
            "tools": [scenario_tool, objection_tool, eval_tool, use_llm],
            "system_prompt": "你是一个医药代表培训协调员。你的任务是根据用户输入协调场景生成、医生互动和培训评估。"
        }
        
        # 修改: 优先使用 OpenAI，然后 Bedrock，最后默认
        if openai_api_key and openai_base_url:
            agent_kwargs["model"] = OpenAIModel(
                client_args={
                    "api_key": openai_api_key,
                    "base_url": openai_base_url,
                },
                model_id=os.getenv("OPENAI_MODEL_ID", "deepseek-ai/DeepSeek-R1"), # 允许通过环境变量配置模型ID，默认为 Qwen/Qwen3-32B
                params={
                    "max_tokens": int(os.getenv("OPENAI_MAX_TOKENS", 1500)), # 确保是整数
                    "temperature": float(os.getenv("OPENAI_TEMPERATURE", 0.7)),
                }
            )
            print("INFO: Using OpenAI model.")
        elif bedrock_model_id:
            agent_kwargs["model"] = bedrock_model_id
            # model_provider defaults to "bedrock" if not set, which is desired.
            # AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY are picked up by AWS SDK from env.
            print(f"INFO: Using Bedrock model: {bedrock_model_id}.")
        else:
            print("INFO: Using default Strands Agent model.")

        self.strands_agent = Agent(**agent_kwargs)
        self.current_mode = "waiting_for_start"  # waiting_for_start, doctor_interaction, final_summary
        self.doctor_persona = None  # 存储医生角色信息 (name, opening_line, characteristics)
        self.conversation_log = []  # 存储对话历史 (speaker, utterance)

    def _get_doctor_system_prompt(self) -> str:
        if not self.doctor_persona or 'name' not in self.doctor_persona:
            return "你是一位资深临床医生。请以专业、有时略带挑战性的语气与医药代表互动。确保你的回答符合医学专业知识和常见的临床情景。"
        
        name = self.doctor_persona.get('name', '医生')
        specialty = self.doctor_persona.get('specialty', '相关科室')
        prompt = f"你是一位名叫 {name} 的{specialty}医生。你的任务是与医药代表进行角色扮演对话。请根据你的专业背景和当前对话情境进行回应。"
        if 'characteristics' in self.doctor_persona:
            prompt += f" 你的背景信息：{self.doctor_persona['characteristics']}。"
        prompt += " 请确保你的发言自然、专业，并能推动对话有效进行。"
        return prompt

    def handle_message(self, user_input: str) -> list[str]:
        responses = []
        self.conversation_log.append(("User", user_input))

        if self.current_mode == "waiting_for_start":
            if ("药品" in user_input and "科室" in user_input and 
                ("start" in user_input.lower() or "开始" in user_input)):
                responses.append("System: 正在生成医生场景…")
                try:
                    if "semaglutide" in user_input.lower() and "endocrinology" in user_input.lower():
                        self.doctor_persona = {
                            "name": "李伟", "specialty": "内分泌科",
                            "opening_line": "“你好，我是李伟主任，最近门诊里肥胖合并 2 型糖尿病的患者越来越多。你们司美格鲁肽有哪些新版数据？”",
                            "characteristics": "男·45 岁·主任医师·周处方量≈25 支"
                        }
                    else:
                         self.doctor_persona = {
                            "name": "王医生", "specialty": "相关科室",
                            "opening_line": "“你好，关于你提到的药品，请详细介绍一下数据和证据。”",
                            "characteristics": "经验丰富，关注药物的实际临床价值。"
                        }
                    
                    self.current_mode = "doctor_interaction"
                    doctor_display_name = self.doctor_persona.get('name', '医生')
                    responses.append(f"Doctor {doctor_display_name} ▶ {self.doctor_persona['opening_line']}")
                    if self.doctor_persona.get('characteristics'):
                        responses.append(f"System     ▶ 【医生档案】{self.doctor_persona['characteristics']}")
                    self.conversation_log.append((f"Doctor {doctor_display_name}", self.doctor_persona['opening_line']))

                except Exception as e:
                    responses.append(f"System: 抱歉，生成场景时出错: {str(e)}")
                    self.current_mode = "waiting_for_start"
                return responses
            else:
                responses.append('System: 请提供药品、科室、难度信息并包含"Start"或"开始"以启动。例如："药品: Semaglutide；科室: Endocrinology；难度: Basic。点击【Start】"')
                return responses

        elif self.current_mode == "doctor_interaction":
            responses.append("Coach: 正在评估您的回答…")
            try:
                doctor_last_utterance = self.conversation_log[-2][1] if len(self.conversation_log) >= 2 else self.doctor_persona.get('opening_line', '')
                eval_prompt = f"作为医药销售培训教练，请针对医生刚才所说的{doctor_last_utterance}，评估医药代表的以下回答：{user_input}。请给出评分（例如X/100）、合规性（例如🟢或🔴）以及具体的亮点和改进建议。"
                
                coach_feedback = self.strands_agent(eval_prompt)
                responses.append(f"Coach      ▶ {coach_feedback}")
                self.conversation_log.append(("Coach", coach_feedback))
            except Exception as e:
                responses.append(f"Coach: 评估时出错: {str(e)}")

            if "结束训练" in user_input or "end training" in user_input.lower():
                self.current_mode = "final_summary"
                responses.append("System: 正在生成总结报告…")
                try:
                    summary_prompt = f"作为医药销售培训教练，请对以下完整的对话记录进行总结性评估。内容应包括整体表现评分、主要优势、关键改进领域，以及可能的雷达图数据点（例如：学术性、沟通技巧、异议处理、合规性等维度，每个维度给一个分数）。对话记录如下：\n"
                    for speaker, utterance in self.conversation_log:
                        summary_prompt += f"{speaker}: {utterance}\n"
                    
                    final_summary = self.strands_agent(summary_prompt)
                    responses.append(f"Summary    ▶\n{final_summary}")
                    self.conversation_log.append(("Summary", final_summary))
                    
                    self.current_mode = "waiting_for_start"
                    self.doctor_persona = None
                except Exception as e:
                    responses.append(f"System: 生成总结报告时出错: {str(e)}")
                return responses

            try:
                doctor_system_prompt_text = self._get_doctor_system_prompt()
                
                context_for_doctor_list = []
                for log_speaker, log_utterance in reversed(self.conversation_log):
                    if log_speaker.startswith("Doctor") or log_speaker == "User":
                        context_for_doctor_list.append(f"{log_speaker}: {log_utterance}")
                    if len(context_for_doctor_list) >= 4:
                        break
                context_for_doctor = "\n".join(reversed(context_for_doctor_list))
                
                next_doctor_llm_prompt = (
                    f"这是最近的对话历史:\n{context_for_doctor}\n\n"
                    f"现在轮到你 ({self.doctor_persona.get('name', '医生')}) 回应。你可以继续之前的对话，或者针对代表的发言提出一个相关的临床问题或常见的顾虑/异议（例如关于药物效果、副作用、价格、患者依从性等）。请生成你的下一句对话。"
                )
                
                if hasattr(self.strands_agent, 'tool') and hasattr(self.strands_agent.tool, 'use_llm'):
                    doctor_next_line_data = self.strands_agent.tool.use_llm(
                        prompt=next_doctor_llm_prompt,
                        system_prompt=doctor_system_prompt_text
                    )
                    if isinstance(doctor_next_line_data, dict) and 'content' in doctor_next_line_data and \
                       isinstance(doctor_next_line_data['content'], list) and len(doctor_next_line_data['content']) > 0 and \
                       'text' in doctor_next_line_data['content'][0]:
                        doctor_next_line = str(doctor_next_line_data['content'][0]['text'])
                    else:
                        doctor_next_line = str(doctor_next_line_data)
                else:
                    original_prompt = self.strands_agent.system_prompt
                    self.strands_agent.system_prompt = doctor_system_prompt_text
                    doctor_next_line = str(self.strands_agent(next_doctor_llm_prompt))
                    self.strands_agent.system_prompt = original_prompt

                tool_marker = ""
                objection_keywords = ["价格", "费用", "太贵", "效果", "疗效", "副作用", "不良反应", "依从性"]
                if any(keyword in doctor_next_line for keyword in objection_keywords):
                    tool_marker = " _ObjectionTool_"

                doctor_display_name = self.doctor_persona.get('name', '医生')
                responses.append(f"Doctor {doctor_display_name} ▶ {doctor_next_line}{tool_marker}")
                self.conversation_log.append((f"Doctor {doctor_display_name}", doctor_next_line))
            except Exception as e:
                responses.append(f"Doctor: 生成回复时出错: {str(e)}")
            return responses
        
        elif self.current_mode == "final_summary":
            responses.append("System: 培训已结束。如需开始新的培训，请按格式提示开始。")
            self.current_mode = "waiting_for_start"
            self.doctor_persona = None
            return responses
        
        return responses

def demonstrate_chat_flow():
    print("欢迎来到 PharmaRep Coach！")
    coach_agent = PharmaRepCoachAgent()

    chat_interactions = [
        ("User", "药品: Semaglutide；科室: Endocrinology；难度: Basic。点击【Start】"),
        ("User", "主任好！最新 SELECT 研究显示口服司美格鲁肽可显著降低 MACE 复合终点，心血管获益明确..."),
        ("User", "关于价格，我们有相应的患者援助项目，同时长期来看，良好的血糖和体重控制能减少并发症治疗费用，总体是经济的。"),
        ("User", "我们有详细的剂量递增指导方案，前4周使用0.25mg起始剂量，随后逐步增加到维持剂量，能很好地管理胃肠道反应，提高患者耐受性和依从性。"),
        ("User", "好的主任，我会把SELECT研究摘要和剂量递增方案发到您的邮箱，并向您预约下周进行一次详细的学术拜访。"),
        ("User", "点击【结束训练】")
    ]

    for speaker, message in chat_interactions:
        print(f"\n{speaker:10} ▶ {message}")
        if speaker == "User":
            agent_responses = coach_agent.handle_message(message)
            for res in agent_responses:
                # Standard prefixes for display
                doctor_prefix_display = f"{'Doctor':<10} ({coach_agent.doctor_persona.get('name', '') if coach_agent.doctor_persona else ''})"
                coach_prefix_display = f"{'Coach':<10}"
                summary_prefix_display = f"{'Summary':<10}"

                if res.startswith("Doctor"):
                    parts = res.split('▶', 1)
                    message_content = parts[1].strip() if len(parts) > 1 else res
                    if message_content.startswith("Doctor: "): # Strip "Doctor: " if it's an error message
                        message_content = message_content[len("Doctor: "):].strip()
                    print(f"{doctor_prefix_display} ▶ {message_content}")
                
                elif res.startswith("Coach"):
                    parts = res.split('▶', 1)
                    message_content = parts[1].strip() if len(parts) > 1 else res
                    if message_content.startswith("Coach: "): # Strip "Coach: " if it's an error message
                        message_content = message_content[len("Coach: "):].strip()
                    print(f"{coach_prefix_display} ▶ {message_content}")

                elif res.startswith("Summary"):
                    parts = res.split('▶', 1)
                    message_content = parts[1].strip() if len(parts) > 1 else res
                    if message_content.startswith("Summary: "): # Strip "Summary: " if it's an error message
                        message_content = message_content[len("Summary: "):].strip()
                    print(f"{summary_prefix_display} ▶ {message_content}")
                
                else: # System messages (e.g., "System: ...", "System     ▶ ...")
                    print(res)
            
if __name__ == "__main__":
    demonstrate_chat_flow()

    # 如果需要交互式测试:
    # print("\n=== 进入交互测试模式 (输入 'exit' 结束) ===")
    # agent_interactive = PharmaRepCoachAgent()
    # while True:
    #     user_input_interactive = input("User       ▶ ")
    #     if user_input_interactive.lower() == "exit":
    #         break
    #     responses_interactive = agent_interactive.handle_message(user_input_interactive)
    #     for r_interactive in responses_interactive:
    #         print(r_interactive) 