#!/bin/bash

# Initialize LocalStack with DynamoDB table and SQS queue

ENDPOINT="http://localhost:4566"
REGION="us-east-1"

echo "Creating DynamoDB table..."

aws dynamodb create-table \
  --endpoint-url $ENDPOINT \
  --table-name jobs \
  --attribute-definitions \
    AttributeName=job_id,AttributeType=S \
    AttributeName=status,AttributeType=S \
    AttributeName=created_at,AttributeType=N \
  --key-schema \
    AttributeName=job_id,KeyType=HASH \
  --global-secondary-indexes \
    'IndexName=status-created_at-index,KeySchema=[{AttributeName=status,KeyType=HASH},{AttributeName=created_at,KeyType=RANGE}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5}' \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --region $REGION \
  --no-cli-pager

echo "Waiting for table to be active..."
aws dynamodb wait table-exists \
  --endpoint-url $ENDPOINT \
  --table-name jobs \
  --region $REGION

echo "Creating SQS queue..."

aws sqs create-queue \
  --endpoint-url $ENDPOINT \
  --queue-name job-queue \
  --attributes \
    VisibilityTimeout=300,MessageRetentionPeriod=1209600 \
  --region $REGION \
  --no-cli-pager

echo "Getting queue URL..."
QUEUE_URL=$(aws sqs get-queue-url \
  --endpoint-url $ENDPOINT \
  --queue-name job-queue \
  --region $REGION \
  --query 'QueueUrl' \
  --output text)

echo "Queue URL: $QUEUE_URL"
echo "Setup complete!"
