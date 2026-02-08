#!/bin/bash
set -e

# PCP Workboard — AWS Infrastructure Teardown
# Usage: ./teardown.sh [component]
# Components: all, dynamodb, iam, lambda, apigateway, s3, eventbridge

REGION="us-east-1"
TABLE_NAME="pcp-workboard"
LAMBDA_NAME="pcp-api"
LAMBDA_ROLE_NAME="pcp-lambda-role"
API_NAME="pcp-api-gateway"
BUCKET_PREFIX="pcp-workboard-frontend"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region $REGION)
BUCKET_NAME="${BUCKET_PREFIX}-${ACCOUNT_ID}"

echo "=== PCP Workboard Teardown ==="
echo "Account: $ACCOUNT_ID"
echo "Region: $REGION"
echo ""

COMPONENT=${1:-all}

# Confirmation
if [ "$COMPONENT" = "all" ]; then
    read -p "This will DELETE all PCP resources. Type 'yes' to confirm: " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi
fi

# ── EventBridge Schedules ──
teardown_eventbridge() {
    echo ">>> Deleting EventBridge schedules..."
    for name in pcp-morning-briefing pcp-midday-checkin pcp-evening-summary pcp-nudge-checker; do
        aws scheduler delete-schedule --name $name --region $REGION 2>/dev/null && \
            echo "  Deleted $name" || echo "  $name not found"
    done

    # Delete dynamic block check-in schedules
    BLOCK_SCHEDULES=$(aws scheduler list-schedules --region $REGION \
        --query "Schedules[?starts_with(Name, 'pcp-block-')].Name" --output text 2>/dev/null)
    for name in $BLOCK_SCHEDULES; do
        aws scheduler delete-schedule --name "$name" --region $REGION 2>/dev/null
        echo "  Deleted $name"
    done
}

# ── S3 ──
teardown_s3() {
    echo ">>> Deleting S3 bucket..."
    aws s3 rb "s3://${BUCKET_NAME}" --force --region $REGION 2>/dev/null && \
        echo "  Bucket deleted." || echo "  Bucket not found."
}

# ── API Gateway ──
teardown_apigateway() {
    echo ">>> Deleting API Gateway..."
    API_ID=$(aws apigatewayv2 get-apis --region $REGION \
        --query "Items[?Name=='${API_NAME}'].ApiId" --output text 2>/dev/null)
    if [ -n "$API_ID" ] && [ "$API_ID" != "None" ]; then
        aws apigatewayv2 delete-api --api-id "$API_ID" --region $REGION
        echo "  API deleted: $API_ID"
    else
        echo "  API not found."
    fi
}

# ── Lambda ──
teardown_lambda() {
    echo ">>> Deleting Lambda function..."
    aws lambda delete-function --function-name $LAMBDA_NAME --region $REGION 2>/dev/null && \
        echo "  Lambda deleted." || echo "  Lambda not found."
}

# ── IAM ──
teardown_iam() {
    echo ">>> Deleting IAM role..."

    # Detach managed policies
    aws iam detach-role-policy \
        --role-name $LAMBDA_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
        2>/dev/null || true

    # Delete inline policies
    aws iam delete-role-policy \
        --role-name $LAMBDA_ROLE_NAME \
        --policy-name pcp-lambda-policy \
        2>/dev/null || true

    # Delete role
    aws iam delete-role --role-name $LAMBDA_ROLE_NAME 2>/dev/null && \
        echo "  IAM role deleted." || echo "  IAM role not found."
}

# ── DynamoDB ──
teardown_dynamodb() {
    echo ">>> Deleting DynamoDB table..."
    aws dynamodb delete-table --table-name $TABLE_NAME --region $REGION 2>/dev/null && \
        echo "  Table deletion initiated." || echo "  Table not found."
    echo "  Waiting for table deletion..."
    aws dynamodb wait table-not-exists --table-name $TABLE_NAME --region $REGION 2>/dev/null || true
    echo "  Table deleted."
}

# ── Run Components ──
case $COMPONENT in
    all)
        teardown_eventbridge
        teardown_s3
        teardown_apigateway
        teardown_lambda
        teardown_iam
        teardown_dynamodb
        echo ""
        echo "=== Teardown Complete ==="
        ;;
    dynamodb) teardown_dynamodb ;;
    iam) teardown_iam ;;
    lambda) teardown_lambda ;;
    apigateway) teardown_apigateway ;;
    s3) teardown_s3 ;;
    eventbridge) teardown_eventbridge ;;
    *)
        echo "Unknown component: $COMPONENT"
        echo "Usage: ./teardown.sh [all|dynamodb|iam|lambda|apigateway|s3|eventbridge]"
        exit 1
        ;;
esac
