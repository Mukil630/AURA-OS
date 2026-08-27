"""Intent Classification and Entity Extraction Subsystem."""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.core.contracts.intent import (
    ExtractedEntitiesContract,
    ParsedIntentContract,
)
from app.core.enums import (
    IntentCategory,
    RiskLevel,
    TaskType,
)
from app.core.normalizer import NormalizedRequestPayload


class IntentClassifier:
    """
    Classifies normalized user requests into structured IntentCategory, TaskType,
    required capability dependencies, and extracted entity slots.
    """

    def classify(self, payload: NormalizedRequestPayload) -> ParsedIntentContract:
        """Analyze normalized text and produce structured ParsedIntentContract."""
        text = payload.cleaned_text.strip()
        lowered = text.lower()

        # 1. Schedule & Reminder Intent
        if self._is_reminder_or_schedule(lowered):
            entities = self._extract_reminder_entities(text)
            return ParsedIntentContract(
                raw_input=payload.original_raw,
                normalized_input=text,
                intent=IntentCategory.AUTOMATION_SCHEDULE,
                task_type=TaskType.SCHEDULED_TASK,
                required_capabilities=["reminder.create"],
                risk_level=RiskLevel.LOW,
                extracted_entities=entities,
                confidence_score=0.95,
            )

        # 2. GitHub & Coding CI Intent
        if self._is_coding_or_ci(lowered):
            entities = self._extract_coding_entities(text)
            capabilities = ["github.read_ci"]
            if any(w in lowered for w in ["fix", "repair", "patch", "resolve"]):
                capabilities.extend(["coding.apply_fix", "coding.run_tests"])
            return ParsedIntentContract(
                raw_input=payload.original_raw,
                normalized_input=text,
                intent=IntentCategory.CODE_ASSISTANCE,
                task_type=TaskType.CODING,
                required_capabilities=capabilities,
                risk_level=RiskLevel.MEDIUM,
                extracted_entities=entities,
                confidence_score=0.95,
            )

        # 3. Cloud / File / Drive Sync Intent
        if self._is_file_or_drive(lowered):
            entities = self._extract_file_entities(text)
            return ParsedIntentContract(
                raw_input=payload.original_raw,
                normalized_input=text,
                intent=IntentCategory.FILE_SYNC,
                task_type=TaskType.FILE_OPERATION,
                required_capabilities=["drive.upload", "drive.search"],
                risk_level=RiskLevel.MEDIUM,
                extracted_entities=entities,
                confidence_score=0.92,
            )

        # 4. Communication & Messaging Intent (Telegram / Email)
        if self._is_communication(lowered):
            entities = self._extract_comm_entities(text)
            capabilities = ["telegram.send_message"] if "telegram" in lowered else ["communication.send_notification"]
            return ParsedIntentContract(
                raw_input=payload.original_raw,
                normalized_input=text,
                intent=IntentCategory.COMMUNICATION_DISPATCH,
                task_type=TaskType.COMMUNICATION,
                required_capabilities=capabilities,
                risk_level=RiskLevel.LOW,
                extracted_entities=entities,
                confidence_score=0.93,
            )

        # 5. Local PC Hardware / System Control Intent
        if self._is_pc_control(lowered):
            entities = ExtractedEntitiesContract(subject=text)
            is_destructive = any(w in lowered for w in ["shutdown", "restart", "delete all", "format"])
            return ParsedIntentContract(
                raw_input=payload.original_raw,
                normalized_input=text,
                intent=IntentCategory.PC_HARDWARE_CONTROL,
                task_type=TaskType.SYSTEM_CONTROL,
                required_capabilities=["pc.system_info", "pc.execute_command"],
                risk_level=RiskLevel.HIGH if is_destructive else RiskLevel.LOW,
                extracted_entities=entities,
                confidence_score=0.90,
            )

        # 6. Research & Query Intent
        if self._is_research_query(lowered):
            entities = ExtractedEntitiesContract(query_text=text)
            return ParsedIntentContract(
                raw_input=payload.original_raw,
                normalized_input=text,
                intent=IntentCategory.QUERY,
                task_type=TaskType.RESEARCH,
                required_capabilities=["web.search", "research.synthesize"],
                risk_level=RiskLevel.LOW,
                extracted_entities=entities,
                confidence_score=0.88,
            )

        # Default Fallback: General Action Task
        return ParsedIntentContract(
            raw_input=payload.original_raw,
            normalized_input=text,
            intent=IntentCategory.UNKNOWN,
            task_type=TaskType.ACTION,
            required_capabilities=["system.general_action"],
            risk_level=RiskLevel.LOW,
            extracted_entities=ExtractedEntitiesContract(subject=text),
            confidence_score=0.70,
            ambiguity_detected=True,
            suggested_clarification="Could you please specify what action or tool you would like me to use?",
        )

    # ── Matcher Predicates ────────────────────────────────────────────────────────────

    def _matches_any_keyword(self, text: str, keywords: List[str]) -> bool:
        for k in keywords:
            if " " in k or "-" in k:
                if k in text:
                    return True
            else:
                if re.search(rf"\b{re.escape(k)}\b", text):
                    return True
        return False

    def _is_reminder_or_schedule(self, text: str) -> bool:
        keywords = ["remind", "reminder", "schedule", "tomorrow", "every day", "daily", "alarm", "at 9", "at 10", "at 8"]
        return self._matches_any_keyword(text, keywords)

    def _is_coding_or_ci(self, text: str) -> bool:
        keywords = ["github", "ci", "build", "pipeline", "repository", "repo", "commit", "bug", "code", "pytest", "unit test", "fix", "patch", "issue", "error", "traceback"]
        return self._matches_any_keyword(text, keywords)

    def _is_file_or_drive(self, text: str) -> bool:
        keywords = ["drive", "google drive", "upload", "backup", "vault", "sync file", "save file", "pdf", "csv"]
        return self._matches_any_keyword(text, keywords)

    def _is_communication(self, text: str) -> bool:
        keywords = ["telegram", "send message", "notify me", "send report", "email", "mail to", "alert me"]
        return self._matches_any_keyword(text, keywords)

    def _is_pc_control(self, text: str) -> bool:
        keywords = [
            "battery", "volume", "open chrome", "launch", "powershell", "pc status", "cpu", "ram",
            "screen", "pc", "computer", "machine", "hardware", "disk", "temperature", "telemetry",
            "pc doing", "pc health", "system health"
        ]
        return self._matches_any_keyword(text, keywords)

    def _is_research_query(self, text: str) -> bool:
        keywords = ["what is", "who is", "how to", "search", "find information", "research", "explain", "why"]
        return self._matches_any_keyword(text, keywords)

    # ── Entity Extractors ─────────────────────────────────────────────────────────────

    def _extract_reminder_entities(self, text: str) -> ExtractedEntitiesContract:
        """Extract time, relative day, and subject from reminder prompts."""
        lowered = text.lower()
        extracted_time: Optional[str] = None
        extracted_day: Optional[str] = None
        subject: Optional[str] = None

        # Time extraction (e.g. '9 AM', '09:00', '9:30 pm', '9am')
        time_match = re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", lowered)
        if time_match:
            raw_time = time_match.group(1).strip()
            extracted_time = self._format_standard_time(raw_time)

        # Day extraction
        for day in ["tomorrow", "today", "tonight", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            if day in lowered:
                extracted_day = day
                break

        # Subject extraction: Text after "remind me to" or clean stripped topic
        remind_pattern = re.search(r"remind\s+(?:me\s+)?(?:to\s+)?(.+)", text, re.IGNORECASE)
        if remind_pattern:
            raw_subj = remind_pattern.group(1).strip()
            # Clean out relative day or time from subject if included
            clean_subj = re.sub(r"\b(tomorrow|today|at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", "", raw_subj, flags=re.IGNORECASE).strip()
            subject = clean_subj if clean_subj else raw_subj
        else:
            subject = text

        return ExtractedEntitiesContract(
            time=extracted_time,
            relative_day=extracted_day,
            subject=subject,
        )

    def _extract_coding_entities(self, text: str) -> ExtractedEntitiesContract:
        """Extract target repo or file names from coding prompts."""
        repo_match = re.search(r"([a-zA-Z0-9_\-]+/[a-zA-Z0-9_\-]+)", text)
        target_repo = repo_match.group(1) if repo_match else None
        return ExtractedEntitiesContract(
            target_repo=target_repo,
            subject=text,
        )

    def _extract_file_entities(self, text: str) -> ExtractedEntitiesContract:
        """Extract file paths or targets."""
        file_match = re.search(r"([a-zA-Z0-9_\-/\\]+\.[a-zA-Z0-9]+)", text)
        file_path = file_match.group(1) if file_match else None
        return ExtractedEntitiesContract(
            file_path=file_path,
            subject=text,
        )

    def _extract_comm_entities(self, text: str) -> ExtractedEntitiesContract:
        """Extract recipient or channel."""
        recipient_match = re.search(r"@([a-zA-Z0-9_]+)", text)
        recipient = recipient_match.group(1) if recipient_match else None
        return ExtractedEntitiesContract(
            recipient=recipient,
            subject=text,
        )

    def _format_standard_time(self, raw: str) -> str:
        """Standardize '9 am', '9:30pm', '14:00' to HH:MM format."""
        raw = raw.lower().replace(" ", "")
        try:
            if "am" in raw or "pm" in raw:
                # Parse 12-hour format
                is_pm = "pm" in raw
                digits = raw.replace("am", "").replace("pm", "")
                if ":" in digits:
                    h, m = digits.split(":")
                else:
                    h, m = digits, "00"
                hour = int(h)
                if is_pm and hour < 12:
                    hour += 12
                elif not is_pm and hour == 12:
                    hour = 0
                return f"{hour:02d}:{m.zfill(2)}"
            elif ":" in raw:
                h, m = raw.split(":")
                return f"{int(h):02d}:{m.zfill(2)}"
            else:
                return f"{int(raw):02d}:00"
        except Exception:
            return raw
