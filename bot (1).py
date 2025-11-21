import os
import asyncio
from typing import Dict, Any, List, TypedDict
import json
from datetime import datetime

import telebot
from telebot import types
from langchain_community.chat_models import GigaChat
from langchain.schema import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

# Настройки
BOT_TOKEN = "7843609023:AAFm67xyJmizDbsW0HY-AsZhnlUJJ-1Ak4s"
GIGACHAT_CREDENTIALS = ""


# Инициализация моделей
llm = GigaChat(
    credentials=GIGACHAT_CREDENTIALS,
    scope="GIGACHAT_API_PERS",
    verify_ssl_certs=False
)

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Хранилище состояний пользователей
user_sessions = {}


class UserState:
    def __init__(self):
        self.language = "ru"
        self.work_type = ""
        self.requirements = ""
        self.work_text = ""
        self.analysis_results = {}
        self.errors_list = []
        self.current_step = "start"


# Определение состояния для LangGraph
class AnalysisState(TypedDict):
    text: str
    work_type: str
    requirements: str
    language: str
    structure_analysis: Dict[str, Any]
    argument_analysis: Dict[str, Any]
    formal_analysis: Dict[str, Any]
    final_summary: str
    all_errors: List[str]


# Агент анализа структуры
def structure_agent(state: AnalysisState) -> AnalysisState:
    work_type_requirements = {
        "ru": {
            "📝 Эссе": "Эссе должно иметь четкую трехчастную структуру: введение, основная часть, заключение. Во введении - постановка проблемы, в основной части - аргументы, в заключении - выводы.",
            "📄 Курсовая": "Курсовая работа должна содержать: титульный лист, оглавление, введение, основную часть (2-3 главы), заключение, список литературы, приложения (при необходимости).",
            "🎓 Дипломная": "Дипломная работа включает: титульный лист, реферат, оглавление, введение, основную часть (3-4 главы), заключение, библиографию, приложения.",
            "🔬 Научная статья": "Научная статья должна содержать: аннотацию, ключевые слова, введение, методы исследования, результаты, обсуждение, заключение, список литературы.",
            "📚 Реферат": "Реферат имеет структуру: титульный лист, оглавление, введение, основную часть, заключение, список литературы.",
            "💼 Доклад": "Доклад включает: введение, основную часть (разделенную на логические части), заключение с выводами."
        },
        "en": {
            "📝 Essay": "Essay should have clear three-part structure: introduction, main body, conclusion. Introduction - problem statement, main body - arguments, conclusion - findings.",
            "📄 Coursework": "Coursework should contain: title page, table of contents, introduction, main part (2-3 chapters), conclusion, bibliography, appendices (if needed).",
            "🎓 Thesis": "Thesis includes: title page, abstract, table of contents, introduction, main part (3-4 chapters), conclusion, bibliography, appendices.",
            "🔬 Research Paper": "Research paper should contain: abstract, keywords, introduction, methods, results, discussion, conclusion, references.",
            "📚 Report": "Report structure: title page, table of contents, introduction, main part, conclusion, bibliography.",
            "💼 Presentation": "Presentation includes: introduction, main part (divided into logical sections), conclusion with findings."
        }
    }

    prompts = {
        "ru": """Ты - эксперт по анализу структуры академических текстов. Проанализируй предоставленный текст и оцени:
    1. Наличие четкого введения, постановки проблемы, основной части, заключения
    2. Логичность изложения и последовательность аргументов
    3. Соответствие содержания заявленной теме
    4. Наличие и уместность примеров, доказательств

    ОБЯЗАТЕЛЬНО обращай внимания на требования пользователя и редактируй текст в соответствии с ними
    Верни ответ в формате JSON:
    {
        "strengths": ["сильные_стороны"],
        "weaknesses": ["слабые_стороны", "конкретные_рекомендации по улучшению текста"],
        "errors": ["ошибка1", "ошибка2"]
    }""",

        "en": """You are an expert in analyzing the structure of academic texts. Analyze the provided text and evaluate:
    1. The presence of a clear introduction, problem statement, main body, and conclusion.
    2. The logic of the exposition and the sequence of arguments.
    3. The relevance of the content to the stated topic.
    4. The presence and appropriateness of examples and evidence.

    It is MANDATORY to pay attention to the user's requirements and edit the text accordingly.
    Return the answer in JSON format:
    {
        "strengths": ["strengths"],
        "weaknesses": ["weaknesses", "specific_recommendations for improving the text"],
        "errors": ["error1", "error2"]
    }""",

        "es": """Eres un experto en analizar la estructura de textos académicos. Analiza el texto proporcionado y evalúa:
    1. La presencia de una introducción clara, planteamiento del problema, cuerpo principal y conclusión.
    2. La lógica de la exposición y la secuencia de los argumentos.
    3. La pertinencia del contenido con el tema anunciado.
    4. La presencia y pertinencia de ejemplos y evidencias.

    Es OBLIGATORIO prestar atención a los requisitos del usuario y editar el texto de acuerdo con ellos.
    Devuelve la respuesta en formato JSON:
    {
        "strengths": ["fortalezas"],
        "weaknesses": ["debilidades", "recomendaciones_específicas para mejorar el texto"],"
        ""errors": ["error1", "error2"]
    }""",

        "fr": """Vous êtes un expert en analyse de la structure des textes académiques. Analysez le texte fourni et évaluez :
    1. La présence d'une introduction claire, d'une problématique, d'un développement et d'une conclusion.
    2. La logique de l'exposé et la séquence des arguments.
    3. La pertinence du contenu par rapport au sujet annoncé.
    4. La présence et la pertinence des exemples et des preuves.

    Il est OBLIGATOIRE de prêter attention aux exigences de l'utilisateur et de modifier le texte en conséquence.
    Retournez la réponse au format JSON :
    {
        "strengths": ["points_forts],
        "weaknesses": ["points_faibles", "recommandations_spécifiques pour améliorer le texte"],
        "errors": ["erreur1", "erreur2"]
    }""",

        "de": """Sie sind ein Experte für die Analyse der Struktur akademischer Texte. Analysieren Sie den bereitgestellten Text und bewerten Sie:
    1. Das Vorhandensein einer klaren Einleitung, Problemstellung, eines Hauptteils und eines Schlussteils.
    2. Die Logik der Darstellung und die Abfolge der Argumente.
    3. Die Relevanz des Inhalts für das angekündigte Thema.
    4. Das Vorhandensein und die Angemessenheit von Beispielen und Beweisen.

    Es ist ZWINGEND erforderlich, die Anforderungen des Nutzers zu beachten und den Text entsprechend zu bearbeiten.
    Geben Sie die Antwort im JSON-Format zurück:
    {
        "strengths": ["stärken"],
        "weaknesses": ["schwächen", "konkrete_empfehlungen zur verbesserung des textes"],
        "errors": ["fehler1", "fehler2"]
    }"""
    }

    work_type_req = work_type_requirements[state['language']].get(state['work_type'], "")

    prompt = f"""
ТИП РАБОТЫ: {state['work_type']}
ТРЕБОВАНИЯ К СТРУКТУРЕ ДЛЯ ДАННОГО ТИПА РАБОТЫ: {work_type_req}
ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ ПОЛЬЗОВАТЕЛЯ: {state['requirements'] if state['requirements'] else "Не указаны"}
ТЕКСТ ДЛЯ АНАЛИЗА: {state['text'][:4000]}
"""

    messages = [
        SystemMessage(content=prompts[state['language']]),
        HumanMessage(content=prompt)
    ]

    response = llm.invoke(messages)
    try:
        state['structure_analysis'] = json.loads(response.content)
    except:
        state['structure_analysis'] = {
            "score": "7",
            "strengths": ["Текст имеет базовую структуру"],
            "weaknesses": ["Нужно улучшить логические переходы"],
            "errors": ["Недостаточно четкое заключение"]
        }

    return state


