#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from openai import OpenAI
from dotenv import load_dotenv


MODEL = "gpt-5.6-luna"
client = None
CACHE_PATH = Path(__file__).with_name(".answer_cache.json")

ANSWER_FORMAT = {
    "type": "json_schema",
    "name": "homework_answer",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "values": {"type": "array", "items": {"type": "string"}},
            "choice_indices": {"type": "array", "items": {"type": "integer", "minimum": 1}},
        },
        "required": ["values", "choice_indices"],
        "additionalProperties": False,
    },
}

DOM_JS = r"""
(() => {
  const shown = e => {
    const s = getComputedStyle(e), r = e.getBoundingClientRect();
    return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0;
  };
  const visible = e => { const r = e.getBoundingClientRect(); return shown(e) && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
  const usable = e => shown(e) || shown(e.closest(".choice-row") || e.closest("label") || e.parentElement);
  const text = e => e ? (e.innerText || "").replace(/\s+/g, " ").trim() : "";
  const score = e => {
    const r = e.getBoundingClientRect();
    return Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0)) *
      Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0));
  };
  const prompts = [...document.querySelectorAll(".prompt")].filter(visible).sort((a, b) => score(b) - score(a));
  if (!prompts.length) return JSON.stringify({question: "", type: "unavailable", error: "No visible question was found"});

  const prompt = prompts[0];
  const question = prompt.closest('[data-automation-id="scoresheet-container"]') || prompt.closest(".dlc_question") || prompt.parentElement;
  const targetId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  prompt.dataset.homeworkReviewTarget = targetId;
  const promptCopy = prompt.cloneNode(true);
  promptCopy.querySelectorAll("script, style, [hidden], ._visuallyHidden, .sr-only").forEach(e => e.remove());
  let blankNumber = 0;
  promptCopy.querySelectorAll('.fitb-input, input[type="text"], input:not([type]), input[type="number"], textarea, select').forEach(e => {
    const label = e.tagName === "SELECT" ? `DROPDOWN ${++blankNumber}` : `BLANK ${++blankNumber}`;
    e.replaceWith(document.createTextNode(`[${label}]`));
  });
  const questionText = (promptCopy.textContent || "").replace(/\s+/g, " ").replace(/\s+([.,;:!?])/g, "$1").trim();
  const out = {type: "unknown", question: questionText, target_id: targetId};

  const radios = [...question.querySelectorAll('input[type="radio"]')].filter(usable);
  const checks = [...question.querySelectorAll('input[type="checkbox"]')].filter(usable);
  const numbers = [...question.querySelectorAll('input[type="number"]')].filter(usable);
  const blanks = [...question.querySelectorAll('.fitb-input, input[type="text"], input:not([type]), textarea')].filter(usable);
  const selects = [...question.querySelectorAll("select")].filter(usable);
  const tables = [...question.querySelectorAll("table")].filter(shown);
  const editableTable = tables.some(table => table.querySelector("input, textarea, select"));

  if (editableTable) {
    out.type = "table";
  } else if (radios.length) {
    out.type = "multiple_choice";
    out.choices = [...question.querySelectorAll(".choice-row .choiceText")].filter(shown).map(text);
  } else if (checks.length) {
    out.type = "multi_select";
    out.choices = [...question.querySelectorAll(".choice-row .choiceText")].filter(shown).map(text);
  } else if (selects.length) {
    out.type = "dropdown";
  } else if (numbers.length) {
    out.type = "numeric";
    out.fields = numbers.length;
  } else if (blanks.length) {
    out.type = "fill_blank";
    out.fields = blanks.length;
  }

  if (out.type === "unknown" || (out.choices && !out.choices.length)) {
    out.error = "No supported answer controls were found";
  }

  const visual = [...question.querySelectorAll("img, canvas, svg")].some(e => {
    if (!shown(e)) return false;
    const r = e.getBoundingClientRect();
    if (e.tagName === "CANVAS") return r.width > 40 && r.height > 30;
    if (e.tagName === "IMG") return r.width > 60 && r.height > 60;
    return r.width > 60 && r.height > 25 && !text(e) && !e.getAttribute("aria-label");
  });
  if (!out.question || visual) {
    out.error = !out.question ? "The extracted question was empty" : "Visual questions cannot be auto-filled";
  }
  return JSON.stringify(out);
})()
"""

