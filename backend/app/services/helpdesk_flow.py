"""InfyShield-style helpdesk wizard — Python state machine.

Mirrors the multi-step flow from chatbot.infyshield.com: intent selection,
registration, claims, tracking, and bank/settlement details. Sessions are
held in memory (suitable for single-node dev; swap for Redis in production).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.config import Settings, get_settings
from app.schemas.helpdesk import HelpdeskOption, HelpdeskStepView
from app.services.cache import get_redis

_MOBILE_RE = re.compile(r"^[1-9]\d{9}$")
_PIN_RE = re.compile(r"^\d{6}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_PRODUCT_TYPES = [
    "Mobile / Tablet",
    "Laptop / Desktop",
    "Television",
    "Home Appliance",
    "Other Gadget",
]

_PLANS = [
    "Extended Warranty (EW)",
    "Screen Damage Protection (SDP)",
    "Accidental Damage Protection (ADP)",
    "Combo Protection Plan (CPP)",
]

_STATES = [
    "Andaman & Nicobar",
    "Andhra Pradesh",
    "Delhi",
    "Karnataka",
    "Maharashtra",
    "Tamil Nadu",
    "Uttar Pradesh",
    "West Bengal",
    "Other",
]

_DAMAGE_TYPES = [
    "Screen crack / display damage",
    "Liquid spillage",
    "Physical drop / impact",
    "Power / charging issue",
    "Other damage",
]

_COMPLAINT_TYPES = [
    "Compliment",
    "Question",
    "Complaint",
    "Feedback",
]


@dataclass
class HelpdeskSession:
    session_id: str
    step_id: str = "main_menu"
    answers: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


# step_id -> (message, field_type, options, placeholder, next_resolver)
# next_resolver(answer, session) -> next step_id | "complete"


def _choice_step(
    step_id: str,
    message: str,
    options: list[tuple[str, str]],
    *,
    progress: int,
    next_map: dict[str, str] | None = None,
    default_next: str | None = None,
) -> HelpdeskStepView:
    return HelpdeskStepView(
        step_id=step_id,
        message=message,
        field_type="choice",
        options=[HelpdeskOption(id=o[0], label=o[1]) for o in options],
        progress=progress,
    )


def _text_step(
    step_id: str,
    message: str,
    *,
    field_type: str = "text",
    placeholder: str | None = None,
    progress: int,
) -> HelpdeskStepView:
    return HelpdeskStepView(
        step_id=step_id,
        message=message,
        field_type=field_type,  # type: ignore[arg-type]
        placeholder=placeholder,
        progress=progress,
    )


_STEP_VIEWS: dict[str, HelpdeskStepView] = {
    "main_menu": _choice_step(
        "main_menu",
        "Welcome to Helpdesk! How can we assist you today?",
        [
            ("register_plan", "Register / Activate Plan"),
            ("raise_claim", "Raise Service Request / Claim"),
            ("track_request", "Track Existing Request"),
            ("plan_inquiry", "Plan & Coverage Inquiry"),
            ("complaint", "Complaint / Feedback"),
            ("general_help", "General Help"),
        ],
        progress=5,
    ),
    "mobile": _text_step(
        "mobile",
        "Please enter your registered 10-digit mobile number.",
        field_type="phone",
        placeholder="e.g. 9876543210",
        progress=12,
    ),
    "reg_product_type": _choice_step(
        "reg_product_type",
        "Select your product type.",
        [(p, p) for p in _PRODUCT_TYPES],
        progress=22,
    ),
    "reg_plan": _choice_step(
        "reg_plan",
        "Select at least one protection plan.",
        [(p, p) for p in _PLANS],
        progress=32,
    ),
    "reg_promo": _choice_step(
        "reg_promo",
        "Do you have a promotion code?",
        [("yes", "Yes"), ("no", "No")],
        progress=38,
    ),
    "reg_promo_code": _text_step(
        "reg_promo_code",
        "Enter your promotion code.",
        placeholder="Promotion code",
        progress=42,
    ),
    "reg_device_id": _text_step(
        "reg_device_id",
        "Provide ONE device identifier: IMEI, serial number, previous ticket, or invoice number.",
        placeholder="IMEI / Serial / Ticket / Invoice",
        progress=48,
    ),
    "reg_customer_name": _text_step(
        "reg_customer_name",
        "Enter the customer name as on the purchase invoice.",
        placeholder="Full name",
        progress=55,
    ),
    "reg_state": _choice_step(
        "reg_state",
        "Select your state.",
        [(s, s) for s in _STATES],
        progress=62,
    ),
    "reg_city": _text_step(
        "reg_city",
        "Enter your city.",
        placeholder="City",
        progress=68,
    ),
    "reg_pincode": _text_step(
        "reg_pincode",
        "Enter your 6-digit PIN code.",
        field_type="number",
        placeholder="110001",
        progress=74,
    ),
    "reg_address": _text_step(
        "reg_address",
        "Enter your full address for correspondence.",
        field_type="textarea",
        placeholder="House no., street, landmark…",
        progress=80,
    ),
    "reg_brand": _text_step(
        "reg_brand",
        "Enter the product brand.",
        placeholder="e.g. Samsung, Apple, LG",
        progress=86,
    ),
    "reg_model": _text_step(
        "reg_model",
        "Enter the product model name or number.",
        placeholder="e.g. Galaxy S24",
        progress=92,
    ),
    "claim_problem": _text_step(
        "claim_problem",
        "Describe the problem reported on your device.",
        field_type="textarea",
        placeholder="What happened? When did it start?",
        progress=45,
    ),
    "claim_damage_time": _text_step(
        "claim_damage_time",
        "When did the damage or malfunction occur?",
        placeholder="e.g. 2 days ago, 15 Jan 2026",
        progress=52,
    ),
    "claim_damage_place": _text_step(
        "claim_damage_place",
        "Where did the damage occur?",
        placeholder="e.g. Home, office, while travelling",
        progress=58,
    ),
    "claim_damage_type": _choice_step(
        "claim_damage_type",
        "What type of damage are you reporting?",
        [(d, d) for d in _DAMAGE_TYPES],
        progress=64,
    ),
    "claim_phone_on": _choice_step(
        "claim_phone_on",
        "Is the device switching on?",
        [("yes", "Yes"), ("no", "No"), ("partial", "Partially / intermittently")],
        progress=70,
    ),
    "claim_touch_working": _choice_step(
        "claim_touch_working",
        "Is the touch screen working?",
        [("yes", "Yes"), ("no", "No"), ("na", "Not applicable")],
        progress=76,
    ),
    "claim_bank_needed": _choice_step(
        "claim_bank_needed",
        "Do you need bank details for settlement (BER / total loss)?",
        [("yes", "Yes"), ("no", "No")],
        progress=82,
    ),
    "bank_account": _text_step(
        "bank_account",
        "Enter your bank account number.",
        field_type="number",
        placeholder="Account number",
        progress=88,
    ),
    "bank_ifsc": _text_step(
        "bank_ifsc",
        "Enter the IFSC code.",
        placeholder="e.g. SBIN0001234",
        progress=92,
    ),
    "bank_name": _text_step(
        "bank_name",
        "Enter the bank name.",
        placeholder="Bank name",
        progress=95,
    ),
    "track_ticket": _text_step(
        "track_ticket",
        "Enter your case / ticket ID.",
        placeholder="e.g. HD-123456",
        progress=35,
    ),
    "inquiry_topic": _choice_step(
        "inquiry_topic",
        "What would you like to know about?",
        [
            ("plan_types", "Plan types (EW / SDP / ADP / CPP)"),
            ("eligibility", "Eligibility & registration"),
            ("claim_process", "How to raise a claim"),
            ("charges", "Service order charges"),
            ("exclusions", "What is not covered"),
        ],
        progress=30,
    ),
    "complaint_type": _choice_step(
        "complaint_type",
        "Select the type of feedback.",
        [(c, c) for c in _COMPLAINT_TYPES],
        progress=25,
    ),
    "complaint_details": _text_step(
        "complaint_details",
        "Please share the details of your compliment, question, complaint, or feedback.",
        field_type="textarea",
        placeholder="Tell us more…",
        progress=55,
    ),
    "general_query": _text_step(
        "general_query",
        "Type your question and we will route it to the right team.",
        field_type="textarea",
        placeholder="How can we help?",
        progress=40,
    ),
}

_INQUIRY_ANSWERS: dict[str, str] = {
    "plan_types": (
        "InfyShield offers Extended Warranty (EW), Screen Damage Protection (SDP), "
        "Accidental Damage Protection (ADP), and Combo Protection Plans (CPP)."
    ),
    "eligibility": (
        "Devices must be new, purchased in India with a valid GST invoice, and registered "
        "within 7 days (up to 15 days with documented delay)."
    ),
    "claim_process": (
        "Contact customer care first to obtain a case ID before visiting any service centre. "
        "You may need invoice, IMEI/serial, photos, and ID proof."
    ),
    "charges": (
        "EW claims have no service order charge. ADP/SDP/CPP charges range from ₹500 to 3% "
        "of product price depending on the price band."
    ),
    "exclusions": (
        "Batteries, wear-and-tear, software issues, commercial use, and unauthorized "
        "service visits without prior approval are excluded."
    ),
}


def _validate(step_id: str, answer: str) -> str | None:
    """Return an error message or None if valid."""
    a = answer.strip()
    if not a:
        return "This field is required."

    if step_id == "mobile":
        if not _MOBILE_RE.match(a):
            return "Please enter a valid 10-digit mobile number (starting 1–9)."
    elif step_id == "reg_pincode":
        if not _PIN_RE.match(a):
            return "Please enter a valid 6-digit PIN code."
    elif step_id == "reg_promo_code" and len(a) < 3:
        return "Please enter a valid promotion code."
    return None


def _next_step(session: HelpdeskSession, answer: str) -> str:
    step = session.step_id
    intent = session.answers.get("main_menu", "")

    if step == "main_menu":
        return "mobile"

    if step == "mobile":
        if intent == "register_plan":
            return "reg_product_type"
        if intent == "raise_claim":
            return "reg_device_id"
        if intent == "track_request":
            return "track_ticket"
        if intent == "plan_inquiry":
            return "inquiry_topic"
        if intent == "complaint":
            return "complaint_type"
        return "general_query"

    flow_register: dict[str, str] = {
        "reg_product_type": "reg_plan",
        "reg_plan": "reg_promo",
        "reg_promo": "reg_promo_code" if answer.lower() in ("yes", "y") else "reg_device_id",
        "reg_promo_code": "reg_device_id",
        "reg_device_id": "reg_customer_name",
        "reg_customer_name": "reg_state",
        "reg_state": "reg_city",
        "reg_city": "reg_pincode",
        "reg_pincode": "reg_address",
        "reg_address": "reg_brand",
        "reg_brand": "reg_model",
        "reg_model": "complete",
    }
    if step == "reg_device_id" and intent == "raise_claim":
        return "claim_problem"
    if step in flow_register:
        return flow_register[step]

    flow_claim: dict[str, str] = {
        "claim_problem": "claim_damage_time",
        "claim_damage_time": "claim_damage_place",
        "claim_damage_place": "claim_damage_type",
        "claim_damage_type": "claim_phone_on",
        "claim_phone_on": "claim_touch_working",
        "claim_touch_working": "claim_bank_needed",
        "claim_bank_needed": "bank_account" if answer.lower() in ("yes", "y") else "complete",
        "bank_account": "bank_ifsc",
        "bank_ifsc": "bank_name",
        "bank_name": "complete",
    }
    if step in flow_claim:
        return flow_claim[step]

    if step == "track_ticket":
        return "complete"
    if step == "inquiry_topic":
        return "complete"
    if step == "complaint_type":
        return "complaint_details"
    if step == "complaint_details":
        return "complete"
    if step == "general_query":
        return "complete"

    return "complete"


def _completion_message(session: HelpdeskSession) -> str:
    intent = session.answers.get("main_menu", "request")
    labels = {
        "register_plan": "Plan registration",
        "raise_claim": "Service / claim request",
        "track_request": "Request tracking",
        "plan_inquiry": "Plan inquiry",
        "complaint": "Feedback submission",
        "general_help": "General help query",
    }
    label = labels.get(intent, "Helpdesk request")
    ref = f"HD-{session.session_id[:8].upper()}"
    extra = ""
    topic = session.answers.get("inquiry_topic", "")
    if topic and topic in _INQUIRY_ANSWERS:
        extra = f"\n\n{ _INQUIRY_ANSWERS[topic]}"
    return (
        f"✅ Your {label} has been recorded.\n\n"
        f"Reference: **{ref}**\n"
        f"Our team will contact you on {session.answers.get('mobile', 'your registered number')} "
        f"within 1–2 business days.{extra}"
    )


def _session_to_json(s: HelpdeskSession) -> str:
    return json.dumps({
        "session_id": s.session_id,
        "step_id": s.step_id,
        "answers": s.answers,
        "created_at": s.created_at.isoformat(),
    })


def _session_from_json(raw: str) -> HelpdeskSession:
    d = json.loads(raw)
    return HelpdeskSession(
        session_id=d["session_id"],
        step_id=d["step_id"],
        answers=d.get("answers", {}),
        created_at=datetime.fromisoformat(d["created_at"]),
    )


class HelpdeskFlowService:
  """Helpdesk session manager.

  Sessions live in-process by default (single-node dev, and fine for a single
  backend container). When ``REDIS_URL`` is set they are stored in Redis with a
  TTL instead, so wizard state survives restarts and is shared across replicas.
  """

  def __init__(self, settings: Settings | None = None) -> None:
      self._sessions: dict[str, HelpdeskSession] = {}
      self._redis = get_redis(settings) if settings else None
      self._ttl = settings.cache_ttl_seconds if settings else 3600

  def _rkey(self, sid: str) -> str:
      return f"helpdesk:{sid}"

  async def _load(self, sid: str) -> HelpdeskSession | None:
      if self._redis is not None:
          try:
              raw = await self._redis.get(self._rkey(sid))
              return _session_from_json(raw) if raw else None
          except Exception:  # noqa: BLE001 — fall back to in-memory copy
              return self._sessions.get(sid)
      return self._sessions.get(sid)

  async def _save(self, session: HelpdeskSession) -> None:
      if self._redis is not None:
          try:
              await self._redis.set(
                  self._rkey(session.session_id), _session_to_json(session), ex=self._ttl
              )
              return
          except Exception:  # noqa: BLE001 — fall back to in-memory copy
              pass
      self._sessions[session.session_id] = session

  async def start(self) -> tuple[HelpdeskSession, HelpdeskStepView]:
      sid = uuid.uuid4().hex
      session = HelpdeskSession(session_id=sid)
      await self._save(session)
      return session, _STEP_VIEWS["main_menu"]

  async def get(self, session_id: str) -> HelpdeskSession | None:
      return await self._load(session_id)

  async def respond(
      self, session_id: str, answer: str
  ) -> tuple[HelpdeskSession, HelpdeskStepView | None, bool, str | None]:
      session = await self._load(session_id)
      if not session:
          raise KeyError("session_not_found")

      err = _validate(session.step_id, answer)
      if err:
          raise ValueError(err)

      session.answers[session.step_id] = answer.strip()
      nxt = _next_step(session, answer.strip())

      if nxt == "complete":
          msg = _completion_message(session)
          session.step_id = "complete"
          await self._save(session)
          return session, None, True, msg

      session.step_id = nxt
      view = _STEP_VIEWS.get(nxt)
      if not view:
          session.step_id = "complete"
          await self._save(session)
          return session, None, True, _completion_message(session)
      await self._save(session)
      return session, view, False, None

  def summary(self, session: HelpdeskSession) -> dict[str, Any]:
      return {
          "session_id": session.session_id,
          "intent": session.answers.get("main_menu"),
          "mobile": session.answers.get("mobile"),
          "answers": dict(session.answers),
          "submitted_at": datetime.now(UTC).isoformat(),
      }


# Module-level singleton for the API layer.
helpdesk_service = HelpdeskFlowService(get_settings())
