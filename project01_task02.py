import os
import sys
import json
from datetime import datetime

os.environ["USER_AGENT"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

from langchain_gigachat import GigaChat
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.document_loaders import UnstructuredURLLoader, WebBaseLoader
from pydantic import BaseModel, Field, ValidationError

API_KEY = "MDE5YTAyMjQtZjA3YS03Y2JhLTljYWQtMzM3ZDQ5MGUwMzM1OmFjMDRmNjRmLTdhMGQtNDhiZS1iODZhLWEzNjNjODA3OWRhNg=="

llm = GigaChat(credentials=API_KEY, verify_ssl_certs=False)

class LinkAnalysis(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    subject: str = Field(..., description="Один из: Численные методы | Компьютерные сети | Программирование на Python | Физика")
    url: str = Field(..., description="Оригинальная ссылка")

system_prompt = SystemMessage(content="""
Ты — помощник студента. По тексту (до 1000 символов) определи наиболее подходящий предмет:
- Численные методы
- Компьютерные сети
- Программирование на Python
- Физика

Верни ровно ВАЛИДНЫЙ JSON следующей структуры (и ничто больше):
{"date":"YYYY-MM-DD","subject":"<одно из названий точно так>","url":"<оригинальная ссылка>"}
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

def extract_json(text: str):
    # Найти первый валидный JSON-объект в тексте
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    return None
    return None

def ask_model(url: str, snippet: str, date_str: str):
    user_prompt = HumanMessage(content=f"Ссылка: {url}\nДата: {date_str}\nТекст:\n{snippet}\n\nВерни ровно JSON.")
    messages = [system_prompt, user_prompt]
    resp = llm.invoke(messages)
    raw = resp.content if hasattr(resp, "content") else str(resp)
    parsed = extract_json(raw)
    if parsed is None:
        raise ValueError("Не удалось извлечь JSON из ответа модели.")
    # валидация pydantic
    try:
        validated = LinkAnalysis.model_validate(parsed) if hasattr(LinkAnalysis, "model_validate") else LinkAnalysis(**parsed)
        return validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
    except ValidationError as e:
        raise ValueError(f"JSON есть, но не прошёл валидацию pydantic: {e}\nJSON: {parsed}")

def main():
    if API_KEY == "" or API_KEY is None:
        print("Ошибка: нужно вставить API_KEY в файл перед запуском.")
        return
    print("Введите ссылку (или 'exit'):")
    for line in sys.stdin:
        url = line.strip()
        if url.lower() == "exit":
            break
        if not url:
            print("Пустая строка. Введите ссылку или 'exit'.")
            continue
        snippet = load_text_from_url(url)
        if not snippet:
            print("Не удалось извлечь текст с этой страницы.")
            continue
        date_now = datetime.now().strftime("%Y-%m-%d")
        try:
            result = ask_model(url, snippet, date_now)
            print("\nJSON")
            print(json.dumps(result, ensure_ascii=False, indent=4))
            print("\n")
        except Exception as e:
            print("Ошибка при получении/проверке JSON:", e)
        print("Введите ссылку (или 'exit'):")

if __name__ == "__main__":
    main()