REVIEW_JS = r"""
(() => {
  const shown = e => {
    const s = getComputedStyle(e), r = e.getBoundingClientRect();
    return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0;
  };
  const visible = e => { const r = e.getBoundingClientRect(); return shown(e) && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
  const score = e => {
    const r = e.getBoundingClientRect();
    return Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0)) *
      Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0));
  };
  const prompts = [...document.querySelectorAll(".prompt")].filter(visible).sort((a, b) => score(b) - score(a));
  if (!prompts.length) return JSON.stringify({error: "No visible question was found"});
  const prompt = prompts[0];
  const question = prompt.closest('[data-automation-id="scoresheet-container"]') || prompt.closest(".dlc_question") || prompt.parentElement;
  const promptCopy = prompt.cloneNode(true);
  promptCopy.querySelectorAll("script, style, [hidden], ._visuallyHidden, .sr-only").forEach(e => e.remove());
  let blankNumber = 0;
  promptCopy.querySelectorAll('.fitb-input, input[type="text"], input:not([type]), input[type="number"], textarea, select').forEach(e => {
    e.replaceWith(document.createTextNode(`[BLANK ${++blankNumber}]`));
  });
  const questionText = (promptCopy.textContent || "").replace(/\s+/g, " ").replace(/\s+([.,;:!?])/g, "$1").trim();
  if (!questionText) return JSON.stringify({error: "The reviewed question was empty"});
  const normalize = value => value.replace(/\s+/g, " ").trim().toLowerCase();
  const correctHeader = [...document.querySelectorAll("*")].find(e => !e.children.length && normalize(e.textContent) === "correct answer");
  const correctAnswers = correctHeader ? correctHeader.parentElement.innerText.split("\n")
    .map(line => line.trim()).filter(line => line && normalize(line) !== "correct answer") : [];
  const choices = [...question.querySelectorAll('input[type="radio"], input[type="checkbox"]')]
    .filter(e => shown(e) || shown(e.closest("label") || e.parentElement));
  const numbers = [...question.querySelectorAll('input[type="number"]')]
    .filter(e => shown(e) || shown(e.closest("label") || e.parentElement));
  const blanks = [...question.querySelectorAll('.fitb-input, input[type="text"], input:not([type]), textarea')]
    .filter(e => shown(e) || shown(e.closest("label") || e.parentElement));
  if (choices.length) {
    if (choices.some(e => e.type === "radio") && choices.some(e => e.type === "checkbox")) {
      return JSON.stringify({error: "The reviewed question has mixed choice controls"});
    }
    const type = choices[0].type === "radio" ? "multiple_choice" : "multi_select";
    const choiceText = control => {
      const label = control.closest("label") || control.closest(".choice-row") || control.parentElement;
      const direct = [...label.childNodes].filter(node => node.nodeType === Node.TEXT_NODE).map(node => node.textContent).join(" ").trim();
      return direct || label.querySelector(".choiceText")?.innerText.trim() || "";
    };
    const marked = choices.flatMap((control, index) => {
      const label = control.closest("label") || control.closest(".choice-row") || control.parentElement;
      const status = (label.querySelector(".sr-only")?.textContent || "").trim();
      return /\bcorrect\b/i.test(status) && !/\bincorrect\b/i.test(status) ? [index + 1] : [];
    });
    const expected = new Set(correctAnswers.map(normalize));
    const fromPanel = choices.flatMap((control, index) => expected.has(normalize(choiceText(control))) ? [index + 1] : []);
    const choice_indices = marked.length ? marked : fromPanel;
    if (!choice_indices.length) return JSON.stringify({error: "No correct answer was shown"});
    return JSON.stringify({type, question: questionText, values: [], choice_indices});
  }
  const type = numbers.length ? "numeric" : blanks.length ? "fill_blank" : "unknown";
  const fields = numbers.length || blanks.length;
  if (!fields) return JSON.stringify({error: "No supported reviewed answer controls were found"});
  if (correctAnswers.length !== fields) return JSON.stringify({error: "Could not match the displayed correct answer to every field"});
  return JSON.stringify({type, question: questionText, values: correctAnswers, choice_indices: []});
})()
"""

