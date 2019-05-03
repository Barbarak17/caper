#!/usr/bin/env python3
"""CromwellRestAPI
"""

import requests
import io
import fnmatch
import json


class CromwellRestAPI(object):
    QUERY_URL = 'http://{ip}:{port}'
    ENDPOINT_WORKFLOWS = '/api/workflows/v1/query'
    ENDPOINT_METADATA = '/api/workflows/v1/{wf_id}/metadata'
    ENDPOINT_LABELS = '/api/workflows/v1/{wf_id}/labels'
    ENDPOINT_ABORT = '/api/workflows/v1/{wf_id}/abort'
    ENDPOINT_SUBMIT = '/api/workflows/v1'
    KEY_LABEL = 'cromwell_rest_api_label'

    def __init__(self, server_ip='localhost', server_port=8000,
                 server_user=None, server_password=None, verbose=False):
        self._verbose = verbose
        self._server_ip = server_ip
        self._server_port = server_port

        self._server_user = server_user
        self._server_password = server_password
        self.__init_auth()

    def submit(self, source, dependencies=None,
               inputs_file=None, options_file=None, str_label=None):
        """Submit a workflow. Labels file is not allowed. Instead,
        a string label can be given and it is written to a labels file
        as a value under the key name CromwellRestAPI.KEY_LABEL
        ("cromwell_rest_api_label")

        Returns:
            JSON Response from POST request submit a workflow
        """
        manifest = {}
        manifest['workflowSource'] = \
            CromwellRestAPI.__get_string_io_from_file(source)
        if dependencies is not None:
            manifest['workflowDependencies'] = \
                CromwellRestAPI.__get_string_io_from_file(dependencies)
        if inputs_file is not None:
            manifest['workflowInputs'] = \
                CromwellRestAPI.__get_string_io_from_file(inputs_file)
        else:
            manifest['workflowInputs'] = io.StringIO('{}')
        if options_file is not None:
            manifest['workflowOptions'] = \
                CromwellRestAPI.__get_string_io_from_file(options_file)
        if str_label is not None:
            manifest['labels'] = io.StringIO(
                '{{ "{key}":"{val}" }}'.format(
                    key=CromwellRestAPI.KEY_LABEL, val=str_label))
        r = self.__query_post(CromwellRestAPI.ENDPOINT_SUBMIT, manifest)
        if self._verbose:
            print("submit: ", str(r))
        return r

    def abort(self, wf_ids_or_str_labels):
        """Abort a workflow

        Returns:
            List of JSON responses from POST request
            for aborting workflows
        """
        workflows = self.find_by_workflow_ids_or_str_labels(
            wf_ids_or_str_labels)
        result = []
        for w in workflows:
            r = self.__query_post(
                CromwellRestAPI.ENDPOINT_ABORT.format(
                    wf_id=w['id']))
            if self._verbose:
                print("abort: ", str(r))
            result.append(r)
        return result

    def metadata(self, wf_ids_or_str_labels):
        """Retrieve metadata for a workflow

        Returns:
            Metadata JSON for a workflow
        """
        workflows = self.find_by_workflow_ids_or_str_labels(
            wf_ids_or_str_labels)
        if len(workflows) != 1:
            if self._verbose:
                print('Error: There are multiple matching workflows. '
                      'Need only one to retrive metadata.')
                print(workflows)
            return None
        m = self.get_metadata(workflows[0]['id'])
        if self._verbose:
            print(json.dumps(m, indent=4))
        return m

    def list(self, wf_ids_or_str_labels):
        """List running/pending workflows

        Returns:
            Filtered list of workflow JSONs
        """
        if self._verbose:
            print('\t'.join(['name', 'status', 'workflow_id', 'str_label',
                             'submit', 'start', 'end']))

        if len(wf_ids_or_str_labels) == 0:
            workflows = self.get_workflows()
        else:
            workflows = self.find_by_workflow_ids_or_str_labels(
                wf_ids_or_str_labels)

        for w in workflows:
            workflow_id = w['id'] if 'id' in w else None
            name = w['name'] if 'name' in w else None
            status = w['status'] if 'status' in w else None
            submission = w['submission'] if 'submission' in w else None
            start = w['start'] if 'start' in w else None
            end = w['end'] if 'end' in w else None
            label = self.get_str_label(workflow_id)
            if self._verbose:
                print('\t'.join(
                    [str(s) for s in [name, status, workflow_id, label,
                                      submission, start, end]]))
        return workflows

    def get_workflows(self):
        """Get all workflows

        Returns:
            List of JSON object for all workflows
        """
        return self.__query_get(
            CromwellRestAPI.ENDPOINT_WORKFLOWS)['results']

    def get_metadata(self, workflow_id):
        """Get metadata for a specified workflow

        Returns:
            Metadata JSON for a workflow
        """
        if workflow_id is None:
            return None
        return self.__query_get(
            CromwellRestAPI.ENDPOINT_METADATA.format(
                wf_id=workflow_id))

    def get_str_label(self, workflow_id):
        """Get a string label for a specified workflow

        Returns:
            String label. This is different from raw "labels"
            JSON directly retrieved from Cromwell server.
            This string label is one of the values in it.
            See __get_labels() for details about JSON labels.
        """
        labels = self.__get_labels(workflow_id)
        if labels is None or 'labels' not in labels:
            return None
        for key in labels['labels']:
            if key == CromwellRestAPI.KEY_LABEL:
                return labels['labels'][key]
        return None

    def find_by_workflow_ids(self, workflow_ids):
        """Find a workflow by matching workflow_ids
        Wildcards (? and *) are allowed for workflow_id.

        Returns:
            List of matched workflow JSONs
        """
        matched = set()
        workflows = self.get_workflows()
        for w in workflows:
            if 'id' not in w:
                continue
            if workflow_ids is not None:
                for workflow_id in workflow_ids:
                    if fnmatch.fnmatchcase(w['id'], workflow_id):
                        matched.add(w['id'])
        result = []
        for w in workflows:
            if 'id' not in w:
                continue
            if w['id'] in matched:
                result.append(w)
        return result

    def find_by_str_labels(self, str_labels):
        """Find a workflow by matching string label.
        Wildcards (? and *) are allowed for str_label.

        Returns:
            List of matched workflow JSONs
        """
        matched = set()
        workflows = self.get_workflows()
        for w in workflows:
            if 'id' not in w:
                continue
            s = self.get_str_label(w['id'])
            if s is None:
                continue
            if str_labels is not None:
                for str_label in str_labels:
                    if fnmatch.fnmatchcase(s, str_label):
                        matched.add(w['id'])
        result = []
        for w in workflows:
            if 'id' not in w:
                continue
            if w['id'] in matched:
                result.append(w)
        return result

    def find_by_workflow_ids_or_str_labels(self, wf_ids_or_str_labels):
        """Find a workflow by matching workflow_ids or str_labels
        Wildcards (? and *) are allowed for them.

        Returns:
            List of matched workflow JSONs
        """
        matched = set()
        workflows = self.get_workflows()
        for w in workflows:
            if 'id' not in w:
                continue
            s = self.get_str_label(w['id'])
            if wf_ids_or_str_labels is not None:
                for wf_id_or_str_label in wf_ids_or_str_labels:
                    if fnmatch.fnmatchcase(w['id'], wf_id_or_str_label):
                        matched.add(w['id'])
                    elif s is not None and fnmatch.fnmatchcase(
                                           s, wf_id_or_str_label):
                        matched.add(w['id'])
        result = []
        for w in workflows:
            if 'id' not in w:
                continue
            if w['id'] in matched:
                result.append(w)
        return result

    def __init_auth(self):
        """Init auth object
        """
        if self._server_user is not None and self._server_password is not None:
            self._auth = (self._server_user, self._server_password)
        else:
            self._auth = None

    def __get_labels(self, workflow_id):
        """Get dict of a label for a specified workflow
        This is different from string label.
        String label is one of the values in
        Cromwell's labels dict.

        Returns:
            JSON labels for a workflow
        """
        if workflow_id is None:
            return None
        return self.__query_get(
            CromwellRestAPI.ENDPOINT_LABELS.format(
                wf_id=workflow_id))

    def __query_get(self, endpoint):
        """GET request

        Returns:
            JSON response
        """
        url = CromwellRestAPI.QUERY_URL.format(
                ip=self._server_ip,
                port=self._server_port) + endpoint
        resp = requests.get(url, headers={'accept': 'application/json'},
                            auth=self._auth)
        if resp.ok:
            return resp.json()
        else:
            print("HTTP Error: ", resp.status_code, resp.content)
            print("Query: ", url)
            return None

    def __query_post(self, endpoint, manifest=None):
        """POST request

        Returns:
            JSON response
        """
        url = CromwellRestAPI.QUERY_URL.format(
                ip=self._server_ip,
                port=self._server_port) + endpoint
        resp = requests.post(url, headers={'accept': 'application/json'},
                             files=manifest, auth=self._auth)
        if resp.ok:
            return resp.json()
        else:
            print("HTTP Error: ", resp.status_code, resp.content)
            print("Query: ", url, manifest)
            return None

    @staticmethod
    def __get_string_io_from_file(fname):
        with open(fname, 'r') as fp:
            return io.StringIO(fp.read())


def main():
    pass


if __name__ == '__main__':
    main()