def argument_agent(state: AnalysisState) -> AnalysisState:
    style_requirements = {
        "ru": {
            "📝 Эссе": "Стиль эссе - публицистический, допускается использование риторических вопросов, метафор, но аргументация должна быть четкой и логичной.",
            "📄 Курсовая": "Научный стиль, строгая аргументация, использование терминологии, ссылки на источники.",
            "🎓 Дипломная": "Академический стиль высшего уровня, глубокая аргументация, системный подход, обязательное использование научной литературы.",
            "🔬 Научная статья": "Строго научный стиль, объективность, точность формулировок, доказательность.",
            "📚 Реферат": "Научно-популярный стиль, доступность изложения при сохранении точности.",
            "💼 Доклад": "Публицистический стиль с элементами научности, ясность и доступность изложения."
        },
        "en": {
            "📝 Essay": "Essay style - publicistic, rhetorical questions and metaphors are allowed, but arguments should be clear and logical.",
            "📄 Coursework": "Scientific style, strict argumentation, terminology usage, references to sources.",
            "🎓 Thesis": "Highest level academic style, deep argumentation, systematic approach, mandatory use of scientific literature.",
            "🔬 Research Paper": "Strict scientific style, objectivity, precision of formulations, evidence-based.",
            "📚 Report": "Scientific-popular style, accessibility of presentation while maintaining accuracy.",
            "💼 Presentation": "Publicistic style with scientific elements, clarity and accessibility of presentation."
        }
    }

    prompts = {
        "ru": """Ты - эксперт по анализу аргументации и стиля. Проанализируй текст по критериям с учетом типа работы:
1. Убедительность и обоснованность аргументов (соответствие типу работы)
2. Соответствие стиля требованиям для данного типа работы
3. Ясность, точность и лаконичность формулировок
4. Использование клише, воды, эмоционально окрашенных выражений
5. Соответствие лексики и терминологии академическим стандартам для данного типа работы

Верни ответ в формате JSON:
{
    "score": "оценка_от_1_до_10",
    "argument_analysis": "анализ_аргументации",
    "style_analysis": "анализ_стиля", 
    "recommendations": ["рекомендация1", "рекомендация2"],
    "errors": ["ошибка1", "ошибка2"]
}""",
        "en": """You are an expert in argumentation and style analysis. Analyze the text by criteria considering work type:
1. Persuasiveness and validity of arguments (appropriate for work type)
2. Style appropriateness for this work type requirements
3. Clarity, precision, and conciseness of formulations
4. Use of clichés, filler words, emotionally colored expressions
5. Compliance of vocabulary and terminology with academic standards for this work type

Return response in JSON format:
{
    "score": "score_1_to_10", 
    "argument_analysis": "argument_analysis",
    "style_analysis": "style_analysis",
    "recommendations": ["recommendation1", "recommendation2"],
    "errors": ["error1", "error2"]
}"""
    }

    style_req = style_requirements[state['language']].get(state['work_type'], "")

    prompt = f"""
ТИП РАБОТЫ: {state['work_type']}
ТРЕБОВАНИЯ К СТИЛЮ И АРГУМЕНТАЦИИ ДЛЯ ДАННОГО ТИПА РАБОТЫ: {style_req}
ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ ПОЛЬЗОВАТЕЛЯ: {state['requirements'] if state['requirements'] else "Не указаны"}
ТЕКСТ ДЛЯ АНАЛИЗА: {state['text'][:4000]}
"""

    messages = [
        SystemMessage(content=prompts[state['language']]),
        HumanMessage(content=prompt)
    ]

    response = llm.invoke(messages)
    try:
        state['argument_analysis'] = json.loads(response.content)
    except:
        state['argument_analysis'] = {
            "score": "7",
            "argument_analysis": "Аргументация присутствует",
            "style_analysis": "Стиль соответствует типу работы",
            "recommendations": ["Улучшить доказательную базу"],
            "errors": ["Недостаточно источников"]
        }

    return state


