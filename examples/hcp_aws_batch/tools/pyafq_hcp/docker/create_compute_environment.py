import boto3
from argparse import ArgumentParser

def create_compute_environment():
    pass


def main():
    description = 'Create a compute environment for AWS batch runs.'
    argparser = ArgumentParser(description=description)

    argparser.add_argument('--resource-type', dest='resource_type', type=str,
            help='Compute environment resource type("EC2" or "SPOT")',
            required=True)
    argparser.add_argument('--min-vcpu', dest='min_vcpu', type=int,
            help='Min number of vCPUs', required=False, default=0)
    argparser.add_argument('--max-vcpu', dest='max_vcpu', type=int,
            help='Max number of vCPUs', required=False, default=256)
    argparser.add_argument('--desired-vcpu', type=int,
            help='Desired number of vCPUs', required=False, default=8)
    argparser.add_argument('--mem', type=int,
            help='Memory (MiB) per batch job', required=False, default=32000)
    argparser.add_argument('--username', type=str,
            help='Username for batch jobs', required=False, default='py-afq-user')

    args = argparser.parse_args()
    
    batch = boto3.client('batch')

    compute_resources = {
            'type': args.resource_type,
            'minvCpus': args.min_vcpu,
            'maxvCpus': args.max_vcpu,
            'desiredvCpus': args.desired_vcpu,
            'instanceTypes': [
                'optimal',
                ],
            'imageId': 'string',
            'subnets': [
                'string',
                ],
            'securityGroupIds': [
                'string',
                ],
            'ec2KeyPair': 'string',
            'instanceRole': 'string',
            'tags': {
                'string': 'string'
                },
            'bidPercentage': 50,
            'spotIamFleetRole': 'string'
            }

    response = batch.create_compute_environment(
            computeEnvironmentName=,
            type='MANAGED',
            state='ENABLED',
            computeResources=compute_resources,
            serviceRole='',
            )

if __name__ == '__main__':
    main()
