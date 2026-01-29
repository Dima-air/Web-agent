import asyncio
import json
from playwright.async_api import async_playwright, Page, BrowserContext

# --- JS СКРИПТ ДЛЯ АНАЛИЗА DOM ---
# Этот скрипт внедряется в страницу. Он находит интерактивные элементы,
# рисует на них ID (для визуализации) и возвращает JSON для LLM.
DOM_JS_SCRIPT = """
(() => {
    // 1. Очистка старых маркеров
    document.querySelectorAll('.agent-highlight').forEach(e => e.remove());
    document.querySelectorAll('[agent-id]').forEach(e => {
        e.removeAttribute('agent-id');
        e.style.outline = '';
    });

    let items = [];
    let idCounter = 1;

    // 2. Функция проверки видимости
    function isVisible(elem) {
        if (!elem) return false;
        const style = window.getComputedStyle(elem);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
        const rect = elem.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    }

    // 3. Сбор элементов (кнопки, ссылки, инпуты)
    const selectors = [
        'a[href]', 'button', 'input', 'textarea', 'select', 
        '[role="button"]', '[role="link"]', '[role="checkbox"]', '[role="menuitem"]'
    ];

    document.querySelectorAll(selectors.join(',')).forEach(el => {
        if (isVisible(el)) {
            const aid = idCounter++;
            el.setAttribute('agent-id', aid.toString());

            // Визуальная подсветка (Требование: "Видно, как это работает")
            el.style.outline = '2px solid red'; 

            // Добавляем метку с номером
            const label = document.createElement('div');
            label.className = 'agent-highlight';
            label.innerText = aid;
            label.style.position = 'absolute';
            label.style.background = 'yellow';
            label.style.color = 'black';
            label.style.border = '1px solid black';
            label.style.zIndex = '9999';
            label.style.padding = '2px';
            label.style.fontSize = '12px';
            label.style.fontWeight = 'bold';

            const rect = el.getBoundingClientRect();
            label.style.top = (window.scrollY + rect.top) + 'px';
            label.style.left = (window.scrollX + rect.left) + 'px';
            document.body.appendChild(label);

            // Собираем инфо для LLM
            let text = (el.innerText || el.value || el.getAttribute('aria-label') || "").slice(0, 50).replace(/\\n/g, ' ');
            items.push({
                id: aid,
                tag: el.tagName.toLowerCase(),
                text: text,
                type: el.getAttribute('type') || ''
            });
        }
    });

    return items;
})();
"""


class BrowserEngine:
    def __init__(self, headless=False, session_path="user_session"):
        self.headless = headless
        self.session_path = session_path
        self.playwright = None
        self.browser_context = None
        self.page = None

    async def start(self):
        """Запускает браузер с сохраненным профилем."""
        self.playwright = await async_playwright().start()

        self.browser_context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=self.session_path,
            headless=self.headless,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"]  # Скрываем, что мы робот
        )

        if self.browser_context.pages:
            self.page = self.browser_context.pages[0]
        else:
            self.page = await self.browser_context.new_page()

        print(f"🌐 Браузер запущен. Сессия: {self.session_path}")

    async def stop(self):
        if self.browser_context:
            await self.browser_context.close()
        if self.playwright:
            await self.playwright.stop()

    async def navigate(self, url: str):
        """Переход по URL."""
        print(f"👉 Переход: {url}")
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(2)
        except Exception as e:
            return f"Error navigating: {e}"
        return f"Navigated to {url}"

    async def scan_page(self):
        """
        Внедряет JS, подсвечивает элементы и возвращает упрощенное описание страницы.
        Это решает проблему токенов.
        """
        try:
            elements = await self.page.evaluate(DOM_JS_SCRIPT)
            observation = "Interactive Elements on Screen:\n"
            for el in elements:
                observation += f"[{el['id']}] <{el['tag']} type='{el['type']}'> {el['text']}\n"
            return observation
        except Exception as e:
            return f"Error scanning page: {e}"

    async def click_element(self, element_id: int):
        """Клик по элементу по его agent-id (который мы присвоили)."""
        selector = f"[agent-id='{element_id}']"
        try:
            count = await self.page.locator(selector).count()
            if count == 0:
                return f"Error: Element [{element_id}] not found."

            await self.page.click(selector)
            await asyncio.sleep(2)
            return f"Clicked element [{element_id}]"
        except Exception as e:
            return f"Error clicking [{element_id}]: {e}"

    async def type_text(self, element_id: int, text: str):
        """Ввод текста в поле."""
        selector = f"[agent-id='{element_id}']"
        try:
            await self.page.fill(selector, text)
            return f"Typed '{text}' into element [{element_id}]"
        except Exception as e:
            return f"Error typing in [{element_id}]: {e}"

    async def get_url(self):
        return self.page.url