# Агент проверки формальных требований
def formal_agent(state: AnalysisState) -> AnalysisState:
    formal_requirements = {
        "ru": {
            "📝 Эссе": "Объем: 2-5 страниц. Структура: введение, основная часть, заключение. Обязательно: заголовок, абзацы.",
            "📄 Курсовая": "Объем: 25-40 страниц. Обязательные элементы: титульный лист, оглавление, введение, главы, заключение, библиография (15+ источников).",
            "🎓 Дипломная": "Объем: 50-80 страниц. Обязательные элементы: титульный лист, аннотация, оглавление, введение, 3-4 главы, заключение, библиография (30+ источников), приложения.",
            "🔬 Научная статья": "Объем: 8-15 страниц. Обязательные элементы: аннотация, ключевые слова, введение, методы, результаты, обсуждение, заключение, литература (10+ источников).",
            "📚 Реферат": "Объем: 15-25 страниц. Обязательные элементы: титульный лист, оглавление, введение, основная часть, заключение, список литературы (10+ источников).",
            "💼 Доклад": "Объем: 5-10 страниц. Обязательные элементы: введение, основная часть (с подзаголовками), заключение, возможны иллюстрации."
        },
        "en": {
            "📝 Essay": "Volume: 2-5 pages. Structure: introduction, main body, conclusion. Required: title, paragraphs.",
            "📄 Coursework": "Volume: 25-40 pages. Required elements: title page, table of contents, introduction, chapters, conclusion, bibliography (15+ sources).",
            "🎓 Thesis": "Volume: 50-80 pages. Required elements: title page, abstract, table of contents, introduction, 3-4 chapters, conclusion, bibliography (30+ sources), appendices.",
            "🔬 Research Paper": "Volume: 8-15 pages. Required elements: abstract, keywords, introduction, methods, results, discussion, conclusion, references (10+ sources).",
            "📚 Report": "Volume: 15-25 pages. Required elements: title page, table of contents, introduction, main part, conclusion, bibliography (10+ sources).",
            "💼 Presentation": "Volume: 5-10 pages. Required elements: introduction, main part (with subheadings), conclusion, illustrations possible."
        }
    }

    prompts = {
        "ru": """Ты - эксперт по формальным требованиям к академическим работам. Проверь с учетом типа работы:
1. Структурные требования: наличие всех обязательных элементов для данного типа работы
2. Соответствие формальным критериям оформления (объем, структура)
3. Наличие всех требуемых разделов согласно типу работы
4. Выполнение специальных требований пользователя
5. Соответствие объема работы стандартам для данного типа

Верни ответ в формате JSON:
{
    "score": "оценка_от_1_до_10",
    "formal_evaluation": "оценка_формальных_требований",
    "missing_elements": ["отсутствующий_элемент1", "отсутствующий_элемент2"],
    "compliance_issues": ["проблема_соответствия1", "проблема_соответствия2"],
    "errors": ["ошибка1", "ошибка2"]
}""",
        "en": """You are an expert in formal requirements for academic works. Check considering work type:
1. Structural requirements: presence of all mandatory elements for this work type
2. Compliance with formal formatting criteria (volume, structure)
3. Presence of all required sections according to work type
4. Fulfillment of user's special requirements
5. Volume compliance with standards for this work type

Return response in JSON format:
{
    "score": "score_1_to_10",
    "formal_evaluation": "formal_evaluation", 
    "missing_elements": ["missing_element1", "missing_element2"],
    "compliance_issues": ["compliance_issue1", "compliance_issue2"],
    "errors": ["error1", "error2"]
}"""
    }

    formal_req = formal_requirements[state['language']].get(state['work_type'], "")

    prompt = f"""
ТИП РАБОТЫ: {state['work_type']}
ФОРМАЛЬНЫЕ ТРЕБОВАНИЯ ДЛЯ ДАННОГО ТИПА РАБОТЫ: {formal_req}
ДОПОЛНИТЕЛЬНЫЕ ТРЕБОВАНИЯ ПОЛЬЗОВАТЕЛЯ: {state['requirements'] if state['requirements'] else "Не указаны"}
ТЕКСТ ДЛЯ АНАЛИЗА: {state['text'][:4000]}
"""

    messages = [
        SystemMessage(content=prompts[state['language']]),
        HumanMessage(content=prompt)
    ]

    response = llm.invoke(messages)
    try:
        state['formal_analysis'] = json.loads(response.content)
    except:
        state['formal_analysis'] = {
            "score": "7",
            "formal_evaluation": "Базовые требования соблюдены",
            "missing_elements": ["Аннотация"],
            "compliance_issues": ["Не указаны ключевые слова"],
            "errors": ["Отсутствует список литературы"]
        }

    return state

