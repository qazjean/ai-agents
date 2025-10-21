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

# Pydantic схема для валидации JSON
class LinkAnalysis(BaseModel):
    date: str = Field(..., description="Дата получения ссылки в формате YYYY-MM-DD")
    subject: str = Field(..., description="Название предмета: Численные методы | Компьютерные сети | Программирование на Python | Физика")
    url: str = Field(..., description="Оригинальная ссылка")

# Инструмент (tool) для записи
def save_json_to_file(data: dict) -> dict:
    filename = "requests.json"
    try:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                try:
                    existing = json.load(f)
                    if not isinstance(existing, list):
                        existing = []
                except json.JSONDecodeError:
                    existing = []
        else:
            existing = []

        existing.append(data)

        with open(filename, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=4)

        return {"status": "ok", "message": f"Saved to {filename}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


tool_registered = False
tool_name = "save_json_to_file"
try:
    if hasattr(llm, "bind_tools"):
        try:
            llm.bind_tools([save_json_to_file])
            tool_registered = True
        except Exception:
            try:
                llm.bind_tools([{"name": tool_name, "function": save_json_to_file}])
                tool_registered = True
            except Exception:
                tool_registered = False
    elif hasattr(llm, "register_tools"):
        try:
            llm.register_tools([save_json_to_file])
            tool_registered = True
        except Exception:
            tool_registered = False
    else:
        tool_registered = False
except Exception:
    tool_registered = False

if tool_registered:
    print(f"Tool registration attempt: OK (registered as '{tool_name}')")
else:
    print("Tool registration: SKIPPED or FAILED — fallback to local saving will be used.")

system_prompt = SystemMessage(content="""
Ты — помощник студента. У тебя список предметов:
- Численные методы
- Компьютерные сети
- Программирование на Python
- Физика

Задача: по фрагменту текста (до 1000 символов) определить наиболее подходящий предмет.
Если инструмент 'save_json_to_file' доступен, можешь сгенерировать tool_call с именем 'save_json_to_file' и аргументом args — JSON (date, subject, url).
Если не используешь tool_call, просто верни ровно валидный JSON:
{"date":"YYYY-MM-DD","subject":"<одно из названий точно так>","url":"<оригинальная ссылка>"}
НИЧЕГО ЛИШНЕГО вокруг JSON.
""")

# Вспомогательные функции
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

def extract_json_from_text(text: str):
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = text[start:i+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    return None
    return None

# получить JSON, валидировать, сохранить
def analyze_and_save(url: str) -> dict:
    snippet = load_text_from_url(url)
    if not snippet:
        return {"status": "error", "message": "Не удалось извлечь текст с этой страницы", "url": url}

    date_now = datetime.now().strftime("%Y-%m-%d")
    user_prompt = HumanMessage(content=f"Ссылка: {url}\nДата: {date_now}\nТекст:\n{snippet}\n\nВерни JSON или сделай tool_call как указано в системном сообщении.")
    messages = [system_prompt, user_prompt]

    response = llm.invoke(messages)


    tool_calls = getattr(response, "tool_calls", None)
    if tool_calls:
        try:
            if isinstance(tool_calls, dict):
                tool_calls_list = [tool_calls]
            else:
                tool_calls_list = list(tool_calls)
        except Exception:
            tool_calls_list = []

        for tc in tool_calls_list:
            name = tc.get("name") if isinstance(tc, dict) else None
            args = tc.get("args") if isinstance(tc, dict) else None
            if name and args and (name == tool_name or name == "save_json_to_file"):
                try:
                    if isinstance(args, str):
                        args_parsed = json.loads(args)
                    else:
                        args_parsed = args
                except Exception:
                    args_parsed = args
                try:
                    validated = LinkAnalysis.model_validate(args_parsed) if hasattr(LinkAnalysis, "model_validate") else LinkAnalysis(**args_parsed)
                    record = validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
                    save_res = save_json_to_file(record)
                    return {"status": "saved_via_toolcall", "tool_result": save_res, "record": record}
                except ValidationError as e:
                    return {"status": "error", "message": f"Toolcall JSON failed validation: {e}", "raw_args": args}
                    # если tool_calls есть, но не нашёлся подходящий — продолжаем парсинг content
                    # если tool_calls отсутствуют или не сработали — пытаемся извлечь JSON из content

    raw = getattr(response, "content", None)
    if raw is None:
        raw = str(response)
    raw_text = raw.strip()

    extracted = extract_json_from_text(raw_text)
    if not extracted:
        return {"status": "error", "message": "Не удалось извлечь JSON из ответа модели", "raw": raw_text}

    # Валидация через pydantic

    try:
        validated = LinkAnalysis.model_validate(extracted) if hasattr(LinkAnalysis, "model_validate") else LinkAnalysis(**extracted)
        record = validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
    except ValidationError as e:
        return {"status": "error", "message": f"JSON не прошёл валидацию: {e}", "extracted": extracted}

    save_res = save_json_to_file(record)
    return {"status": "saved", "save_result": save_res, "record": record}

def main():
    if not API_KEY:
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
        res = analyze_and_save(url)
        print(json.dumps(res, ensure_ascii=False, indent=4))
        print("\nВведите ссылку (или 'exit'):")

if __name__ == "__main__":
    main()