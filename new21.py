import os
import sys
import json
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

os.environ["USER_AGENT"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

API_KEY = "MDE5YTAyMjQtZjA3YS03Y2JhLTljYWQtMzM3ZDQ5MGUwMzM1OmFjMDRmNjRmLTdhMGQtNDhiZS1iODZhLWEzNjNjODA3OWRhNg=="
REQUESTS_FILE = "requests.json"
MAX_SNIPPET_CHARS = 1000

from langchain_gigachat import GigaChat
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.document_loaders import UnstructuredURLLoader
from pydantic import BaseModel, Field, ValidationError

if not API_KEY:
    print("ERROR: вставь API_KEY в переменную API_KEY в файле перед запуском.")
    sys.exit(1)

llm = GigaChat(credentials=API_KEY, verify_ssl_certs=False)


class LinkAnalysis(BaseModel):
    date: str = Field(..., description="Дата получения ссылки в формате YYYY-MM-DD")
    subject: str = Field(...,
                         description="Один из: Численные методы | Компьютерные сети | Программирование на Python | Физика")
    url: str = Field(..., description="Оригинальная ссылка")


# ========== СОДЕРЖАМОЕ ВАШЕГО КОДА (минимальные изменения) ==========

def save_json_to_file(record: dict) -> dict:
    """Сохранение записи в файл (ваш код без изменений)"""
    try:
        if os.path.exists(REQUESTS_FILE):
            try:
                with open(REQUESTS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        data = []
            except Exception:
                data = []
        else:
            data = []

        data.append(record)
        with open(REQUESTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return {"status": "ok", "message": f"Saved to {REQUESTS_FILE}"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def load_text_snippet(url: str, max_chars: int = MAX_SNIPPET_CHARS) -> str:
    """Загрузка текста с URL (ваш код)"""
    try:
        loader = UnstructuredURLLoader(urls=[url])
        docs = loader.load()
        if not docs:
            return ""
        full = " ".join(d.page_content for d in docs)
        cleaned = " ".join(full.split())
        return cleaned[:max_chars]
    except Exception:
        return ""


def extract_json_from_text(text: str) -> Optional[dict]:
    """Извлечение JSON из текста (ваш код)"""
    if not text:
        return None
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
                candidate = text[start:i + 1]
                try:
                    return json.loads(candidate)
                except Exception:
                    return None
    return None


def parse_iso_date(s: str) -> Optional[datetime]:
    """Парсинг дат (ваш код)"""
    try:
        return datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except Exception:
            return None


def query_records(subject: str, date_from: str, date_to: str) -> List[dict]:
    """Запрос записей (ваш код)"""
    if not os.path.exists(REQUESTS_FILE):
        return []
    try:
        with open(REQUESTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []
    except Exception:
        return []

    df = parse_iso_date(date_from)
    dt = parse_iso_date(date_to)
    if df is None or dt is None:
        return []

    out = []
    for rec in data:
        try:
            rec_date = parse_iso_date(rec.get("date", ""))
            rec_subject = rec.get("subject", "")
            if rec_date and df <= rec_date <= dt and rec_subject == subject:
                out.append(rec)
        except Exception:
            continue
    return out


def load_links_docx(filename: str) -> List[str]:
    """Загрузка ссылок из DOCX (ваш код)"""
    try:
        from docx import Document
    except Exception:
        print("python-docx not installed. Install: pip install python-docx")
        return []
    try:
        doc = Document(filename)
        urls = []
        for p in doc.paragraphs:
            text = p.text.strip()
            if text and text.startswith("http"):
                urls.append(text)
        return urls
    except Exception as e:
        print("Error reading docx:", e)
        return []


# ========== ИНСТРУМЕНТЫ ДЛЯ LANGGraph ==========

from langchain_core.tools import tool


@tool
def classify_url_tool(url: str) -> str:
    """Классифицирует URL по учебным предметам и сохраняет результат"""
    snippet = load_text_snippet(url)
    if not snippet:
        return f"Ошибка: не удалось загрузить текст с URL {url}"

    date_now = datetime.now().strftime("%Y-%m-%d")

    # Используем LLM для классификации
    system_prompt = SystemMessage(content="""
    Ты — помощник студента. Определи предмет для учебного материала.
    Доступные предметы: Численные методы, Компьютерные сети, Программирование на Python, Физика.
    Верни ТОЛЬКО JSON формата: {"date":"YYYY-MM-DD","subject":"название предмета","url":"ссылка"}
    """)

    user_prompt = HumanMessage(content=f"URL: {url}\nДата: {date_now}\nТекст:\n{snippet}\n\nВерни JSON.")

    try:
        response = llm.invoke([system_prompt, user_prompt])
        raw_content = response.content if hasattr(response, 'content') else str(response)

        # Извлекаем JSON
        json_match = re.search(r'\{[^{}]*\}', raw_content)
        if json_match:
            parsed = json.loads(json_match.group())
            validated = LinkAnalysis(**parsed)
            record = validated.dict()

            # Сохраняем
            save_result = save_json_to_file(record)
            return f"Успешно классифицирован: {record['subject']}. Сохранено: {save_result['status']}"
        else:
            return f"Ошибка: не найден JSON в ответе. Ответ: {raw_content}"

    except Exception as e:
        return f"Ошибка классификации: {str(e)}"


@tool
def get_report_tool(subject: str, date_from: str, date_to: str) -> str:
    """Возвращает отчет по материалам за указанный период"""
    records = query_records(subject, date_from, date_to)

    if not records:
        return f"Нет материалов по предмету '{subject}' за период с {date_from} по {date_to}"

    # Сортируем по дате
    sorted_records = sorted(records, key=lambda x: x["date"])

    # Формируем отчет
    report = {
        "subject": subject,
        "count": len(records),
        "period": f"{date_from} - {date_to}",
        "materials": sorted_records
    }

    return json.dumps(report, ensure_ascii=False, indent=2)


@tool
def process_docx_tool(filename: str = "links.docx") -> str:
    """Обрабатывает все ссылки из DOCX файла"""
    urls = load_links_docx(filename)

    if not urls:
        return "Не найдено ссылок в файле или файл не существует"

    results = []
    for i, url in enumerate(urls, 1):
        result = classify_url_tool.invoke({"url": url})
        results.append(f"{i}. {url}: {result}")

    return f"Обработано {len(urls)} ссылок:\n" + "\n".join(results)


# ========== LANGGraph АГЕНТ ==========

from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class State(TypedDict):
    messages: Annotated[list, add_messages]


# Регистрируем инструменты
TOOLS = [classify_url_tool, get_report_tool, process_docx_tool]
llm_with_tools = llm.bind_tools(TOOLS)

# Системный промпт агента
SYSTEM_PROMPT = SystemMessage(content="""
Ты — интеллектуальный помощник для управления учебными материалами.
Ты помогаешь студентам классифицировать учебные материалы по предметам и получать отчеты.

Доступные инструменты:
1. classify_url_tool - классифицирует URL по предметам и сохраняет
2. get_report_tool - возвращает отчет по материалам за период  
3. process_docx_tool - обрабатывает ссылки из DOCX файла

Ты понимаешь команды:
- Прямой URL для классификации
- "отчет предмет=<название> с=<дата> по=<дата>"
- "обработать docx" для пакетной обработки
- "выход" для завершения

Всегда отвечай вежливо и помогай пользователю.
""")

from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, START

# Создаем граф
graph_builder = StateGraph(State)

# Узел для инструментов
tool_node = ToolNode(tools=TOOLS)


# Узел агента
def agent_node(state: State):
    messages = [SYSTEM_PROMPT] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}


# Добавляем узлы
graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tools", tool_node)

# Условные переходы
from langgraph.prebuilt import tools_condition

graph_builder.add_conditional_edges(
    "agent",
    tools_condition,
    {"tools": "tools"}
)

graph_builder.add_edge("tools", "agent")
graph_builder.add_edge(START, "agent")

# Компилируем граф
graph = graph_builder.compile()


# ========== ИНТЕРАКТИВНЫЙ ИНТЕРФЕЙС (адаптированный ваш код) ==========

def interactive_loop():
    print("Реактивный агент учебных материалов (LangGraph) запущен!")
    print("Команды:")
    print(" - Введите URL для классификации")
    print(" - 'отчет предмет=<предмет> с=<дата> по=<дата>'")
    print(" - 'обработать docx' для пакетной обработки")
    print(" - 'выход' для завершения")
    print()

    while True:
        try:
            user_input = input("Пользователь: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nЗавершение работы.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "выход"):
            break

        # Преобразуем команды в естественный язык для агента
        processed_input = user_input

        # Обработка команды отчета
        report_match = re.search(
            r"отчет\s+предмет=(?P<subject>.+?)\s+с=(?P<from_date>\d{4}-\d{2}-\d{2})\s+по=(?P<to_date>\d{4}-\d{2}-\d{2})",
            user_input, re.IGNORECASE)
        if report_match:
            subject = report_match.group("subject").strip()
            from_date = report_match.group("from_date")
            to_date = report_match.group("to_date")
            processed_input = f"Получи отчет по предмету {subject} с {from_date} по {to_date}"

        # Обработка команды docx
        elif user_input.lower() == "обработать docx":
            processed_input = "Обработай все ссылки из файла links.docx"

        # Запускаем граф
        print("Агент: ", end="", flush=True)

        try:
            for event in graph.stream({"messages": [{"role": "user", "content": processed_input}]}):
                for value in event.values():
                    last_message = value["messages"][-1]

                    if hasattr(last_message, 'content'):
                        content = last_message.content
                        if content:  # Не печатаем пустые сообщения
                            print(content)

                    # Если есть результаты инструментов, покажем их
                    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                        for tool_call in last_message.tool_calls:
                            print(f"[Вызван инструмент: {tool_call['name']}]")

        except Exception as e:
            print(f"Ошибка выполнения: {e}")

        print()


if __name__ == "__main__":
    interactive_loop()