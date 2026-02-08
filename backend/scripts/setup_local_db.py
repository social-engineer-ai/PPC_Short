"""Create DynamoDB table with GSIs for local development."""
import boto3
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

ENDPOINT_URL = os.getenv("LOCAL_DYNAMODB_URL", "http://localhost:8000")
TABLE_NAME = os.getenv("TABLE_NAME", "pcp-workboard")
REGION = os.getenv("AWS_REGION", "us-east-1")


def create_table():
    client = boto3.client(
        "dynamodb",
        endpoint_url=ENDPOINT_URL if ENDPOINT_URL else None,
        region_name=REGION,
    )

    try:
        client.describe_table(TableName=TABLE_NAME)
        print(f"Table '{TABLE_NAME}' already exists.")
        return
    except client.exceptions.ResourceNotFoundException:
        pass

    print(f"Creating table '{TABLE_NAME}'...")
    client.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
            {"AttributeName": "week_id", "AttributeType": "S"},
            {"AttributeName": "date", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "week-index",
                "KeySchema": [
                    {"AttributeName": "week_id", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "date-index",
                "KeySchema": [
                    {"AttributeName": "date", "KeyType": "HASH"},
                    {"AttributeName": "sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )
    print(f"Table '{TABLE_NAME}' created successfully.")


if __name__ == "__main__":
    create_table()
