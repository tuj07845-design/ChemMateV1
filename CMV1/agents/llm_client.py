import time

from openai import OpenAI
class OpenAICompatibleClient:
            """
            一个用于调用任何兼容OpenAI接口的LLM服务的客户端。
            """

            def __init__(self, model: str, api_key: str, base_url: str):
                self.model = model
                self.client = OpenAI(api_key=api_key, base_url=base_url)

            def generate(self, prompt: str, system_prompt: str) -> str:
                """调用LLM API来生成回应。"""
                print("正在调用大语言模型...")
                messages = [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': prompt}
                ]
                last_error = None
                for attempt in range(2):
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            stream=False,
                        )
                        answer = response.choices[0].message.content
                        if not answer or not str(answer).strip():
                            raise RuntimeError("模型返回空内容")
                        print("大语言模型响应成功。")
                        return str(answer)
                    except Exception as exc:
                        last_error = exc
                        print(f"调用LLM API时发生错误（第 {attempt + 1} 次）: {exc}")
                        if attempt == 0:
                            time.sleep(1.0)

                raise RuntimeError(
                    f"LLM 调用失败（{type(last_error).__name__}）：{last_error}"
                ) from last_error
