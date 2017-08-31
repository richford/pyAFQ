import boto3
from argparse import ArgumentParser
import time
import sys

def create_job_queue(job_queue_name, compute_environments, priority=1):
    batch = boto3.client('batch')

    compute_environment_order = []
    for i, ce in enumerate(compute_environments):
        compute_environment_order.append({
            'order': i,
            'computeEnvironment': ce
            })

    response = batch.create_job_queue(
            jobQueueName=job_queue_name,
            state='ENABLED',
            priority=priority,
            computeEnvironmentOrder=compute_environment_order
            )

    # Wait for job queue to be in VALID state
    waiting = True
    num_waits = 0
    while waiting:
        print('Waiting for AWS to create job queue {name:s} ...'.format(
            name=job_queue_name))
        response = batch.describe_job_queues(jobQueues=[job_queue_name])
        waiting = (response.get('jobQueues')[0]['status'] != 'VALID')
        time.sleep(3)
        num_waits += 1
        if num_waits > 60:
            sys.exit('Waiting to long to create job queue. Aborting.')

    name = response.get('jobQueues')[0]['jobQueueName']
    arn = response.get('jobQueues')[0]['jobQueueArn']
    return name, arn


def main():
    description = 'Create job queue for AWS batch run.'
    argparser = ArgumentParser(description=description)

    argparser.add_argument('--job-queue-name', dest='job_queue_name', type=str,
            help='Name of AWS batch job definition', required=True)
    argparser.add_argument('--priority', type=int,
            help='Priority for the job queue', required=False, default=1)
    argparser.add_argument('--compute-environments', nargs='+',
            dest='compute_environments', type=str,
            help='List of compute environment (from high to low priority)',
            required=False, default=['first-run-compute-environment'])

    args = argparser.parse_args()
    
    create_job_queue(job_queue_name=args.job_queue_name,
            compute_environments=args.compute_environments,
            priority=args.priority)


if __name__ == '__main__':
    main()