APPLY_ANSWER_JS = r"""
(() => {
  const answer = __ANSWER__;
  const shown = e => {
    const s = getComputedStyle(e), r = e.getBoundingClientRect();
    return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0;
  };
  const visible = e => { const r = e.getBoundingClientRect(); return shown(e) && r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; };
  const usable = e => !e.disabled && (shown(e) || shown(e.closest(".choice-row") || e.closest("label") || e.parentElement));
  const score = e => {
    const r = e.getBoundingClientRect();
    return Math.max(0, Math.min(r.bottom, innerHeight) - Math.max(r.top, 0)) *
      Math.max(0, Math.min(r.right, innerWidth) - Math.max(r.left, 0));
  };
  const prompts = [...document.querySelectorAll(".prompt")].filter(visible).sort((a, b) => score(b) - score(a));
  const prompt = prompts.find(element => element.dataset.homeworkReviewTarget === answer.target_id);
  if (!prompt) return JSON.stringify({applied: false, reason: "The question changed before the answer arrived"});
  const question = prompt.closest('[data-automation-id="scoresheet-container"]') || prompt.closest(".dlc_question") || prompt.parentElement;
  const setValue = (element, value) => {
    const prototype = element.tagName === "TEXTAREA" ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value").set;
    setter.call(element, String(value));
    element.dispatchEvent(new Event("input", {bubbles: true}));
    element.dispatchEvent(new Event("change", {bubbles: true}));
  };

  if (answer.type === "fill_blank" || answer.type === "numeric") {
    const selector = answer.type === "numeric"
      ? 'input[type="number"]'
      : '.fitb-input, input[type="text"], input:not([type]), textarea';
    const fields = [...question.querySelectorAll(selector)].filter(usable);
    if (!fields.length) return JSON.stringify({applied: false, reason: "No answer fields were found"});
    if (answer.values.length !== fields.length) {
      return JSON.stringify({applied: false, reason: `Expected ${fields.length} answer values, received ${answer.values.length}`});
    }
    fields.forEach((field, index) => setValue(field, answer.values[index]));
    fields[fields.length - 1].dispatchEvent(new Event("blur", {bubbles: true}));
    return JSON.stringify({applied: true, kind: answer.type, count: fields.length});
  }

  if (answer.type === "multiple_choice") {
    if (answer.choice_indices.length !== 1) {
      return JSON.stringify({applied: false, reason: "The answer did not contain exactly one choice index"});
    }
    const index = answer.choice_indices[0] - 1;
    const rows = [...question.querySelectorAll(".choice-row")].filter(shown);
    const radios = [...question.querySelectorAll('input[type="radio"]')].filter(usable);
    const radio = rows[index]?.querySelector('input[type="radio"]') || radios[index];
    if (!radio || radio.disabled) return JSON.stringify({applied: false, reason: "The selected choice was not found"});
    radio.click();
    return JSON.stringify({applied: true, kind: answer.type, count: 1, choice_index: index + 1});
  }

  if (answer.type === "multi_select") {
    const selected = new Set(answer.choice_indices.map(index => index - 1));
    const rows = [...question.querySelectorAll(".choice-row")].filter(shown);
    const checkboxes = [...question.querySelectorAll('input[type="checkbox"]')].filter(usable);
    if (!checkboxes.length) return JSON.stringify({applied: false, reason: "No checkbox choices were found"});
    if ([...selected].some(index => index < 0 || index >= checkboxes.length)) {
      return JSON.stringify({applied: false, reason: "A selected choice index was not found"});
    }
    checkboxes.forEach((checkbox, index) => {
      const shouldBeChecked = selected.has(index);
      if (checkbox.checked !== shouldBeChecked) {
        const rowCheckbox = rows[index]?.querySelector('input[type="checkbox"]');
        (rowCheckbox || checkbox).click();
      }
    });
    return JSON.stringify({applied: true, kind: answer.type, count: selected.size, choice_indices: answer.choice_indices});
  }

  return JSON.stringify({applied: false, reason: `Automatic entry is not supported for ${answer.type}`});
})()
"""


