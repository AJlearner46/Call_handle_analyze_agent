from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TypedDict

from sqlalchemy.orm import Session

from app.db import models
from app.services import appointment_service, storage_service
from app.services.llm_service import LLMService
from app.utils.timeparse import extract_date, extract_name, extract_time, find_specialization
from app.utils.config import settings

try:
    from langgraph.graph import END, StateGraph
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False


@dataclass
class AgentTurnResult:
    response_text: str
    actions: list
    call_complete: bool = False


def detect_intent_heuristic(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ["reschedule", "change", "move", "busy", "can't make"]):
        return "appointment_reschedule"
    if "cancel" in lowered:
        return "appointment_cancel"
    if "availability" in lowered or "available" in lowered or "slot" in lowered:
        return "doctor_availability"
    if any(word in lowered for word in ["book", "appointment", "schedule", "see a doctor", "see doctor", "consult", "visit"]):
        return "appointment_booking"
    if any(word in lowered for word in ["question", "inquiry", "information", "info"]):
        return "general_query"
    return "general_query"


def _normalize_date(value: str | None, fallback_text: str) -> Optional[str]:
    if not value:
        parsed = extract_date(fallback_text)
        return parsed.isoformat() if parsed else None
    if value.lower() in {"today", "tomorrow"}:
        parsed = extract_date(value)
        return parsed.isoformat() if parsed else None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    except ValueError:
        parsed = extract_date(value)
        return parsed.isoformat() if parsed else None


def _normalize_time(value: str | None, fallback_text: str) -> Optional[str]:
    if value:
        parsed = extract_time(value)
        if parsed:
            return parsed
    return extract_time(fallback_text)


def interpret_text(text: str) -> dict:
    data: dict = {}
    llm = None
    if settings.gemini_api_key:
        try:
            llm = LLMService()
        except RuntimeError:
            llm = None

    if llm:
        prompt = (
            "Extract intent and entities from the user request. "
            "Return strict JSON with keys: intent, specialization, date, time, patient_name. "
            "Valid intents: appointment_booking, appointment_cancel, appointment_reschedule, "
            "doctor_availability, general_query. "
            "Infer specialization from symptoms (e.g., heart issues -> cardiologist). "
            "Date must be YYYY-MM-DD if possible. Time must be HH:MM 24h if possible. "
            f"User: {text}"
        )
        data = llm.generate_json(prompt, fallback={})

    intent = data.get("intent") or detect_intent_heuristic(text)
    specialization = data.get("specialization") or find_specialization(text)
    date_value = _normalize_date(data.get("date"), text)
    time_value = _normalize_time(data.get("time"), text)
    patient_name = data.get("patient_name") or extract_name(text)

    return {
        "intent": intent,
        "specialization": specialization,
        "date": date_value,
        "time": time_value,
        "patient_name": patient_name,
    }


class AgentState(TypedDict):
    call: models.Call
    db: Session
    text: str
    context: dict
    intent: str
    response_text: str
    call_complete: bool


def _node_interpret(state: AgentState) -> AgentState:
    context = state.get("context") or {}
    extracted = interpret_text(state["text"])
    intent = extracted.get("intent", "general_query")
    context["intent"] = intent
    for key in ("specialization", "date", "time", "patient_name"):
        if extracted.get(key):
            context[key] = extracted[key]
    state["context"] = context
    state["intent"] = intent
    return state


def _node_route(state: AgentState) -> AgentState:
    return state


def _node_booking(state: AgentState) -> AgentState:
    result = handle_booking(state["call"], state["context"], state["db"], state["text"])
    state["response_text"] = result.response_text
    state["call_complete"] = result.call_complete
    return state


def _node_availability(state: AgentState) -> AgentState:
    result = handle_availability(state["call"], state["context"], state["db"], state["text"])
    state["response_text"] = result.response_text
    state["call_complete"] = result.call_complete
    return state


def _node_cancel(state: AgentState) -> AgentState:
    result = handle_cancel(
        state["call"],
        state["context"],
        state["db"],
        state["text"],
        reschedule=state.get("intent") == "appointment_reschedule",
    )
    state["response_text"] = result.response_text
    state["call_complete"] = result.call_complete
    return state


def _node_fallback(state: AgentState) -> AgentState:
    result = handle_general_query(state["call"], state["context"], state["text"])
    state["response_text"] = result.response_text
    state["call_complete"] = result.call_complete
    return state


_GRAPH = None