def editor_agent(state: AnalysisState) -> AnalysisState:
    prompts = {
        "ru": {
            "summary": """Собери итоговый отчет на основе анализов трех экспертов. Ты отправляешь это пользователю напрямую, разговариваешь с ним. Ты не укоряешь пользователя, ты подбадриваешь и предлагаешь способы улучшения.

УЧТИ ТИП РАБОТЫ: {work_type}

Структура отчета:
1. Похвала (пример: "Здорово! Ты большой молодец! Ты хорошо справился с {work_type}!") и выделение сильных сторон, мягкая поддержка. 
2. Критика и слабые стороны (пронумерованный список ошибок) - объясни, почему это важно именно для {work_type}
3. Конкретные рекомендации по улучшению с учетом типа работы

Будь вежливым, конструктивным и профессиональным.""",
            "correction": """Исправь текст работы, устранив указанные ошибки. 
УЧТИ ТИП РАБОТЫ: {work_type}
Сохрани основное содержание, но улучши грамотность, структуру и стиль, соответствующий {work_type}.
После исправленного текста добавь комментарий о том, что именно было исправлено."""
        },
        "en": {
            "summary": """Compile a final report based on analyses from three experts.

CONSIDER WORK TYPE: {work_type}

Report structure:
1. Praise and strengths of the work - mention how well they handled {work_type}
2. Criticism and weaknesses (numbered list of errors) - explain why this is important specifically for {work_type}
3. Specific improvement recommendations considering work type

Be polite, constructive and professional.""",
            "correction": """Correct the text work by fixing the specified errors.
CONSIDER WORK TYPE: {work_type}
Preserve the main content but improve literacy, structure and style appropriate for {work_type}.
After the corrected text, add a comment about what exactly was fixed."""
        }
    }

    summary_prompt = prompts[state['language']]['summary'].format(work_type=state['work_type'])

    prompt = f"""
{summary_prompt}

ТИП РАБОТЫ: {state['work_type']}

АНАЛИЗ СТРУКТУРЫ:
{json.dumps(state['structure_analysis'], ensure_ascii=False, indent=2)}

АНАЛИЗ АРГУМЕНТАЦИИ И СТИЛЯ:
{json.dumps(state['argument_analysis'], ensure_ascii=False, indent=2)}

ФОРМАЛЬНЫЙ АНАЛИЗ:
{json.dumps(state['formal_analysis'], ensure_ascii=False, indent=2)}

Сгенерируй финальный отчет для студента:
"""

    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    state['final_summary'] = response.content

    # Собираем все ошибки
    all_errors = []
    for analysis in [state['structure_analysis'], state['argument_analysis'], state['formal_analysis']]:
        if 'errors' in analysis:
            all_errors.extend(analysis['errors'])

    state['all_errors'] = all_errors

    return state


# Создание графа мультиагентной системы
def create_analysis_graph():
    # Создаем граф
    workflow = StateGraph(AnalysisState)

    # Добавляем узлы
    workflow.add_node("structure_agent", structure_agent)
    workflow.add_node("argument_agent", argument_agent)
    workflow.add_node("formal_agent", formal_agent)
    workflow.add_node("editor_agent", editor_agent)

    # Определяем потоки
    workflow.set_entry_point("structure_agent")
    workflow.add_edge("structure_agent", "argument_agent")
    workflow.add_edge("argument_agent", "formal_agent")
    workflow.add_edge("formal_agent", "editor_agent")
    workflow.add_edge("editor_agent", END)

    return workflow.compile()


