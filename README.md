# Asyncio Job Scheduler

A robust, enterprise-grade asynchronous job scheduler built in Python using `asyncio`. This application reads continuous job configurations from a YAML file and executes shell commands in non-blocking continuous intervals. It supports advanced scheduling features, including cycle-based dependency management, comprehensive configuration error handling, dynamic path execution, structured JSON logging, and security validation against shell metacharacters.

---

## Core Architecture and Features

This project was built to meet industry-level requirements for a production-ready asynchronous job scheduler. 

### 1. Centralized Scheduling Engine
Instead of individual, disconnected `while True` loops for each job, the scheduler uses a **centralized event loop** (`JobScheduler.start`). This central loop checks the pool of jobs every second, identifies which jobs are due based on their intervals, and launches them. This centralized architecture provides optimal hardware management and precise control over job execution across multiple cycles.

### 2. Cycle-Based Dependency Management
This scheduler handles task dependencies dynamically per cycle. 
- If `job3` depends on `job1` and `job2`, it will only run when *both* `job1` and `job2` have completed within the **current scheduling cycle**.
- Once a cycle completes and a new interval arises, the dependency states are explicitly reset, preventing jobs from incorrectly relying on completions from previous historical runs.

### 3. Asynchronous Subprocess Execution
The scheduler utilizes `asyncio.create_subprocess_shell` to execute user-defined shell commands in separate, non-blocking subprocesses. This ensures the main scheduler loop remains fully responsive while long-running commands execute concurrently. Data flows like `stdout` and `stderr` are safely captured via `asyncio.subprocess.PIPE`.

### 4. Robust Configuration Validation & Security
The scheduler uses robust defensive programming to handle configuration issues dynamically without runtime crashing:
- **File Integrity:** Verifies existence of the YAML config immediately, catching `FileNotFoundError`.
- **YAML Format Parsing:** Catches `yaml.YAMLError` for malformed structural errors.
- **Field Completeness:** Validates that every job defined contains all required schema keys (`name`, `command`, and `interval`).
- **Uniqueness Check:** Enforces strict uniqueness of all job names. Duplicate references block initialization.
- **Positive Interval Requirement:** Rejects any `interval` configuration passed as a string/negative int, exclusively forcing ints and floats `> 0`.
- **Cross-Reference Dependency Verification:** Cross-matches all `depends_on` arguments inside the configuration file, guaranteeing zero blind dependencies or "dead" jobs.
- **Shell Metacharacter Sanitization (Security Risk Mitigation):** The `command` parser algorithmically checks dynamic string payloads for dangerous unescaped shell injection metacharacters (e.g. `;`, `&&`, `$()`).

### 5. Structured JSON Logging
All scheduler outputs are formatted as structured JSON streams directly to standard output. This layout ensures total observability for scraping via platforms like ElasticSearch/Datadog. Event elements log:
- `timestamp`: Mathematical epoch interval mapping.
- `level`: Log severity standard strings (`INFO`, `WARNING`, `ERROR`).
- `event`: Context of execution stream (`start`, `success`, `failure`, `waiting`, `CONFIG_ERROR`).
- `job`: Active job mapping ID name.
- `message`: Contextual action payloads, warning descriptions, or dynamic application output via `stdout`/`stderr`.

---

## Setup Instructions

### Prerequisites
- **Python 3.8** or higher
- **PyYAML** Python Package (`pip install PyYAML`)

### Installation Commands

1. **Clone or navigate to the project root directory:**
   ```bash
   cd path/to/job_schedular
   ```

2. **Create a virtual environment (Recommended isolation layer):**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment scope:**
   - On **Windows**:
     ```bash
     venv\Scripts\activate
     ```
   - On **macOS/Linux**:
     ```bash
     source venv/bin/activate
     ```

4. **Install necessary project requirements:**
   ```bash
   pip install -r requirements.txt
   ```

---

## Configuration (`jobs.yml`)

The scheduler runs based on a simple, declarative configuration file formatted in YAML. 

### Example Configuration Snippet
```yaml
jobs:
  - name: build_data
    command: "python scripts/build.py"
    interval: 5

  - name: query_database
    command: "python scripts/query.py"
    interval: 3

  - name: analyze_results
    command: "python scripts/analyze.py"
    interval: 10
    depends_on: ["build_data", "query_database"]
```

### Supported Job Fields
- **`name`** *(string, required)*: Unique identifier.
- **`command`** *(string, required)*: The standard shell command mapping logic for concurrent subprocess execution.
- **`interval`** *(integer/float, required)*: Polling interval mapping in seconds (`x > 0`).
- **`depends_on`** *(list of string values, optional)*: A mapped list of job definitions that must complete successfully *during the current runtime cycle constraint* before attempting to run.

---

## Execution Guide

### Starting the Scheduler Application

By default, the central script dynamically parses the application root for `jobs.yml`:
```bash
python scheduler.py
```

### Loading Custom Configuration Configurations

You can manually provide dynamic YAML path arguments dynamically via the `--config` CLI argument parameter:
```bash
python scheduler.py --config configs/production_jobs.yml
```

---

## Development and Testing Suite

The project includes an extensive modular unit testing suite to evaluate isolated job execution environments, schema parsers, error checking mapping, array loops, security risks checks, and the centralized loop logic mapping safely.

The `unittest.mock` package is explicitly used to circumvent real machine side-effects (fake terminal process creation) while checking the validation parameters independently.

**To run the entire unit testing framework (7 modular validation patterns):**
```bash
python -m unittest discover tests/
```

**To run an exact isolated file suite:**
```bash
python tests/test_scheduler.py
```
