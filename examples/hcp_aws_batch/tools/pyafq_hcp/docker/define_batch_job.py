import boto3
from argparse import ArgumentParser
from datetime import datetime

def create_job_definition(job_def_name, job_role_arn, container_uri,
        vcpus=1, memory=32000, user_name='afq-user', retries=3):
    batch = boto3.client('batch')

    job_container_properties = {
            'image': container_uri,
            'vcpus': vcpus,
            'memory': memory,
            'command': [],
            'jobRoleArn': job_role_arn,
            'user': user_name
            }
    
    response = batch.register_job_definition(
            jobDefinitionName=job_def_name,
            type='container',
            containerProperties=job_container_properties,
            retryStrategy={'attempts': retries}
            )

    print('Created AWS batch job definition {name:s}'.format(
        name=job_def_name))

    return job_def_name, response['jobDefinitionArn']


def main():
    description = 'Create a job definition for an AWS batch job'
    argparser = ArgumentParser(description=description)

    argparser.add_argument('--job-def-name', dest='job_def_name', type=str,
            help='Name of AWS batch job definition', required=True)

    job_role_grp = argparser.add_mutually_exclusive_group(required=True)
    job_role_grp.add_argument('--job-role-name', dest='job_role_name',
            type=str, help='Job role name', required=False,
            default='afqBatchJobRole')
    job_role_grp.add_argument('--job-role-arn', dest='job_role_arn', type=str,
            help='Job role ARN', required=False)

    argparser.add_argument('-u', '--container-uri', dest='container_uri',
            type=str, help='Link to container URI', required=True)
    argparser.add_argument('--retries', type=int,
            help='Number of retries', required=False, default=3)
    argparser.add_argument('--vcpus', type=int,
            help='Number of vCPUs per batch job', required=False, default=1)
    argparser.add_argument('--mem', type=int,
            help='Memory (MiB) per batch job', required=False, default=32000)
    argparser.add_argument('--username', type=str,
            help='Username for batch jobs', required=False, default='afq-user')

    args = argparser.parse_args()

    # If user supplied only the job role name, then get the
    # corresponding job role ARN
    if args.job_role_name:
        iam = boto3.client('iam')
        response = iam.get_role(RoleName=args.job_role_name)
        job_role_arn = response.get('Role')['Arn']
    else:
        job_role_arn = args.job_role_arn

    job_def_arn = create_job_definition(job_def_name=args.job_def_name,
            job_role_arn=job_role_arn, container_uri=args.container_uri,
            vcpus=args.vcpus, memory=args.mem, user_name=args.username,
            retries=args.retries)


if __name__ == '__main__':
    main()