# Функция для исправления текста
async def correct_text(text: str, errors_to_fix: List[str], language: str, work_type: str) -> tuple[str, str]:
    prompts = {
        "ru": {
            "correction": """Исправь текст работы, устранив указанные ошибки. 
УЧТИ ТИП РАБОТЫ: {work_type}
Сохрани основное содержание, но улучши грамотность, структуру и стиль, соответствующий {work_type}.
После исправленного текста добавь комментарий о том, что именно было исправлено."""
        },
        "en": {
            "correction": """Correct the text work by fixing the specified errors.
CONSIDER WORK TYPE: {work_type}
Preserve the main content but improve literacy, structure and style appropriate for {work_type}.
After the corrected text, add a comment about what exactly was fixed."""
        }
    }

    correction_prompt = prompts[language]['correction'].format(work_type=work_type)

    prompt = f"""
{correction_prompt}

ТИП РАБОТЫ: {work_type}
Исходный текст: {text[:3000]}

Ошибки для исправления: {', '.join(errors_to_fix)}

Верни ответ в формате:
ИСПРАВЛЕННЫЙ ТЕКСТ:
[здесь исправленный текст]

КОММЕНТАРИЙ:
[здесь комментарий об исправлениях]
"""

    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)

    content = response.content
    if "ИСПРАВЛЕННЫЙ ТЕКСТ:" in content and "КОММЕНТАРИЙ:" in content:
        parts = content.split("КОММЕНТАРИЙ:")
        corrected_text = parts[0].replace("ИСПРАВЛЕННЫЙ ТЕКСТ:", "").strip()
        comment = parts[1].strip()
    else:
        corrected_text = content
        comment = "Были применены исправления согласно выбранным ошибкам."

    return corrected_text, comment


# Функции для создания клавиатур (остаются без изменений)
def create_language_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    btn_ru = types.KeyboardButton('🇷🇺 Русский')
    btn_en = types.KeyboardButton('🇺🇸 English')
    btn_es = types.KeyboardButton('🇪🇸 Español')
    btn_fr = types.KeyboardButton('🇫🇷 Français')
    btn_de = types.KeyboardButton('🇩🇪 Deutsch')
    markup.add(btn_ru, btn_en, btn_es, btn_fr, btn_de)
    return markup


def create_work_type_keyboard(language: str):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)

    work_types = {
        'ru': ['📝 Эссе', '📄 Курсовая', '🎓 Дипломная', '🔬 Научная статья', '📚 Реферат', '💼 Доклад'],
        'en': ['📝 Essay', '📄 Coursework', '🎓 Thesis', '🔬 Research Paper', '📚 Report', '💼 Presentation'],
        'es': ['📝 Ensayo', '📄 Trabajo', '🎓 Tesis', '🔬 Artículo', '📚 Informe', '💼 Presentación'],
        'fr': ['📝 Essai', '📄 Projet', '🎓 Mémoire', '🔬 Article', '📚 Rapport', '💼 Présentation'],
        'de': ['📝 Essay', '📄 Arbeit', '🎓 Abschlussarbeit', '🔬 Artikel', '📚 Bericht', '💼 Präsentation']
    }

    work_type_buttons = work_types.get(language, work_types['en'])
    for btn_text in work_type_buttons:
        markup.add(types.KeyboardButton(btn_text))

    return markup


def create_requirements_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    btn_no_req = types.KeyboardButton('-')
    btn_back = types.KeyboardButton('◀Назад')
    markup.add(btn_no_req, btn_back)
    return markup


def create_back_keyboard():
    markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True, one_time_keyboard=True)
    btn_back = types.KeyboardButton('◀Назад')
    markup.add(btn_back)
    return markup


# Обработчики Telegram бота (остаются без изменений)
@bot.message_handler(commands=['start'])
def start_handler(message):
    chat_id = message.chat.id
    user_sessions[chat_id] = UserState()

    welcome_text = """
🇷🇺 Добро пожаловать в AI-ассистент для анализа академических работ!

Я помогу вам:
• Проанализировать структуру работы
• Оценить аргументацию и стиль
• Проверить формальные требования
• Предложить исправления и улучшения

Выберите язык для общения:


🇺🇸 Welcome to the AI Assistant for analyzing academic works!

I will help you:
• Analyze the structure of your work
• Evaluate argumentation and style
• Check formal requirements
• Suggest corrections and improvements

Choose your language for communication:
"""

    bot.send_message(chat_id, welcome_text, reply_markup=create_language_keyboard())
    user_sessions[chat_id].current_step = "language_selection"


@bot.message_handler(func=lambda message:
user_sessions.get(message.chat.id) and
user_sessions[message.chat.id].current_step == "language_selection")
def language_handler(message):
    chat_id = message.chat.id
    lang_map = {
        '🇷🇺 Русский': 'ru',
        '🇺🇸 English': 'en',
        '🇪🇸 Español': 'es',
        '🇫🇷 Français': 'fr',
        '🇩🇪 Deutsch': 'de'
    }

    if message.text in lang_map:
        user_sessions[chat_id].language = lang_map[message.text]
        user_sessions[chat_id].current_step = "work_type_selection"

        greetings = {
            'ru': "Отлично! Теперь выберите тип вашей работы:",
            'en': "Great! Now choose your work type:",
            'es': "¡Excelente! Ahora elija el tipo de trabajo:",
            'fr': "Excellent ! Maintenant choisissez le type de travail :",
            'de': "Ausgezeichnet! Wählen Sie nun die Art der Arbeit:"
        }

        greeting = greetings.get(user_sessions[chat_id].language, greetings['en'])
        bot.send_message(chat_id, greeting, reply_markup=create_work_type_keyboard(user_sessions[chat_id].language))
    else:
        error_text = {
            'ru': "Пожалуйста, выберите язык из предложенных вариантов:",
            'en': "Please choose a language from the options provided:",
            'es': "Por favor, elija un idioma de las opciones proporcionadas:",
            'fr': "Veuillez choisir une langue parmi les options proposées :",
            'de': "Bitte wählen Sie eine Sprache aus den bereitgestellten Optionen:"
        }
        error_msg = error_text.get(user_sessions[chat_id].language, error_text['en'])
        bot.send_message(chat_id, error_msg, reply_markup=create_language_keyboard())


