"""EventBridge Scheduler service for dynamic one-time and recurring schedules."""
import json
import traceback
import boto3

from ..config import AWS_REGION, LAMBDA_ARN, SCHEDULER_ROLE_ARN

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("scheduler", region_name=AWS_REGION)
    return _client


def create_one_time_schedule(name: str, schedule_datetime: str, payload: dict, timezone: str = "America/Chicago"):
    """Create a one-time EventBridge Scheduler schedule.

    Args:
        name: Unique schedule name (e.g., "pcp-block-2026-02-10-1000")
        schedule_datetime: ISO 8601 datetime (e.g., "2026-02-10T10:00:00")
        payload: JSON to pass to Lambda as event
        timezone: Schedule timezone
    """
    if not LAMBDA_ARN or not SCHEDULER_ROLE_ARN:
        print(f"[SCHEDULER] Would schedule '{name}' at {schedule_datetime}: {json.dumps(payload)}")
        return None

    client = _get_client()
    try:
        client.create_schedule(
            Name=name,
            ScheduleExpression=f"at({schedule_datetime})",
            ScheduleExpressionTimezone=timezone,
            FlexibleTimeWindow={"Mode": "OFF"},
            Target={
                "Arn": LAMBDA_ARN,
                "RoleArn": SCHEDULER_ROLE_ARN,
                "Input": json.dumps(payload),
            },
            ActionAfterCompletion="DELETE",
        )
        return name
    except client.exceptions.ConflictException:
        # Already exists, update it
        try:
            client.update_schedule(
                Name=name,
                ScheduleExpression=f"at({schedule_datetime})",
                ScheduleExpressionTimezone=timezone,
                FlexibleTimeWindow={"Mode": "OFF"},
                Target={
                    "Arn": LAMBDA_ARN,
                    "RoleArn": SCHEDULER_ROLE_ARN,
                    "Input": json.dumps(payload),
                },
                ActionAfterCompletion="DELETE",
            )
            return name
        except Exception as e:
            traceback.print_exc()
            return None
    except Exception as e:
        traceback.print_exc()
        return None


def delete_schedule(name: str):
    """Delete an EventBridge Scheduler schedule."""
    if not LAMBDA_ARN:
        print(f"[SCHEDULER] Would delete schedule '{name}'")
        return

    client = _get_client()
    try:
        client.delete_schedule(Name=name)
    except client.exceptions.ResourceNotFoundException:
        pass
    except Exception as e:
        traceback.print_exc()
