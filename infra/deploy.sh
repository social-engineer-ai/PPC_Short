#!/bin/bash
set -e

# PCP Workboard — AWS Infrastructure Deployment
# Usage: ./deploy.sh [component]
# Components: all, dynamodb, iam, lambda, apigateway, s3, cloudfront, eventbridge, seed

REGION="us-east-1"
TABLE_NAME="pcp-workboard"
LAMBDA_NAME="pcp-api"
LAMBDA_ROLE_NAME="pcp-lambda-role"
API_NAME="pcp-api-gateway"
BUCKET_PREFIX="pcp-workboard-frontend"
STACK_PREFIX="pcp"

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --region $REGION)
BUCKET_NAME="${BUCKET_PREFIX}-${ACCOUNT_ID}"
LAMBDA_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${LAMBDA_NAME}"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

echo "=== PCP Workboard Deploy ==="
echo "Account: $ACCOUNT_ID"
echo "Region: $REGION"
echo ""

COMPONENT=${1:-all}

# ── DynamoDB ──
deploy_dynamodb() {
    echo ">>> Creating DynamoDB table..."
    aws dynamodb create-table \
        --table-name $TABLE_NAME \
        --attribute-definitions \
            AttributeName=pk,AttributeType=S \
            AttributeName=sk,AttributeType=S \
            AttributeName=week_id,AttributeType=S \
            AttributeName=date,AttributeType=S \
        --key-schema \
            AttributeName=pk,KeyType=HASH \
            AttributeName=sk,KeyType=RANGE \
        --global-secondary-indexes \
            '[
                {
                    "IndexName": "week-index",
                    "KeySchema": [{"AttributeName": "week_id", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
                    "Projection": {"ProjectionType": "ALL"}
                },
                {
                    "IndexName": "date-index",
                    "KeySchema": [{"AttributeName": "date", "KeyType": "HASH"}, {"AttributeName": "sk", "KeyType": "RANGE"}],
                    "Projection": {"ProjectionType": "ALL"}
                }
            ]' \
        --billing-mode PAY_PER_REQUEST \
        --region $REGION \
        2>/dev/null && echo "  Table created." || echo "  Table already exists."

    echo "  Waiting for table to be active..."
    aws dynamodb wait table-exists --table-name $TABLE_NAME --region $REGION
    echo "  Table ready."
}

# ── IAM Role ──
deploy_iam() {
    echo ">>> Creating IAM role..."

    # Trust policy
    cat > /tmp/pcp-trust-policy.json << 'TRUST'
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {
            "Service": ["lambda.amazonaws.com", "scheduler.amazonaws.com"]
        },
        "Action": "sts:AssumeRole"
    }]
}
TRUST

    aws iam create-role \
        --role-name $LAMBDA_ROLE_NAME \
        --assume-role-policy-document file:///tmp/pcp-trust-policy.json \
        --region $REGION \
        2>/dev/null && echo "  Role created." || echo "  Role already exists."

    # Attach basic Lambda execution
    aws iam attach-role-policy \
        --role-name $LAMBDA_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
        2>/dev/null || true

    # Inline policy for DynamoDB + Scheduler
    cat > /tmp/pcp-inline-policy.json << POLICY
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": "dynamodb:*",
            "Resource": [
                "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}",
                "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${TABLE_NAME}/index/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": "scheduler:*",
            "Resource": "arn:aws:scheduler:${REGION}:${ACCOUNT_ID}:schedule/default/pcp-*"
        },
        {
            "Effect": "Allow",
            "Action": "iam:PassRole",
            "Resource": "arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"
        },
        {
            "Effect": "Allow",
            "Action": "lambda:InvokeFunction",
            "Resource": "${LAMBDA_ARN}"
        }
    ]
}
POLICY

    aws iam put-role-policy \
        --role-name $LAMBDA_ROLE_NAME \
        --policy-name pcp-lambda-policy \
        --policy-document file:///tmp/pcp-inline-policy.json \
        2>/dev/null

    echo "  IAM configured. Waiting 10s for propagation..."
    sleep 10
}