@bot.message_handler(func=lambda message:
user_sessions.get(message.chat.id) and
user_sessions[message.chat.id].current_step == "work_type_selection")
def work_type_handler(message):
    chat_id = message.chat.id

    # Проверяем, не является ли сообщение командой "Назад"
    if message.text == '◀Назад':
        user_sessions[chat_id].current_step = "language_selection"
        back_text = {
            'ru': "Выберите язык для общения:",
            'en': "Choose language for communication:",
            'es': "Elija idioma para la comunicación:",
            'fr': "Choisissez la langue pour la communication :",
            'de': "Wählen Sie die Sprache für die Kommunikation:"
        }
        text = back_text.get(user_sessions[chat_id].language, back_text['en'])
        bot.send_message(chat_id, text, reply_markup=create_language_keyboard())
        return

    user_sessions[chat_id].work_type = message.text
    user_sessions[chat_id].current_step = "requirements_input"

    prompts = {
        'ru': "Укажите особые требования к работе (или нажмите '-', если требований нет):",
        'en': "Specify special requirements for the work (or press '-' if no requirements):",
        'es': "Especifique requisitos especiales para el trabajo (o presione '-' si no hay requisitos):",
        'fr': "Spécifiez les exigences particulières pour le travail (ou appuyez sur '-' s'il n'y a pas d'exigences):",
        'de': "Geben Sie besondere Anforderungen für die Arbeit an (oder drücken Sie '-', wenn keine Anforderungen vorhanden sind):"
    }

    prompt = prompts.get(user_sessions[chat_id].language, prompts['en'])
    bot.send_message(chat_id, prompt, reply_markup=create_requirements_keyboard())


@bot.message_handler(func=lambda message:
user_sessions.get(message.chat.id) and
user_sessions[message.chat.id].current_step == "requirements_input")
def requirements_handler(message):
    chat_id = message.chat.id

    # Обработка кнопки "Назад"
    if message.text == '◀Назад':
        user_sessions[chat_id].current_step = "work_type_selection"
        back_text = {
            'ru': "Выберите тип вашей работы:",
            'en': "Choose your work type:",
            'es': "Elija el tipo de trabajo:",
            'fr': "Choisissez le type de travail :",
            'de': "Wählen Sie die Art der Arbeit:"
        }
        text = back_text.get(user_sessions[chat_id].language, back_text['en'])
        bot.send_message(chat_id, text, reply_markup=create_work_type_keyboard(user_sessions[chat_id].language))
        return

    user_sessions[chat_id].requirements = message.text
    user_sessions[chat_id].current_step = "text_input"

    prompts = {
        'ru': "Теперь отправьте текст вашей работы:",
        'en': "Now send the text of your work:",
        'es': "Ahora envíe el texto de su trabajo:",
        'fr': "Envoyez maintenant le texte de votre travail :",
        'de': "Senden Sie nun den Text Ihrer Arbeit:"
    }

    prompt = prompts.get(user_sessions[chat_id].language, prompts['en'])
    bot.send_message(chat_id, prompt, reply_markup=create_back_keyboard())


@bot.message_handler(func=lambda message:
user_sessions.get(message.chat.id) and
user_sessions[message.chat.id].current_step == "text_input")
def text_handler(message):
    chat_id = message.chat.id

    # Обработка кнопки "Назад"
    if message.text == '◀Назад':
        user_sessions[chat_id].current_step = "requirements_input"
        back_text = {
            'ru': "Укажите особые требования к работе (или нажмите '-', если требований нет):",
            'en': "Specify special requirements for the work (or press '-' if no requirements):",
            'es': "Especifique requisitos especiales para el trabajo (o presione '-' si no hay requisitos):",
            'fr': "Spécifiez les exigences particulières pour le travail (ou appuyez sur '-' s'il n'y a pas d'exigences):",
            'de': "Geben Sie besondere Anforderungen für die Arbeit an (oder drücken Sie '-', wenn keine Anforderungen vorhanden sind):"
        }
        text = back_text.get(user_sessions[chat_id].language, back_text['en'])
        bot.send_message(chat_id, text, reply_markup=create_requirements_keyboard())
        return

    user_sessions[chat_id].work_text = message.text
    user_sessions[chat_id].current_step = "processing"

    processing_texts = {
        'ru': "⏳ Анализирую вашу работу... Это займет несколько секунд.",
        'en': "⏳ Analyzing your work... This will take a few seconds.",
        'es': "⏳ Analizando su trabajo... Esto tomará unos segundos.",
        'fr': "⏳ Analyse de votre travail... Cela prendra quelques secondes.",
        'de': "⏳ Analysiere Ihre Arbeit... Dies wird einige Sekunden dauern."
    }

    bot.send_message(chat_id, processing_texts.get(user_sessions[chat_id].language, processing_texts['en']))

    # Запускаем анализ в отдельном потоке
    asyncio.run(perform_analysis(chat_id))


