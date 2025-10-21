import os
import sys
import json
import re
from datetime import datetime
from typing import Optional, List

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
    subject: str = Field(..., description="Один из: Численные методы | Компьютерные сети | Программирование на Python | Физика")
    url: str = Field(..., description="Оригинальная ссылка")


def save_json_to_file(record: dict) -> dict:
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

tool_registered = False
try:
    if hasattr(llm, "bind_tools"):
        try:
            llm.bind_tools([save_json_to_file])
            tool_registered = True
        except Exception:
            tool_registered = False
except Exception:
    tool_registered = False

print(f"Tool registration: {'OK' if tool_registered else 'SKIPPED/FAILED (using local save)'}")


def load_text_snippet(url: str, max_chars: int = MAX_SNIPPET_CHARS) -> str:
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
                candidate = text[start:i+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    return None
    return None


SYSTEM_PROMPT_CLASSIFY = SystemMessage(content="""
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

def classify_url_with_llm(url: str, max_attempts: int = 2) -> dict:
    snippet = load_text_snippet(url)
    if not snippet:
        return {"status": "error", "message": "Unable to extract page text", "url": url}

    date_now = datetime.now().strftime("%Y-%m-%d")
    user_prompt = HumanMessage(content=f"URL: {url}\nDate: {date_now}\nSnippet:\n{snippet}\n\nReturn strict JSON or tool_call as specified in system prompt.")
    for attempt in range(1, max_attempts + 1):
        try:
            response = llm.invoke([SYSTEM_PROMPT_CLASSIFY, user_prompt])
        except Exception as e:
            return {"status": "error", "message": f"LLM invoke error: {e}"}

        raw = getattr(response, "content", str(response)).strip()

        tool_calls = getattr(response, "tool_calls", None)
        if tool_calls:
            return {"status": "tool_call", "tool_calls": tool_calls, "raw": raw}

        parsed = None
        if raw.startswith("{") and raw.endswith("}"):
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = extract_json_from_text(raw)
        else:
            parsed = extract_json_from_text(raw)

        if not parsed:
            if attempt < max_attempts:
                continue
            return {"status": "error", "message": "LLM did not return valid JSON", "raw": raw}

        try:
            validated = LinkAnalysis.model_validate(parsed) if hasattr(LinkAnalysis, "model_validate") else LinkAnalysis(**parsed)
            record = validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
            return {"status": "ok", "record": record}
        except ValidationError as e:
            if attempt < max_attempts:
                continue
            return {"status": "error", "message": f"Validation failed: {e}", "parsed": parsed}

    return {"status": "error", "message": "Unreachable end of classify routine"}


def parse_iso_date(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except Exception:
            return None

def query_records(subject: str, date_from: str, date_to: str) -> List[dict]:
    """Return list of saved records matching subject and date range inclusive."""
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
    try:
        import Document
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


def interactive_loop():
    print("Reactive agent started.")
    print("Commands:")
    print(" - Enter a URL to classify & save it.")
    print(" - show subject=<subject> from=YYYY-MM-DD to=YYYY-MM-DD")
    print(" - exit")
    while True:
        try:
            line = input("User: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            break

        m = re.search(r"show\s+subject=(?P<sub>.+?)\s+from=(?P<fr>\d{4}-\d{2}-\d{2})\s+to=(?P<to>\d{4}-\d{2}-\d{2})", line, flags=re.IGNORECASE)
        if m:
            subject = m.group("sub").strip()
            fr = m.group("fr")
            to = m.group("to")
            results = query_records(subject, fr, to)
            print(json.dumps(results, ensure_ascii=False, indent=4))
            continue

        if line.startswith("http://") or line.startswith("https://"):
            print("Classifying URL...")
            res = classify_url_with_llm(line)
            if res.get("status") == "ok":
                save_res = save_json_to_file(res["record"])
                print("Saved:", save_res)
                print("Record:", json.dumps(res["record"], ensure_ascii=False, indent=4))
            elif res.get("status") == "tool_call":
                tcs = res.get("tool_calls") or []
                processed_any = False
                for tc in tcs:
                    args = tc.get("args")
                    try:
                        args_parsed = args if not isinstance(args, str) else json.loads(args)
                    except Exception:
                        args_parsed = args
                    try:
                        validated = LinkAnalysis.model_validate(args_parsed) if hasattr(LinkAnalysis, "model_validate") else LinkAnalysis(**args_parsed)
                        rec = validated.model_dump() if hasattr(validated, "model_dump") else validated.dict()
                        save_res = save_json_to_file(rec)
                        print("Saved via tool_call:", save_res)
                        print("Record:", json.dumps(rec, ensure_ascii=False, indent=4))
                        processed_any = True
                    except ValidationError as e:
                        print("Tool call args validation failed:", e)
                if not processed_any:
                    print("Tool_call present but none processed successfully:", tcs)
            else:
                print("Error:", res)
            continue

        print("Не распознана команда. Доступные команды:")
        print(" - Введите URL (starting with http/https) to classify & save it")
        print(" - show subject=<subject> from=YYYY-MM-DD to=YYYY-MM-DD")
        print(" - exit")

if __name__ == "__main__":
    interactive_loop()