# ── Lambda ──
deploy_lambda() {
    echo ">>> Packaging Lambda..."
    cd "$(dirname "$0")/../backend"

    rm -rf package/ lambda.zip
    mkdir -p package

    pip install -r requirements.txt -t package/ --quiet \
        --platform manylinux2014_x86_64 --only-binary=:all: 2>/dev/null || \
        pip install -r requirements.txt -t package/ --quiet

    cp -r app package/

    cd package
    zip -r ../lambda.zip . -q
    cd ..

    echo "  Package size: $(du -sh lambda.zip | cut -f1)"

    # Load env vars from .env
    ENV_FILE="$(dirname "$0")/../.env"
    if [ -f "$ENV_FILE" ]; then
        echo "  Loading env vars from .env..."
        # Parse key=value pairs
        ENV_VARS=$(grep -v '^#' "$ENV_FILE" | grep '=' | while IFS='=' read -r key value; do
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)
            if [ -n "$key" ] && [ -n "$value" ]; then
                echo "${key}=${value},"
            fi
        done | tr -d '\n' | sed 's/,$//')
    fi

    # Add infra-specific env vars
    ENV_JSON="{\"Variables\":{\"TABLE_NAME\":\"${TABLE_NAME}\",\"AWS_REGION_NAME\":\"${REGION}\",\"LAMBDA_ARN\":\"${LAMBDA_ARN}\",\"SCHEDULER_ROLE_ARN\":\"${ROLE_ARN}\"}}"

    # Check if function exists
    if aws lambda get-function --function-name $LAMBDA_NAME --region $REGION 2>/dev/null; then
        echo "  Updating existing Lambda..."
        aws lambda update-function-code \
            --function-name $LAMBDA_NAME \
            --zip-file fileb://lambda.zip \
            --region $REGION \
            --output text --query 'FunctionArn' 2>/dev/null
    else
        echo "  Creating Lambda function..."
        aws lambda create-function \
            --function-name $LAMBDA_NAME \
            --runtime python3.11 \
            --handler app.main.handler \
            --role "arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}" \
            --zip-file fileb://lambda.zip \
            --timeout 30 \
            --memory-size 512 \
            --environment "$ENV_JSON" \
            --region $REGION \
            --output text --query 'FunctionArn'
    fi

    rm -rf package/
    echo "  Lambda deployed."
    cd "$(dirname "$0")"
}

# ── API Gateway ──
deploy_apigateway() {
    echo ">>> Creating API Gateway..."

    # Check if API exists
    API_ID=$(aws apigatewayv2 get-apis --region $REGION --query "Items[?Name=='${API_NAME}'].ApiId" --output text 2>/dev/null)

    if [ -z "$API_ID" ] || [ "$API_ID" = "None" ]; then
        API_ID=$(aws apigatewayv2 create-api \
            --name $API_NAME \
            --protocol-type HTTP \
            --cors-configuration "AllowOrigins=*,AllowMethods=*,AllowHeaders=*" \
            --region $REGION \
            --query 'ApiId' --output text)
        echo "  API created: $API_ID"
    else
        echo "  API exists: $API_ID"
    fi

    # Create Lambda integration
    INTEGRATION_ID=$(aws apigatewayv2 get-integrations \
        --api-id $API_ID --region $REGION \
        --query 'Items[0].IntegrationId' --output text 2>/dev/null)

    if [ -z "$INTEGRATION_ID" ] || [ "$INTEGRATION_ID" = "None" ]; then
        INTEGRATION_ID=$(aws apigatewayv2 create-integration \
            --api-id $API_ID \
            --integration-type AWS_PROXY \
            --integration-uri $LAMBDA_ARN \
            --payload-format-version 2.0 \
            --region $REGION \
            --query 'IntegrationId' --output text)
        echo "  Integration created: $INTEGRATION_ID"
    fi

    # Create route
    ROUTE_EXISTS=$(aws apigatewayv2 get-routes \
        --api-id $API_ID --region $REGION \
        --query "Items[?RouteKey=='ANY /api/{proxy+}'].RouteId" --output text 2>/dev/null)

    if [ -z "$ROUTE_EXISTS" ] || [ "$ROUTE_EXISTS" = "None" ]; then
        aws apigatewayv2 create-route \
            --api-id $API_ID \
            --route-key 'ANY /api/{proxy+}' \
            --target "integrations/$INTEGRATION_ID" \
            --region $REGION \
            --output text 2>/dev/null
        echo "  Route created."
    fi

    # Create default stage
    aws apigatewayv2 create-stage \
        --api-id $API_ID \
        --stage-name '$default' \
        --auto-deploy \
        --region $REGION 2>/dev/null || true

    # Grant API Gateway permission to invoke Lambda
    aws lambda add-permission \
        --function-name $LAMBDA_NAME \
        --statement-id apigateway-invoke \
        --action lambda:InvokeFunction \
        --principal apigateway.amazonaws.com \
        --source-arn "arn:aws:execute-api:${REGION}:${ACCOUNT_ID}:${API_ID}/*/*" \
        --region $REGION 2>/dev/null || true

    API_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com"
    echo "  API URL: $API_URL"
    echo "$API_URL" > /tmp/pcp-api-url.txt
}

# ── S3 ──
deploy_s3() {
    echo ">>> Creating S3 bucket..."
    aws s3 mb "s3://${BUCKET_NAME}" --region $REGION 2>/dev/null || echo "  Bucket already exists."

    # Block public access (CloudFront uses OAC)
    aws s3api put-public-access-block \
        --bucket $BUCKET_NAME \
        --public-access-block-configuration "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" \
        --region $REGION

    echo "  Bucket ready: $BUCKET_NAME"
}

