import asyncio
import yaml
import json
import time
import os
import sys
import argparse
from asyncio.subprocess import create_subprocess_shell

class JobScheduler:
    def __init__(self, config_path):
        if not os.path.exists(config_path):
            error_msg = f"Configuration file not found: {config_path}"
            print(json.dumps({"timestamp": time.time(), "level": "ERROR", "event": "CONFIG_ERROR", "message": error_msg}))
            raise FileNotFoundError(error_msg)
            
        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            error_msg = f"Malformed YAML configuration: {e}"
            print(json.dumps({"timestamp": time.time(), "level": "ERROR", "event": "CONFIG_ERROR", "message": error_msg}))
            raise ValueError(error_msg)
            
        if not data or not isinstance(data, dict):
            data = {}

        self.jobs = data.get("jobs", [])
        if not isinstance(self.jobs, list):
            error_msg = "'jobs' key must be a list in YAML config."
            print(json.dumps({"timestamp": time.time(), "level": "ERROR", "event": "CONFIG_ERROR", "message": error_msg}))
            raise ValueError(error_msg)
            
        job_names = set()
        for job in self.jobs:
            if "name" in job:
                if job["name"] in job_names:
                    error_msg = f"Duplicate job name found: {job['name']}"
                    print(json.dumps({"timestamp": time.time(), "level": "ERROR", "event": "CONFIG_ERROR", "job": job["name"], "message": error_msg}))
                    raise ValueError(error_msg)
                job_names.add(job["name"])
            
            for key in ["name", "command", "interval"]:
                if key not in job:
                    job_name = job.get("name", "N/A")
                    error_msg = f"Missing required field '{key}' in job configuration."
                    print(json.dumps({"timestamp": time.time(), "level": "ERROR", "event": "CONFIG_ERROR", "job": job_name, "message": error_msg}))
                    raise ValueError(error_msg)
            
            # Security validation for command
            command = job["command"]
            if not isinstance(command, str) or not command.strip():
                error_msg = f"Job '{job['name']}' has an invalid or empty command."
                print(json.dumps({"timestamp": time.time(), "level": "ERROR", "event": "CONFIG_ERROR", "job": job['name'], "message": error_msg}))
                raise ValueError(error_msg)
                
            suspicious_patterns = [';', '&&', '||', '`', '$(']
            if any(p in command for p in suspicious_patterns):
                warning_msg = f"Potential security risk: shell metacharacters found in command: '{command}'"
                print(json.dumps({"timestamp": time.time(), "level": "WARNING", "event": "SECURITY_WARNING", "job": job['name'], "message": warning_msg}))

            interval = job["interval"]
            if not isinstance(interval, (int, float)) or interval <= 0:
                error_msg = f"Job '{job['name']}' interval must be a positive number."
                print(json.dumps({"timestamp": time.time(), "level": "ERROR", "event": "CONFIG_ERROR", "job": job['name'], "message": error_msg}))
                raise ValueError(error_msg)

        # Cross-reference dependencies
        for job in self.jobs:
            deps = job.get("depends_on", [])
            if not isinstance(deps, list):
                error_msg = f"Job '{job['name']}' depends_on must be a list."
                print(json.dumps({"timestamp": time.time(), "level": "ERROR", "event": "CONFIG_ERROR", "job": job['name'], "message": error_msg}))
                raise ValueError(error_msg)
            for dep in deps:
                if dep not in job_names:
                    error_msg = f"Job '{job['name']}' depends on unknown job: '{dep}'"
                    print(json.dumps({"timestamp": time.time(), "level": "ERROR", "event": "CONFIG_ERROR", "job": job['name'], "message": error_msg}))
                    raise ValueError(error_msg)

    async def log(self, level, event_type, job_name, message):
        log_entry = {
            "timestamp": time.time(),
            "level": level,
            "event": event_type,
            "job": job_name,
            "message": message
        }
        print(json.dumps(log_entry), flush=True)

    async def run_job_instance(self, job_name, command):
        await self.log("INFO", "start", job_name, "Starting job")
        
        process = await create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            await self.log("INFO", "success", job_name, stdout.decode().strip())
            return True
        else:
            await self.log("ERROR", "failure", job_name, stderr.decode().strip())
            return False

    async def run_job_wrapper(self, job_name, command, interval, job_next_run):
        success = await self.run_job_instance(job_name, command)
        job_next_run[job_name] = time.time() + interval
        return success

    async def start(self):
        job_next_run = {job["name"]: time.time() for job in self.jobs}
        job_defs = {job["name"]: job for job in self.jobs}
        
        active_tasks = {}
        pending_jobs = set()
        current_cycle_completed = {}
        
        try:
            while True:
                now = time.time()
                
                # 1. Identify newly due jobs
                for job_name, next_run in job_next_run.items():
                    if next_run <= now and job_name not in pending_jobs and job_name not in active_tasks:
                        pending_jobs.add(job_name)
                        current_cycle_completed[job_name] = {}
                
                # 2. Check finished tasks
                finished = []
                for job_name, task in list(active_tasks.items()):
                    if task.done():
                        try:
                            success = task.result()
                        except Exception as e:
                            success = False
                            await self.log("ERROR", "error", job_name, f"Job failed with exception: {e}")
                        
                        if success:
                            # Mark this dependency as completed for any pending job that depends on it
                            for pending_job in pending_jobs:
                                job_deps = job_defs[pending_job].get("depends_on", [])
                                if job_name in job_deps:
                                    current_cycle_completed[pending_job][job_name] = True
                        finished.append(job_name)
                
                for job_name in finished:
                    del active_tasks[job_name]

                # 3. Try to start pending jobs
                moved_to_start = set()
                for job_name in pending_jobs:
                    job = job_defs[job_name]
                    dependencies = job.get("depends_on", [])
                    
                    can_run = True
                    for dep in dependencies:
                        if not current_cycle_completed[job_name].get(dep, False):
                            can_run = False
                            break
                    
                    if can_run:
                        task = asyncio.create_task(self.run_job_wrapper(job_name, job["command"], job["interval"], job_next_run))
                        active_tasks[job_name] = task
                        moved_to_start.add(job_name)
                    else:
                        pending_deps = [dep for dep in dependencies if not current_cycle_completed[job_name].get(dep, False)]
                        # Optional: Log waiting every cycle or intermittently. We log once it's waiting:
                        await self.log("INFO", "waiting", job_name, f"Waiting for {pending_deps} in current cycle")
                
                pending_jobs.difference_update(moved_to_start)
                
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Asyncio Job Scheduler")
    parser.add_argument("--config", type=str, default="jobs.yml", help="Path to the YAML config file")
    args = parser.parse_args()

    try:
        scheduler = JobScheduler(args.config)
        asyncio.run(scheduler.start())
    except Exception as e:
        sys.exit(1)