def execute_javascript(browser, source):
    js = source.replace("\n", " ").replace("\\", "\\\\").replace('"', '\\"')
    if browser == "Google Chrome":
        script = f'tell application "Google Chrome" to execute active tab of front window javascript "{js}"'
    elif browser == "Safari":
        script = f'tell application "Safari" to do JavaScript "{js}" in current tab of front window'
    else:
        return None, f"Frontmost app is {browser or 'unknown'}"
    result = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True)
    if result.returncode:
        return None, result.stderr.strip() or "Could not execute JavaScript in browser"
    return result.stdout.strip(), None


def extract_question(browser):
    output, execution_error = execute_javascript(browser, DOM_JS)
    if execution_error and not output:
        if not browser or browser not in ("Google Chrome", "Safari"):
            return {"question": "", "type": "unavailable", "error": f"Frontmost app is {browser or 'unknown'}"}
        error = execution_error.lower()
        if "-1743" in error or "not authorized to send apple events" in error or "apple events denied" in error:
            reason = "Apple Events access was denied"
        elif browser == "Google Chrome" and any(x in error for x in ("-600", "isn't running", "isn’t running", "connection invalid", "can't get")):
            reason = "Could not communicate with Chrome"
        else:
            reason = "Could not read the question from the browser"
        return {"question": "", "type": "unavailable", "error": reason}
    if output is None:
        return {"question": "", "type": "unavailable", "error": f"Frontmost app is {browser or 'unknown'}"}
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        return {"question": "", "type": "unavailable", "error": "The browser returned invalid question data"}


def extract_review(browser):
    output, execution_error = execute_javascript(browser, REVIEW_JS)
    if execution_error:
        return {"error": "Could not read the reviewed answer from the browser"}
    try:
        return json.loads(output)
    except (TypeError, json.JSONDecodeError):
        return {"error": "The browser returned an invalid reviewed answer"}