# ── EventBridge Scheduler Rules ──
deploy_eventbridge() {
    echo ">>> Creating EventBridge Scheduler rules..."

    # Create schedule group
    aws scheduler create-schedule-group \
        --name default \
        --region $REGION 2>/dev/null || true

    # Morning briefing: 7 AM CT = 13:00 UTC, Mon-Fri
    aws scheduler create-schedule \
        --name pcp-morning-briefing \
        --schedule-expression "cron(0 13 ? * MON-FRI *)" \
        --schedule-expression-timezone "UTC" \
        --flexible-time-window '{"Mode": "OFF"}' \
        --target "{\"Arn\": \"${LAMBDA_ARN}\", \"RoleArn\": \"${ROLE_ARN}\", \"Input\": \"{\\\"action\\\": \\\"morning_briefing\\\"}\"}" \
        --region $REGION 2>/dev/null && echo "  Morning briefing scheduled." || echo "  Morning briefing already exists."

    # Midday check-in: 1 PM CT = 19:00 UTC
    aws scheduler create-schedule \
        --name pcp-midday-checkin \
        --schedule-expression "cron(0 19 ? * MON-FRI *)" \
        --schedule-expression-timezone "UTC" \
        --flexible-time-window '{"Mode": "OFF"}' \
        --target "{\"Arn\": \"${LAMBDA_ARN}\", \"RoleArn\": \"${ROLE_ARN}\", \"Input\": \"{\\\"action\\\": \\\"midday_checkin\\\"}\"}" \
        --region $REGION 2>/dev/null && echo "  Midday check-in scheduled." || echo "  Midday check-in already exists."

    # Evening summary: 6 PM CT = 00:00 UTC next day
    aws scheduler create-schedule \
        --name pcp-evening-summary \
        --schedule-expression "cron(0 0 ? * TUE-SAT *)" \
        --schedule-expression-timezone "UTC" \
        --flexible-time-window '{"Mode": "OFF"}' \
        --target "{\"Arn\": \"${LAMBDA_ARN}\", \"RoleArn\": \"${ROLE_ARN}\", \"Input\": \"{\\\"action\\\": \\\"evening_summary\\\"}\"}" \
        --region $REGION 2>/dev/null && echo "  Evening summary scheduled." || echo "  Evening summary already exists."

    # Nudge checker: every 15 minutes
    aws scheduler create-schedule \
        --name pcp-nudge-checker \
        --schedule-expression "rate(15 minutes)" \
        --flexible-time-window '{"Mode": "OFF"}' \
        --target "{\"Arn\": \"${LAMBDA_ARN}\", \"RoleArn\": \"${ROLE_ARN}\", \"Input\": \"{\\\"action\\\": \\\"nudge_check\\\"}\"}" \
        --region $REGION 2>/dev/null && echo "  Nudge checker scheduled." || echo "  Nudge checker already exists."
}

# ── Seed Data ──
seed_data() {
    echo ">>> Seeding default data..."
    cd "$(dirname "$0")/../backend"
    python scripts/seed_data.py
    cd "$(dirname "$0")"
}

# ── Deploy Frontend ──
deploy_frontend() {
    echo ">>> Building and deploying frontend..."
    cd "$(dirname "$0")/../frontend"

    # Read API URL
    API_URL=$(cat /tmp/pcp-api-url.txt 2>/dev/null || echo "")
    if [ -n "$API_URL" ]; then
        echo "VITE_API_URL=$API_URL" > .env.production
    fi

    npm install --quiet
    npm run build

    aws s3 sync dist/ "s3://${BUCKET_NAME}/" --delete --region $REGION
    echo "  Frontend uploaded to S3."

    cd "$(dirname "$0")"
}

# ── Run Components ──
case $COMPONENT in
    all)
        deploy_dynamodb
        deploy_iam
        deploy_lambda
        deploy_apigateway
        deploy_s3
        deploy_eventbridge
        seed_data
        deploy_frontend
        echo ""
        echo "=== Deployment Complete ==="
        echo "API: $(cat /tmp/pcp-api-url.txt 2>/dev/null || echo 'check API Gateway console')"
        echo "S3: $BUCKET_NAME"
        echo ""
        echo "Next steps:"
        echo "1. Set up CloudFront distribution (manual for now)"
        echo "2. Configure Twilio webhook URL"
        echo "3. Update .env with LAMBDA_ARN and SCHEDULER_ROLE_ARN"
        ;;
    dynamodb) deploy_dynamodb ;;
    iam) deploy_iam ;;
    lambda) deploy_lambda ;;
    apigateway) deploy_apigateway ;;
    s3) deploy_s3 ;;
    eventbridge) deploy_eventbridge ;;
    seed) seed_data ;;
    frontend) deploy_frontend ;;
    *)
        echo "Unknown component: $COMPONENT"
        echo "Usage: ./deploy.sh [all|dynamodb|iam|lambda|apigateway|s3|eventbridge|seed|frontend]"
        exit 1
        ;;
esac
