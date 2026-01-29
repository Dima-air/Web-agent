import asyncio
import os
from rich.console import Console
from browser_engine import BrowserEngine
from agent_core import AutonomousAgent

os.environ["GROQ_API_KEY"] = "YOUR_GROQ_API_KEY"
console = Console()

console = Console()


async def main():
    console.print("[bold yellow]Initializing Agent & Browser...[/]")

    browser = BrowserEngine(headless=False, session_path="./my_browser_session")
    await browser.start()

    agent = AutonomousAgent(browser_engine=browser)

    console.print("\n" + "=" * 50)
    console.print("AI Web Agent готов к работе.")
    console.print("Примеры задач:")
    console.print(" - 'Найди на hh.ru вакансии Python разработчика и перейди на первую'")
    console.print(" - 'Зайди на Яндекс Маркет, найди iPhone 15 и добавь в корзину'")
    console.print("=" * 50)
    task = input("Введите вашу задачу для агента > ")

    if not task:
        task = "Перейди на google.com и найди 'LangChain'"
        console.print(f"Задача не введена, использую тестовую: {task}")

    # 3. Запуск выполнения
    try:
        await agent.run_task(task)
    except KeyboardInterrupt:
        console.print("\n[bold red]Agent stopped by user.[/]")
    finally:
        console.print("[yellow]Shutting down browser...[/]")
        await browser.stop()
        console.print("[green]Done.[/]")


if __name__ == "__main__":
    if not os.getenv("GROQ_API_KEY"):
        console.print("[bold red]ОШИБКА: Не найден GROQ_API_KEY.[/]")
        console.print("Пожалуйста, установите переменную окружения: export GROQ_API_KEY='ваш-ключ'")
        exit(1)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass