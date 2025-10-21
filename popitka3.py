import os
import telebot
from langchain_gigachat import GigaChat
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START
from langgraph.prebuilt import ToolNode, tools_condition
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
import json
from datetime import date

API_KEY = "MDE5YTAyMjQtZjA3YS03Y2JhLTljYWQtMzM3ZDQ5MGUwMzM1OmFjMDRmNjRmLTdhMGQtNDhiZS1iODZhLWEzNjNjODA3OWRhNg=="
BOT_TOKEN = "8319899525:AAHjo6r5kM4JV2aKJOOJIdvXXDiPYefh9N8"

llm = GigaChat(credentials=API_KEY, verify_ssl_certs=False, model="GigaChat-2")

# --- 2. Определяем tool для сохранения JSON ---
@tool
def save_json_tool(data: dict):
    """Сохраняет данные в файл requests.json"""
    file_path = "requests.json"
    try:
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        else:
            existing = []
    except json.JSONDecodeError:
        existing = []

    existing.append(data)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=4)
    return " успешно сохранены."

TOOLS = [save_json_tool]
llm = llm.bind_tools(TOOLS)

# --- 3. Системный промпт для агента ---
SYSTEM_PROMPT = SystemMessage(content="""
You are a strict classification assistant. GIVEN a short snippet of a web page, you MUST return EXACTLY ONE of two formats and NOTHING else:

1) If your environment supports calling a tool named 'save_json_to_file', you MAY return a tool_call specifying the tool and providing ARGUMENTS (args) as a JSON object with keys: date, subject, url. Example tool_call (pseudocode):
{
  "name": "save_json_to_file",
  "args": {"date":"2025-10-20","subject":"Программирование на Python","url":"https://..."}
}

OR

2) If you cannot or do not call tools, you MUST return EXACTLY a single JSON object (no explanations, no extra text) with fields:
{"date":"YYYY-MM-DD","subject":"<one of: Численные методы | Компьютерные сети | Программирование на Python | Физика>","url":"<original url>"}

If unsure, choose the best-matching subject from the provided list. Do NOT invent schedules, narratives, or other text.
""")

# --- 4. Определение состояния агента ---
class State(TypedDict):
    messages: Annotated[list, add_messages]

# --- 5. Узлы графа ---
tool_node = ToolNode(tools=TOOLS)

def chatbot(state: State):
    """Основной чат-бот узел"""
    return {"messages": [llm.invoke([SYSTEM_PROMPT] + state["messages"])]}

# --- 6. Сборка графа ---
graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", tool_node)
graph_builder.add_conditional_edges("chatbot", tools_condition)
graph_builder.add_edge("tools", "chatbot")
graph_builder.add_edge(START, "chatbot")
graph = graph_builder.compile()

# --- 7. Telegram бот ---
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id,
                     "Привет! Я учебный ИИ-агент 🤖.\n"
                     "Отправь ссылку, чтобы я её разобрал и сохранил.\n"
                     "Или задай вопрос типа:\n"
                     "«Покажи материалы по математике за октябрь 2025».")

@bot.message_handler(content_types=['text'])
def process_message(message):
    user_input = message.text.strip()
    user_id = message.chat.id

    try:
        # Передаём сообщение в граф агента
        for event in graph.stream({"messages": [HumanMessage(content=user_input)]}):
            for value in event.values():
                if "messages" in value and len(value["messages"]) > 0:
                    response = value["messages"][-1].content
                    bot.send_message(user_id, f"Ответ агента:\n{response}")
    except Exception as e:
        bot.send_message(user_id, f"⚠Ошибка: {str(e)}")

# --- 8. Запуск бота ---
print("🤖 Telegram бот запущен. Открой его в Telegram и начни чат.")
bot.polling(none_stop=True)