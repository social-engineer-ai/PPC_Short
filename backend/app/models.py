from pydantic import BaseModel
from typing import Literal, Optional


# ── Projects ──

class ProjectCreate(BaseModel):
    area: Literal["teaching", "research", "admin", "personal"]
    name: str
    description: str = ""
    match_keywords: list[str] = []


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    match_keywords: Optional[list[str]] = None
    active: Optional[bool] = None


# ── Tasks ──

class TaskCreate(BaseModel):
    week_id: str
    day: Optional[str] = None
    block_start: Optional[str] = None
    block_end: Optional[str] = None
    project_id: str
    name: str
    subtype: str = ""
    priority: Literal["urgent", "high", "normal", "low"] = "normal"
    status: Literal["pending", "todo", "doing", "done", "skipped", "dropped"] = "todo"
    estimated_hours: float = 1.0
    notes: str = ""
    due_date: Optional[str] = None
    course_week: Optional[str] = None
    recurring: bool = False
    is_time_block: bool = False
    carried_from_week: Optional[str] = None
    date: Optional[str] = None
    drop_task_id: Optional[str] = None  # For lock/trade


class TaskUpdate(BaseModel):
    day: Optional[str] = None
    block_start: Optional[str] = None
    block_end: Optional[str] = None
    name: Optional[str] = None
    subtype: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    estimated_hours: Optional[float] = None
    notes: Optional[str] = None
    due_date: Optional[str] = None
    course_week: Optional[str] = None
    recurring: Optional[bool] = None
    is_time_block: Optional[bool] = None
    date: Optional[str] = None


# ── Day Plans ──

class Block(BaseModel):
    start: str
    end: str
    task_id: Optional[str] = None
    type: Literal["work", "break"] = "work"
    label: str = ""


class DayPlanUpdate(BaseModel):
    blocks: Optional[list[Block]] = None
    day_capacity_hours: Optional[float] = None


# ── Week ──

class WeekLockAction(BaseModel):
    locked: bool


# ── Settings ──

class SettingsUpdate(BaseModel):
    weekly_capacity_hours: Optional[int] = None
    daily_capacity_hours: Optional[int] = None
    morning_briefing_time: Optional[str] = None
    midday_checkin_time: Optional[str] = None
    evening_summary_time: Optional[str] = None
    block_duration_minutes: Optional[int] = None
    nudge_delay_minutes: Optional[int] = None
    whatsapp_number: Optional[str] = None
    timezone: Optional[str] = None
    agent_persona: Optional[str] = None


# ── Reminders ──

class ReminderCreate(BaseModel):
    type: Literal["one_time", "recurring"]
    message: str
    trigger_date: Optional[str] = None
    trigger_time: str = "09:00"
    recurrence: Optional[str] = None


# ── Agent Notes ──

class AgentNoteCreate(BaseModel):
    note: str
    applies_from: Optional[str] = None
    applies_until: Optional[str] = None
    affects: Literal["schedule", "priorities", "behavior", "general"] = "general"


# ── Behavior Overrides ──

class BehaviorOverrideCreate(BaseModel):
    setting: str
    value: str
    applies_from: Optional[str] = None
    applies_until: Optional[str] = None