async def perform_analysis(chat_id):
    try:
        user_state = user_sessions[chat_id]

        # Создаем граф и выполняем анализ
        graph = create_analysis_graph()

        initial_state = AnalysisState(
            text=user_state.work_text,
            work_type=user_state.work_type,
            requirements=user_state.requirements,
            language=user_state.language,
            structure_analysis={},
            argument_analysis={},
            formal_analysis={},
            final_summary="",
            all_errors=[]
        )

        result = graph.invoke(initial_state)

        # Сохраняем результаты
        user_state.analysis_results = result
        user_state.errors_list = result['all_errors']

        # Отправляем результаты пользователю
        success_texts = {
            'ru': "Анализ завершен! Вот результаты:",
            'en': "Analysis completed! Here are the results:",
            'es': "Análisis completado! Aquí están los resultados:",
            'fr': "Analyse terminée ! Voici les résultats :",
            'de': "Analyse abgeschlossen! Hier sind die Ergebnisse:"
        }

        bot.send_message(chat_id, success_texts.get(user_state.language, success_texts['en']))
        bot.send_message(chat_id, result['final_summary'])

        # Показываем ошибки для выбора
        if user_state.errors_list:
            error_text = "\n".join([f"{i + 1}. {error}" for i, error in enumerate(user_state.errors_list)])
            prompt_texts = {
                'ru': f"Обнаруженные ошибки:\n{error_text}\n\nВведите номера ошибок через запятую для исправления (например: 1,3,5) или '0' чтобы пропустить:",
                'en': f"Detected errors:\n{error_text}\n\nEnter error numbers separated by commas to fix (e.g.: 1,3,5) or '0' to skip:",
                'es': f"Errores detectados:\n{error_text}\n\nIngrese números de error separados por comas para corregir (ej.: 1,3,5) o '0' para omitir:",
                'fr': f"Erreurs détectées :\n{error_text}\n\nEntrez les numéros d'erreur séparés par des virgules pour les corriger (ex. : 1,3,5) ou '0' pour ignorer :",
                'de': f"Gefundene Fehler:\n{error_text}\n\nGeben Sie Fehlernummern getrennt durch Kommas ein, um sie zu beheben (z.B.: 1,3,5) oder '0' zum Überspringen:"
            }

            # Создаем клавиатуру для выбора ошибок
            markup = types.ReplyKeyboardMarkup(row_width=3, resize_keyboard=True)
            if len(user_state.errors_list) > 0:
                for i in range(min(6, len(user_state.errors_list))):
                    markup.add(types.KeyboardButton(str(i + 1)))
            markup.add(types.KeyboardButton('0 - Пропустить'))
            markup.add(types.KeyboardButton('◀Назад к началу'))

            bot.send_message(chat_id, prompt_texts.get(user_state.language, prompt_texts['en']), reply_markup=markup)
            user_state.current_step = "error_selection"
        else:
            no_errors_texts = {
                'ru': "Поздравляю! Серьезных ошибок не обнаружено. Хотите начать заново?",
                'en': "Congratulations! No serious errors detected. Want to start over?",
                'es': "¡Felicidades! No se detectaron errores graves. ¿Quieres empezar de nuevo?",
                'fr': "Félicitations ! Aucune erreur grave détectée. Voulez-vous recommencer ?",
                'de': "Glückwunsch! Keine schwerwiegenden Fehler gefunden. Möchten Sie von vorne beginnen?"
            }

            markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
            markup.add(types.KeyboardButton('/start'))

            bot.send_message(chat_id, no_errors_texts.get(user_state.language, no_errors_texts['en']),
                             reply_markup=markup)
            user_state.current_step = "start"

    except Exception as e:
        error_texts = {
            'ru': f"Произошла ошибка при анализе: {str(e)}",
            'en': f"An error occurred during analysis: {str(e)}",
            'es': f"Ocurrió un error durante el análisis: {str(e)}",
            'fr': f"Une erreur s'est produite lors de l'analyse : {str(e)}",
            'de': f"Während der Analyse ist ein Fehler aufgetreten: {str(e)}"
        }

        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        markup.add(types.KeyboardButton('/start'))

        bot.send_message(chat_id, error_texts.get(user_sessions[chat_id].language, error_texts['en']),
                         reply_markup=markup)
        user_sessions[chat_id].current_step = "start"