def cache_key(question):
    source = json.dumps({"type": question["type"], "question": question["question"]}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(source.encode()).hexdigest()


def cached_answer(question):
    try:
        with CACHE_PATH.open() as cache_file:
            return json.load(cache_file).get(cache_key(question))
    except (OSError, json.JSONDecodeError):
        return None


def save_review(review):
    key = cache_key(review)
    try:
        with CACHE_PATH.open() as cache_file:
            cache = json.load(cache_file)
    except (OSError, json.JSONDecodeError):
        cache = {}
    cache[key] = {"values": review["values"], "choice_indices": review["choice_indices"]}
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n")
    return len(review["choice_indices"]) or len(review["values"])


def answer(payload):
    prepare_client()
    content = [{"type": "input_text", "text": "Question:\n" + json.dumps(payload, ensure_ascii=False)}]
    response = client.responses.create(
        model=MODEL,
        instructions=(
            "Return only valid JSON with exactly these keys: "
            '{"values": string[], "choice_indices": integer[]}. '
            "For fill_blank or numeric questions, put one exact answer per field in values, in DOM order. "
            "For multiple_choice questions, put exactly one 1-based choice index in choice_indices. "
            "For other choice questions, put every correct 1-based index in choice_indices. "
            "Do not include an explanation or markdown."
        ),
        input=[{"role": "user", "content": content}],
        reasoning={"effort": "none"},
        text={"format": ANSWER_FORMAT, "verbosity": "low"},
        max_output_tokens=256,
        store=False,
    )
    raw = response.output_text.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        if raw.startswith("```") and raw.endswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            parsed = json.loads(raw)
        else:
            raise RuntimeError("The model returned an answer in an unexpected format")

    values = [str(value) for value in parsed.get("values", [])]
    try:
        choice_indices = [int(index) for index in parsed.get("choice_indices", [])]
    except (TypeError, ValueError):
        choice_indices = []
    return {
        "values": values,
        "choice_indices": choice_indices,
    }


def apply_answer(browser, question, result):
    question_type = question.get("type", "unknown")
    if question_type not in ("fill_blank", "numeric", "multiple_choice", "multi_select"):
        return {"applied": False, "attempted": False, "reason": f"Automatic entry is not supported for {question_type}"}
    answer_data = {
        "type": question_type,
        "target_id": question.get("target_id", ""),
        "values": result["values"],
        "choice_indices": result["choice_indices"],
    }
    source = APPLY_ANSWER_JS.replace("__ANSWER__", json.dumps(answer_data, ensure_ascii=False))
    output, execution_error = execute_javascript(browser, source)
    if execution_error:
        return {"applied": False, "attempted": True, "reason": "Could not apply the answer in the browser"}
    try:
        application = json.loads(output)
    except (TypeError, json.JSONDecodeError):
        return {"applied": False, "attempted": True, "reason": "The browser returned an invalid apply result"}
    application["attempted"] = True
    return application


def prepare_client():
    global client
    if client is not None:
        return
    load_dotenv(Path(sys.prefix).parent / ".env")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Add OPENAI_API_KEY to the project .env file")
    client = OpenAI()


def handle_request(browser, debug=False, learn=False, started=None):
    started = started or time.perf_counter()
    timings = {"request_received": 0.0} if debug else None
    if learn:
        review = extract_review(browser)
        if review.get("error"):
            return {"error": review["error"]}
        return {"saved": save_review(review), "type": review["type"]}
    payload = extract_question(browser)
    if debug:
        timings["dom_extraction_complete"] = time.perf_counter() - started

    try:
        if payload.get("error"):
            raise RuntimeError(payload["error"])
        if payload.get("type") not in ("fill_blank", "numeric", "multiple_choice", "multi_select"):
            raise RuntimeError(f"Automatic entry is not supported for {payload.get('type', 'unknown')}")
        if debug:
            timings["api_request_start"] = time.perf_counter() - started
        result = cached_answer(payload) or answer(payload)
        if debug:
            timings["api_response_received"] = time.perf_counter() - started
        application = {"applied": False, "attempted": False} if debug else apply_answer(browser, payload, result)
        if debug:
            response = {"result": result, "application": application}
        elif application.get("applied"):
            response = {"applied": True}
        else:
            response = {"error": application.get("reason", "Could not apply the answer"), "application": application}
    except Exception as e:
        response = {"error": str(e)}
    if debug:
        response.update(payload=payload, timings=timings)
    return response


def worker():
    global client
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        for line in sys.stdin:
            started = time.perf_counter()
            try:
                request = json.loads(line)
                if request.get("command") == "quit":
                    break
                response = handle_request(
                    request.get("browser", ""),
                    request.get("debug", False),
                    request.get("learn", False),
                    started,
                )
            except Exception as e:
                response = {"error": str(e)}
            print(json.dumps(response, ensure_ascii=False), flush=True)
    finally:
        if client is not None:
            client.close()


def main():
    if "--worker" in sys.argv:
        worker()
        return
    browser = next((a for a in sys.argv[1:] if not a.startswith("--")), "")
    payload = extract_question(browser)
    if "--debug" in sys.argv or os.environ.get("HOMEWORK_REVIEW_DEBUG") == "1":
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    try:
        if payload.get("error"):
            raise RuntimeError(payload["error"])
        if payload.get("type") not in ("fill_blank", "numeric", "multiple_choice", "multi_select"):
            raise RuntimeError(f"Automatic entry is not supported for {payload.get('type', 'unknown')}")
        prepare_client()
        application = apply_answer(browser, payload, answer(payload))
        if not application.get("applied"):
            raise RuntimeError(application.get("reason", "Could not apply the answer"))
    except Exception as e:
        print(f"Homework Review — {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
