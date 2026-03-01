import unittest
from unittest.mock import patch, AsyncMock
import asyncio
import os
import sys
import tempfile
import yaml

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock print so tests run quietly
with patch('builtins.print'):
    from scheduler import JobScheduler

class TestJobScheduler(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.test_dir.name, "jobs.yml")
        
    def tearDown(self):
        self.test_dir.cleanup()

    @patch('builtins.print')
    def test_missing_config(self, mock_print):
        with self.assertRaises(FileNotFoundError):
            JobScheduler("non_existent.yml")

    @patch('builtins.print')
    def test_malformed_yaml(self, mock_print):
        with open(self.config_path, "w") as f:
            f.write("jobs: [this is not valid yaml")
        with self.assertRaises(ValueError):
            JobScheduler(self.config_path)

    @patch('builtins.print')
    def test_missing_required_fields(self, mock_print):
        data = {
            "jobs": [
                {"name": "job1", "command": "echo 1"} # missing interval
            ]
        }
        with open(self.config_path, "w") as f:
            yaml.dump(data, f)
        with self.assertRaises(ValueError):
            JobScheduler(self.config_path)

    @patch('builtins.print')
    def test_duplicate_job_names(self, mock_print):
        data = {
            "jobs": [
                {"name": "job1", "command": "echo 1", "interval": 5},
                {"name": "job1", "command": "echo 2", "interval": 10}
            ]
        }
        with open(self.config_path, "w") as f:
            yaml.dump(data, f)
        with self.assertRaises(ValueError):
            JobScheduler(self.config_path)

    @patch('builtins.print')
    def test_invalid_dependencies(self, mock_print):
        data = {
            "jobs": [
                {"name": "job1", "command": "echo 1", "interval": 5, "depends_on": ["job2"]}
            ]
        }
        with open(self.config_path, "w") as f:
            yaml.dump(data, f)
        with self.assertRaises(ValueError):
            JobScheduler(self.config_path)

    @patch('builtins.print')
    def test_invalid_interval(self, mock_print):
        data = {
            "jobs": [
                {"name": "job1", "command": "echo 1", "interval": -5}
            ]
        }
        with open(self.config_path, "w") as f:
            yaml.dump(data, f)
        with self.assertRaises(ValueError):
            JobScheduler(self.config_path)

    @patch('scheduler.create_subprocess_shell')
    async def test_run_job_instance_success(self, mock_create):
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0
        mock_create.return_value = mock_process

        data = {
            "jobs": [
                {"name": "job1", "command": "echo 1", "interval": 5}
            ]
        }
        with open(self.config_path, "w") as f:
            yaml.dump(data, f)
            
        scheduler = JobScheduler(self.config_path)
        
        with patch.object(scheduler, 'log', new_callable=AsyncMock) as mock_log:
            result = await scheduler.run_job_instance("job1", "echo 1")
            self.assertTrue(result)
            mock_log.assert_any_call("INFO", "success", "job1", "output")

if __name__ == '__main__':
    unittest.main()