@bot.message_handler(func=lambda message:
user_sessions.get(message.chat.id) and
user_sessions[message.chat.id].current_step == "error_selection")
def error_selection_handler(message):
    chat_id = message.chat.id
    user_state = user_sessions[chat_id]

    # Обработка кнопки "Назад к началу"
    if message.text == '◀Назад к началу':
        user_state.current_step = "start"
        bot.send_message(chat_id, "Начинаем заново...", reply_markup=types.ReplyKeyboardRemove())
        start_handler(
            types.Message(message_id=message.message_id, chat=message.chat, date=message.date, content_type='text',
                          text='/start', json_string=''))
        return

    # Обработка пропуска исправлений
    if message.text in ['0', '0 - Пропустить']:
        skip_texts = {
            'ru': "Вы пропустили исправления. Хотите начать заново?",
            'en': "You skipped corrections. Want to start over?",
            'es': "Omitiste las correcciones. ¿Quieres empezar de nuevo?",
            'fr': "Vous avez ignoré les corrections. Voulez-vous recommencer ?",
            'de': "Sie haben die Korrekturen übersprungen. Möchten Sie von vorne beginnen?"
        }

        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        markup.add(types.KeyboardButton('/start'))

        bot.send_message(chat_id, skip_texts.get(user_state.language, skip_texts['en']), reply_markup=markup)
        user_state.current_step = "start"
        return

    try:
        selected_indices = [int(x.strip()) - 1 for x in message.text.split(",")]
        errors_to_fix = []

        for idx in selected_indices:
            if 0 <= idx < len(user_state.errors_list):
                errors_to_fix.append(user_state.errors_list[idx])

        if errors_to_fix:
            user_state.current_step = "correcting"
            correcting_texts = {
                'ru': "Исправляю выбранные ошибки...",
                'en': "Correcting selected errors...",
                'es': "Corrigiendo errores seleccionados...",
                'fr': "Correction des erreurs sélectionnées...",
                'de': "Korrigiere ausgewählte Fehler..."
            }
            bot.send_message(chat_id, correcting_texts.get(user_state.language, correcting_texts['en']))

            # Запускаем исправление
            asyncio.run(perform_correction(chat_id, errors_to_fix))
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите корректные номера ошибок.")

    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, введите номера через запятую (например: 1,3,5).")


async def perform_correction(chat_id, errors_to_fix):
    try:
        user_state = user_sessions[chat_id]

        corrected_text, comment = await correct_text(user_state.work_text, errors_to_fix, user_state.language,
                                                     user_state.work_type)

        result_texts = {
            'ru': "Исправленный текст:",
            'en': "Corrected text:",
            'es': "Texto corregido:",
            'fr': "Texte corrigé :",
            'de': "Korrigierter Text:"
        }

        bot.send_message(chat_id, result_texts.get(user_state.language, result_texts['en']))
        bot.send_message(chat_id, corrected_text)

        comment_texts = {
            'ru': "Комментарий к исправлениям:",
            'en': "Correction comments:",
            'es': "Comentarios de corrección:",
            'fr': "Commentaires de correction :",
            'de': "Korrekturkommentare:"
        }

        bot.send_message(chat_id, f"{comment_texts.get(user_state.language, comment_texts['en'])}\n{comment}")

        # Предлагаем начать заново
        restart_texts = {
            'ru': "Хотите проанализировать другой текст?",
            'en': "Want to analyze another text?",
            'es': "¿Quieres analizar otro texto?",
            'fr': "Voulez-vous analyser un autre texte ?",
            'de': "Möchten Sie einen anderen Text analysieren?"
        }

        markup = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
        markup.add(types.KeyboardButton('/start'))

        bot.send_message(chat_id, restart_texts.get(user_state.language, restart_texts['en']), reply_markup=markup)
        user_state.current_step = "start"

    except Exception as e:
        error_texts = {
            'ru': f"Ошибка при исправлении: {str(e)}",
            'en': f"Error during correction: {str(e)}",
            'es': f"Error durante la corrección: {str(e)}",
            'fr': f"Erreur lors de la correction : {str(e)}",
            'de': f"Fehler während der Korrektur: {str(e)}"
        }
        bot.send_message(chat_id, error_texts.get(user_sessions[chat_id].language, error_texts['en']))
        user_sessions[chat_id].current_step = "start"


# Обработчик команды помощи
@bot.message_handler(commands=['help'])
def help_handler(message):
    help_text = """
 <b>Помощь по боту</b>

<b>Основные команды:</b>
/start - Начать работу с ботом
/help - Показать эту справку

<b>Как работает бот:</b>
1. Выбираете язык общения
2. Выбираете тип работы
3. Указываете требования (или пропускаете)
4. Отправляете текст работы
5. Получаете анализ от 3 AI-агентов
6. Выбираете ошибки для исправления
7. Получаете исправленный текст

<b>Поддерживаемые типы работ:</b>
• Эссе, курсовые, дипломные
• Научные статьи, рефераты
• Доклады и презентации

<b>Языки:</b> Русский, English, Español, Français, Deutsch
"""
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')


# Обработчик любых других сообщений
@bot.message_handler(func=lambda message: True)
def default_handler(message):
    chat_id = message.chat.id

    if chat_id not in user_sessions:
        user_sessions[chat_id] = UserState()

    # Если пользователь просто написал сообщение без контекста
    if user_sessions[chat_id].current_step == "start":
        bot.send_message(chat_id, "Для начала работы отправьте команду /start",
                         reply_markup=types.ReplyKeyboardRemove())
    else:
        bot.send_message(chat_id, "Пожалуйста, следуйте инструкциям выше ")


# Запуск бота
if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling() 