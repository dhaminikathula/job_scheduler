import asyncio
import yaml
import json
import time
from asyncio.subprocess import create_subprocess_shell

class JobScheduler:
    def __init__(self, config_path):
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
        self.jobs = data.get("jobs", [])
        self.completed = {}

    async def log(self, event_type, job_name, message):
        log_entry = {
            "timestamp": time.time(),
            "event": event_type,
            "job": job_name,
            "message": message
        }
        print(json.dumps(log_entry))

    async def run_job(self, job):
        name = job["name"]
        command = job["command"]
        interval = job["interval"]
        dependencies = job.get("depends_on", [])

        while True:
            if dependencies:
                pending = [
                    dep for dep in dependencies
                    if not self.completed.get(dep, False)
                ]

                if pending:
                    await self.log("waiting", name, f"Waiting for {pending}")
                    await asyncio.sleep(1)
                    continue

            await self.log("start", name, "Starting job")

            process = await create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                await self.log("success", name, stdout.decode().strip())
                self.completed[name] = True
            else:
                await self.log("failure", name, stderr.decode().strip())
                self.completed[name] = False

            await asyncio.sleep(interval)

    async def start(self):
        tasks = [self.run_job(job) for job in self.jobs]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    scheduler = JobScheduler("jobs.yml")
    asyncio.run(scheduler.start())
