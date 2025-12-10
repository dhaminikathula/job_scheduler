# Async Job Scheduler (Python + Asyncio)

## Overview
This project is a lightweight asynchronous job scheduler written in Python.  
It reads a YAML configuration file (`jobs.yml`) and schedules multiple jobs concurrently using `asyncio`.  
Jobs can depend on other jobs and only run after their dependencies succeed.

---

## How to Install & Run

### 1. Create Virtual Environment
