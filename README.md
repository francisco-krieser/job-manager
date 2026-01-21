# Jobs-Based Application

A job management system built with FastAPI and Next.js that demonstrates distributed job processing with fault tolerance, real-time status streaming, and distributed locking.

## Demo

Watch a video demonstration of the application: [Demo Video](https://www.loom.com/share/0662aedbba1c4e638dfdff58aaa4cf96)

## Quickstart

### Prerequisites

- Docker and Docker Compose
- AWS CLI (for LocalStack initialization)

### Setup and Run

1. **Start all services**:
   ```bash
   docker-compose up -d
   ```

2. **Initialize LocalStack** (wait a few seconds for LocalStack to start):
   ```bash
   ./scripts/init-localstack.sh
   ```

   This script creates:
   - DynamoDB table `jobs` with a Global Secondary Index for status queries
   - SQS queue `job-queue` with a Dead Letter Queue (DLQ) for failed messages

3. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Create Your First Job

1. Navigate to http://localhost:3000
2. Click "Create New Job"
3. Select a job type (Data Processing, Report Generation, or Image Resize)
4. Configure metadata and click "Create Job"
5. Watch the job process in real-time on the dashboard or job detail page

### Scaling Workers

To test distributed locking with multiple workers:
```bash
docker-compose up --scale worker=3
```

## Tech Design

### Architecture Overview

The application follows an event-driven architecture with the following components:

- **Frontend (Next.js)**: React-based UI with Server-Sent Events (SSE) for real-time job status updates
- **Backend API (FastAPI)**: RESTful API for job management operations
- **Workers**: Distributed Python workers that process jobs with distributed locking
- **DynamoDB**: Job state persistence with Global Secondary Index for efficient status queries
- **SQS**: Job message queue for decoupled job processing
- **Redis**: Pub/Sub for real-time status streaming to frontend clients

### Job Processing Flow

1. **Job Creation**: User creates a job via the frontend, which calls the FastAPI backend
2. **Job Storage**: Job is stored in DynamoDB with status `pending`
3. **Queue Notification**: Job ID is sent to SQS queue (in production, this would be via DynamoDB Streams)
4. **Worker Processing**: Workers poll SQS for new jobs and process them with distributed locking
5. **Status Updates**: Progress updates are published to Redis Pub/Sub and streamed to frontend via SSE
6. **Completion**: Job status is updated in DynamoDB and final result is stored

### Distributed Locking

To ensure only one worker processes a job at a time (critical for multi-container deployments), the system uses DynamoDB conditional updates:

- **Lock Acquisition**: Workers attempt to acquire a lock using a conditional update that checks:
  - No lock exists OR lock has expired
  - Job status is `pending`
- **Lock Heartbeat**: Active workers refresh the lock every 30 seconds to prevent expiration during long-running jobs
- **Lock Release**: Locks are released when jobs complete, fail, are cancelled, or when workers shut down gracefully

This approach handles SQS's at-least-once delivery guarantee and ensures exactly-once processing across multiple worker containers.

### Polling vs. Event-Driven Processing

**Current Implementation (Polling)**:
The workers currently poll SQS using long polling (20-second wait time) to receive job messages. This approach is used for local development and demonstration purposes because:
- **Simplicity**: Easy to set up and debug locally
- **No additional infrastructure**: Works with LocalStack without complex stream configurations
- **Sufficient for demo**: Adequate for showcasing the distributed locking and job processing logic

**Production Implementation (Lambda Streams)**:
In production, the system would use **DynamoDB Streams + Lambda** instead of polling for several critical reasons:

1. **Cost Efficiency**: 
   - Polling requires continuous SQS API calls (even with long polling), incurring costs per request
   - DynamoDB Streams + Lambda triggers are event-driven and only incur costs when jobs are actually created
   - At scale, this can result in significant cost savings

2. **Lower Latency**:
   - Polling introduces delay (up to 20 seconds in worst case with long polling)
   - Streams provide near-instantaneous job processing (< 1 second from creation to worker notification)
   - Critical for time-sensitive job processing

3. **Better Scalability**:
   - Polling requires workers to be running continuously, consuming resources even when idle
   - Lambda functions scale automatically and only consume resources during execution
   - Better resource utilization and auto-scaling capabilities

4. **Reduced Complexity**:
   - No need to manage worker containers and their lifecycle
   - Lambda handles scaling, retries, and error handling automatically
   - Simpler deployment and operational overhead

5. **Event-Driven Architecture**:
   - Aligns with modern cloud-native patterns
   - Better integration with other AWS services (EventBridge, Step Functions, etc.)
   - More resilient to failures with built-in retry mechanisms

**Production Architecture**:
```
Job Creation → DynamoDB → DynamoDB Streams → EventBridge Pipes → SQS → Lambda Function → Process Job
```

The Lambda function would:
- Receive job messages from SQS (triggered by EventBridge Pipes)
- Acquire distributed lock using DynamoDB conditional updates
- Process the job and update status
- Handle retries and failures automatically via SQS DLQ

This maintains the same distributed locking guarantees while leveraging AWS's serverless infrastructure for better cost, latency, and scalability.

### Real-Time Status Streaming

The application uses **Server-Sent Events (SSE)** over HTTP for real-time job status updates:

- **Backend**: FastAPI SSE endpoint subscribes to Redis Pub/Sub channel
- **Frontend**: React components connect to SSE endpoint and receive updates
- **Why SSE over WebSocket**: Simpler implementation, standard HTTP, sufficient for one-way status updates, built-in reconnection support

Workers publish progress updates to Redis Pub/Sub, which are then streamed to connected frontend clients via SSE.

### Fault Tolerance

The system implements comprehensive fault tolerance:

1. **ECS Task Killed (Graceful Shutdown)**:
   - SIGTERM handler releases all active locks before shutdown
   - Ensures jobs are not left in locked state
   - Jobs automatically become available for other workers

2. **ECS Task Fails (OOM/Crash)**:
   - **Self-Healing Workers**: Each worker periodically checks for stale jobs (locks expired > 5 minutes)
   - **Automatic Recovery**: Stale jobs are reset to `pending` status and re-queued for processing
   - **Lock Expiry**: DynamoDB TTL automatically cleans up expired locks
   - No manual intervention required

3. **Retry Logic**:
   - Failed jobs are automatically retried with exponential backoff
   - Maximum retry count is configurable per job
   - Failed jobs after max retries are sent to Dead Letter Queue (DLQ)

4. **Idempotency**:
   - Job processing is idempotent - duplicate SQS messages don't cause duplicate processing
   - Distributed locking ensures only one worker processes each job

### Job Management Features

The application implements all required features from the take-home description:

1. **Multiple Job Types** ✅:
   - `data_processing`: Processes data in configurable chunks
   - `report_generation`: Generates reports with multiple pages
   - `image_resize`: Resizes images to multiple sizes
   - Extensible job type system via factory pattern

2. **Cancel and Resume Jobs** ✅:
   - **Cancel**: Jobs can be cancelled from any state except `completed`
   - **Pause/Resume**: Running jobs can be paused and resumed with checkpoint support
   - **Resume State**: Paused jobs save their progress state and resume from the last checkpoint
   - All actions available from both dashboard and job detail pages

3. **Backend Job Processing** ✅:
   - Workers automatically detect new jobs via SQS polling
   - Distributed locking ensures only one worker processes each job
   - Supports horizontal scaling across multiple containers

4. **Streaming Status Updates** ✅:
   - Real-time status streaming via SSE
   - Intermediate results and progress updates streamed to frontend
   - Redis Pub/Sub decouples workers from frontend clients

5. **Fault Tolerance** ✅:
   - Graceful shutdown handling (SIGTERM)
   - Self-healing workers detect and recover stale jobs
   - Automatic retry with exponential backoff
   - Dead Letter Queue for failed jobs

### Project Structure

```
invention/
├── backend/
│   ├── app/
│   │   ├── api/routes/jobs.py          # REST API endpoints
│   │   ├── models/job.py                # Pydantic models
│   │   ├── services/                    # AWS service wrappers
│   │   │   ├── dynamodb.py              # DynamoDB operations
│   │   │   ├── redis_service.py         # Redis Pub/Sub
│   │   │   └── sqs_service.py           # SQS operations
│   │   ├── job_types/                   # Job processors
│   │   │   ├── base.py                  # Base job processor
│   │   │   ├── factory.py               # Job type factory
│   │   │   ├── data_processing.py
│   │   │   ├── report_generation.py
│   │   │   └── image_resize.py
│   │   ├── workers/processor.py         # Worker main loop
│   │   └── main.py                      # FastAPI app
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   │   ├── page.tsx                     # Dashboard
│   │   ├── jobs/
│   │   │   ├── new/page.tsx             # Create job
│   │   │   └── [id]/page.tsx            # Job details with streaming
│   │   └── providers.tsx                # React Query provider
│   ├── lib/
│   │   ├── api.ts                       # API client
│   │   ├── websocket.ts                 # SSE client
│   │   └── jobTypes.ts                  # Job type definitions
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
├── scripts/init-localstack.sh
└── README.md
```

### API Endpoints

- `POST /jobs` - Create a new job
- `GET /jobs` - List all jobs (optional `?status=` filter)
- `GET /jobs/{job_id}` - Get job details
- `POST /jobs/{job_id}/cancel` - Cancel a job
- `POST /jobs/{job_id}/resume` - Resume a paused job
- `POST /jobs/{job_id}/pause` - Pause a running job
- `GET /jobs/{job_id}/stream` - SSE stream for job status updates
- `GET /jobs/stream/events` - SSE stream for all job updates (broadcast)

### Environment Variables

**Backend/Worker**:
- `DYNAMODB_TABLE`: DynamoDB table name (default: `jobs`)
- `DYNAMODB_ENDPOINT_URL`: DynamoDB endpoint (for LocalStack: `http://localstack:4566`)
- `SQS_QUEUE_NAME`: SQS queue name (default: `job-queue`)
- `SQS_ENDPOINT_URL`: SQS endpoint (for LocalStack: `http://localstack:4566`)
- `AWS_REGION`: AWS region (default: `us-east-1`)
- `REDIS_URL`: Redis connection string (default: `redis://redis:6379/0`)
- `WORKER_ID`: Unique worker identifier (defaults to process ID)

**Frontend**:
- `NEXT_PUBLIC_API_URL`: Backend API URL (default: `http://localhost:8000`)
