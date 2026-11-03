# ADR-0001: Cloud provider is Google Cloud (Mumbai)

Status: **Accepted** (2026-11-03)

## Context
The system needs batch ML jobs, a small API, a relational store, an analytics store and a public
web front end. The owner has AWS experience and currently holds **GCP credits**.

## Decision
Run on GCP in `asia-south1`: Cloud Run (API and jobs), Cloud SQL Postgres, BigQuery, Cloud
Storage, Cloud Scheduler with Workflows, Pub/Sub, Vertex AI Model Registry, Secret Manager.
Three separate projects: dev, staging, prod. All infrastructure in Terraform.

## Alternatives
- **AWS in Mumbai** (App Runner/Fargate, RDS, S3, Step Functions): equally capable and familiar
  to the owner, but no credits.
- **Azure**: no advantage here.

## Consequences
- The application stays plain Python, FastAPI and Postgres in containers, so a move to AWS would
  mostly change Terraform and a few managed-service calls.
- Credit expiry and eligible products must be checked before Phase 1; a budget alert is created
  before any resource.
- Data stays in India.
