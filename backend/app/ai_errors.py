"""Turns any failure into a friendly message + short reference. Ported from the Streamlit app."""
from .config import CLAUDE_MODEL


def create_json_message(client, **kw):
    """messages.create that never silently returns a half-written JSON answer:
    if the reply was cut off by the token limit, retry once with more room."""
    msg = client.messages.create(**kw)
    if getattr(msg, "stop_reason", None) == "max_tokens":
        bigger = dict(kw, max_tokens=min(int(kw.get("max_tokens", 4096)) * 2, 16000))
        print(f"[ai] answer hit max_tokens={kw.get('max_tokens')} - retrying with {bigger['max_tokens']}")
        msg = client.messages.create(**bigger)
        if getattr(msg, "stop_reason", None) == "max_tokens":
            raise ValueError("ANSWER_TOO_LONG")
    return msg

def describe_ai_error(e):
    """Turns any failure into (friendly message, short reference) for the customer,
    and writes the full detail + traceback to the server log (Railway logs)."""
    import traceback
    name = type(e).__name__
    status = getattr(e, "status_code", None)
    text = str(e)
    low = text.lower()
    if isinstance(e, ValueError) and text in ("EMPTY_RESUME", "NOT_WORD", "ENCRYPTED_DOC", "BAD_DOC", "DOC_LIB_MISSING"):
        # an ordinary "this file can't be read" - one short line, so real problems stand out in the logs
        cause = f" (cause: {type(e.__cause__).__name__})" if e.__cause__ else ""
        print(f"[file] resume not readable: {text}{cause}")
    else:
        print(f"[ai-error] {name} status={status}: {text[:500]}")
        traceback.print_exc()
    busy = "Our AI service is busy right now — please wait a minute and try again."
    generic = "Something went wrong while generating your result. Please try again."
    if isinstance(e, ValueError) and text == "EMPTY_RESUME":
        msg = ("We couldn't read any text from your resume. If it's a scanned image, please upload a "
               "text-based PDF or a Word (.docx) file instead.")
    elif text == "NOT_WORD":
        msg = ("That file has a Word name, but it isn't a Word document we can read (it may be a web page or another "
               "format saved as .doc). Please open it in Word, use Save As → Word (.docx) or PDF, and upload it again.")
    elif text == "ENCRYPTED_DOC":
        msg = "That Word file is password-protected. Please remove the password, or save an unprotected copy as PDF or .docx, and upload it again."
    elif text == "BAD_DOC":
        msg = "We couldn't read that Word file. It may be damaged or very old. Please open it in Word, save it as .docx or PDF, and upload it again."
    elif text == "DOC_LIB_MISSING":
        print("[ai-error] *** 'olefile' is not installed on the server: add `olefile` to requirements.txt and redeploy ***")
        msg = "Reading .doc files is temporarily unavailable. Please save your resume as .docx or PDF and upload it again."
    elif name in ("PackageNotFoundError", "BadZipFile") or "package not found" in low or "not a zip file" in low:
        msg = "We couldn't open that file. It may be damaged. Please save it again as .docx or PDF and upload it again."
    elif "credit balance" in low or "billing" in low or "purchase credits" in low:
        print("[ai-error] *** The Anthropic account is out of credit / billing problem - top up at console.anthropic.com ***")
        msg = "Our AI service is temporarily unavailable. Please try again a little later."
    elif "could not resolve authentication" in low or status in (401, 403):
        print("[ai-error] *** ANTHROPIC_API_KEY is missing, wrong or not allowed - check the Railway variable ***")
        msg = "Our AI service is temporarily unavailable. Please try again a little later."
    elif status == 404 or ("model" in low and "not found" in low):
        print(f"[ai-error] *** Model '{CLAUDE_MODEL}' was not found - set CLAUDE_MODEL in Railway to a current model id ***")
        msg = "Our AI service is temporarily unavailable. Please try again a little later."
    elif status == 429 or "rate" in name.lower() and "limit" in name.lower() or "overloaded" in low or status in (500, 502, 503, 504, 529):
        msg = busy
    elif "timeout" in name.lower() or "timed out" in low:
        msg = "The AI took too long to respond. Please try again."
    elif "APIConnection" in name:
        msg = "We couldn't reach our AI service. Please try again in a moment."
    elif (isinstance(e, ValueError) and text in ("ANSWER_TOO_LONG", "No JSON found")) or "JSONDecodeError" in name:
        msg = "The AI's answer came back incomplete. Please try again."
    else:
        msg = generic
    ref = name + (f" {status}" if status else "")
    return {"message": msg, "ref": ref}

