"""Language-model connection for Speed Compass. Optional: every feature has an offline fallback.

Works with Google Gemini (free tier) or Anthropic Claude. Production would run the model on Amazon Bedrock.
Answers are shared across sessions, so when several judges click the same example the model is called once.
"""
import json
import os
import re
import threading
import time

GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]  # most accurate first; Lite has more free room
CLAUDE_MODEL = "claude-opus-5-5"
CLAUDE_FALLBACK_BETA = "server-side-fallback-2026-07-01"

_CACHE, _LOCK = {}, threading.Lock()
_BUSY_UNTIL = {}  # model -> time until which we skip it after a free-tier limit (shared by all judges)
BUSY_SECONDS = 60


class AIUnavailable(Exception):
    """Raised when the model cannot be used; the caller switches to offline rules."""


def clean(text):
    """House style: no em or en dashes."""
    text = re.sub(r"(\d)\s*[–—]\s*(\d)", r"\1 to \2", text)
    text = re.sub(r"\s*[–—]\s*", ", ", text)
    return text.strip()


def _parse_json(text):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
    raise AIUnavailable("The model returned malformed JSON.")


def detect_provider(key):
    key = (key or "").strip()
    if key.startswith("sk-ant-"):
        return "claude"
    if key.startswith("AIza"):
        return "gemini"
    return None


class AI:
    """provider: 'gemini' or 'claude'. key: pasted in the sidebar, or read from the environment."""

    def __init__(self, provider="gemini", api_key=None):
        typed = (api_key or "").strip() or None
        self.provider = detect_provider(typed) or provider
        env = {"gemini": os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"),
               "claude": os.environ.get("ANTHROPIC_API_KEY")}
        self.api_key = typed or env.get(self.provider)
        self.source = "typed" if typed else ("server" if self.api_key else None)
        self.last_model = None

    def configured(self):
        return bool(self.api_key)

    @property
    def label(self):
        name = "Gemini" if self.provider == "gemini" else "Claude"
        return f"{name} ({self.last_model})" if self.last_model else name

    # -------------------------------------------------------------- public
    def ask(self, system, user, schema=None, effort="low", max_tokens=4000):
        """One request. Returns parsed JSON when a schema is given, otherwise cleaned text."""
        if not self.configured():
            raise AIUnavailable("No API key set.")
        key = (self.provider, system, user, json.dumps(schema, sort_keys=True) if schema else None)
        with _LOCK:
            if key in _CACHE:
                self.last_model = _CACHE[key][1]
                return json.loads(json.dumps(_CACHE[key][0]))  # a copy, so callers cannot change the cache
        if self.provider == "gemini":
            result, model = self._gemini(system, user, schema, max_tokens)
        else:
            result, model = self._claude(system, user, schema, effort, max_tokens)
        self.last_model = model
        with _LOCK:
            if len(_CACHE) > 500:
                _CACHE.clear()
            _CACHE[key] = (result, model)
        return json.loads(json.dumps(result))

    # -------------------------------------------------------------- Gemini
    def _gemini(self, system, user, schema, max_tokens):
        from google import genai  # imported on first use: keeps app start fast
        from google.genai import errors

        client = genai.Client(api_key=self.api_key)
        busy = False
        for model in GEMINI_MODELS:
            if _BUSY_UNTIL.get(model, 0) > time.time() and model != GEMINI_MODELS[-1]:
                busy = True
                continue  # this model hit its free limit recently: go straight to the lighter one
            request = dict(model=model, input=user, system_instruction=system,
                           generation_config={"thinking_level": "low", "max_output_tokens": max_tokens})
            if schema:
                request["response_format"] = {"type": "text", "mime_type": "application/json", "schema": schema}
            try:
                try:
                    out = client.interactions.create(**request)
                except errors.ClientError as e:
                    if schema and getattr(e, "code", None) == 400:
                        # schema not accepted: ask for JSON in the prompt instead and parse it ourselves
                        request.pop("response_format")
                        request["input"] = (f"{user}\n\nReply with JSON only, matching this JSON schema:\n"
                                            f"{json.dumps(schema)}")
                        out = client.interactions.create(**request)
                    else:
                        raise
            except errors.ClientError as e:
                code = getattr(e, "code", None)
                if code == 429:
                    busy = True
                    _BUSY_UNTIL[model] = time.time() + BUSY_SECONDS
                    continue  # free-tier limit on this model: try the lighter one
                if code in (401, 403) or (code == 400 and "API key" in str(e)):
                    raise AIUnavailable("The Gemini API key was not accepted.")
                if code == 404:
                    continue
                raise AIUnavailable(f"Gemini returned an error ({code}).")
            except errors.ServerError:
                continue
            except errors.APIError as e:
                raise AIUnavailable(f"Gemini returned an error ({getattr(e, 'code', '')}).")
            except Exception:
                raise AIUnavailable("No connection to Gemini.")
            text = getattr(out, "output_text", None) or ""
            if not text.strip():
                continue
            return (_parse_json(text) if schema else clean(text)), model
        if busy:
            raise AIUnavailable("Gemini's free limit is busy right now.")
        raise AIUnavailable("Gemini did not return an answer.")

    # -------------------------------------------------------------- Claude
    def _claude(self, system, user, schema, effort, max_tokens):
        import anthropic  # imported on first use: the SDK takes several seconds to load

        output_config = {"effort": effort}
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        request = dict(model=CLAUDE_MODEL, max_tokens=max_tokens, system=system,
                       messages=[{"role": "user", "content": user}], output_config=output_config)
        client = anthropic.Anthropic(api_key=self.api_key, timeout=90.0, max_retries=1)
        try:
            try:
                # Server-side fallback: if a safety classifier declines, the API re-runs the request on
                # Anthropic's recommended fallback model instead of returning a refusal.
                response = client.beta.messages.create(betas=[CLAUDE_FALLBACK_BETA], fallbacks="default", **request)
            except anthropic.BadRequestError:
                response = client.messages.create(**request)
        except anthropic.AuthenticationError:
            raise AIUnavailable("The Claude API key was not accepted.")
        except anthropic.PermissionDeniedError:
            raise AIUnavailable("This API key cannot use the model.")
        except anthropic.RateLimitError:
            raise AIUnavailable("Claude is rate limited right now.")
        except anthropic.APIConnectionError:
            raise AIUnavailable("No connection to Claude.")
        except anthropic.APIStatusError as e:
            raise AIUnavailable(f"Claude returned an error ({e.status_code}).")
        if response.stop_reason == "refusal":
            raise AIUnavailable("Claude declined this request.")
        if response.stop_reason == "max_tokens":
            raise AIUnavailable("Claude's answer was cut off.")
        text = "".join(b.text for b in response.content if b.type == "text")
        return (_parse_json(text) if schema else clean(text)), CLAUDE_MODEL


# Backwards-compatible name used by older code
Claude = AI
