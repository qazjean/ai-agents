import os

os.environ["USER_AGENT"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

from langchain_gigachat import GigaChat
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.document_loaders import UnstructuredURLLoader, WebBaseLoader
import sys

API_KEY = "MDE5YTAyMjQtZjA3YS03Y2JhLTljYWQtMzM3ZDQ5MGUwMzM1OmFjMDRmNjRmLTdhMGQtNDhiZS1iODZhLWEzNjNjODA3OWRhNg=="

llm = GigaChat(credentials=API_KEY, verify_ssl_certs=False)

# Системный промпт
system_prompt = SystemMessage(content="""
Ты — помощник студента. У тебя есть список предметов:
- Численные методы
- Компьютерные сети
- Программирование на Python
- Физика

Твоя задача: по тексту страницы определить, для какого именно предмета материал будет полезен.
Отвечай только одним из названий предметов из списка (ровно так, как в перечне выше).
""")


def load_text_from_url(url: str) -> str:
    try:
        loader = UnstructuredURLLoader(urls=[url])
        docs = loader.load()
        if docs:
            full = " ".join(d.page_content for d in docs)
        else:
            # WebBaseLoader, если Unstructured не сработал
            loader2 = WebBaseLoader(url)
            docs2 = loader2.load()
            full = " ".join(d.page_content for d in docs2) if docs2 else ""
        # стиль
        cleaned = " ".join(full.split())
        return cleaned[:1000]
    except Exception as e:
        return f"Ошибка загрузки страницы: {e}"

def classify_subject(text_snippet: str) -> str:
    user_prompt = HumanMessage(content=f"Содержимое (ограничено):\n{text_snippet}\n\nКакой это предмет?")
    messages = [system_prompt, user_prompt]
    response = llm.invoke(messages)
    return response.content.strip()

def main():
    if API_KEY == "" or API_KEY is None:
        print("Ошибка: нужно вставить API_KEY в файл перед запуском.")
        return
    print("Введите ссылку (или 'exit' для выхода): ", end="")
    for line in sys.stdin:
        url = line.strip()
        if url.lower() == "exit":
            break
        if not url:
            print("Пустая строка. Введите ссылку или 'exit'.")
            print("Введите ссылку (или 'exit' для выхода): ", end="")
            continue

        snippet = load_text_from_url(url)
        if snippet.startswith("Ошибка загрузки"):
            print(snippet)
        elif not snippet:
            print("Не удалось извлечь текст с этой страницы.")
        else:
            subject = classify_subject(snippet)
            print("Предмет:", subject)

        print("\nВведите ссылку (или 'exit' для выхода): ", end="")

if __name__ == '__main__':
    main()