def _get_graph():
    global _GRAPH
    if _GRAPH is not None:
        return _GRAPH
    if not _LANGGRAPH_AVAILABLE:
        return None
    graph = StateGraph(AgentState)
    graph.add_node("interpret", _node_interpret)
    graph.add_node("route", _node_route)
    graph.add_node("booking", _node_booking)
    graph.add_node("availability", _node_availability)
    graph.add_node("cancel", _node_cancel)
    graph.add_node("fallback", _node_fallback)
    graph.set_entry_point("interpret")
    graph.add_edge("interpret", "route")
    graph.add_conditional_edges(
        "route",
        lambda state: state.get("intent", "general_query"),
        {
            "appointment_booking": "booking",
            "doctor_availability": "availability",
            "appointment_cancel": "cancel",
            "appointment_reschedule": "cancel",
            "general_query": "fallback",
        },
    )
    graph.add_edge("booking", END)
    graph.add_edge("availability", END)
    graph.add_edge("cancel", END)
    graph.add_edge("fallback", END)
    _GRAPH = graph.compile()
    return _GRAPH


def handle_user_text(call: models.Call, text: str, db: Session) -> AgentTurnResult:
    context = call.context or {}
    graph = _get_graph() if settings.enable_langgraph else None
    if graph is not None:
        state = graph.invoke(
            {
                "call": call,
                "db": db,
                "text": text,
                "context": context,
                "intent": "",
                "response_text": "",
                "call_complete": False,
            }
        )
        call.context = state.get("context", context)
        return AgentTurnResult(
            response_text=state.get("response_text", ""),
            actions=[],
            call_complete=state.get("call_complete", False),
        )

    extracted = interpret_text(text)
    intent = extracted["intent"]
    context["intent"] = intent
    if extracted.get("specialization"):
        context["specialization"] = extracted["specialization"]
    if extracted.get("date"):
        context["date"] = extracted["date"]
    if extracted.get("time"):
        context["time"] = extracted["time"]
    if extracted.get("patient_name"):
        context["patient_name"] = extracted["patient_name"]

    if intent == "appointment_booking":
        result = handle_booking(call, context, db, text)
    elif intent == "doctor_availability":
        result = handle_availability(call, context, db, text)
    elif intent in {"appointment_cancel", "appointment_reschedule"}:
        result = handle_cancel(call, context, db, text, reschedule=intent == "appointment_reschedule")
    else:
        result = handle_general_query(call, context, text)

    call.context = context
    return result


def handle_booking(call: models.Call, context: dict, db: Session, latest_text: str) -> AgentTurnResult:
    if is_decline(latest_text):
        call.status = "declined"
        storage_service.append_action(call, "booking_declined", {"reason": latest_text})
        return AgentTurnResult(
            "Understood. If you'd like, I can check another date or connect you to a human assistant.",
            [],
            True,
        )

    if not context.get("specialization"):
        return AgentTurnResult("Which type of doctor do you need?", [])
    if not context.get("date"):
        return AgentTurnResult("What date would you like to book?", [])

    doctors = appointment_service.list_doctors(db, context["specialization"])
    if not doctors:
        return AgentTurnResult("I could not find a doctor for that specialization.", [])

    doctor = doctors[0]
    context["doctor_id"] = doctor.id

    target_date = datetime.strptime(context["date"], "%Y-%m-%d").date()
    slots = appointment_service.get_slots(db, doctor.id, target_date)

    if not slots:
        storage_service.append_action(call, "no_slots", {"doctor_id": doctor.id, "date": context["date"]})
        return AgentTurnResult("No slots are available on that date. Would you like another day?", [])

    if context.get("time"):
        chosen = pick_slot(slots, context["time"], latest_text)
        if chosen:
            return finalize_booking(call, context, doctor.id, chosen, db)
        return AgentTurnResult("I did not catch the time. Please choose one of the available slots.", [])

    context["pending_slots"] = slots[:3]
    slot_labels = ", ".join([s.split(" ")[1] for s in context["pending_slots"]])
    response = f"Dr. {doctor.name} is available at {slot_labels}. Which time works for you?"
    return AgentTurnResult(response, [])


def handle_availability(call: models.Call, context: dict, db: Session, latest_text: str) -> AgentTurnResult:
    if not context.get("specialization"):
        return AgentTurnResult("Which type of doctor do you need?", [])
    if not context.get("date"):
        return AgentTurnResult("What date should I check?", [])

    doctors = appointment_service.list_doctors(db, context["specialization"])
    if not doctors:
        return AgentTurnResult("I could not find a doctor for that specialization.", [])

    doctor = doctors[0]
    target_date = datetime.strptime(context["date"], "%Y-%m-%d").date()
    slots = appointment_service.get_slots(db, doctor.id, target_date)

    if not slots:
        return AgentTurnResult("No slots are available on that date.", [])

    slot_labels = ", ".join([s.split(" ")[1] for s in slots[:3]])
    response = f"Dr. {doctor.name} has slots at {slot_labels}. Would you like to book one?"
    if is_decline(latest_text):
        return AgentTurnResult("No problem. If you want, I can check other dates or help you book later.", [])

    return AgentTurnResult(response, [])


