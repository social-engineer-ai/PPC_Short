import boto3
from boto3.dynamodb.conditions import Key, Attr
from datetime import datetime, timedelta
from decimal import Decimal
import json

from .config import TABLE_NAME, AWS_REGION, LOCAL_DYNAMODB_URL, DEFAULT_SETTINGS

_table = None


def _convert_decimals(obj):
    """Convert DynamoDB Decimal types to int/float for JSON serialization."""
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    return obj


def _convert_floats(obj):
    """Convert Python floats to Decimal for DynamoDB storage."""
    if isinstance(obj, list):
        return [_convert_floats(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: _convert_floats(v) for k, v in obj.items()}
    elif isinstance(obj, float):
        return Decimal(str(obj))
    return obj


def get_table():
    global _table
    if _table is None:
        kwargs = {"region_name": AWS_REGION}
        if LOCAL_DYNAMODB_URL:
            kwargs["endpoint_url"] = LOCAL_DYNAMODB_URL
        dynamodb = boto3.resource("dynamodb", **kwargs)
        _table = dynamodb.Table(TABLE_NAME)
    return _table


# ── Generic Operations ──


def put_item(item: dict) -> None:
    item = _convert_floats(item)
    get_table().put_item(Item=item)


def get_item(pk: str, sk: str) -> dict | None:
    resp = get_table().get_item(Key={"pk": pk, "sk": sk})
    item = resp.get("Item")
    return _convert_decimals(item) if item else None


def delete_item(pk: str, sk: str) -> None:
    get_table().delete_item(Key={"pk": pk, "sk": sk})


def query_pk(pk: str, sk_prefix: str = None, limit: int = None) -> list[dict]:
    kwargs = {"KeyConditionExpression": Key("pk").eq(pk)}
    if sk_prefix:
        kwargs["KeyConditionExpression"] &= Key("sk").begins_with(sk_prefix)
    if limit:
        kwargs["Limit"] = limit
    resp = get_table().query(**kwargs)
    items = resp.get("Items", [])
    # Handle pagination
    while "LastEvaluatedKey" in resp:
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        resp = get_table().query(**kwargs)
        items.extend(resp.get("Items", []))
    return _convert_decimals(items)


def query_gsi(index_name: str, pk_attr: str, pk_value: str,
              filter_pk: str = None) -> list[dict]:
    kwargs = {
        "IndexName": index_name,
        "KeyConditionExpression": Key(pk_attr).eq(pk_value),
    }
    if filter_pk:
        kwargs["FilterExpression"] = Attr("pk").eq(filter_pk)
    resp = get_table().query(**kwargs)
    items = resp.get("Items", [])
    while "LastEvaluatedKey" in resp:
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]
        resp = get_table().query(**kwargs)
        items.extend(resp.get("Items", []))
    return _convert_decimals(items)


def update_item(pk: str, sk: str, updates: dict) -> dict:
    if not updates:
        return get_item(pk, sk)
    updates = _convert_floats(updates)
    expr_parts = []
    names = {}
    values = {}
    for i, (key, val) in enumerate(updates.items()):
        pn = f"#k{i}"
        pv = f":v{i}"
        expr_parts.append(f"{pn} = {pv}")
        names[pn] = key
        values[pv] = val
    resp = get_table().update_item(
        Key={"pk": pk, "sk": sk},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues="ALL_NEW",
    )
    return _convert_decimals(resp.get("Attributes", {}))


# ── Entity-Specific Operations ──


def list_projects(active_only: bool = True) -> list[dict]:
    projects = query_pk("PROJECT")
    if active_only:
        projects = [p for p in projects if p.get("active", True)]
    return projects


def get_tasks_for_week(week_id: str, day: str = None) -> list[dict]:
    tasks = query_gsi("week-index", "week_id", week_id, filter_pk="TASK")
    if day:
        tasks = [t for t in tasks if t.get("day") == day]
    return tasks


def get_tasks_for_date(date_str: str) -> list[dict]:
    return query_gsi("date-index", "date", date_str, filter_pk="TASK")


def get_dayplan(date_str: str) -> dict | None:
    return get_item("DAYPLAN", date_str)


def get_week_lock(week_id: str) -> dict | None:
    return get_item("WEEK", week_id)


def get_checkins_for_date(date_str: str) -> list[dict]:
    return query_pk(f"CHECKIN#{date_str}")


def get_pending_task() -> dict | None:
    item = get_item("PENDING", "USER")
    if not item:
        return None
    # Check expiry
    expires = item.get("expires_at", "")
    if expires and datetime.fromisoformat(expires) < datetime.utcnow():
        delete_item("PENDING", "USER")
        return None
    return item


def save_pending_task(task_data: dict) -> None:
    now = datetime.utcnow()
    item = {
        "pk": "PENDING",
        "sk": "USER",
        **task_data,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
    }
    put_item(item)


def clear_pending_task() -> None:
    delete_item("PENDING", "USER")


def get_settings() -> dict:
    item = get_item("SETTINGS", "USER")
    if not item:
        return {**DEFAULT_SETTINGS}
    # Merge with defaults for any missing keys
    result = {**DEFAULT_SETTINGS}
    result.update({k: v for k, v in item.items() if k not in ("pk", "sk")})
    return result


def list_active_reminders() -> list[dict]:
    reminders = query_pk("REMINDER")
    return [r for r in reminders if r.get("active", True)]


def list_active_agent_notes() -> list[dict]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    notes = query_pk("AGENTNOTE")
    return [
        n for n in notes
        if n.get("active", True)
        and (not n.get("applies_until") or n["applies_until"] >= today)
    ]


def get_chat_log(date_str: str, limit: int = 20) -> list[dict]:
    """Get chat messages for a date, sorted by timestamp (newest last)."""
    msgs = query_pk(f"CHAT#{date_str}")
    msgs.sort(key=lambda m: m.get("timestamp", ""))
    if limit:
        msgs = msgs[-limit:]
    return msgs


def save_chat_message(date_str: str, role: str, content: str, intent: str = None) -> None:
    """Save a chat message (user or assistant)."""
    from datetime import datetime as dt
    now = dt.utcnow()
    msg_id = now.strftime("%Y%m%dT%H%M%S%f")
    item = {
        "pk": f"CHAT#{date_str}",
        "sk": msg_id,
        "role": role,
        "content": content,
        "timestamp": now.isoformat(),
        "date": date_str,
    }
    if intent:
        item["intent"] = intent
    put_item(item)


def list_active_behavior_overrides() -> list[dict]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    overrides = query_pk("BEHAVIOR")
    return [
        o for o in overrides
        if o.get("active", True)
        and (not o.get("applies_until") or o["applies_until"] >= today)
    ]
