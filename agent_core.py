import os
import json
import asyncio
from groq import AsyncGroq
from rich.console import Console
from rich.panel import Panel

console = Console()


SYSTEM_PROMPT = """
You are an autonomous intelligent agent controlling a web browser.
Your goal is to complete the user's task by navigating and interacting with the page.

**INPUT DATA:**
At each step, you will receive:
1. The current URL.
2. A simplified representation of the DOM, where interactive elements have unique numerical IDs (e.g., `[12] <button> Submit`).

**YOUR OUTPUT (CRITICAL):**
You must respond strictly in **JSON format** representing one single action. Do not write any conversational text outside the JSON.

**AVAILABLE ACTIONS (TOOLS):**

1.  `{"action": "navigate", "url": "https://..."}`
    Use this to go to a specific URL.

2.  `{"action": "click", "element_id": 123}`
    Click on an element by its ID shown in the DOM representation.

3.  `{"action": "type", "element_id": 123, "text": "what to type"}`
    Type text into an input field identified by ID.

4.  `{"action": "ask_user", "question": "..."}`
    **SECURITY REQUIREMENT:** If the task involves a critical or destructive action (e.g., finalizing a payment, deleting emails, confirming a purchase), you MUST use this tool to ask for user confirmation first. Wait for their "yes" in the next turn.

5.  `{"action": "finish", "summary": "Task completed successfully. I ordered..."}`
    Use this when the task is fully finished or if it's impossible to complete.

**RULES:**
* Only use IDs presented in the current DOM observation.
* If you are stuck, try navigating back or searching.
* Be decisive. Plan a few steps ahead implicitly but execute only one action at a time.
"""


class AutonomousAgent:
    def __init__(self, browser_engine):
        self.browser = browser_engine
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model_name = "llama-3.3-70b-versatile"
        self.history = []

    async def run_task(self, user_goal: str):
        """Основной цикл работы агента: Observe -> Think -> Act"""
        console.print(Panel(f"🎯 Цель: {user_goal}", title="Agent Started", style="bold green"))

        self.history = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Current Goal: {user_goal}"}
        ]

        step_count = 0
        max_steps = 20

        while step_count < max_steps:
            step_count += 1
            console.rule(f"[bold blue]Step {step_count}[/]")

            url = await self.browser.get_url()
            console.print(f"Current URL: [underline]{url}[/]")

            dom_observation = await self.browser.scan_page()
            truncated_dom = dom_observation[:6000]

            current_context = f"Current URL: {url}\n\nVisible Elements:\n{truncated_dom}"
            self.history.append({"role": "user", "content": current_context})

            console.print("[grey50]🤔 Thinking...[/]")
            try:
                response = await self.client.chat.completions.create(
                    model=self.model_name,
                    messages=self.history,
                    response_format={"type": "json_object"},
                    temperature=0.1
                )
                ai_content = response.choices[0].message.content
                tool_call = json.loads(ai_content)
                self.history.append({"role": "assistant", "content": ai_content})
            except Exception as e:
                console.print(f"[bold red]AI Error:[/]{e}")
                break

            action_type = tool_call.get("action")
            console.print(Panel(str(tool_call), title="🤖 AI Decided", border_style="blue"))

            result_message = ""

            if action_type == "navigate":
                result_message = await self.browser.navigate(tool_call["url"])

            elif action_type == "click":
                result_message = await self.browser.click_element(tool_call["element_id"])

            elif action_type == "type":
                result_message = await self.browser.type_text(tool_call["element_id"], tool_call["text"])

            elif action_type == "ask_user":
                console.print(Panel(tool_call["question"], title="✋ Security Stop / User Question", style="bold red"))
                loop = asyncio.get_running_loop()
                user_answer = await loop.run_in_executor(None, input, "🧑‍💻 Ваш ответ (в терминале) > ")
                result_message = f"User answered: {user_answer}"

            elif action_type == "finish":
                console.print(Panel(tool_call["summary"], title="✅ Task Finished", style="bold green"))
                return

            else:
                result_message = f"Error: Unknown tool '{action_type}'"
                console.print(f"[red]{result_message}[/]")

            if result_message:
                console.print(f"[grey50]Result: {result_message}[/]")
                self.history.append({"role": "user", "content": f"Action result: {result_message}"})

        console.print("[bold red]Max steps reached. Stopping agent.[/]")