def handle_cancel(
    call: models.Call,
    context: dict,
    db: Session,
    latest_text: str,
    reschedule: bool = False,
) -> AgentTurnResult:
    appointment_id = extract_appointment_id(latest_text)
    if appointment_id:
        success = appointment_service.cancel_appointment(db, appointment_id)
        if success:
            storage_service.append_action(call, "appointment_cancelled", {"appointment_id": appointment_id})
            call.status = "completed"
            if reschedule:
                return AgentTurnResult(
                    "Your appointment is cancelled. What date would you like to reschedule?",
                    [],
                    False,
                )
            return AgentTurnResult("Your appointment has been cancelled.", [], True)

    phone = call.phone_number or context.get("phone")
    doctor_id = context.get("doctor_id")
    slot_time = None
    if context.get("date") and context.get("time"):
        try:
            slot_time = datetime.strptime(
                f"{context['date']} {context['time']}", "%Y-%m-%d %H:%M"
            )
        except ValueError:
            slot_time = None

    if phone or doctor_id or slot_time:
        appointment = appointment_service.find_appointment_by_details(db, phone, doctor_id, slot_time)
        if appointment:
            appointment_service.cancel_appointment(db, appointment.id)
            storage_service.append_action(call, "appointment_cancelled", {"appointment_id": appointment.id})
            call.status = "completed"
            if reschedule:
                return AgentTurnResult(
                    "Your appointment is cancelled. What date would you like to reschedule?",
                    [],
                    False,
                )
            return AgentTurnResult("Your appointment has been cancelled.", [], True)

    if reschedule:
        return AgentTurnResult(
            "I can help reschedule. Please share your appointment ID or the date and time you booked.",
            [],
            False,
        )

    return AgentTurnResult("Please provide the appointment ID you want to cancel.", [])


def pick_slot(slots: list[str], requested_time: str, text: str) -> Optional[str]:
    for slot in slots:
        if slot.endswith(requested_time):
            return slot

    lowered = text.lower()
    ordinal_map = {"first": 0, "second": 1, "third": 2}
    for key, idx in ordinal_map.items():
        if key in lowered and idx < len(slots):
            return slots[idx]
    return None


def finalize_booking(
    call: models.Call,
    context: dict,
    doctor_id: int,
    slot: str,
    db: Session,
) -> AgentTurnResult:
    payload = {
        "patient_name": context.get("patient_name") or "Unknown",
        "phone": call.phone_number or "",
        "doctor_id": doctor_id,
        "slot_time": datetime.strptime(slot, "%Y-%m-%d %H:%M"),
    }
    appointment = appointment_service.book_appointment(db, payload)
    storage_service.append_action(call, "appointment_booked", {"appointment_id": appointment.id})
    call.status = "completed"
    response = f"Your appointment is booked for {slot}. Your appointment ID is {appointment.id}."
    return AgentTurnResult(response, ["appointment_booked"], True)


def extract_appointment_id(text: str) -> Optional[int]:
    import re

    match = re.search(r"(appointment\\s*id|appointment|id)\\s*[:#]?\\s*(\\d+)", text, re.IGNORECASE)
    if match:
        try:
            return int(match.group(2))
        except ValueError:
            return None
    return None


def is_decline(text: str) -> bool:
    lowered = text.lower()
    decline_phrases = [
        "don't want",
        "do not want",
        "no longer",
        "not interested",
        "none of those",
        "none of these",
        "forget it",
        "not available",
        "no slots",
        "can't make it",
        "cant make it",
    ]
    return any(phrase in lowered for phrase in decline_phrases)


def handle_general_query(call: models.Call, context: dict, text: str) -> AgentTurnResult:
    llm = None
    if settings.gemini_api_key:
        try:
            llm = LLMService()
        except RuntimeError:
            llm = None

    if llm:
        prompt = (
            "You are a healthcare call assistant. Answer briefly and suggest booking an appointment "
            "with the right specialist if relevant. Keep it to 2 sentences. "
            f"User: {text}"
        )
        response = llm.generate(prompt).strip()
        if response:
            return AgentTurnResult(response, [])

    return AgentTurnResult(
        "I can help with appointment booking, cancellations, or availability checks. "
        "Would you like to book a visit?",
        [],
    )
