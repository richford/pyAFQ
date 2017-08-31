import boto3
from argparse import ArgumentParser
from datetime import datetime
import os
from build_push_repo import build_and_push
from iam_role import create_role_attach_policy
from define_batch_job import create_job_definition
from create_job_queue import create_job_queue
import math


def submit_job(job_name, job_queue, job_def, commands, env_vars):
    batch = boto3.client('batch')

    container_overrides = {
            'environment': env_vars,
            'command': commands
            }

    response = batch.submit_job(
            jobName=job_name,
            jobQueue=job_queue,
            jobDefinition=job_def,
            containerOverrides=container_overrides
            )

    print('Submitted {name:s} batch job with jobID {job_id:s}'.format(
        name=job_name, job_id=response['jobId']))
    print('to queue {queue:s} with definition {defn:s}'.format(
        queue=job_queue, defn=job_def))

    return response['jobId']


def main():
    description = 'Submit an AWS batch job'
    argparser = ArgumentParser(description=description)

    argparser.add_argument('--name-base-string', dest='name_base_string',
            type=str, required=False, default='pyAFQ-aws',
            help='Base string for names of repos, job roles, job queues, ' +
            'job definitions, etc. (e.g. job_queue_name = name_base_string ' +
            '+ "-job-queue"')

    repo = argparser.add_argument_group('Docker Image Options')
    repo.add_argument('-t', '--tags', nargs='+', type=str,
            help='List of repository tags (space separated)', required=False)
    repo.add_argument('-r', '--reg-id', dest='reg_id', type=str,
            help='Registry ID', required=False)
    repo.add_argument('--reqpath', type=str,
            help='Path to requirements.txt file', required=False)
    repo.add_argument('-d', '--dockerfile', type=str,
            help='Path to dockerfile', required=False, default='./Dockerfile')
    repo.add_argument('-p', '--buildpath', type=str,
            help='Docker buildpath', required=False, default='.')
    repo.add_argument('-v', '--verbose', dest='verbose',
            help='Get verbose Docker output', action='store_true')

    role = argparser.add_argument_group('Job Role Creation Options')
    role.add_argument('--policies', nargs='+', type=str,
            help='List of policy names (space separated)', required=False,
            default=['AmazonS3FullAccess'])
    role.add_argument('--role-description', dest='role_description',
            type=str, help='Role description', required=False,
            default='AFQ batch job role')
    
    defn = argparser.add_argument_group('Job Definition Creation Options')
    defn.add_argument('--retries', type=int,
            help='Number of retries', required=False, default=3)
    defn.add_argument('--vcpus', type=int,
            help='Number of vCPUs per batch job', required=False, default=1)
    defn.add_argument('--mem', type=int,
            help='Memory (MiB) per batch job', required=False, default=32000)
    defn.add_argument('--username', type=str,
            help='Username for batch jobs', required=False, default='afq-user')

    q = argparser.add_argument_group('Job Queue Creation Options')
    q.add_argument('--priority', type=int,
            help='Priority for the job queue', required=False, default=1)
    q.add_argument('--compute-environments', nargs='+',
            dest='compute_environments', type=str,
            help='List of compute environment (from high to low priority)',
            required=False, default=['first-run-compute-environment'])

    submit = argparser.add_argument_group('Batch Job Submission Options')
    submit.add_argument('--env-vars', nargs='+', dest='env_vars', type=str,
            help='List of environment variables to pass through ' + 
            '(e.g. NAME1 value1 NAME2 value2 ...', required=False)
    submit.add_argument('--commands', nargs='+', dest='commands', type=str,
            help='List of commands to pass to batch job (space separated)',
            required=False)

    args = argparser.parse_args()

    nbs = args.name_base_string
    time_stamp = (str(datetime.now().date()).replace('-', '') + '-'
            + str(datetime.now().time()).split('.')[0].replace(':', ''))

    repo_name = ('awsbatch/' + nbs + '-repo-' + time_stamp).lower()
    job_role_name = nbs + '-batch-job-role-' + time_stamp
    job_def_name = nbs + '-batch-job-def-' + time_stamp
    job_queue_name = nbs + '-batch-job-queue-' + time_stamp
    job_name = nbs + '-batch-job-' + time_stamp

    # Convert relative paths for Dockerfile and build path to absolute paths
    dockerfile = os.path.abspath(args.dockerfile)
    buildpath = os.path.abspath(args.buildpath)
    if args.reqpath:
        reqpath = os.path.abspath(args.reqpath)
    else:
        reqpath = None

    if args.tags:
        tags = args.tags
    else:
        tags = ['latest']

    verbose = False
    if args.verbose:
        verbose = args.verbose

    container_name, container_uri = build_and_push(
            repo_name=repo_name, buildpath=buildpath, dockerfile=dockerfile,
            reqpath=reqpath, tags=tags, verbose_docker=verbose)

    job_role_name, job_role_arn = create_role_attach_policy(
            role_name=job_role_name,
            role_description=args.role_description,
            policy_names=args.policies)

    job_def_name, job_def_arn = create_job_definition(
            job_def_name=job_def_name, job_role_arn=job_role_arn,
            container_uri=container_uri,
            vcpus=args.vcpus, memory=args.mem,
            user_name=args.username, retries=args.retries)

    job_queue_name, job_queue_arn = create_job_queue(
            job_queue_name=job_queue_name,
            compute_environments=args.compute_environments,
            priority=args.priority)

    env_vars = []
    if args.env_vars:
        message = '''number of entries on environment variable list should be
                even (e.g. NAME1 value1 NAME2 value2)'''
        assert len(args.env_vars) % 2 == 0, message

        for name, value in zip(args.env_vars[::2], args.env_vars[1::2]):
            env_vars.append({
                'name': name,
                'value': value
                })

    range_max = 10
    for index in range(range_max):
        commands = ['--index', str(index)]
        job_name = job_name + '-{i:0{log:d}d}'.format(
                i=index, log=int(math.log10(range_max) + 1))
        submit_job(job_name=job_name, job_queue=job_queue_name,
                job_def=job_def_name, commands=commands, env_vars=env_vars)
    

if __name__ == '__main__':
    main()
