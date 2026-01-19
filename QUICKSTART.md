# Quick Start Guide

## Prerequisites

- Docker and Docker Compose installed
- AWS CLI installed (for LocalStack setup)

## Step 1: Start Services

```bash
docker-compose up -d
```

This starts:
- LocalStack (DynamoDB, SQS)
- Redis
- Backend API
- Worker
- Frontend

## Step 2: Initialize LocalStack

Wait a few seconds for LocalStack to start, then run:

```bash
./scripts/init-localstack.sh
```

Or manually:

```bash
# Create DynamoDB table
aws dynamodb create-table \
  --endpoint-url http://localhost:4566 \
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
  --region us-east-1

# Create SQS queue
aws sqs create-queue \
  --endpoint-url http://localhost:4566 \
  --queue-name job-queue \
  --attributes VisibilityTimeout=300,MessageRetentionPeriod=1209600 \
  --region us-east-1
```

## Step 3: Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Step 4: Create Your First Job

1. Go to http://localhost:3000
2. Click "Create New Job"
3. Select a job type (e.g., "Data Processing")
4. Click "Create Job"
5. Watch it process in real-time!

## Troubleshooting

### Services won't start
- Check if ports 3000, 8000, 4566, 6379 are available
- Check Docker logs: `docker-compose logs`

### Jobs not processing
- Check worker logs: `docker-compose logs worker`
- Verify SQS queue exists: `aws sqs list-queues --endpoint-url http://localhost:4566`
- Verify DynamoDB table exists: `aws dynamodb list-tables --endpoint-url http://localhost:4566`

### Frontend not connecting
- Check `NEXT_PUBLIC_API_URL` is set correctly
- Check backend is running: `curl http://localhost:8000/health`

## Scaling Workers

To test distributed locking with multiple workers:

```bash
docker-compose up --scale worker=3
```

## Stopping Services

```bash
docker-compose down
```

To also remove volumes:

```bash
docker-compose down -v
```
