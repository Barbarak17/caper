import json
import logging

from autouri import AutoURI

logger = logging.getLogger(__name__)


class CromwellMetadata:
    DEFAULT_METADATA_BASENAME = 'metadata.json'

    def __init__(self, metadata):
        """Parses metadata JSON (dict) object or file.
        """
        if isinstance(metadata, dict):
            self._metadata = metadata
        else:
            s = AutoURI(metadata).read()
            self._metadata = json.loads(s)

    @property
    def data(self):
        return self._metadata

    @property
    def metadata(self):
        return self._metadata

    @property
    def workflow_id(self):
        return self._metadata['id']

    @property
    def workflow_status(self):
        return self._metadata['status']

    @property
    def failures(self):
        if 'failures' in self._metadata:
            return self._metadata['failures']
        return None

    @property
    def calls(self):
        if 'calls' in self._metadata:
            return self._metadata['calls']
        return None

    def recurse_calls(self, fnc_call, parent_call_names=tuple()):
        """Recurse on tasks in metadata.

        Args:
            fnc_call:
                Function to be called recursively for each call (task).
                This function should take the following three arguments.
                    call_name:
                        Cromwell workflow's call (task)'s name.
                    call:
                        Cromwell workflow's call (task) itself.
                    parent_call_names:
                        Tuple of parent call's name.
                        e.g. (..., great grand parent, grand parent, parent, ...)
        """
        if not self.calls:
            return
        for call_name, call_list in self.calls.items():
            for call in call_list:
                if 'subWorkflowMetadata' in call:
                    subworkflow = call['subWorkflowMetadata']
                    sub_m = CromwellMetadata(subworkflow)
                    sub_m.recurse_calls(
                        fnc_call, parent_call_names=parent_call_names + (call_name,)
                    )
                else:
                    fnc_call(call_name, call, parent_call_names)

    def write_on_workflow_root(self, basename=DEFAULT_METADATA_BASENAME):
        """Update metadata JSON file on metadata's output root directory.
        If there is a subworkflow, nest it's metadata into main workflow's one

        Args:
            write_subworkflow:
                Write metadata JSON file for subworkflows.
        """
        if 'workflowRoot' in self._metadata:
            root = self._metadata['workflowRoot']
            metadata_file = '/'.join([root, basename])

            AutoURI(metadata_file).write(json.dumps(self._metadata, indent=4))
            logger.info('Wrote metadata file. {f}'.format(f=metadata_file))
        else:
            metadata_file = None
            workflow_id = self._metadata['id'] if 'id' in self._metadata else None
            logger.warning(
                'Failed to write metadata file. No root directory found. '
                'wf_id={i}'.format(i=workflow_id)
            )

        return metadata_file

    def troubleshoot(self, fileobj, show_completed_task=False, show_stdout=False):
        """Troubleshoots a workflow.
        Also, finds failure reasons and prints out STDERR and STDOUT.

        Args:
            fileobj:
                File-like object to write troubleshooting messages to.
            show_completed_task:
                Show STDERR (or STDOUT) of completed tasks.
            show_stdout:
                Show failed task's STDOUT along with STDERR.
        """
        fileobj.write(
            '* Started troubleshooting workflow: id={id}, status={status}\n'.format(
                id=self.workflow_id, status=self.workflow_status
            )
        )

        if self.workflow_status == 'Succeeded':
            fileobj.write('* Workflow ran Successfully.\n')
            return

        if self.failures:
            fileobj.write(
                '* Found failures JSON object.\n{s}\n'.format(
                    s=json.dumps(self.failures, indent=4)
                )
            )

        def troubleshoot_call(call_name, call, parent_call_names):
            status = call['executionStatus'] if 'executionStatus' in call else None
            shard_index = call['shardIndex'] if 'shardIndex' in call else None
            rc = call['returnCode'] if 'returnCode' in call else None
            job_id = call['jobId'] if 'jobId' in call else None
            stdout = call['stdout'] if 'stdout' in call else None
            stderr = call['stderr'] if 'stderr' in call else None
            run_start = None
            run_end = None
            if 'executionEvents' in call:
                for ev in call['executionEvents']:
                    if ev['description'].startswith('Running'):
                        run_start = ev['startTime']
                        run_end = ev['endTime']
                        break
            if not show_completed_task and status in ('Done', 'Succeeded'):
                return
            fileobj.write(
                '\n==== NAME={name}, STATUS={status}, PARENT={p}\n'
                'SHARD_IDX={shard_idx}, RC={rc}, JOB_ID={job_id}\n'
                'START={start}, END={end}\n'
                'STDOUT={stdout}\nSTDERR={stderr}\n'.format(
                    name=call_name,
                    status=status,
                    p=','.join(parent_call_names),
                    start=run_start,
                    end=run_end,
                    shard_idx=shard_index,
                    rc=rc,
                    job_id=job_id,
                    stdout=stdout,
                    stderr=stderr,
                )
            )
            if stderr:
                u = AutoURI(stderr)
                if u.exists:
                    fileobj.write('STDERR_CONTENTS=\n{s}\n'.format(s=u.read()))
            if show_stdout and stdout:
                u = AutoURI(stdout)
                if u.exists:
                    fileobj.write('STDOUT_CONTENTS=\n{s}\n'.format(s=u.read()))

        fileobj.write('* Recursively finding failures in calls (tasks)...\n')
        self.recurse_calls(troubleshoot_call)