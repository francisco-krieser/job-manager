# Jobs-Based Application

A production-ready job management system built with FastAPI, Next.js, DynamoDB, SQS, and Redis. This application demonstrates distributed job processing with fault tolerance, real-time status streaming, and distributed locking.

## Architecture

- **Frontend**: Next.js 14 with TypeScript, React Query, and Server-Sent Events (SSE) for real-time updates
- **Backend API**: FastAPI with REST endpoints for job management
- **Workers**: Distributed Python workers that poll SQS and process jobs with distributed locking
- **Database**: DynamoDB for job state persistence
- **Queue**: SQS for job message queuing (simulated with LocalStack locally)
- **Streaming**: Redis Pub/Sub for real-time job status updates

## Features

### Core Requirements ✅

1. **Job Creation Interface**: Create multiple job types (data_processing, report_generation, image_resize)
2. **Job Management**: Cancel and resume jobs from the interface
3. **Backend Processing**: Workers detect and process new jobs
4. **Distributed Locking**: Ensures only one worker processes a job at a time using DynamoDB conditional updates

### Bonus Features ✅

1. **Real-time Streaming**: SSE endpoint streams job status and intermediate results via Redis Pub/Sub
2. **Fault Tolerance**:
   - ECS task killed: Graceful shutdown with SIGTERM handling
   - ECS task fails (OOM): Heartbeat + self-healing workers detect stale locks and recover jobs

## Project Structure

```
invention/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes/
│   │   │       └── jobs.py          # API endpoints
│   │   ├── models/
│   │   │   └── job.py               # Pydantic models
│   │   ├── services/
│   │   │   ├── dynamodb.py          # DynamoDB operations
│   │   │   ├── redis_service.py     # Redis Pub/Sub
│   │   │   └── sqs_service.py       # SQS operations
│   │   ├── job_types/
│   │   │   ├── base.py              # Base job processor
│   │   │   ├── data_processing.py   # Data processing job
│   │   │   ├── report_generation.py # Report generation job
│   │   │   └── image_resize.py      # Image resize job
│   │   ├── workers/
│   │   │   └── processor.py         # Worker main loop
│   │   └── main.py                  # FastAPI app
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx                 # Dashboard
│   │   ├── jobs/
│   │   │   ├── new/
│   │   │   │   └── page.tsx         # Create job
│   │   │   └── [id]/
│   │   │       └── page.tsx         # Job details with streaming
│   │   └── providers.tsx            # React Query provider
│   ├── lib/
│   │   ├── api.ts                   # API client
│   │   └── websocket.ts             # SSE client
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- Node.js 18+ (for local development)

### Local Development with Docker

1. **Start all services**:
   ```bash
   docker-compose up -d
   ```

2. **Initialize DynamoDB table** (in a separate terminal):
   ```bash
   # Create DynamoDB table
   aws dynamodb create-table \
     --endpoint-url http://localhost:4566 \
     --table-name jobs \
     --attribute-definitions \
       AttributeName=job_id,AttributeType=S \
       AttributeName=status,AttributeType=S \
     --key-schema \
       AttributeName=job_id,KeyType=HASH \
     --global-secondary-indexes \
       IndexName=status-created_at-index,KeySchema=[{AttributeName=status,KeyType=HASH},{AttributeName=created_at,KeyType=RANGE}],Projection={ProjectionType=ALL},ProvisionedThroughput={ReadCapacityUnits=5,WriteCapacityUnits=5} \
     --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
     --region us-east-1
   ```

3. **Create SQS queue**:
   ```bash
   aws sqs create-queue \
     --endpoint-url http://localhost:4566 \
     --queue-name job-queue \
     --region us-east-1
   ```

4. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Local Development (Without Docker)

1. **Start LocalStack and Redis**:
   ```bash
   docker-compose up localstack redis -d
   ```

2. **Set up Python environment**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Start backend API**:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

4. **Start worker** (in another terminal):
   ```bash
   cd backend
   python -m app.workers.processor
   ```

5. **Start frontend**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## Usage

### Creating a Job

1. Navigate to http://localhost:3000
2. Click "Create New Job"
3. Select job type:
   - **Data Processing**: Processes data in chunks
   - **Report Generation**: Generates a report with multiple pages
   - **Image Resize**: Resizes images to multiple sizes
4. Configure metadata (JSON format) and max retries
5. Click "Create Job"

### Monitoring Jobs

- **Dashboard**: View all jobs with status, progress, and actions
- **Job Details**: Click on a job to see detailed information and real-time progress updates
- **Streaming**: Job detail page automatically streams status updates via SSE

### Job Actions

- **Cancel**: Cancel a running or pending job
- **Pause**: Pause a running job
- **Resume**: Resume a paused job

## API Endpoints

- `POST /jobs` - Create a new job
- `GET /jobs` - List all jobs (optional `?status=` filter)
- `GET /jobs/{job_id}` - Get job details
- `POST /jobs/{job_id}/cancel` - Cancel a job
- `POST /jobs/{job_id}/resume` - Resume a paused job
- `POST /jobs/{job_id}/pause` - Pause a running job
- `GET /jobs/{job_id}/stream` - SSE stream for job status

## Architecture Decisions

### Why Event-Driven (DynamoDB Streams + SQS)?

- **Lower costs**: No continuous polling of DynamoDB
- **Better scalability**: Decouples job creation from worker capacity
- **Fault tolerance**: SQS provides durability and automatic retries

### Why Distributed Locking?

- SQS provides at-least-once delivery
- Distributed locking ensures exactly-once processing
- Handles edge cases (duplicate messages, worker crashes)

### Why SSE over WebSocket?

- Simpler implementation (one-way communication)
- Standard HTTP (easier to debug)
- Sufficient for status-only updates
- Built-in reconnection support

### Fault Tolerance

1. **Worker Crash (Normal)**: SIGTERM handler releases locks gracefully
2. **Worker Crash (OOM)**: Self-healing workers detect stale locks and recover jobs
3. **Lock Expiry**: DynamoDB TTL automatically cleans up expired locks
4. **Retry Logic**: Exponential backoff for failed jobs

## Testing

### Manual Testing

1. Create multiple jobs and verify they're processed
2. Cancel a running job and verify it stops
3. Pause and resume a job
4. Kill a worker container and verify jobs are recovered
5. Check real-time streaming on job detail page

### Load Testing

Scale workers to test distributed locking:
```bash
docker-compose up --scale worker=3
```

## Production Deployment

### AWS ECS Deployment

1. **Build and push Docker images** to ECR
2. **Create ECS Task Definitions**:
   - API service (FastAPI)
   - Worker service (scalable)
3. **Configure**:
   - DynamoDB table with streams enabled
   - EventBridge Pipes (DynamoDB Streams → SQS)
   - SQS queue with DLQ
   - Redis cluster (ElastiCache)
4. **Set environment variables** in ECS task definitions

### Environment Variables

- `DYNAMODB_TABLE`: DynamoDB table name
- `SQS_QUEUE_URL`: SQS queue URL
- `REDIS_URL`: Redis connection string
- `AWS_REGION`: AWS region
- `WORKER_ID`: Unique worker identifier (ECS task ARN)

## Future Enhancements

- [ ] Add authentication/authorization
- [ ] Implement job priorities
- [ ] Add job scheduling (cron-like)
- [ ] Implement job result storage (S3)
- [ ] Add comprehensive monitoring (CloudWatch)
- [ ] Implement rate limiting
- [ ] Add job templates

## License

MIT
